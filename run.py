"""
File: run.py

Purpose
-------
BrisartAI's single entry point. GUI-only. Formerly named brisartai.py;
renamed to run.py so starting the application is simply `python run.py`
(or `py run.py` on Windows, matching start.bat).

Communication / relationships
------------------------------
- Imports DEFAULT_DB from brisart_ai.knowledge.index -- the path to
  BrisartAI's SQLite index file, anchored to the project root
  regardless of the working directory this script was launched from.
- Calls brisart_ai.ui.app.run(DEFAULT_DB), which is the only other
  function this file touches. Every startup behavior -- constructing
  the backend service, opening the Tk window, and handling any startup
  failure -- lives inside ui/app.py's run(), not here.

Settings / parameters
----------------------
- No parameters or constants of its own. run() accepts an optional
  db_path argument (defaulting to DEFAULT_DB), which this file passes
  through explicitly for clarity rather than relying on the default.

Edge cases
----------
- A startup failure (e.g. the SQLite index file is locked by another
  running copy of BrisartAI, or the install folder is read-only) is
  handled entirely inside brisart_ai.ui.app.run() -- it shows a
  messagebox dialog and returns cleanly rather than letting an
  exception propagate up to this file. This file itself has no
  try/except, since there is nothing here for it to catch.
- The `if __name__ == "__main__":` guard means importing this module
  from elsewhere (which nothing in the codebase currently does) would
  not launch the GUI as a side effect.
"""
from __future__ import annotations

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui.app import run

if __name__ == "__main__":
    run(DEFAULT_DB)
