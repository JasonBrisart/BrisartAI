"""Source-grounded answer generation with BrisartAI's analytical voice."""

from __future__ import annotations

import collections
import re
from typing import Dict, List, Set, Tuple

from .personality import confidence_label, limitation, next_step, observation, opening, reasoning_bullets
from .util import split_sentences, tokenize


def sentence_score(sentence: str, query_terms: Set[str]) -> float:
    words = tokenize(sentence)
    if not words:
        return 0.0
    counts = collections.Counter(words)
    overlap = sum(counts[t] for t in query_terms)
    density = overlap / max(1, len(words))
    return overlap + density


def format_source(doc: Dict[str, object]) -> str:
    kind = doc.get("source_type", "source")
    title = doc.get("title") or doc.get("location")
    location = doc.get("location")
    return f"{kind}: {title} :: {location}"


def _source_pattern_note(docs: List[Dict[str, object]]) -> str:
    local = sum(1 for d in docs if d.get("source_type") == "file")
    web = sum(1 for d in docs if d.get("source_type") == "web")
    if local and web:
        return "I found both local files and web-indexed material, so I treated local data as the main evidence and web data as supporting context."
    if local:
        return "The answer is based on local indexed files, which keeps the result tied to inspectable data on this machine."
    if web:
        return "The answer is based on web-indexed pages because no matching local files were retrieved."
    return "The retrieved evidence is limited."


def synthesize(query: str, docs: List[Dict[str, object]], max_sources: int = 6, max_sentences: int = 10, recent_topics=None) -> str:
    if not docs:
        lines = [
            "BrisartAI: I do not have enough indexed information to answer that yet.",
            limitation("No matching local or web-indexed sources were retrieved."),
            next_step("Ingest a folder with `python brisartai.py ingest ./your_data`, preview a scan with `scan-drive --preview`, or use `ask --web` when internet context is allowed."),
        ]
        return "\n".join(lines)

    query_terms = set(tokenize(query))
    candidates: List[Tuple[float, int, str, Dict[str, object]]] = []
    for source_num, doc in enumerate(docs[:max_sources], start=1):
        for sentence in split_sentences(str(doc["text"])):
            score = sentence_score(sentence, query_terms)
            if score > 0:
                candidates.append((score, source_num, sentence, doc))
    candidates.sort(key=lambda item: item[0], reverse=True)

    chosen = []
    seen = set()
    for score, source_num, sentence, doc in candidates:
        key = re.sub(r"\W+", "", sentence.lower())[:160]
        if key in seen:
            continue
        seen.add(key)
        chosen.append((score, source_num, sentence, doc))
        if len(chosen) >= max_sentences:
            break

    if not chosen:
        return "\n".join([
            "BrisartAI: I found related sources, but not enough sentence-level evidence to build a strong answer.",
            observation(_source_pattern_note(docs)),
            limitation("The indexed sources matched some terms, but the relevant passages were too weak or too fragmented."),
            next_step("Try a broader question, ingest more focused data, or ask me to analyze the indexed dataset first."),
        ])

    by_source = collections.defaultdict(list)
    docs_by_number = {}
    best_score = 0.0
    for score, source_num, sentence, doc in chosen:
        by_source[source_num].append(sentence)
        docs_by_number[source_num] = doc
        best_score = max(best_score, score)

    lines = [opening("answer", len(docs))]
    if recent_topics:
        lines.append(f"Context I still have in view: {' | '.join(recent_topics[:3])}")
    lines.append(observation(_source_pattern_note(docs)))
    lines.append(f"Confidence: {confidence_label(best_score)} based on retrieved sentence overlap.")
    lines.append("")

    lines.append("Answer:")
    for source_num in sorted(by_source):
        paragraph = " ".join(by_source[source_num][:3])
        lines.append(f"[{source_num}] {paragraph}")

    reason_items = []
    reason_items.append(f"I found {len(chosen)} relevant passage{'s' if len(chosen) != 1 else ''} across {len(docs_by_number)} cited source{'s' if len(docs_by_number) != 1 else ''}.")
    if query_terms:
        reason_items.append("The strongest matches were tied to query terms such as: " + ", ".join(sorted(list(query_terms))[:8]) + ".")
    reason_items.append(_source_pattern_note(docs))
    lines.append("")
    lines.extend(reasoning_bullets(reason_items))

    lines.append("")
    lines.append("Sources:")
    for source_num in sorted(docs_by_number):
        lines.append(f"[{source_num}] {format_source(docs_by_number[source_num])}")

    lines.append("")
    lines.append(next_step("Ask a narrower follow-up if you want me to inspect one theme, one file, or one recommendation more deeply."))
    return "\n".join(lines)
