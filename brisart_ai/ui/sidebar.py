"""Sidebar with the five core actions plus a live status readout."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from brisart_ai import APP_NAME, __version__
from brisart_ai.ui import theme


class Sidebar(ttk.Frame):
    def __init__(self, master, actions: dict):
        super().__init__(master, style="Sidebar.TFrame", width=theme.SIDEBAR_WIDTH)
        self.pack_propagate(False)
        self.actions = actions
        self._build()

    def _build(self) -> None:
        title = tk.Label(
            self,
            text=APP_NAME,
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_ACCENT,
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD, 0))

        version = tk.Label(
            self,
            text=__version__,
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_MUTED,
            font=("Segoe UI", 9),
        )
        version.pack(anchor="w", padx=theme.PAD, pady=(0, theme.PAD))

        ttk.Separator(self, orient="horizontal").pack(
            fill="x", padx=theme.PAD, pady=theme.PAD_SMALL
        )

        core_label = tk.Label(
            self,
            text="CORE ACTIONS",
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        core_label.pack(anchor="w", padx=theme.PAD, pady=(theme.PAD_SMALL, theme.PAD_SMALL))

        for label, key in (
            ("Import Files", "import"),
            ("Add Note", "note"),
            ("Research Web", "research"),
            ("Settings", "settings"),
            ("Help", "help"),
        ):
            self._make_button(label, key)

        ttk.Separator(self, orient="horizontal").pack(
            fill="x", padx=theme.PAD, pady=theme.PAD
        )

        advanced_label = tk.Label(
            self,
            text="KNOWLEDGE",
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_MUTED,
            font=("Segoe UI", 8, "bold"),
        )
        advanced_label.pack(anchor="w", padx=theme.PAD, pady=(0, theme.PAD_SMALL))

        for label, key in (
            ("Vault Report", "vault"),
            ("Collections", "collections"),
            ("Notes", "notes"),
            ("Analyze", "analyze"),
            ("Recommend", "recommend"),
            ("Project Report", "project"),
            ("Research Report", "research_report"),
        ):
            self._make_button(label, key, small=True)

        self.status_var = tk.StringVar(value="Indexed: 0 (0 local, 0 web)")
        status = tk.Label(
            self,
            textvariable=self.status_var,
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_MUTED,
            font=("Segoe UI", 8),
            wraplength=theme.SIDEBAR_WIDTH - 2 * theme.PAD,
            justify="left",
        )
        status.pack(side="bottom", anchor="w", padx=theme.PAD, pady=theme.PAD)

    def _make_button(self, label: str, key: str, small: bool = False) -> None:
        btn = tk.Button(
            self,
            text=label,
            anchor="w",
            command=lambda k=key: self.actions[k](),
            bg=theme.BG_SIDEBAR,
            fg=theme.FG_TEXT,
            activebackground=theme.BG_PANEL,
            activeforeground=theme.FG_ACCENT,
            relief="flat",
            font=theme.FONT_UI if not small else ("Segoe UI", 9),
            padx=theme.PAD,
            pady=4,
        )
        btn.pack(fill="x", padx=theme.PAD_SMALL, pady=1)

    def set_status(self, total: int, files: int, web: int) -> None:
        self.status_var.set(f"Indexed: {total} ({files} local, {web} web)")


__all__ = ["Sidebar"]