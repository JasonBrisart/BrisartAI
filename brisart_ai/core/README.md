# brisart_ai/core/

Answer routing, persisted user settings, and lightweight session memory. Nothing in this folder talks to the network or does any ranking math itself — it orchestrates the modules that do.

```
core/
├── conversation.py     Answer routing: the single entry point for "answer this question"
├── session_memory.py   Compact rolling log of recent chat topics
└── settings.py         Persistent research toggles (data/research_settings.json)
```

## `conversation.py`

`build_conversation_answer()` is the one function everything else in this folder exists to support. Given a question, it:

1. Cleans the input (`io/input_cleaner.py`).
2. Builds the set of allowed source types from the current settings — `web` is always included (previously-indexed pages stay searchable regardless of the Local Files toggle); `file` and `note` are added per-toggle.
3. Runs `knowledge/ranker.search()` against that scope.
4. Triggers at most one web search per question — either forced (the explicit "Research Web" action) or as a fallback when local search is empty and Automatic Web Research is on — never both stacked together.
5. Hands surviving evidence to `knowledge/synthesizer.synthesize()`.
6. Records both the question and the answer to session memory, even on the "nothing found" path.

Called by exactly one place: `ui/service.py`'s `BrisartService.ask()`.

## `session_memory.py`

A tiny SQLite-backed rolling log of recent chat topics — not full answers, just compressed keywords (tokenized and capped at 12 terms, falling back to the first 140 raw characters if tokenization finds nothing). Shares its SQLite file with `knowledge/index.py`'s `Index` but owns a separate `conversation_memory` table. Uses `check_same_thread=False` because web research runs on a background thread in `ui/app.py` while the connection is created on the main thread; the app's `_busy` flag already serializes access, so no extra locking was needed.

`recent_topics(limit=6)` returns the most-recent, de-duplicated topics newest-first.

## `settings.py`

Three persistent toggles, backed by `data/research_settings.json`:

| Setting | Default | Effect |
|---|---|---|
| `search_local_files` | on | Include imported files in local search |
| `search_notes` | on | Include saved notes in local search |
| `auto_web_research` | **off** | Search the web when local evidence comes up empty |

`load()` creates the settings file with defaults if it doesn't exist, and silently falls back to defaults on a corrupt/unreadable file rather than raising — a broken settings file can never crash startup. Only known boolean keys are accepted on load; a stale key from an older build is simply ignored rather than raising or being re-persisted.

`SETTING_ALIASES` maps short typed keys (`"web"`, `"local"`, `"notes"`) to their canonical setting name.
