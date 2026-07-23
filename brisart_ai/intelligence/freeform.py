"""
Improved conversational fallback for BrisartAI.
"""

from __future__ import annotations

from typing import Iterable, List

from .personality import observation
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
        "hl",
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
        lines.append("Current State:")
        lines.append(f"- Indexed Sources: {total}")
        lines.append(f"- Local Files: {files}")
        lines.append(f"- Web Pages: {web}")
        lines.append("")
        lines.append(
            "You can chat normally, ingest data, scan folders, "
            "search the web, or analyze imported knowledge."
        )

        return "\n".join(lines)

    if intent == "status":

        lines.append("BrisartAI Status")
        lines.append("")
        lines.append(f"Indexed Sources: {total}")
        lines.append(f"Local Files: {files}")
        lines.append(f"Web Pages: {web}")

        if recent_topics:
            lines.append("")
            lines.append("Recent Topics:")

            for topic in list(recent_topics)[:5]:
                lines.append(f"- {topic}")

        lines.append("")

        if total == 0:

            lines.append(
                "Assessment: System is operational but no data "
                "has been imported yet."
            )

        else:

            lines.append(
                "Assessment: Local knowledge base available."
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
            "I don't have imported evidence available yet."
        )

        lines.append("")

        lines.append(
            f"You said: {user_text}"
        )

        lines.append("")

        lines.append(
            "I can still converse normally, but this answer "
            "is based on built-in assistant logic rather than "
            "indexed files."
        )

    else:

        lines.append(
            observation(
                f"I searched {total} indexed sources but found "
                "no strong evidence match for this specific request."
            )
        )

    if recent_topics:

        recent = list(recent_topics)[:3]

        if recent:

            lines.append("")
            lines.append(
                "Recent context:"
            )

            for item in recent:
                lines.append(f"- {item}")

    lines.append("")
    lines.append(
        "Tell me more about what you're trying to do and I'll "
        "attempt to help from available context."
    )

    return "\n".join(lines)