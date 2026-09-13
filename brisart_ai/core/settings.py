"""
File: brisart_ai/core/settings.py

Purpose
-------
Persistent research toggles, backed by data/research_settings.json, so
the user's choices survive an app restart. Three toggles:
auto_web_research (search the web when local evidence comes up empty),
search_local_files (include imported files in local search), and
search_notes (include saved notes).

Communication / relationships
------------------------------
- brisart_ai/core/conversation.py: reads all three toggles via .get()
  every time build_conversation_answer() answers a question.
- brisart_ai/ui/dialogs.py: SettingsDialog renders one checkbox per
  toggle straight from TOGGLE_LABELS and calls .set()/.toggle() on
  ResearchSettings when the user clicks one.
- brisart_ai/ui/service.py: constructs and owns the single
  ResearchSettings instance for the app's lifetime.
- Imports nothing from elsewhere in brisart_ai; only json/pathlib/typing.

Settings / parameters
----------------------
- DEFAULT_SETTINGS_PATH: data/research_settings.json, relative to the
  process working directory.
- DEFAULT_SETTINGS: {"search_local_files": True, "search_notes": True,
  "auto_web_research": False} -- files and notes are searched locally by
  default; automatic web research is opt-in.
- TOGGLE_LABELS: the human-readable label shown per toggle in the
  Settings dialog and in render()'s text panel.
- SETTING_ALIASES: short typed keys ("web", "local", "notes") mapped to
  their canonical setting name, for any future text-command surface;
  resolve_key() raises KeyError with a helpful hint for an unknown key.

Edge cases
----------
- load() creates the settings file with defaults if it does not exist,
  and swallows a corrupt/unreadable file rather than raising -- a broken
  settings file can only ever fall back to defaults, never crash
  startup.
- Only known boolean keys are accepted on load(); a stale key from an
  older build (e.g. the removed "search_collections" toggle) is
  silently ignored rather than raising or being re-persisted.
- A fourth "Research Collections" toggle used to exist here and was
  removed -- collections are just tags with no "active collection"
  concept anywhere in the UI, so the checkbox did nothing. Re-add only
  once a collection-scoped search actually exists.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

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

# Accepted short keys for toggling a setting by name (for any future
# text-command surface).
SETTING_ALIASES = {
    "web": "auto_web_research",
    "auto-web": "auto_web_research",
    "auto_web": "auto_web_research",
    "auto_web_research": "auto_web_research",
    "local": "search_local_files",
    "local-files": "search_local_files",
    "search_local_files": "search_local_files",
    "notes": "search_notes",
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
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        for key in DEFAULT_SETTINGS:
            if key in data and isinstance(data[key], bool):
                self.values[key] = data[key]

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.values, indent=2, sort_keys=True),
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
        """Flip a setting and persist it. Returns the new value."""
        new_value = not self.get(key)
        self.set(key, new_value)
        return new_value

    def resolve_key(self, raw_key: str) -> str:
        """Resolve a short typed key (e.g. 'web') to its canonical name."""
        cleaned = str(raw_key or "").strip().lower()
        resolved = SETTING_ALIASES.get(cleaned)
        if not resolved:
            raise KeyError(
                f"Unknown setting '{raw_key}'. Try: web, local, notes"
            )
        return resolved

    def render(self) -> str:
        """Human-readable settings panel."""
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
    "DEFAULT_SETTINGS",
    "DEFAULT_SETTINGS_PATH",
    "ResearchSettings",
    "SETTING_ALIASES",
    "TOGGLE_LABELS",
]
