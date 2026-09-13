"""
File: brisart_ai/io/input_cleaner.py

Purpose
-------
Normalizes a typed chat question before it reaches search: trims
whitespace and unwraps one pair of matching quotes around a pasted
question. The chat box only ever receives questions, never commands, so
this deliberately does no shell-syntax or typo correction.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: calls normalize_shellish_input()
  before every search in build_conversation_answer().
- brisart_ai/core/session_memory.py: calls normalize_shellish_input()
  before compressing and storing a topic.
- Imports nothing from elsewhere in brisart_ai; pure string logic.

Settings / parameters
----------------------
- None. The function takes no configuration; behavior is fixed.

Edge cases
----------
- Only a single layer of quotes is stripped on purpose -- a question
  that is itself about quoted text (e.g. `say "hi"`) is not mangled,
  because the inner quotes are not adjacent to the string boundaries.
- An all-whitespace input returns "" rather than raising.
- The older shell-command-unwrapping/typo-correction logic that used to
  live here is gone; it could silently rewrite a real one-word question
  like "stats" into a command that no longer exists in this GUI-only
  build.
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
