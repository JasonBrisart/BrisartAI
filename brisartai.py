#!/usr/bin/env python3
"""
BrisartAI command-line entry point.

Default behavior (no arguments) now launches the desktop GUI
introduced in 1.0.0-beta.1. Terminal chat mode and every existing
CLI subcommand (ingest, ask, web, vault, ...) still work exactly as
before.
"""
from __future__ import annotations

import sys

from brisart_ai.core.assistant import cmd_chat, main
from brisart_ai.knowledge.index import DEFAULT_DB


def _launch_gui() -> None:
    from brisart_ai.ui.app import run
    run(DEFAULT_DB)


if __name__ == "__main__":
    argv = sys.argv[1:]

    if not argv:
        try:
            _launch_gui()
        except Exception as exc:
            print(f"GUI unavailable ({exc}). Falling back to terminal chat.")
            cmd_chat(DEFAULT_DB, 8)
    elif argv[0] in {"--cli", "chat"}:
        cmd_chat(DEFAULT_DB, 8)
    elif argv[0] == "--gui":
        _launch_gui()
    else:
        raise SystemExit(main(argv))