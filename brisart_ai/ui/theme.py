"""
File: brisart_ai/ui/theme.py

Purpose
-------
The single dark color palette, font tuples, and two spacing constants
every widget in brisart_ai/ui/ shares.

Communication / relationships
------------------------------
- Imported by every module in brisart_ai/ui/.
- Imports nothing; pure constants, no Tk imports.

Settings / parameters
----------------------
- BG_*/FG_* constants, FONT_*, PAD/PAD_SMALL, SIDEBAR_WIDTH.

Edge cases
----------
- None -- this module has no logic, only literal constants.

Known limitations
-----------------
- A flat palette of color/spacing constants; it defines no behavior and
  imports nothing.
- Single hard-coded dark theme; there is no runtime theme switching.
- Colors are chosen for the desktop Tkinter shell, not validated for
  every OS's native rendering.

Examples
--------
    >>> from brisart_ai.ui import theme
    >>> theme.BG_APP.startswith("#")
    True
"""
from __future__ import annotations

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


