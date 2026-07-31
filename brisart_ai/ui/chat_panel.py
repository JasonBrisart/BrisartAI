"""Chat transcript panel for the BrisartAI desktop UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk

from brisart_ai.ui import theme


class ChatPanel(ttk.Frame):
    """Scrollable message transcript plus a single-line input box."""

    def __init__(self, master, on_submit):
        super().__init__(master, style="Panel.TFrame")
        self.on_submit = on_submit
        self._build()

    def _build(self) -> None:
        self.transcript = scrolledtext.ScrolledText(
            self,
            wrap="word",
            bg=theme.BG_CHAT,
            fg=theme.FG_TEXT,
            insertbackground=theme.FG_TEXT,
            font=theme.FONT_MONO,
            borderwidth=0,
            highlightthickness=0,
            padx=theme.PAD,
            pady=theme.PAD,
            state="disabled",
        )
        self.transcript.pack(side="top", fill="both", expand=True)

        self.transcript.tag_configure(
            "user", foreground=theme.FG_USER, font=theme.FONT_MONO_BOLD
        )
        self.transcript.tag_configure("assistant", foreground=theme.FG_ASSISTANT)
        self.transcript.tag_configure(
            "system", foreground=theme.FG_SYSTEM, font=("Consolas", 9, "italic")
        )

        input_row = ttk.Frame(self, style="Panel.TFrame")
        input_row.pack(side="bottom", fill="x", pady=(theme.PAD_SMALL, 0))

        self.input_var = tk.StringVar()
        self.entry = tk.Entry(
            input_row,
            textvariable=self.input_var,
            bg=theme.BG_INPUT,
            fg=theme.FG_TEXT,
            insertbackground=theme.FG_TEXT,
            font=theme.FONT_UI,
            relief="flat",
        )
        self.entry.pack(
            side="left", fill="x", expand=True, ipady=6, padx=(0, theme.PAD_SMALL)
        )
        self.entry.bind("<Return>", self._submit)

        send_btn = tk.Button(
            input_row,
            text="Send",
            command=self._submit,
            bg=theme.FG_ACCENT_DIM,
            fg="#0b0d10",
            activebackground=theme.FG_ACCENT,
            relief="flat",
            font=theme.FONT_UI_BOLD,
            padx=14,
        )
        send_btn.pack(side="right")

    def _submit(self, _event=None) -> None:
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        self.on_submit(text)

    def append(self, text: str, tag: str = "assistant") -> None:
        self.transcript.configure(state="normal")
        if self.transcript.index("end-1c") != "1.0":
            self.transcript.insert("end", "\n\n")
        self.transcript.insert("end", text, tag)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def append_user(self, text: str) -> None:
        self.append(f"You: {text}", "user")

    def append_assistant(self, text: str) -> None:
        self.append(text, "assistant")

    def append_system(self, text: str) -> None:
        self.append(text, "system")

    def focus_input(self) -> None:
        self.entry.focus_set()


__all__ = ["ChatPanel"]