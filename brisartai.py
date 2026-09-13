"""
File: brisartai.py

Purpose
-------
BrisartAI's single entry point. GUI-only: launches the desktop
application unconditionally, with no command-line arguments and no
alternate mode. The former terminal CLI/chat stack (assistant.py,
chat.py, cli.py, commands.py) was fully removed as part of stripping
BrisartAI down to its core loop: connect to the internet, import files,
use those files.

Communication / relationships
------------------------------
- Calls brisart_ai.ui.app.run(DEFAULT_DB), the only function this file
  invokes.
- Imports DEFAULT_DB from brisart_ai.knowledge.index so the database
  path is defined in exactly one place (knowledge/index.py) and simply
  passed through here.

Settings / parameters
----------------------
- None here directly; run() accepts db_path with DEFAULT_DB as its
  default, so running this file with no arguments always opens the
  project-root-anchored database.

Edge cases
----------
- A startup failure (locked/read-only/unopenable database) is handled
  entirely inside brisart_ai.ui.app.run(); this file has no try/except
  of its own, by design -- there is exactly one place in the codebase
  that decides how to react to a construction failure.
"""
from __future__ import annotations

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui.app import run

if __name__ == "__main__":
    run(DEFAULT_DB)
