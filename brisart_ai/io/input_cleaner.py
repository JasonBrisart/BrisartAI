"""
File: brisart_ai/io/input_cleaner.py

Purpose
-------
Normalizes a typed chat question: trims whitespace and unwraps one
pair of matching quotes.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py, brisart_ai/core/session_memory.py
  both call normalize_shellish_input().

Settings / parameters
----------------------
- None.

Edge cases
----------
- Only a single layer of quotes is stripped.
- An all-whitespace input returns "".

Known limitations
-----------------
- Only strips a single matched pair of surrounding quotes and outer
  whitespace; it does not unescape shell metacharacters or split args.
- Not a shell parser -- embedded quotes and escapes inside the string
  are left untouched.

Examples
--------
    >>> normalize_shellish_input('  "who founded microsoft"  ')
    'who founded microsoft'
    >>> normalize_shellish_input("plain text")
    'plain text'
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


