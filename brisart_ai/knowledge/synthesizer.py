"""
File: brisart_ai/knowledge/synthesizer.py

Purpose
-------
Turns ranked documents into an answer by extracting the most relevant
sentences and presenting them directly, followed by a plain source list.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: calls synthesize().
- Imports brisart_ai.intent.{INTENT_COMPARISON, INTENT_EXPLANATION,
  INTENT_STATISTIC, detect_intent} and brisart_ai.util.{split_sentences, tokenize}.

Settings / parameters
----------------------
- max_sources (6) / max_sentences (10).
- _HAS_QUANTITY / _HAS_COMPARISON_SIGNAL / _HAS_REASON_SIGNAL.

Edge cases
----------
- Boosts only apply to sentences sharing at least one query term.
- Chosen sentences de-duplicated by normalized key.
"""
from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Set, Tuple

from brisart_ai.intent import INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_STATISTIC, detect_intent
from brisart_ai.util import split_sentences, tokenize

Document = Dict[str, object]
Candidate = Tuple[float, int, str, Document]


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
    r"(million|billion|trillion|thousand|percent|%|households|"
    r"people|cats|dogs|pets|residents|adults|users|"
    r"estimated|approximately|dollars?|usd|"
    r"kilometers?|km|miles?|mi\b|meters?|metres?|feet|ft\b|"
    r"kilograms?|kg|pounds?|lbs?\b|tons?|tonnes?|"
    r"years?|months?|weeks?|days?|hours?|minutes?|seconds?|"
    r"calories|degrees)",
    re.IGNORECASE,
)
_HAS_COMPARISON_SIGNAL = re.compile(
    r"\b(than|more|less|longer|shorter|faster|slower|"
    r"better|worse|compared\s+to|versus|vs\.?|"
    r"outlive[sd]?|outlast[sd]?|"
    r"bigger|smaller|cheaper|higher|lower|"
    r"most|least|stronger|weaker)\b",
    re.IGNORECASE,
)
_HAS_REASON_SIGNAL = re.compile(
    r"\b(because|due\s+to|caused?\s+by|reason|since|"
    r"as\s+a\s+result|leads?\s+to|results?\s+in|"
    r"allows?|enables?|so\s+that|triggers?|prompts?)\b",
    re.IGNORECASE,
)


def _clean_sentence(sentence: str) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    text = text.lstrip(".,;:|- ").strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def format_source(document: Document) -> str:
    source_type = str(document.get("source_type", "source"))
    location = str(document.get("location", ""))
    title = str(document.get("title") or location or "Untitled source")
    return f"{source_type}: {title} :: {location}"


def _deduplication_key(sentence: str) -> str:
    return re.sub(r"\W+", "", sentence.casefold())[:240]


def sentence_score(
    sentence: str, query_terms: Set[str], quantity_mode: bool = False,
    comparison_mode: bool = False, reason_mode: bool = False,
) -> float:
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = collections.Counter(words)
    overlap = sum(counts[term] for term in query_terms)
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


def synthesize(
    query: str, docs: List[Document], max_sources: int = 6, max_sentences: int = 10,
    recent_topics: Iterable[str] | None = None,
) -> str:
    """Return the most relevant information from ranked documents."""
    if not docs:
        return "I don't have any indexed information that answers that yet."

    safe_source_limit = max(1, int(max_sources))
    safe_sentence_limit = max(1, int(max_sentences))
    query_terms = set(tokenize(query))

    quantity_mode = query_wants_quantity(query)
    comparison_mode = query_wants_comparison(query)
    reason_mode = query_wants_reason(query)

    candidates: List[Candidate] = []
    for source_number, document in enumerate(docs[:safe_source_limit], start=1):
        text = str(document.get("text", ""))
        for sentence in split_sentences(text):
            score = sentence_score(
                sentence, query_terms, quantity_mode=quantity_mode,
                comparison_mode=comparison_mode, reason_mode=reason_mode,
            )
            if score > 0:
                candidates.append((score, source_number, sentence, document))

    candidates.sort(key=lambda item: item[0], reverse=True)

    chosen: List[Candidate] = []
    seen = set()
    for candidate in candidates:
        score, source_number, sentence, document = candidate
        key = _deduplication_key(sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        chosen.append((score, source_number, sentence, document))
        if len(chosen) >= safe_sentence_limit:
            break

    if not chosen:
        return (
            "I found related sources, but none of them contained a "
            "passage that directly answers that."
        )

    if quantity_mode:
        signal_re = _HAS_QUANTITY
    elif comparison_mode:
        signal_re = _HAS_COMPARISON_SIGNAL
    elif reason_mode:
        signal_re = _HAS_REASON_SIGNAL
    else:
        signal_re = None

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

    display_number: Dict[int, int] = {}
    for new_index, original_number in enumerate(order, start=1):
        display_number[original_number] = new_index

    lines: List[str] = []
    for original_number in order:
        paragraph = " ".join(by_source[original_number][:3])
        lines.append(f"[{display_number[original_number]}] {paragraph}")
        lines.append("")

    lines.append("Sources:")
    for original_number in order:
        lines.append(f"[{display_number[original_number]}] {format_source(original_docs[original_number])}")

    return "\n".join(lines).rstrip()


__all__ = [
    "format_source", "query_wants_comparison", "query_wants_quantity",
    "query_wants_reason", "sentence_score", "synthesize",
]
