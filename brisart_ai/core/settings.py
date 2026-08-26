"""Persistent research settings for BrisartAI.

This gives BrisartAI a small set of user-facing toggles so behavior can
be changed from the Settings dialog without editing code.

Two toggles change real routing behavior, both wired through
``core/conversation.py``:
  * ``auto_web_research`` -- whether the public web is searched when no
    local evidence is found.
  * ``search_local_files`` -- when off, local search is restricted to
    previously indexed web pages only; imported files are excluded.
  * ``search_notes`` -- when on, saved vault notes are merged into the
    local evidence pool alongside files and web pages.

A "Research Collections" toggle previously existed here but was
removed: collections are just tags on top of already-indexed sources,
and there is no "active collection" concept anywhere in the UI for a
toggle to meaningfully restrict. Re-add it once a collection-scoped
search UX actually exists, instead of shipping a checkbox that does
nothing.

Pure Python. No dependencies.
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

# Accepted short keys for toggling a setting by name.
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
    """Loads, saves, and applies BrisartAI research toggles.

    Backed by a small JSON file so settings persist across restarts.
    """

    def __init__(self, path: Path = DEFAULT_SETTINGS_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.values: Dict[str, bool] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        """Load settings from disk, creating defaults if missing."""
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
        """Persist current settings to disk."""
        self.path.write_text(
            json.dumps(self.values, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get(self, key: str) -> bool:
        """Return the current value of a setting."""
        return bool(self.values.get(key, False))

    def set(self, key: str, value: bool) -> None:
        """Set and persist a setting value."""
        if key not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown setting: {key}")
        self.values[key] = bool(value)
        self.save()

    def toggle(self, key: str) -> bool:
        """Flip a setting and persist the new value. Returns new value."""
        new_value = not self.get(key)
        self.set(key, new_value)
        return new_value

    def resolve_key(self, raw_key: str) -> str:
        """Resolve a user-typed key (e.g. 'web') to its canonical name."""
        cleaned = str(raw_key or "").strip().lower()
        resolved = SETTING_ALIASES.get(cleaned)
        if not resolved:
            raise KeyError(
                f"Unknown setting '{raw_key}'. "
                "Try: web, local, notes"
            )
        return resolved

    def render(self) -> str:
        """Return a human-readable settings panel."""
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
