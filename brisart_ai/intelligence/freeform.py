"""
Improved conversational fallback for BrisartAI.

Every branch below routes its single-fact statements through
personality.py (observation / limitation / next_step) instead of
hardcoding its own labels, so the voice is actually consistent with
synthesizer.py, analyzer.py, and recommender.py rather than only
partially applied.
"""
from __future__ import annotations

from typing import Iterable, List

from .personality import limitation, next_step, observation
from brisart_ai.util import tokenize


def _classify_intent(text: str) -> str:
    lowered = text.lower().strip()
    terms = set(tokenize(lowered))
    greetings = {
        "hi",
        "hello",
        "hey",
        "sup",
        "yo",
        "hl"
    }
    if lowered in greetings:
        return "greeting"
    if any(x in lowered for x in [
        "whats going on",
        "what's going on",
        "system status"
    ]):
        return "status"
    if any(x in lowered for x in [
        "who are you",
        "what are you"
    ]):
        return "identity"
    if not terms:
        return "empty"
    return "general"


def freeform_response(
    user_text: str,
    index=None,
    recent_topics: Iterable[str] | None = None,
) -> str:
    intent = _classify_intent(user_text)
    total = index.source_count() if index else 0
    files = index.source_count("file") if index else 0
    web = index.source_count("web") if index else 0
    lines: List[str] = []

    if intent == "greeting":
        lines.append("Hello Jason.")
        lines.append("")
        lines.append("BrisartAI is online.")
        lines.append("")
        lines.append(
            observation(
                f"Indexed sources currently available: {total} "
                f"({files} local files, {web} web pages)."
            )
        )
        lines.append("")
        lines.append(
            next_step(
                "Chat normally, ingest data, scan folders, search the "
                "web, or analyze imported knowledge."
            )
        )
        return "\n".join(lines)

    if intent == "status":
        lines.append("BrisartAI Status")
        lines.append("")
        lines.append(
            observation(
                f"Indexed sources: {total} ({files} local files, "
                f"{web} web pages)."
            )
        )
        lines.append("")
        if total == 0:
            lines.append(
                limitation(
                    "No data has been imported yet, so responses rely "
                    "on built-in assistant logic rather than indexed "
                    "evidence."
                )
            )
        else:
            lines.append(
                observation(
                    "A local knowledge base is available for "
                    "source-grounded answers."
                )
            )
        return "\n".join(lines)

    if intent == "identity":
        return (
            "I am BrisartAI.\n\n"
            "A local-first research assistant built entirely "
            "with Python.\n\n"
            "My role is to ingest files, analyze information, "
            "search indexed knowledge, perform local research, "
            "and explain conclusions transparently."
        )

    if total == 0:
        lines.append(
            limitation("I don't have imported evidence available yet.")
        )
        lines.append("")
        lines.append(f"You said: {user_text}")
        lines.append("")
        lines.append(
            next_step(
                "Ingest local files or folders so I can ground answers "
                "in your own evidence instead of general conversation."
            )
        )
    else:
        lines.append(
            observation(
                f"I searched {total} indexed sources but found "
                "no strong evidence match for this specific request."
            )
        )
        lines.append("")
        lines.append(
            next_step(
                "Try a narrower question or ingest more focused data "
                "on this topic."
            )
        )

    return "\n".join(lines)