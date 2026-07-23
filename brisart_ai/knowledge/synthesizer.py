"""Source-grounded response synthesis for BrisartAI."""

from __future__ import annotations

import collections
import re
from typing import Dict, Iterable, List, Set, Tuple

from brisart_ai.intelligence.personality import (
    confidence_label,
    limitation,
    next_step,
    observation,
    opening,
    reasoning_bullets,
)
from brisart_ai.util import split_sentences, tokenize


Document = Dict[str, object]
Candidate = Tuple[float, int, str, Document]


def sentence_score(
    sentence: str,
    query_terms: Set[str],
) -> float:
    """Score a sentence by query-term overlap and density."""

    words = tokenize(sentence)

    if not words:
        return 0.0

    counts = collections.Counter(words)
    overlap = sum(
        counts[term]
        for term in query_terms
    )

    density = overlap / max(1, len(words))

    return float(overlap + density)


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

    return (
        f"{source_type}: {title} :: {location}"
    )


def _source_pattern_note(
    documents: List[Document],
) -> str:
    """Explain the local-versus-web evidence pattern."""

    local_count = sum(
        1
        for document in documents
        if document.get("source_type") == "file"
    )

    web_count = sum(
        1
        for document in documents
        if document.get("source_type") == "web"
    )

    if local_count and web_count:
        return (
            "I found both local files and web-indexed "
            "material. Local data was treated as primary "
            "evidence and web material as supporting context."
        )

    if local_count:
        return (
            "The answer is based on local indexed files, "
            "keeping the result tied to inspectable data "
            "on this machine."
        )

    if web_count:
        return (
            "The answer is based on web-indexed pages "
            "because no matching local files were retrieved."
        )

    return "The retrieved evidence is limited."


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
    """Generate an evidence-grounded answer from ranked documents."""

    if not docs:
        return "\n".join(
            [
                (
                    "BrisartAI: I do not have enough "
                    "indexed information to answer that yet."
                ),
                limitation(
                    "No matching local or web-indexed "
                    "sources were retrieved."
                ),
                next_step(
                    "Ingest focused local data, preview a "
                    "scan, or enable web research when "
                    "internet access is permitted."
                ),
            ]
        )

    safe_source_limit = max(
        1,
        int(max_sources),
    )

    safe_sentence_limit = max(
        1,
        int(max_sentences),
    )

    query_terms = set(tokenize(query))
    candidates: List[Candidate] = []

    for source_number, document in enumerate(
        docs[:safe_source_limit],
        start=1,
    ):
        text = str(
            document.get("text", "")
        )

        for sentence in split_sentences(text):
            score = sentence_score(
                sentence,
                query_terms,
            )

            if score > 0:
                candidates.append(
                    (
                        score,
                        source_number,
                        sentence,
                        document,
                    )
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
            (
                score,
                source_number,
                sentence,
                document,
            )
        )

        if len(chosen) >= safe_sentence_limit:
            break

    if not chosen:
        return "\n".join(
            [
                (
                    "BrisartAI: I found related sources, "
                    "but not enough sentence-level evidence "
                    "to build a strong answer."
                ),
                observation(
                    _source_pattern_note(docs)
                ),
                limitation(
                    "The indexed sources matched some terms, "
                    "but the relevant passages were weak "
                    "or fragmented."
                ),
                next_step(
                    "Try a broader question, ingest more "
                    "focused data, or analyze the current "
                    "index first."
                ),
            ]
        )

    by_source: Dict[int, List[str]] = (
        collections.defaultdict(list)
    )

    docs_by_number: Dict[int, Document] = {}
    best_score = 0.0

    for (
        score,
        source_number,
        sentence,
        document,
    ) in chosen:
        by_source[source_number].append(sentence)
        docs_by_number[source_number] = document
        best_score = max(best_score, score)

    lines = [
        opening(
            "answer",
            len(docs),
        )
    ]

    if recent_topics:
        topics = [
            str(topic).strip()
            for topic in recent_topics
            if str(topic).strip()
        ][:3]

        if topics:
            lines.append(
                "Context I still have in view: "
                + " | ".join(topics)
            )

    lines.append(
        observation(
            _source_pattern_note(docs)
        )
    )

    lines.append(
        "Confidence: "
        f"{confidence_label(best_score)} "
        "based on retrieved sentence overlap."
    )

    lines.append("")
    lines.append("Answer:")

    for source_number in sorted(by_source):
        paragraph = " ".join(
            by_source[source_number][:3]
        )

        lines.append(
            f"[{source_number}] {paragraph}"
        )

    reasoning_items = [
        (
            f"I found {len(chosen)} relevant "
            f"passage{'s' if len(chosen) != 1 else ''} "
            f"across {len(docs_by_number)} cited "
            f"source{'s' if len(docs_by_number) != 1 else ''}."
        )
    ]

    if query_terms:
        reasoning_items.append(
            "The strongest matches were tied to "
            "query terms such as: "
            + ", ".join(
                sorted(query_terms)[:8]
            )
            + "."
        )

    reasoning_items.append(
        _source_pattern_note(docs)
    )

    lines.append("")
    lines.extend(
        reasoning_bullets(
            reasoning_items
        )
    )

    lines.append("")
    lines.append("Sources:")

    for source_number in sorted(docs_by_number):
        lines.append(
            f"[{source_number}] "
            f"{format_source(docs_by_number[source_number])}"
        )

    lines.append("")
    lines.append(
        next_step(
            "Ask a narrower follow-up to inspect "
            "one theme, file, or recommendation."
        )
    )

    return "\n".join(lines)


__all__ = [
    "format_source",
    "sentence_score",
    "synthesize",
]