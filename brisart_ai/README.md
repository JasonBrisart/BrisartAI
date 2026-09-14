# brisart_ai/ui/

The BrisartAI desktop application — pure Python/Tkinter, no third-party GUI dependency. BrisartAI is GUI-only; there is no terminal CLI/chat mode.

```text
ui/
├── app.py           The desktop window — construction, layout, event wiring
├── service.py       Backend facade every widget goes through
├── chat_panel.py    Scrollable transcript + single-line input box
├── sidebar.py       Left-hand nav: app name, core actions, status line
├── dialogs.py       Modal prompts (import, note, settings)
└── theme.py         The one shared dark color palette and font tuples
```

---

## `app.py`

`BrisartApp(tk.Tk)` is the entry point (`run()` is the only other externally-facing function; `run.py` calls it with no arguments). **Construction order matters:** `BrisartService` is built *before* `super().__init__()` creates the Tk window — specifically so a startup failure opening the SQLite index (locked by another running copy, a read-only install folder, missing permissions) propagates out of the constructor with no Tk window ever created, letting `run()` catch it in exactly one `try/except` and show a friendly `messagebox.showerror()` dialog instead of a raw console traceback.

`_answer_question()` runs the actual search on a background thread so the Tk main loop keeps repainting instead of freezing, marshaling the result back via `self.after(0, ...)`. `self._busy` ensures only one request is in flight at a time — a second question typed before the first answers is simply ignored, not queued.

---

## `service.py`

The backend facade every widget goes through instead of touching `Index`/`SessionMemory`/`ResearchSettings` directly. Construction is deliberately unguarded — no `try/except` around opening the index or session memory — so a construction failure propagates straight out to `app.py`'s single catch site.

Two cleanup passes run once at startup, as a side effect of construction: stale dictionary/definition web pages are purged, and any notes saved before note-mirroring existed are reindexed for ranked search.

`ask(text, force_web=None)`: `None` (ordinary typed questions) defers the web-search decision to the `auto_web_research` setting; the explicit "Research Web" sidebar action passes `force_web=True`. Diagnostic `print()` output from the crawler/search/policy/fetcher layers during a call is captured via `contextlib.redirect_stdout` and filtered down to just the WARN/SKIP/ERROR lines worth surfacing in the chat transcript.

---

## `chat_panel.py`, `sidebar.py`, `dialogs.py`, `theme.py`

- **`chat_panel.py`** — the scrollable, read-only transcript (`state="disabled"` outside of `append()`) plus the single-line input box. Calls `on_submit(text)` on Enter or Send-click.
- **`sidebar.py`** — app name/version header, the five core action buttons (Import Files, Add Note, Research Web, Settings, Help), and a status line showing indexed source counts.
- **`dialogs.py`** — the small modal prompts `app.py`'s sidebar actions need: a file/folder picker, a generic text prompt, a two-step title/body prompt for notes, and `SettingsDialog` (one checkbox per toggle in `core/settings.py`'s `TOGGLE_LABELS`, writing directly to the live `ResearchSettings` instance on every click).
- **`theme.py`** — the single dark palette, font tuples, and two spacing constants every widget shares. Pure constants, no Tk imports — importing it never has side effects and never requires a display, which is what makes it (along with `service.py`) headlessly testable.
