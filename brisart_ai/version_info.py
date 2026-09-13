"""
File: brisart_ai/version_info.py

Purpose
-------
Single source of truth for the two pieces of "who am I" metadata every
part of BrisartAI needs: the display name (APP_NAME) and the current
release version (__version__). This file replaces the removed
brisart_ai/__init__.py, which previously held these two constants.

Why this exists (and why it is not brisart_ai/__init__.py)
------------------------------------------------------------
BrisartAI intentionally ships with no __init__.py files anywhere in
the brisart_ai/ package tree. Every subfolder (core/, io/, knowledge/,
ui/, web/) was already an implicit namespace package in all but name --
their __init__.py files were empty markers that did nothing except tell
older Python tooling "this is a package". Removing them changes
nothing for ordinary submodule imports like
`from brisart_ai.knowledge.index import Index`, because Python 3
(PEP 420) resolves a directory with no __init__.py as a namespace
package automatically.

The one exception was the top-level brisart_ai/__init__.py, which
actually defined APP_NAME and __version__ as real values -- not just a
marker. Deleting it without replacement broke every
`from brisart_ai import APP_NAME, __version__` import with:

    ImportError: cannot import name 'APP_NAME' from 'brisart_ai' (unknown location)

("unknown location" is Python's tell that brisart_ai resolved as a
namespace package with no backing file to import a name from.)

This module is a normal, explicitly-imported submodule
(brisart_ai.version_info), not a package initializer, so it carries no
implicit-import magic and does not need brisart_ai/__init__.py to
exist.

Communication / relationships
------------------------------
- brisart_ai/ui/app.py imports APP_NAME and __version__ from here to
  build the desktop window title and the startup chat banner.
- brisart_ai/ui/sidebar.py imports the same two names to render the
  app name and version line in the sidebar.
- brisart_ai/web/policy.py imports __version__ to build the outbound
  USER_AGENT string sent with every HTTP request BrisartAI makes.

Settings / parameters
----------------------
- APP_NAME (str): Hardcoded display name, "BrisartAI". There is no
  reason for this to live anywhere else or be configurable.
- __version__ (str): Read once at import time from version.txt at the
  project root (the same file that already tracked the release
  version). Reading from version.txt instead of hardcoding a duplicate
  string means the version only ever needs to be bumped in one place.

Edge cases
----------
- If version.txt is missing, unreadable, or empty, __version__ falls
  back to "0.0.0-unknown" rather than raising ImportError. A missing
  version string should never be able to crash the whole application
  at import time -- every consumer of __version__ only ever displays
  it as text.
- The project root is located relative to this file's own path
  (parents[1]: brisart_ai/version_info.py -> brisart_ai/ -> project
  root), the same anchoring technique already used in
  brisart_ai/knowledge/index.py for DEFAULT_DB, so this works
  regardless of the current working directory the app was launched
  from.
"""
from __future__ import annotations

from pathlib import Path

APP_NAME = "BrisartAI"

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_FILE = _PROJECT_ROOT / "version.txt"
_FALLBACK_VERSION = "0.0.0-unknown"


def _read_version() -> str:
    try:
        text = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return _FALLBACK_VERSION
    return text or _FALLBACK_VERSION


__version__ = _read_version()

__all__ = ["APP_NAME", "__version__"]
