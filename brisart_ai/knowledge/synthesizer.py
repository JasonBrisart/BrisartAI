"""Source-grounded response synthesis for BrisartAI.

Output philosophy: return the information, not a narration of how it was
produced. The synthesizer extracts the most relevant sentences from the
ranked documents and presents them directly, followed by a plain source
list. It does not emit "Observation:", "Confidence:", "Why I think
this:", or "Suggested next move:" scaffolding.

Quantity awareness: when the question is asking for a count or measure
("how many", "how much", "number", "population", "percent"), sentences
that actually contain a numeric quantity are strongly boosted, so a real
answer like "an estimated 74 million pet cats in the US" is surfaced
ahead of generic topic sentences that merely repeat the keywords.
"""

from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Set, Tuple

from brisart_ai.util import split_sentences, tokenize

Document = Dict[str, object]
Candidate = Tuple[float, int, str, Document]


# Query words that signal the user wants a numeric answer.
_QUANTITY_INTENT: Set[str] = {
    "number", "amount", "population", "many", "much", "count", "total",
    "percent", "percentage", "average", "how", "size", "figure",
    "figures", "statistics", "stat", "stats",
}

# A bare digit anywhere in a sentence.
_HAS_DIGIT = re.compile(r"\d")

# A digit followed by a scale/unit word -- a strong signal that the
# sentence states an actual quantity (e.g. "74 million cats",
# "25 percent of households", "95.6 million").
_HAS_QUANTITY = re.compile(
    r"\d[\d,\.]*\s*"
    r"(million|billion|thousand|percent|%|households|"
    r"people|cats|dogs|pets|residents|adults|users|"
    r"estimated|approximately)",
    re.IGNORECASE,
)


def query_wants_quantity(query: str) -> bool:
    """Return True when the query is asking for a count or measure."""
    return bool(set(tokenize(query)) & _QUANTITY_INTENT)


def sentence_score(
    sentence: str,
    query_terms: Set[str],
    quantity_mode: bool = False,
) -> float:
    """Score a sentence by query-term overlap, density, and quantity."""
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

    # Only reward numbers when the sentence is at least somewhat on-topic
    # (shares a query term), so we don't surface random unrelated numbers.
    if quantity_mode and overlap > 0:
        if _HAS_QUANTITY.search(sentence):
            score += 10.0
        elif _HAS_DIGIT.search(sentence):
            score += 3.0

    return score


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

    # In quantity mode, lead with the single best sentence that actually
    # contains a quantity, so the numeric answer is the first thing seen.
    if quantity_mode:
        chosen.sort(
            key=lambda item: (
                0 if _HAS_QUANTITY.search(item[2]) else 1,
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
    "query_wants_quantity",
    "sentence_score",
    "synthesize",
]
