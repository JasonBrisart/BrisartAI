"""
File: brisart_ai/ui/app.py

Purpose
-------
The BrisartAI desktop window -- the only entry point for the program
(pure Python/Tkinter, no third-party GUI deps). brisartai.py calls
run(), the sole external-facing function here besides BrisartApp
itself.

Communication / relationships
------------------------------
- brisartai.py: the only caller of run().
- Constructs brisart_ai.ui.service.BrisartService,
  brisart_ai.ui.sidebar.Sidebar, brisart_ai.ui.chat_panel.ChatPanel, and
  brisart_ai.ui.dialogs.{SettingsDialog,ask_import_path,ask_note,
  ask_text}.
- Imports brisart_ai.ui.theme for palette/spacing and
  brisart_ai.version_info.{APP_NAME,__version__} for the window title
  and startup banner.

Settings / parameters
----------------------
- Construction order in BrisartApp.__init__ matters: BrisartService is
  built BEFORE the Tk window (super().__init__()), specifically so a
  startup failure opening the SQLite index propagates out of the
  constructor with NO Tk window ever created.
- self._busy: only one request is in flight at a time; a second
  question typed before the first answers is simply ignored rather than
  queued.
- force_web=None (ordinary typed questions) defers to the Automatic Web
  Research setting; the "Research Web" sidebar action passes
  force_web=True to force a fresh search.

Edge cases
----------
- run() wraps app construction in a single try/except and hands any
  failure to _show_startup_error(), which spins up a throwaway hidden
  tk.Tk() purely to host a proper error dialog -- the alternative, a
  half-built invisible window plus a console traceback, is what this
  replaced.
- _answer_question() runs the actual search on a background thread
  (threading.Thread(..., daemon=True)) so the Tk main loop keeps
  repainting instead of freezing, marshaling the result back to the main
  thread via self.after(0, ...).
- _on_answer_ready() catches any exception raised inside the worker and
  turns it into a plain "Something went wrong answering that: ..."
  message rather than letting the background thread's exception be
  silently swallowed or crash the app.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

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
        # Service built BEFORE the Tk window exists (see module docstring).
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
            "import": self._action_import,
            "note": self._action_note,
            "research": self._action_research,
            "settings": self._action_settings,
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

    def _answer_question(
        self,
        question: str,
        force_web: Optional[bool] = None,
    ) -> None:
        """Answer a question on a background thread, then show it inline."""
        question = question.strip()
        if not question or self._busy:
            return

        self._busy = True
        searching_web = (
            force_web
            if force_web is not None
            else self.service.settings.get("auto_web_research")
        )
        if searching_web:
            self.chat.append_system(
                "Searching the public web and reading the top results..."
            )
        else:
            self.chat.append_system("Searching your imported files and notes...")

        def worker() -> None:
            try:
                answer = self.service.ask(question, force_web=force_web)
            except Exception as exc:  # keep the UI alive even on backend errors
                answer = f"Something went wrong answering that: {exc}"
            self.after(0, self._on_answer_ready, answer)

        threading.Thread(target=worker, daemon=True).start()

    def _on_answer_ready(self, answer: str) -> None:
        self._busy = False
        self.chat.append_assistant(answer)
        for diagnostic_line in self.service.last_diagnostics:
            self.chat.append_system(diagnostic_line)
        self._refresh_status()

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
    """Friendly dialog for a startup failure, via a throwaway hidden Tk root."""
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
