"""Source-grounded response synthesis for BrisartAI.

Output philosophy: return the information, not a narration of how it was
produced. The synthesizer extracts the most relevant sentences from the
ranked documents and presents them directly, followed by a plain source
list. It does not emit "Observation:", "Confidence:", "Why I think
this:", or "Suggested next move:" scaffolding.

Intent awareness: a question's phrasing hints at the KIND of sentence
that actually answers it, not just its topic words. Three intents are
detected directly from the raw query text (not the tokenized/stopword-
filtered version, since words like "why" and "how" are themselves
stopwords and would otherwise be invisible to this check):

  * Quantity  ("how many", "how much", "population", "percent", ...)
    -> boost sentences that contain an actual numeric quantity.
  * Comparison ("vs", "outlive", "better", "longer", "compared to", ...)
    -> boost sentences that contain comparative language.
  * Reason    ("why ...")
    -> boost sentences that contain causal language ("because",
       "due to", "caused by", ...).

This is what stops a question like "do dogs outlive cats" from
returning a generic sentence about working dog breeds, and instead
prefers a sentence that actually compares dog and cat lifespans.
"""

from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Set, Tuple

from brisart_ai.util import split_sentences, tokenize

Document = Dict[str, object]
Candidate = Tuple[float, int, str, Document]


# -- intent detection (raw query text, NOT the stopword-filtered tokens) ----

# Words/phrases that signal the user wants a numeric answer.
_QUANTITY_INTENT: Set[str] = {
    "number", "amount", "population", "many", "much", "count", "total",
    "percent", "percentage", "average", "how", "size", "figure",
    "figures", "statistics", "stat", "stats",
}

# Comparison-question phrasing, checked against the raw query.
_COMPARISON_QUERY_RE = re.compile(
    r"\b("
    r"vs\.?|versus|compare|comparison|compared|"
    r"outlive[sd]?|outlast[sd]?|"
    r"better|worse|longer|shorter|faster|slower|"
    r"bigger|smaller|cheaper|more\s+expensive|"
    r"higher|lower|stronger|weaker|"
    r"difference|different|which\s+is"
    r")\b",
    re.IGNORECASE,
)

# "why" questions, checked against the raw query. "why" is itself a
# stopword in util.tokenize(), so it must be detected from the raw text.
_REASON_QUERY_RE = re.compile(r"\bwhy\b", re.IGNORECASE)


def query_wants_quantity(query: str) -> bool:
    """Return True when the query is asking for a count or measure."""
    return bool(set(tokenize(query)) & _QUANTITY_INTENT)


def query_wants_comparison(query: str) -> bool:
    """Return True when the query is asking to compare two things."""
    return bool(_COMPARISON_QUERY_RE.search(str(query or "")))


def query_wants_reason(query: str) -> bool:
    """Return True when the query is a "why" question."""
    return bool(_REASON_QUERY_RE.search(str(query or "")))


# -- sentence-level signal detection -----------------------------------

# A bare digit anywhere in a sentence.
_HAS_DIGIT = re.compile(r"\d")

# A digit followed by a scale/unit word -- a strong signal that the
# sentence states an actual quantity (e.g. "74 million cats",
# "25 percent of households").
_HAS_QUANTITY = re.compile(
    r"\d[\d,\.]*\s*"
    r"(million|billion|thousand|percent|%|households|"
    r"people|cats|dogs|pets|residents|adults|users|"
    r"estimated|approximately)",
    re.IGNORECASE,
)

# Comparative language inside a sentence (not the query).
_HAS_COMPARISON_SIGNAL = re.compile(
    r"\b("
    r"than|more|less|longer|shorter|faster|slower|"
    r"better|worse|compared\s+to|versus|vs\.?|"
    r"outlive[sd]?|outlast[sd]?|"
    r"bigger|smaller|cheaper|higher|lower|"
    r"most|least|stronger|weaker"
    r")\b",
    re.IGNORECASE,
)

# Causal/explanatory language inside a sentence.
_HAS_REASON_SIGNAL = re.compile(
    r"\b("
    r"because|due\s+to|caused?\s+by|reason|since|"
    r"as\s+a\s+result|leads?\s+to|results?\s+in|"
    r"allows?|enables?|so\s+that|triggers?|prompts?"
    r")\b",
    re.IGNORECASE,
)


def _clean_sentence(sentence: str) -> str:
    """Tidy a raw extracted sentence for readable display."""
    text = re.sub(r"\s+", " ", sentence).strip()
    text = text.lstrip(".,;:|- ").strip()
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text


def format_source(
    document: Document,
) -> str:
    """Format a source reference for display."""
    source_type = str(
        document.get("source_type", "source")
    )
    location = str(
        document.get("location", "")
    )
    title = str(
        document.get("title")
        or location
        or "Untitled source"
    )
    return f"{source_type}: {title} :: {location}"


def _deduplication_key(
    sentence: str,
) -> str:
    """Build a stable key for duplicate sentence removal."""
    return re.sub(
        r"\W+",
        "",
        sentence.casefold(),
    )[:240]


def sentence_score(
    sentence: str,
    query_terms: Set[str],
    quantity_mode: bool = False,
    comparison_mode: bool = False,
    reason_mode: bool = False,
) -> float:
    """Score a sentence by query-term overlap, density, and intent match."""
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = collections.Counter(words)
    overlap = sum(
        counts[term]
        for term in query_terms
    )
    density = overlap / max(1, len(words))
    score = float(overlap + density)

    # Intent boosts only apply to sentences that are at least somewhat
    # on-topic (share a query term), so we don't surface a random
    # unrelated sentence just because it happens to contain "because".
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
    query: str,
    docs: List[Document],
    max_sources: int = 6,
    max_sentences: int = 10,
    recent_topics: Iterable[str] | None = None,
) -> str:
    """Return the most relevant information from ranked documents.

    The output is just the answer text followed by a plain source list.
    No reasoning narration, confidence labels, observations, or
    suggested-next-move lines are included.
    """
    if not docs:
        return (
            "I don't have any indexed information that answers that yet."
        )

    safe_source_limit = max(1, int(max_sources))
    safe_sentence_limit = max(1, int(max_sentences))
    query_terms = set(tokenize(query))

    quantity_mode = query_wants_quantity(query)
    comparison_mode = query_wants_comparison(query)
    reason_mode = query_wants_reason(query)

    candidates: List[Candidate] = []
    for source_number, document in enumerate(
        docs[:safe_source_limit],
        start=1,
    ):
        text = str(document.get("text", ""))
        for sentence in split_sentences(text):
            score = sentence_score(
                sentence,
                query_terms,
                quantity_mode=quantity_mode,
                comparison_mode=comparison_mode,
                reason_mode=reason_mode,
            )
            if score > 0:
                candidates.append(
                    (score, source_number, sentence, document)
                )

    candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    chosen: List[Candidate] = []
    seen = set()
    for candidate in candidates:
        score, source_number, sentence, document = candidate
        key = _deduplication_key(sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        chosen.append(
            (score, source_number, sentence, document)
        )
        if len(chosen) >= safe_sentence_limit:
            break

    if not chosen:
        return (
            "I found related sources, but none of them contained a "
            "passage that directly answers that."
        )

    # Lead with the single best sentence that actually matches the
    # detected intent (a real number, a real comparison, a real reason),
    # so that sentence is the first thing seen rather than a merely
    # higher-overlap but less useful sentence. Priority order: quantity,
    # then comparison, then reason -- a query can only really be asking
    # for one of these at a time in practice.
    if quantity_mode:
        signal_re = _HAS_QUANTITY
    elif comparison_mode:
        signal_re = _HAS_COMPARISON_SIGNAL
    elif reason_mode:
        signal_re = _HAS_REASON_SIGNAL
    else:
        signal_re = None

    if signal_re is not None:
        chosen.sort(
            key=lambda item: (
                0 if signal_re.search(item[2]) else 1,
                -item[0],
            )
        )

    # Group chosen sentences by their original source, then assign
    # sequential display numbers so citations read 1, 2, 3 with no gaps.
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
        lines.append(
            f"[{display_number[original_number]}] {paragraph}"
        )
        lines.append("")

    lines.append("Sources:")
    for original_number in order:
        lines.append(
            f"[{display_number[original_number]}] "
            f"{format_source(original_docs[original_number])}"
        )

    return "\n".join(lines).rstrip()


__all__ = [
    "format_source",
    "query_wants_comparison",
    "query_wants_quantity",
    "query_wants_reason",
    "sentence_score",
    "synthesize",
]
