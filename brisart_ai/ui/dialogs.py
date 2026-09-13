"""
File: brisart_ai/ui/dialogs.py

Purpose
-------
The small modal prompts ui/app.py's sidebar actions need: a file/folder
picker, a generic text prompt, a two-step title/body prompt for notes,
and SettingsDialog, a checkbox per toggle in core/settings.py's
TOGGLE_LABELS.

Communication / relationships
------------------------------
- brisart_ai/ui/app.py: calls ask_import_path(), ask_text(), ask_note(),
  and constructs SettingsDialog(self, self.service, on_change=...).
- brisart_ai/core/settings.py: SettingsDialog reads TOGGLE_LABELS to
  render one checkbox per toggle and reads/writes directly against the
  live BrisartService.settings instance.
- Imports brisart_ai.ui.theme for SettingsDialog's colors/fonts.

Settings / parameters
----------------------
- ask_import_path(): folder picker first, falls back to a single-file
  picker if the folder picker is cancelled.
- ask_note(): two sequential prompts (title, then body); short-circuits
  to ("", "") if either step is cancelled or the body ends up empty.
- SettingsDialog(master, service, on_change=None): on_change is called
  after every toggle so the caller (the sidebar's status line) can
  refresh immediately -- there is no separate "Apply" step.

Edge cases
----------
- ask_text()/ask_note() return "" (not None) on cancel, so callers can
  use a plain `if not result:` check without a None check.
- SettingsDialog._toggle() writes directly to
  self.service.settings.set(key, ...), so a toggle is persisted to disk
  immediately, not just held in the dialog's own state.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, simpledialog

from brisart_ai.core.settings import TOGGLE_LABELS
from brisart_ai.ui import theme


def ask_import_path(master) -> str:
    path = filedialog.askdirectory(title="Choose a folder to import")
    if not path:
        path = filedialog.askopenfilename(title="Or choose a single file")
    return path or ""


def ask_text(master, title: str, prompt: str) -> str:
    return simpledialog.askstring(title, prompt, parent=master) or ""


def ask_note(master) -> tuple:
    """Prompt for a note title, then a body. Returns ("", "") on cancel."""
    title = simpledialog.askstring("Add Note", "Note title:", parent=master)
    if not title:
        return "", ""
    body = simpledialog.askstring("Add Note", "Note text:", parent=master)
    if not body:
        return "", ""
    return title, body


class SettingsDialog(tk.Toplevel):
    """Checkbox panel for BrisartAI research settings."""

    def __init__(self, master, service, on_change=None):
        super().__init__(master)
        self.title("Research Settings")
        self.configure(bg=theme.BG_PANEL)
        self.resizable(False, False)
        self.service = service
        self.on_change = on_change
        self.vars = {}
        self._build()

    def _build(self) -> None:
        heading = tk.Label(
            self,
            text="Research Sources",
            bg=theme.BG_PANEL,
            fg=theme.FG_ACCENT,
            font=theme.FONT_HEADING,
        )
        heading.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, theme.PAD_SMALL))

        for key, label in TOGGLE_LABELS.items():
            var = tk.BooleanVar(value=self.service.settings.get(key))
            self.vars[key] = var
            chk = tk.Checkbutton(
                self,
                text=label,
                variable=var,
                command=lambda k=key: self._toggle(k),
                bg=theme.BG_PANEL,
                fg=theme.FG_TEXT,
                selectcolor=theme.BG_INPUT,
                activebackground=theme.BG_PANEL,
                activeforeground=theme.FG_ACCENT,
                font=theme.FONT_UI,
                anchor="w",
            )
            chk.pack(fill="x", padx=theme.PAD, pady=2)

        note = tk.Label(
            self,
            text=(
                "Only Automatic Web Research changes how questions are\n"
                "answered today. Imported files and saved notes are\n"
                "always part of your local knowledge base."
            ),
            bg=theme.BG_PANEL,
            fg=theme.FG_MUTED,
            font=("Segoe UI", 8),
            justify="left",
        )
        note.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, theme.PAD))

        close_btn = tk.Button(
            self,
            text="Close",
            command=self.destroy,
            bg=theme.FG_ACCENT_DIM,
            fg="#0b0d10",
            relief="flat",
            font=theme.FONT_UI_BOLD,
            padx=14,
        )
        close_btn.pack(pady=(0, theme.PAD))

    def _toggle(self, key: str) -> None:
        self.service.settings.set(key, self.vars[key].get())
        if self.on_change:
            self.on_change()


__all__ = ["ask_import_path", "ask_text", "ask_note", "SettingsDialog"]
