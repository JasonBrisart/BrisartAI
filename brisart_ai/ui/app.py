"""BrisartAI desktop application (introduced in 1.0.0-beta.1).

Pure Python / Tkinter standard library only. This is the only entry
point for BrisartAI; the terminal chat/CLI mode from earlier alpha
releases has been removed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from brisart_ai import APP_NAME, __version__
from brisart_ai.knowledge.index import DEFAULT_DB
from brisart_ai.ui import theme
from brisart_ai.ui.chat_panel import ChatPanel
from brisart_ai.ui.dialogs import SettingsDialog, ask_import_path, ask_note, ask_text
from brisart_ai.ui.service import BrisartService
from brisart_ai.ui.sidebar import Sidebar

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
        super().__init__()
        self.title(f"{APP_NAME} {__version__}")
        self.geometry("980x640")
        self.minsize(760, 480)
        self.configure(bg=theme.BG_APP)
        self.service = BrisartService(db_path)
        self._busy = False
        self._configure_style()
        self._build_layout()
        self._refresh_status()
        self.chat.append_system(
            f"{APP_NAME} {__version__} ready. Type a question below and "
            "press Enter -- I'll search the web and answer here."
        )
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- setup ------------------------------------------------------------
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

    # -- shared answer flow -----------------------------------------------
    def _answer_question(self, question: str) -> None:
        """Search the web for a question and show the answer inline.

        A short status line is shown first and the UI is flushed with
        ``update_idletasks`` so the window repaints before the (possibly
        several-second) web search runs, instead of looking frozen.
        """

        question = question.strip()
        if not question or self._busy:
            return

        self._busy = True
        self.chat.append_system(
            "Searching the public web and reading the top results..."
        )
        self.update_idletasks()

        try:
            answer = self.service.ask(question)
        except Exception as exc:  # keep the UI alive even on backend errors
            answer = f"Something went wrong answering that: {exc}"
        finally:
            self._busy = False

        self.chat.append_assistant(answer)
        self._refresh_status()

    # -- chat -------------------------------------------------------------
    def _on_chat_submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.chat.append_user(text)
        self._answer_question(text)

    # -- sidebar actions --------------------------------------------------
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
        self._answer_question(query)

    def _action_settings(self) -> None:
        SettingsDialog(self, self.service, on_change=self._refresh_status)

    def _action_help(self) -> None:
        self.chat.append_system(HELP_TEXT)

    # -- lifecycle --------------------------------------------------------
    def _on_close(self) -> None:
        self.service.close()
        self.destroy()


def run(db_path: str = DEFAULT_DB) -> None:
    app = BrisartApp(db_path)
    app.mainloop()


__all__ = ["BrisartApp", "run"]
