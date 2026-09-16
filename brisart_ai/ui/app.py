"""
File: brisart_ai/ui/app.py

Purpose
-------
The BrisartAI desktop window -- the only entry point for the program.

Communication / relationships
------------------------------
- brisartai.py: the only caller of run().
- Constructs brisart_ai.ui.service.BrisartService, Sidebar, ChatPanel,
  dialogs.
- Imports brisart_ai.ui.theme, brisart_ai.version_info.

Settings / parameters
----------------------
- Construction order: BrisartService built BEFORE the Tk window.
- self._busy.
- force_web=None defers to Automatic Web Research setting.

Edge cases
----------
- run() wraps app construction in a single try/except.
- _answer_question() runs on a background thread; self.service.
  last_citations is read in that SAME worker right after ask() returns
  (never on the Tk main thread), then handed to _on_answer_ready() via
  self.after(0, ...) alongside the answer text -- self._busy already
  serializes calls to service.ask(), so there is no race on
  last_citations between one worker finishing and the next starting.
- Pressing a citation's Relevant/Irrelevant button calls
  _on_mark_citation(), which looks the citation up by its
  BrisartService.last_citations "index" (NOT the in-text "[N]" bracket
  number, which can repeat across a compound question's sub-answers).

Known limitations
-----------------
- Tkinter desktop shell; requires a display and cannot run headless
  (tests exercise the service layer, not this window).
- Single-window, single-session UI; there is no multi-tab or multi-user
  support.
- Long-running search/ingest work is driven through BrisartService; the
  UI thread can appear busy during large synchronous operations.

Examples
--------
    >>> # launched from the console entry point, not imported for use
    >>> run()                                     # doctest: +SKIP
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui import theme
from brisart_ai.ui.chat_panel import ChatPanel
from brisart_ai.ui.dialogs import SettingsDialog, ask_import_path, ask_note, ask_text
from brisart_ai.ui.service import BrisartService
from brisart_ai.ui.sidebar import Sidebar
from brisart_ai.version_info import APP_NAME, __version__

HELP_TEXT = """BrisartAI Help
--------------
Core actions (left sidebar):
  Import Files    bring local files or a folder into the knowledge base
  Add Note        save a short note into the knowledge base
  Research Web    search the public web and answer a question
  Settings        view/toggle research sources
  Help            show this message

Just type a question in the chat box below and press Enter.

Notes and imported files are searched the same way web results are --
ask a question and BrisartAI will pull from anything relevant it has
indexed, including your notes."""


class BrisartApp(tk.Tk):
    def __init__(self, db_path: str = DEFAULT_DB):
        service = BrisartService(db_path)

        super().__init__()
        self.service = service
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("980x640")
        self.minsize(760, 480)
        self.configure(bg=theme.BG_APP)
        self._busy = False

        self._configure_style()
        self._build_layout()
        self._refresh_status()

        self.chat.append_system(
            f"{APP_NAME} {__version__} ready. Type a question below and "
            "press Enter -- I'll search the web and answer here."
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Panel.TFrame", background=theme.BG_PANEL)
        style.configure("Sidebar.TFrame", background=theme.BG_SIDEBAR)
        style.configure("TSeparator", background=theme.BORDER)

    def _build_layout(self) -> None:
        actions = {
            "import": self._action_import, "note": self._action_note,
            "research": self._action_research, "settings": self._action_settings,
            "help": self._action_help,
        }
        self.sidebar = Sidebar(self, actions)
        self.sidebar.pack(side="left", fill="y")

        body = ttk.Frame(self, style="Panel.TFrame")
        body.pack(side="right", fill="both", expand=True, padx=theme.PAD, pady=theme.PAD)

        self.chat = ChatPanel(body, on_submit=self._on_chat_submit)
        self.chat.pack(fill="both", expand=True)
        self.chat.focus_input()

    def _refresh_status(self) -> None:
        total, files, web = self.service.counts()
        self.sidebar.set_status(total, files, web)

    def _answer_question(self, question: str, force_web: Optional[bool] = None) -> None:
        question = question.strip()
        if not question or self._busy:
            return
        self._busy = True
        searching_web = (
            force_web if force_web is not None else self.service.settings.get("auto_web_research")
        )
        if searching_web:
            self.chat.append_system("Searching the public web and reading the top results...")
        else:
            self.chat.append_system("Searching your imported files and notes...")

        def worker() -> None:
            citations: List[Dict[str, object]] = []
            try:
                answer = self.service.ask(question, force_web=force_web)
                citations = list(self.service.last_citations)
            except Exception as exc:
                answer = f"Something went wrong answering that: {exc}"
            self.after(0, self._on_answer_ready, answer, citations)

        threading.Thread(target=worker, daemon=True).start()

    def _on_answer_ready(self, answer: str, citations: Optional[List[Dict[str, object]]] = None) -> None:
        self._busy = False
        self.chat.append_assistant(answer)
        if citations:
            self.chat.render_citation_controls(citations, on_mark=self._on_mark_citation)
        for diagnostic_line in self.service.last_diagnostics:
            self.chat.append_system(diagnostic_line)
        self._refresh_status()

    def _on_mark_citation(self, citation: Dict[str, object], relevant: bool) -> None:
        self.service.mark_citation(int(citation.get("index", -1)), relevant)
        title = str(citation.get("title") or citation.get("location") or "that source")
        verdict = "relevant" if relevant else "irrelevant"
        self.chat.append_system(f"Marked \"{title}\" as {verdict}. Future searches will reflect this.")

    def _on_chat_submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.chat.append_user(text)
        self._answer_question(text)

    def _action_import(self) -> None:
        path = ask_import_path(self)
        if not path:
            return
        result = self.service.import_paths([path])
        self.chat.append_system(result)
        self._refresh_status()

    def _action_note(self) -> None:
        title, body = ask_note(self)
        if not body:
            return
        result = self.service.add_note(title, body)
        self.chat.append_system(result)
        self._refresh_status()

    def _action_research(self) -> None:
        query = ask_text(self, "Research the Web", "What do you want to know?")
        if not query:
            return
        self.chat.append_user(query)
        self._answer_question(query, force_web=True)

    def _action_settings(self) -> None:
        SettingsDialog(self, self.service, on_change=self._refresh_status)

    def _action_help(self) -> None:
        self.chat.append_system(HELP_TEXT)

    def _on_close(self) -> None:
        self.service.close()
        self.destroy()


def _show_startup_error(exc: Exception) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        f"{APP_NAME} could not start",
        "BrisartAI could not open its local database.\n\n"
        f"Details: {exc}\n\n"
        "This usually means the index file is locked by another running "
        "copy of BrisartAI, the folder is read-only, or file permissions "
        "are blocking access. Close any other running copies of "
        "BrisartAI, confirm you have write access to the install folder, "
        "and try again.",
    )
    root.destroy()


def run(db_path: str = DEFAULT_DB) -> None:
    try:
        app = BrisartApp(db_path)
    except Exception as exc:
        _show_startup_error(exc)
        return
    app.mainloop()


__all__ = ["BrisartApp", "run"]



