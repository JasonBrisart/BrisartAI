"""
File: brisart_ai/knowledge/synthesizer.py

Purpose
-------
Turns ranked documents into a cited answer: extracts the most relevant
sentences (intent-aware), groups them by source, and appends a source
list. WIRED with negation-aware sentence selection (a sentence negating a
meaningful query term is down-weighted, not quoted as if it affirmed the
claim), a confidence + contradiction line, and citation-graph population.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: build_conversation_answer() calls
  synthesize(), passing the shared CitationGraph.
- Imports intent (detect_intent, detect_intents, term_is_negated),
  knowledge.citation_graph.CitationGraph, knowledge.confidence
  (ChosenSentence, compute_confidence, detect_contradictions), and
  util (split_sentences, tokenize).

Settings / parameters
---------------------
- max_sources (default 6) / max_sentences (default 10): caps on sources
  and total sentences an answer draws from.
- Sentence-score point values (added only when a sentence already shares
  >= 1 query term): quantity mode +10.0 for a real numeric quantity else
  +3.0 for a bare digit; comparison mode +8.0 for comparative language;
  reason mode +8.0 for causal language.
- NEGATION_PENALTY = 0.35: a sentence negating a meaningful query term is
  scaled to 35%, EXCEPT when the query itself is a validation/fact-check.
- report_confidence (default True): appends a "Confidence: <band> (<pct>),
  from N sources." line -- high >= 0.75, moderate >= 0.45, else low.

Edge cases
----------
- No documents -> "I don't have any indexed information..."; documents
  present but no sentence shares a query term -> "...none of them
  contained a passage that directly answers that."
- Normalized-duplicate sentences are de-duplicated before selection.
- A numeric contradiction adds a "Note: sources disagree..." caveat.
- Passing citation_graph=None simply skips graph recording.

Known limitations
-----------------
- Answers are extractive: sentences are quoted verbatim, never
  paraphrased or condensed, so multi-sentence answers can read choppily.
- Sentence scoring is bag-of-words overlap plus mode boosts; an answer
  phrased without any query terms is not recognized.
- The confidence/contradiction line inherits confidence.py's narrow
  numeric/negation detection.
- Negation suppression is skipped for validation-intent queries, so a
  mixed compound query can under- or over-apply it.

Examples
--------
    >>> synthesize("x", [])
    "I don't have any indexed information that answers that yet."
    >>> docs = [{"id": 1, "source_type": "file", "location": "/a", "title": "MS",
    ...          "text": "Microsoft was founded by Bill Gates and Paul Allen in Albuquerque."}]
    >>> "Sources:" in synthesize("who founded microsoft", docs)
    True
"""
from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

from brisart_ai.intent import (
    INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_STATISTIC, INTENT_VALIDATION,
    detect_intent, detect_intents, term_is_negated,
)
from brisart_ai.knowledge.citation_graph import CitationGraph
from brisart_ai.knowledge.confidence import (
    ChosenSentence, compute_confidence, detect_contradictions,
)
from brisart_ai.util import split_sentences, tokenize

Document = Dict[str, object]
Candidate = Tuple[float, int, str, Document]

NEGATION_PENALTY = 0.35  # a negated meaningful term scales that sentence's score down


def query_wants_quantity(query: str) -> bool:
    return detect_intent(query) == INTENT_STATISTIC


def query_wants_comparison(query: str) -> bool:
    return detect_intent(query) == INTENT_COMPARISON


def query_wants_reason(query: str) -> bool:
    return detect_intent(query) == INTENT_EXPLANATION


_HAS_DIGIT = re.compile(r"\d")
_HAS_QUANTITY = re.compile(
    r"[$\u20ac\u00a3]\s*\d[\d,\.]*"
    r"|\d[\d,\.]*\s*"
    r"(million|billion|trillion|thousand|percent|%|households|people|cats|dogs|"
    r"pets|residents|adults|users|estimated|approximately|dollars?|usd|"
    r"kilometers?|km|miles?|mi\b|meters?|metres?|feet|ft\b|kilograms?|kg|"
    r"pounds?|lbs?\b|tons?|tonnes?|years?|months?|weeks?|days?|hours?|"
    r"minutes?|seconds?|calories|degrees)",
    re.IGNORECASE)
_HAS_COMPARISON_SIGNAL = re.compile(
    r"\b(than|more|less|longer|shorter|faster|slower|better|worse|compared\s+to|"
    r"versus|vs\.?|outlive[sd]?|outlast[sd]?|bigger|smaller|cheaper|higher|lower|"
    r"most|least|stronger|weaker)\b", re.IGNORECASE)
_HAS_REASON_SIGNAL = re.compile(
    r"\b(because|due\s+to|caused?\s+by|reason|since|as\s+a\s+result|leads?\s+to|"
    r"results?\s+in|allows?|enables?|so\s+that|triggers?|prompts?)\b", re.IGNORECASE)


def _clean_sentence(sentence: str) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    text = text.lstrip(".,;:|- ").strip()
    return re.sub(r"\s+([.,;:])", r"\1", text)


def format_source(document: Document) -> str:
    st = str(document.get("source_type", "source"))
    loc = str(document.get("location", ""))
    title = str(document.get("title") or loc or "Untitled source")
    return f"{st}: {title} :: {loc}"


def _dedup_key(sentence: str) -> str:
    return re.sub(r"\W+", "", sentence.casefold())[:240]


def sentence_score(sentence, query_terms, quantity_mode=False,
                   comparison_mode=False, reason_mode=False) -> float:
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = collections.Counter(words)
    overlap = sum(counts[t] for t in query_terms)
    density = overlap / max(1, len(words))
    score = float(overlap + density)
    if overlap > 0:
        if quantity_mode:
            if _HAS_QUANTITY.search(sentence):
                score += 10.0
            elif _HAS_DIGIT.search(sentence):
                score += 3.0
        if comparison_mode and _HAS_COMPARISON_SIGNAL.search(sentence):
            score += 8.0
        if reason_mode and _HAS_REASON_SIGNAL.search(sentence):
            score += 8.0
    return score


def synthesize(query: str, docs: List[Document], max_sources: int = 6,
               max_sentences: int = 10, recent_topics: Optional[Iterable[str]] = None,
               citation_graph: Optional[CitationGraph] = None,
               report_confidence: bool = True) -> str:
    if not docs:
        return "I don't have any indexed information that answers that yet."

    source_limit = max(1, int(max_sources))
    sentence_limit = max(1, int(max_sentences))
    query_terms = set(tokenize(query))
    intents = detect_intents(query)
    primary = intents[0][0] if intents else detect_intent(query)
    quantity_mode = query_wants_quantity(query)
    comparison_mode = query_wants_comparison(query)
    reason_mode = query_wants_reason(query)
    # A validation/fact-check query WANTS negation, so don't down-weight it there.
    apply_negation = primary != INTENT_VALIDATION and INTENT_VALIDATION not in {i for i, _ in intents}

    candidates: List[Candidate] = []
    for source_number, document in enumerate(docs[:source_limit], start=1):
        text = str(document.get("text", ""))
        for sentence in split_sentences(text):
            score = sentence_score(sentence, query_terms, quantity_mode=quantity_mode,
                                   comparison_mode=comparison_mode, reason_mode=reason_mode)
            if score <= 0:
                continue
            # NEW: negation awareness -- a sentence that negates a meaningful
            # query term is a weak witness for the affirmative claim.
            if apply_negation:
                for term in query_terms:
                    if term_is_negated(sentence, term):
                        score *= NEGATION_PENALTY
                        break
            candidates.append((score, source_number, sentence, document))

    candidates.sort(key=lambda item: item[0], reverse=True)
    chosen: List[Candidate] = []
    seen = set()
    for cand in candidates:
        score, source_number, sentence, document = cand
        key = _dedup_key(sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        chosen.append(cand)
        if len(chosen) >= sentence_limit:
            break

    if not chosen:
        return ("I found related sources, but none of them contained a "
                "passage that directly answers that.")

    signal_re = (_HAS_QUANTITY if quantity_mode else
                 _HAS_COMPARISON_SIGNAL if comparison_mode else
                 _HAS_REASON_SIGNAL if reason_mode else None)
    if signal_re is not None:
        chosen.sort(key=lambda item: (0 if signal_re.search(item[2]) else 1, -item[0]))

    by_source: Dict[int, List[str]] = collections.defaultdict(list)
    original_docs: Dict[int, Document] = {}
    order: List[int] = []
    for score, source_number, sentence, document in chosen:
        if source_number not in by_source:
            order.append(source_number)
        by_source[source_number].append(_clean_sentence(sentence))
        original_docs[source_number] = document

    display_number = {orig: i for i, orig in enumerate(order, start=1)}

    lines: List[str] = []
    for orig in order:
        paragraph = " ".join(by_source[orig][:3])
        lines.append(f"[{display_number[orig]}] {paragraph}")
        lines.append("")

    # NEW: confidence + contradiction reporting.
    chosen_sentences = [
        ChosenSentence(original_docs[num].get("id", num),
                       str(original_docs[num].get("location", "")), sent)
        for _s, num, sent, _d in chosen
    ]
    topic = " ".join(sorted(t for t in query_terms))
    if citation_graph is not None:
        for cs in chosen_sentences:
            citation_graph.add_citation(topic, cs.source_id)
    contradictions = detect_contradictions(chosen_sentences)
    if report_confidence:
        confidence = compute_confidence(chosen_sentences, topic=topic,
                                        graph=citation_graph,
                                        contradiction_count=len(contradictions))
        band = "high" if confidence >= 0.75 else "moderate" if confidence >= 0.45 else "low"
        distinct = len({cs.source_id for cs in chosen_sentences})
        lines.append(f"Confidence: {band} ({confidence:.0%}), from {distinct} "
                     f"source{'s' if distinct != 1 else ''}.")
        if contradictions:
            c = contradictions[0]
            lines.append(f"Note: sources disagree on '{c['subject']}' "
                         f"({c['left_value']} vs {c['right_value']}); treat with caution.")
        lines.append("")

    lines.append("Sources:")
    for orig in order:
        lines.append(f"[{display_number[orig]}] {format_source(original_docs[orig])}")
    return "\n".join(lines).rstrip()


__all__ = ["format_source", "query_wants_comparison", "query_wants_quantity",
           "query_wants_reason", "sentence_score", "synthesize"]


