"""brisart_ai/io/input_cleaner.py

BrisartAI's chat box only ever receives questions, never commands, so
this just trims whitespace and unwraps one pair of matching quotes
around a pasted question. Used by core/conversation.py before every
search and by core/session_memory.py before storing a topic. Only a
single layer of quotes is stripped on purpose -- a question that is
itself about quoted text shouldn't get mangled.

(The old shell-command-unwrapping/typo-correction logic that used to
live here is gone; it could silently rewrite a real one-word question,
like "stats", into a command that no longer exists.)
"""
from __future__ import annotations


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def normalize_shellish_input(text: str) -> str:
    """Trim whitespace and unwrap one pair of matching surrounding quotes."""
    raw = text.strip()
    if not raw:
        return raw
    return _strip_quotes(raw)


__all__ = ["normalize_shellish_input"]
