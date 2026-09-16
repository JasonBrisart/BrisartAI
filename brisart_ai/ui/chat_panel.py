"""
File: brisart_ai/ui/chat_panel.py

Purpose
-------
The scrollable transcript plus single-line input box that makes up the
center of the BrisartAI window.

Communication / relationships
------------------------------
- brisart_ai/ui/app.py: constructs ChatPanel and calls append_*(). After
  every assistant answer that carries citations, app.py also calls
  render_citation_controls(citations, on_mark), which embeds a small
  relevant/irrelevant control row per cited source directly into the
  transcript, right under that answer.
- Imports brisart_ai.ui.theme for every color/font constant used.

Settings / parameters
----------------------
- on_submit: callback invoked with stripped, non-empty input text.
- render_citation_controls(citations, on_mark): citations is the list of
  {"index", "title", ...} dicts from BrisartService.last_citations;
  on_mark(citation, relevant: bool) is called when a control is pressed.
  citations=[] (no cited sources for that answer) renders nothing.

Edge cases
----------
- The transcript is read-only outside of append()/
  render_citation_controls().
- append() auto-scrolls to the bottom after every message.
- render_citation_controls() is a no-op for an empty citations list, so an
  uncited answer (e.g. "I don't have any indexed information...") never
  grows a stray, empty controls row.
- Each citation's controls are embedded ONCE, at the point they're
  rendered; marking one does not remove or grey out its buttons -- the
  user can press Relevant/Irrelevant more than once, and
  RelevanceFeedback's own per-term clamping (see
  knowledge/relevance_feedback.py) is what keeps repeated marks bounded,
  not this widget.

Known limitations
-----------------
- A Tkinter view widget only; it renders text and citation controls the
  service produces and holds no business logic or ranking behavior of its
  own -- marking itself is entirely BrisartService.mark_citation()'s job.
- Rendering is plain text with light tagging, not rich HTML/markdown.
- Requires a display; not exercised by the headless test suite.

Examples
--------
    >>> panel = ChatPanel(parent, on_submit=cb)    # doctest: +SKIP
    >>> panel.append_assistant("some answer text") # doctest: +SKIP
    >>> panel.render_citation_controls(            # doctest: +SKIP
    ...     [{"index": 1, "title": "History of Microsoft"}],
    ...     on_mark=lambda citation, relevant: None)
"""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Callable, Dict, List, Optional

from brisart_ai.ui import theme


class ChatPanel(ttk.Frame):
    """Scrollable message transcript plus a single-line input box."""

    def __init__(self, master, on_submit):
        super().__init__(master, style="Panel.TFrame")
        self.on_submit = on_submit
        self._build()

    def _build(self) -> None:
        self.transcript = scrolledtext.ScrolledText(
            self, wrap="word", bg=theme.BG_CHAT, fg=theme.FG_TEXT,
            insertbackground=theme.FG_TEXT, font=theme.FONT_MONO,
            borderwidth=0, highlightthickness=0, padx=theme.PAD, pady=theme.PAD,
            state="disabled",
        )
        self.transcript.pack(side="top", fill="both", expand=True)
        self.transcript.tag_configure("user", foreground=theme.FG_USER, font=theme.FONT_MONO_BOLD)
        self.transcript.tag_configure("assistant", foreground=theme.FG_ASSISTANT)
        self.transcript.tag_configure("system", foreground=theme.FG_SYSTEM, font=("Consolas", 9, "italic"))

        input_row = ttk.Frame(self, style="Panel.TFrame")
        input_row.pack(side="bottom", fill="x", pady=(theme.PAD_SMALL, 0))

        self.input_var = tk.StringVar()
        self.entry = tk.Entry(
            input_row, textvariable=self.input_var, bg=theme.BG_INPUT,
            fg=theme.FG_TEXT, insertbackground=theme.FG_TEXT, font=theme.FONT_UI,
            relief="flat",
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, theme.PAD_SMALL))
        self.entry.bind("<Return>", self._submit)

        send_btn = tk.Button(
            input_row, text="Send", command=self._submit, bg=theme.FG_ACCENT_DIM,
            fg="#0b0d10", activebackground=theme.FG_ACCENT, relief="flat",
            font=theme.FONT_UI_BOLD, padx=14,
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

    def render_citation_controls(
        self,
        citations: List[Dict[str, object]],
        on_mark: Callable[[Dict[str, object], bool], None],
    ) -> None:
        """Embed one Relevant/Irrelevant control row per cited source,
        directly under the most recently appended assistant answer. A
        no-op when `citations` is empty (an uncited answer grows no
        stray controls row)."""
        if not citations:
            return
        self.transcript.configure(state="normal")
        self.transcript.insert("end", "\n")
        container = ttk.Frame(self.transcript, style="Panel.TFrame")
        for citation in citations:
            self._add_citation_row(container, citation, on_mark)
        self.transcript.window_create("end", window=container)
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _add_citation_row(
        self,
        container: ttk.Frame,
        citation: Dict[str, object],
        on_mark: Callable[[Dict[str, object], bool], None],
    ) -> None:
        row = ttk.Frame(container, style="Panel.TFrame")
        row.pack(fill="x", pady=1)
        title = str(citation.get("title") or citation.get("location") or "source")
        label = tk.Label(
            row, text=f"[{citation.get('index', '?')}] {title}", bg=theme.BG_CHAT,
            fg=theme.FG_SYSTEM, font=("Consolas", 9), anchor="w",
        )
        label.pack(side="left", fill="x", expand=True, padx=(theme.PAD, theme.PAD_SMALL))
        relevant_btn = tk.Button(
            row, text="\U0001F44D Relevant", bg=theme.BG_INPUT, fg=theme.FG_SUCCESS,
            activebackground=theme.BG_PANEL, relief="flat", font=("Segoe UI", 8),
            command=lambda c=citation: on_mark(c, True),
        )
        relevant_btn.pack(side="left", padx=(0, theme.PAD_SMALL))
        irrelevant_btn = tk.Button(
            row, text="\U0001F44E Irrelevant", bg=theme.BG_INPUT, fg=theme.FG_WARN,
            activebackground=theme.BG_PANEL, relief="flat", font=("Segoe UI", 8),
            command=lambda c=citation: on_mark(c, False),
        )
        irrelevant_btn.pack(side="left", padx=(0, theme.PAD))

    def focus_input(self) -> None:
        self.entry.focus_set()


__all__ = ["ChatPanel"]



