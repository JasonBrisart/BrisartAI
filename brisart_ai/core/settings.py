"""
File: brisart_ai/core/settings.py

Purpose
-------
Persistent research toggles, backed by data/research_settings.json.

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: reads toggles via .get().
- brisart_ai/ui/dialogs.py: SettingsDialog renders checkboxes.
- brisart_ai/ui/service.py: constructs the single ResearchSettings instance.
- Imports brisart_ai.native.brisart_json.{brisart_dumps, brisart_loads}
  (replacing json.*) -- see native/README.md for verification.

Settings / parameters
----------------------
- DEFAULT_SETTINGS_PATH: data/research_settings.json.
- DEFAULT_SETTINGS: search_local_files/search_notes True,
  auto_web_research False.
- TOGGLE_LABELS / SETTING_ALIASES.

Edge cases
----------
- load() creates defaults if missing; swallows corrupt files.
- Only known boolean keys accepted on load.

Known limitations
-----------------
- Only the fixed toggle keys in DEFAULT_SETTINGS are recognized; an
  unknown key is ignored rather than stored.
- Persistence is a flat JSON file; there is no schema migration if the
  toggle set changes between versions.
- Values are coerced to bool; non-boolean settings are not supported.

Examples
--------
    >>> s = ResearchSettings()
    >>> s.get("search_local_files")
    True
    >>> s.set("auto_web_research", True); s.get("auto_web_research")
    True
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from brisart_ai.native.brisart_json import brisart_dumps, brisart_loads

DEFAULT_SETTINGS_PATH = Path("data/research_settings.json")
DEFAULT_SETTINGS: Dict[str, bool] = {
    "search_local_files": True,
    "search_notes": True,
    "auto_web_research": False,
}

TOGGLE_LABELS = {
    "search_local_files": "Local Files",
    "search_notes": "Research Notes",
    "auto_web_research": "Automatic Web Research",
}

SETTING_ALIASES = {
    "web": "auto_web_research", "auto-web": "auto_web_research",
    "auto_web": "auto_web_research", "auto_web_research": "auto_web_research",
    "local": "search_local_files", "local-files": "search_local_files",
    "search_local_files": "search_local_files", "notes": "search_notes",
    "search_notes": "search_notes",
}


class ResearchSettings:
    """Loads, saves, and applies BrisartAI research toggles."""

    def __init__(self, path: Path = DEFAULT_SETTINGS_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.values: Dict[str, bool] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.save()
            return
        try:
            data = brisart_loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        for key in DEFAULT_SETTINGS:
            if key in data and isinstance(data[key], bool):
                self.values[key] = data[key]

    def save(self) -> None:
        self.path.write_text(
            brisart_dumps(self.values, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get(self, key: str) -> bool:
        return bool(self.values.get(key, False))

    def set(self, key: str, value: bool) -> None:
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting: {key}")
        self.values[key] = bool(value)
        self.save()

    def toggle(self, key: str) -> bool:
        new_value = not self.get(key)
        self.set(key, new_value)
        return new_value

    def resolve_key(self, raw_key: str) -> str:
        cleaned = str(raw_key or "").strip().lower()
        resolved = SETTING_ALIASES.get(cleaned)
        if not resolved:
            raise KeyError(f"Unknown setting '{raw_key}'. Try: web, local, notes")
        return resolved

    def render(self) -> str:
        lines = ["Research Sources", ""]
        for key, label in TOGGLE_LABELS.items():
            mark = "x" if self.get(key) else " "
            lines.append(f"[{mark}] {label}")
        lines.append("")
        if self.get("auto_web_research"):
            lines.append(
                "Automatic Web Research is ON. When no local evidence "
                "is found, BrisartAI will automatically search the "
                "public web before answering."
            )
        else:
            lines.append(
                "Automatic Web Research is OFF. BrisartAI will only "
                "use local indexed evidence unless you turn it on or "
                "use the Research Web action."
            )
        lines.append("")
        if self.get("search_local_files"):
            lines.append(
                "Local Files is ON. Imported files are searched "
                "alongside previously indexed web pages."
            )
        else:
            lines.append(
                "Local Files is OFF. Only previously indexed web pages "
                "are searched locally; imported files are ignored until "
                "this is turned back on."
            )
        lines.append("")
        if self.get("search_notes"):
            lines.append(
                "Research Notes is ON. Saved notes are merged into "
                "search results alongside files and web pages."
            )
        else:
            lines.append(
                "Research Notes is OFF. Saved notes exist in the vault "
                "but are not included in search results."
            )
        return "\n".join(lines)


__all__ = [
    "DEFAULT_SETTINGS", "DEFAULT_SETTINGS_PATH", "ResearchSettings",
    "SETTING_ALIASES", "TOGGLE_LABELS",
]


