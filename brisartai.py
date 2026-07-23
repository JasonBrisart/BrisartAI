#!/usr/bin/env python3

"""
BrisartAI command-line entry point.
"""

from __future__ import annotations

import sys

from brisart_ai.core.assistant import cmd_chat, main
from brisart_ai.knowledge.index import DEFAULT_DB


if __name__ == "__main__":

    if len(sys.argv) == 1:
        cmd_chat(DEFAULT_DB, 8)
    else:
        raise SystemExit(main())