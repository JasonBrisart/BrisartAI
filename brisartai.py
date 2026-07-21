#!/usr/bin/env python3
"""BrisartAI command-line entry point.

Run with no arguments to enter interactive chat mode:
    py brisartai.py

Run with commands for direct CLI mode:
    py brisartai.py status
    py brisartai.py ask "hello"
"""

from __future__ import annotations

import sys

from brisart_ai.assistant import cmd_chat, main
from brisart_ai.index import DEFAULT_DB


if __name__ == "__main__":
    if len(sys.argv) == 1:
        cmd_chat(DEFAULT_DB, 8)
    else:
        raise SystemExit(main())
