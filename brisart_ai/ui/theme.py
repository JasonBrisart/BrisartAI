"""
File: brisart_ai/ui/theme.py

Purpose
-------
The single dark color palette, font tuples, and two spacing constants
every widget in brisart_ai/ui/ shares, so the application's look changes
in exactly one place instead of being hardcoded per-widget.

Communication / relationships
------------------------------
- Imported by every module in brisart_ai/ui/ (app.py, chat_panel.py,
  dialogs.py, sidebar.py) for BG_*/FG_*/FONT_*/PAD constants.
- Imports nothing; pure constants, no Tk imports, so importing this
  module never has side effects and never requires a display.

Settings / parameters
----------------------
- BG_*/FG_* constants: the dark palette (app/panel/sidebar/input/chat
  backgrounds; text/muted/accent/success/warn foregrounds; per-role
  chat-transcript colors for user/assistant/system lines).
- FONT_*: UI, heading, and monospace (chat transcript) font tuples.
- PAD / PAD_SMALL: the two spacing constants used throughout ui/.
- SIDEBAR_WIDTH: fixed pixel width; sidebar.py disables pack-propagation
  against this value so the sidebar never resizes to fit button text.

Edge cases
----------
- None -- this module has no logic, only literal constants, and cannot
  fail at import time.
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

FG_USER = "#9ad1ff"          # user messages in the chat transcript
FG_ASSISTANT = "#c9f2d8"     # assistant messages
FG_SYSTEM = "#8a919b"        # system/status lines

BORDER = "#2c313a"

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_MONO = ("Consolas", 10)         # chat transcript body
FONT_MONO_BOLD = ("Consolas", 10, "bold")

PAD = 8
PAD_SMALL = 4

SIDEBAR_WIDTH = 210  # fixed pixel width; sidebar.py disables pack-propagation
