# data/

Persisted, per-installation runtime state — **not** source code.

```text
data/
└── research_settings.json   The three Research Sources toggles
```

Read and written by `brisart_ai/core/settings.py`'s `ResearchSettings` class. Created automatically with defaults on first run if it doesn't exist:

```json
{
  "auto_web_research": false,
  "search_local_files": true,
  "search_notes": true
}
```

Files and notes are searched locally by default; automatic web research is opt-in. If this file becomes corrupt or unreadable, `ResearchSettings.load()` silently falls back to these same defaults rather than raising — a broken settings file can never crash app startup. See [`brisart_ai/core/README.md`](../brisart_ai/core/README.md) for the full behavior.
