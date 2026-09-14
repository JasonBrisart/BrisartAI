"""
File: brisart_ai/version_info.py

Purpose
-------
Single source of truth for APP_NAME and __version__. Replaces the
removed brisart_ai/__init__.py.

Communication / relationships
------------------------------
- brisart_ai/ui/app.py, brisart_ai/ui/sidebar.py: APP_NAME/__version__.
- brisart_ai/web/policy.py: __version__ for USER_AGENT.

Settings / parameters
----------------------
- APP_NAME (str): "BrisartAI".
- __version__ (str): read from version.py at the project root.
  version.py is loaded directly by file path via importlib.util
  (not a plain `import version`, since it is now a real Python module
  rather than a bare version string in a .txt file) and its own
  __version__ attribute is used. Loading by path (rather than a plain
  `import version`) avoids ever needing to add the project root to
  sys.path, and keeps this the one and only place that touches
  version.py.

Edge cases
----------
- If version.py is missing, unreadable, fails to import (a syntax
  error, for instance), or does not define __version__, this falls
  back to "0.0.0-unknown" rather than raising ImportError -- exactly
  the same failure-tolerant contract the previous version.txt-reading
  implementation had.
- Project root located relative to this file's own path (parents[1]).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

APP_NAME = "BrisartAI"

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_VERSION_FILE = _PROJECT_ROOT / "version.py"
_FALLBACK_VERSION = "0.0.0-unknown"


def _read_version() -> str:
    try:
        spec = importlib.util.spec_from_file_location("_brisart_version", _VERSION_FILE)
        if spec is None or spec.loader is None:
            return _FALLBACK_VERSION
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        version = getattr(module, "__version__", "")
        return str(version).strip() or _FALLBACK_VERSION
    except Exception:
        return _FALLBACK_VERSION


__version__ = _read_version()

__all__ = ["APP_NAME", "__version__"]
