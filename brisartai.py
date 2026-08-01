#!/usr/bin/env python3
"""
BrisartAI entry point.

GUI-only. The terminal CLI/chat stack (assistant.py, chat.py, cli.py,
commands.py) has been removed as part of stripping BrisartAI down to
its core loop: connect to the internet, import files, use those files.
"""

from __future__ import annotations

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui.app import run


if __name__ == "__main__":
    run(DEFAULT_DB)