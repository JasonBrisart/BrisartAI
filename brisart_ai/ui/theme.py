"""Visual theme constants for the BrisartAI desktop UI.

Centralizing colors and fonts here means every widget in ui/ pulls from
the same palette instead of hardcoding values, so the look can be
changed in one place.
"""
from __future__ import annotations

# Base palette (dark theme)
BG_APP = "#1b1e23"
BG_PANEL = "#20242b"
BG_SIDEBAR = "#181b20"
BG_INPUT = "#262b33"
BG_CHAT = "#15171b"

FG_TEXT = "#e6e6e6"
FG_MUTED = "#8a919b"
FG_ACCENT = "#4fc3f7"
FG_ACCENT_DIM = "#2d8cb3"
FG_SUCCESS = "#7bd88f"
FG_WARN = "#f2c94c"
FG_USER = "#9ad1ff"
FG_ASSISTANT = "#c9f2d8"
FG_SYSTEM = "#8a919b"

BORDER = "#2c313a"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 10)
FONT_MONO_BOLD = ("Consolas", 10, "bold")

PAD = 8
PAD_SMALL = 4

SIDEBAR_WIDTH = 210
