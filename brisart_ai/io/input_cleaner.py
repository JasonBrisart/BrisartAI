"""Input cleanup for BrisartAI chat mode.

Users often type full shell commands inside the interactive shell, like:
    py brisartai.py ask "hello"

Inside BrisartAI>, that should be treated as:
    hello
"""

from __future__ import annotations

import shlex
from difflib import get_close_matches

COMMANDS = {"status", "ingest", "scan-drive", "analyze", "recommend", "ask", "web", "crawl", "chat"}
ALIASES = {
    "statys": "status",
    "stats": "status",
    "analyse": "analyze",
    "rec": "recommend",
    "recs": "recommend",
    "char": "chat",
    "chatt": "chat",
    "exit": "/exit",
    "quit": "/exit",
}


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def normalize_shellish_input(text: str) -> str:
    raw = text.strip()
    if not raw:
        return raw

    # Exact alias support.
    lowered = raw.lower()
    if lowered in ALIASES:
        return ALIASES[lowered]

    # Handle accidental trailing slash: analyze\
    if lowered.endswith("\\") and lowered[:-1] in COMMANDS:
        return lowered[:-1]

    try:
        parts = shlex.split(raw, posix=False)
    except Exception:
        parts = raw.split()

    cleaned = [p.strip() for p in parts if p.strip()]
    lowered_parts = [p.lower().strip('"') for p in cleaned]

    # py brisartai.py ask "hello" -> hello
    if len(lowered_parts) >= 3 and lowered_parts[0] in {"py", "python", "python3"} and lowered_parts[1].endswith("brisartai.py"):
        cmd = lowered_parts[2]
        if cmd == "ask":
            return _strip_quotes(" ".join(cleaned[3:]))
        if cmd in COMMANDS:
            rest = " ".join(cleaned[3:])
            return f"/{cmd} {rest}".strip()

    # brisartai.py ask "hello" -> hello
    if len(lowered_parts) >= 2 and lowered_parts[0].endswith("brisartai.py"):
        cmd = lowered_parts[1]
        if cmd == "ask":
            return _strip_quotes(" ".join(cleaned[2:]))
        if cmd in COMMANDS:
            rest = " ".join(cleaned[2:])
            return f"/{cmd} {rest}".strip()

    # Typo correction for top-level single-word commands typed inside chat.
    if len(lowered_parts) == 1 and lowered_parts[0] not in COMMANDS:
        match = get_close_matches(lowered_parts[0], list(COMMANDS), n=1, cutoff=0.75)
        if match:
            return match[0]

    return raw
