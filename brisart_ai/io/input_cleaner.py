"""Input cleanup for the BrisartAI desktop UI.

BrisartAI is GUI-only: every message the user types in the chat box is a
question, not a command. This module normalizes whitespace and strips
accidental surrounding quotes so a pasted or quoted question is treated
the same as a plainly typed one.

The old shell-command unwrapping and typo-correction logic (which mapped
words onto the removed CLI verbs like ``status``/``ingest``/``analyze``)
has been removed. That logic could silently rewrite a legitimate
one-word question -- e.g. "stats" -> "status" -- into a command that no
longer exists, corrupting the search.
"""

from __future__ import annotations


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def normalize_shellish_input(text: str) -> str:
    """Normalize a chat message for searching.

    Collapses surrounding whitespace and removes a single pair of
    matching surrounding quotes. The text is otherwise returned as the
    user typed it.
    """
    raw = text.strip()
    if not raw:
        return raw
    return _strip_quotes(raw)


__all__ = ["normalize_shellish_input"]
