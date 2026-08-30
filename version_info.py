"""brisart_ai/version_info.py

App name and version, read from version.txt at the project root so the
version only has to be bumped in one place. Exists as a normal,
explicitly-imported module (not a package __init__.py) because BrisartAI
ships with no __init__.py files anywhere -- every subfolder is a plain
Python 3 namespace package. ui/app.py, ui/sidebar.py, and web/policy.py
(for its USER_AGENT string) import APP_NAME/__version__ from here.

If version.txt is missing or unreadable, __version__ falls back to
"0.0.0-unknown" rather than raising -- a missing version string should
never be able to crash the app at import time.
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
