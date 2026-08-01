# Changelog

## 1.0.0-beta.2

Removed:
- `knowledge/project_memory.py`, `knowledge/relationship_graph.py`, and
  `knowledge/memory_report.py` -- persistent project memory and relationship
  graph tracking added in beta.1 have been stripped out.
- `knowledge/analyzer.py`, `knowledge/project_awareness.py`, and
  `knowledge/source_attribution.py` -- project analysis and source
  attribution reporting removed along with the memory/relationship layer
  they supported.
- `core/cli.py`, `core/chat.py`, `core/commands.py`, `core/assistant.py` --
  the entire terminal CLI/chat stack has been fully removed. BrisartAI is
  now GUI-only; `brisartai.py` takes no arguments and always launches the
  desktop app.
- `core/conversation_memory.py`, `core/intent_detector.py`,
  `core/response_builder.py`, `core/state_manager.py` -- supporting modules
  for the removed CLI/chat stack.
- The personality/freeform/self-knowledge conversational layer
  (`personality.py`, `freeform.py`, `self_knowledge.py`) -- the
  Observation/Confidence/Why-I-think-this narration voice these modules
  produced is gone; `knowledge/synthesizer.py` now returns the extracted
  answer and a plain source list directly.
- `data/project_memory.json`, `data/relationship_graph.json` storage files
  (no longer written).
- `--gui` / `--cli` startup flags (there is only one mode now).
- All `/vault`, `/collection`, `/timeline`, `/crawl`, `/scan-preview` chat
  slash-commands and the `settings show` / `settings toggle KEY` CLI
  subcommands, since the terminal interface that hosted them is gone.
  The underlying `knowledge/vault.py` functions (`add_note`, `list_notes`,
  `search_notes`, collections, entity extraction, timeline) still exist
  in source and are available to call directly, but are not currently
  wired into the desktop UI.
- The legacy `tests/` folder. It was already noted as removed in beta.1's
  Fixed section for being tied to the pre-beta answer format; the folder
  itself has now been deleted rather than left in place.

Fixed:
- `README.md` no longer describes the `intelligence/`, `scanning/`, and
  `recommendations/` packages, which never existed in this repository's
  actual source tree, or reference `docs/architecture.md`,
  `docs/commands.md`, `docs/drive_scanning.md`, `docs/personality.md`,
  none of which exist. Only `docs/file_types.md` and `docs/safety.md` are
  real.
- `README.md` Quick Start section no longer documents the removed
  `status` / `ingest` / `analyze` / `recommend` / `ask` CLI subcommands.
  `brisartai.py` has no CLI surface -- it launches the GUI unconditionally.
- Full audit of every `from brisart_ai...import` across all remaining
  Python files confirmed zero dead imports and zero references to deleted
  modules; the only stale references found were in documentation
  (README.md, CHANGELOG.md) and orphaned `__pycache__` bytecode for the
  modules removed above.

Note: the beta.1 entry below is left as written for historical accuracy
(it describes what beta.1 actually shipped with at the time), but a large
share of those features were removed in later stripping sessions before a
1.0.0-beta.2 tag was ever cut. This entry documents that removal so the
changelog stays truthful about what currently exists in source.

Current Subsystem Layout (post-beta.2):
```
core/
├── conversation.py
├── session_memory.py
└── settings.py

knowledge/
├── index.py
├── ingest.py
├── ranker.py
├── synthesizer.py
└── vault.py

ui/
├── app.py
├── chat_panel.py
├── dialogs.py
├── service.py
├── sidebar.py
└── theme.py

web/
├── crawler.py
├── fetcher.py
├── models.py
├── policy.py
├── search.py
└── stats.py
```

## 1.0.0-beta.1

Added:
- Persistent project memory that stores discovered facts across restarts (`knowledge/project_memory.py`)
- Persistent relationship graph that survives restarts by serializing to JSON (`knowledge/relationship_graph.py`)
- Automatic fact extraction during ingestion (medium-length lines captured as candidate facts)
- Automatic Python import linking during ingestion to build the relationship graph
- Memory + relationship reporting module for a human-readable view of learned knowledge (`knowledge/memory_report.py`)
- `count()` and `categories()` helpers on `ProjectMemory`
- `data/project_memory.json` and `data/relationship_graph.json` storage files
- Persistent research settings module (`core/settings.py`) backed by `data/research_settings.json`, tracking `search_local_files`, `search_notes`, `search_collections`, and `auto_web_research`
- Automatic Web Research: when enabled, `conversation.py` searches the public web and re-checks for evidence if local search returns nothing, before falling back to a freeform response
- `settings` / `/settings` command in chat mode to view the current research settings panel
- `settings web|local|notes|collections` in chat mode to toggle an individual setting by short key
- `settings show` / `settings toggle KEY` subcommands in the non-interactive CLI (`cli.py`)
- `research` command and CLI subcommand as a beginner-facing alias of `web` (`cmd_research` in `commands.py`)
- Simplified core command set in chat mode (`import`, `note`, `research`, `settings`, `help`), with all existing advanced commands (`/vault`, `/collection`, `/timeline`, `/crawl`, `/scan-preview`, etc.) preserved and moved behind `/help`
- Desktop GUI (`brisart_ai/ui/`) built with Tkinter (standard library only)
- `ui/app.py` desktop application window
- `ui/sidebar.py` navigation sidebar with core actions
- `ui/chat_panel.py` scrollable chat interface
- `ui/dialogs.py` modal dialogs for import, notes, research, and settings
- `ui/service.py` shared backend service layer for GUI integration
- `ui/theme.py` centralized application theme and styling system
- `--gui` and `--cli` startup modes
- Automatic fallback from GUI mode to terminal chat when graphical startup is unavailable
- Query intent hints: count/measure questions append a keyword to steer results toward the right kind of answer ("how many" -> `number`, "how much" -> `amount`, "how old" -> `age`, "how tall" -> `height`, "how long" -> `length duration`, "how far" -> `distance`, "population of" -> `population`) (`web/crawler.py`)
- Number-aware answer synthesis: when a question asks for a quantity ("how many", "how much", "population", "percent", etc.), sentences that contain an actual numeric quantity are strongly boosted and lead the answer, so a real figure like "about 73.8 million cats" is surfaced ahead of generic topic sentences (`knowledge/synthesizer.py`)
- Dictionary/definition host blocking at ingest time so pages from sites like Merriam-Webster, Cambridge, Wiktionary, and Thesaurus.com never enter the index, regardless of what the search layer returns (`web/crawler.py`)
- Off-topic Wikipedia rejection: a Wikipedia page whose title is a bare function word (e.g. `/wiki/Many`) is refused, since it is about the word rather than the topic (`web/crawler.py`)
- Startup index cleanup: stale dictionary and off-topic disambiguation web rows left over from earlier runs are purged automatically when the app starts, so old junk cannot resurface in answers (`knowledge/index.py`, `ui/service.py`)
- Bing HTML search provider added alongside the DuckDuckGo providers, with automatic fallback between providers when one is blocked or rate-limited (`web/search.py`)

Changed:
- `brisartai.py` now launches the desktop interface by default when started without arguments
- BrisartAI transitioned from a terminal-first workflow to a GUI-first workflow
- Public web search in `web/search.py` rewritten to use `html.parser.HTMLParser` instead of regex-based link extraction
- Public web search now attempts multiple DuckDuckGo HTML endpoints (HTML and Lite) before failing, then falls back to Bing HTML
- Result-link extraction now captures only organic result anchors (DuckDuckGo `result__a` / `result-link` classes and Bing `<h2>` / `<h3>` result titles) instead of every anchor on the page, so navigation, ads, and dictionary widgets are ignored (`web/search.py`)
- DuckDuckGo and Bing redirect wrappers are now unwrapped to the real destination URL, and stray tracking parameters (`utm_*`, `fbclid`, etc.) are removed (`web/search.py`)
- Added explicit diagnostics for failed search requests, failed parsing attempts, and blocked search providers
- Web search behavior is now transparent when providers return anomaly-detection or rate-limit pages
- Improved resilience against future search-provider HTML layout changes by replacing brittle pattern matching with structured HTML parsing
- The web search query is cleaned before it is sent to a search engine: filler/question words are stripped so a natural question searches for its topic terms, and search engines stop returning dictionary "definition cards" for common words in the question (`web/crawler.py`)
- Retrieval ranking now down-weights ultra-common stop/function words (e.g. "many", "how", "the") and adds a coverage multiplier that rewards documents matching more of the distinct meaningful query terms, so topic pages rank above pages that merely repeat a common word (`knowledge/ranker.py`)
- The desktop GUI performs a fresh public web search for every typed question and shows the answer inline, without requiring the Automatic Web Research toggle or a separate command; the "Research Web" sidebar action likewise returns an answer instead of only an index count (`ui/service.py`, `ui/app.py`, `core/conversation.py`)
- The knowledge index database is now anchored to the project root (next to `brisartai.py`) instead of a bare relative filename, so it is always created in the same, easy-to-find place regardless of the launch directory (`knowledge/index.py`)
- `ingest.py` now feeds long-term project memory and the relationship graph during ingestion, persisting knowledge accumulated per run
- `relationship_graph.py` refactored from in-memory-only into a persisted knowledge graph with `save()` / `load()`
- `build_conversation_answer()` in `conversation.py` now accepts a `settings` parameter and routes through Automatic Web Research when local evidence is absent
- `build_answer()` in `commands.py` now loads `ResearchSettings()` automatically, so typed questions get Automatic Web Research behavior without extra flags
- `chat.py` help text reorganized into "Core commands" (five items) and "Advanced commands" (everything else), rather than one flat list
- `assistant.py` compatibility shim updated to re-export `cmd_research`, `cmd_settings_show`, and `cmd_settings_toggle`
- `freeform.py` and `self_knowledge.py` now route all single-fact statements (observations, limits, suggested actions) through `personality.py` (`observation()`, `limitation()`, `next_step()`) instead of hardcoding their own labels, matching the voice already used in `analyzer.py` and `recommender.py`

Fixed:
- Web search no longer returns dictionary/definition results for factual questions. Filler and question words are stripped from a query before it is sent to a search engine, so "how many cats are in america" searches for `cats america number` instead of triggering a dictionary "definition card" for the word "many" (`web/crawler.py`)
- Synthesized answers no longer include narration scaffolding ("Observation:", "Confidence:", "Why I think this:", "Suggested next move:"); answers now present the extracted information followed by a plain source list (`knowledge/synthesizer.py`)
- Public web search could silently fail even when valid search pages were returned, due to broken link extraction logic in `web/search.py`
- Fixed destination URL extraction so crawler ingestion receives usable target URLs
- Fixed cases where web research returned no results despite successful provider responses
- Added automatic fallback from `html.duckduckgo.com/html/` to `lite.duckduckgo.com/lite/`
- Added detection of DuckDuckGo anomaly / rate-limit pages so blocked searches are properly reported
- Resolved cases where public web research appeared to succeed but produced zero indexed pages
- `robots.txt` retrieval failures (missing, unreachable, or malformed) are treated as "allowed" instead of a site-wide block, so fetchable pages are no longer skipped by mistake (`web/policy.py`)
- Corrected the `categories()` helper in `project_memory.py` that was malformed during earlier drafting
- Removed the "Recent Topics:" / "Recent context:" raw session-memory dumps from `freeform.py` and `self_knowledge.py`. These previously surfaced compressed, tokenized, and truncated internal memory strings (e.g. fragments like "thi", "don imported evidence available yet said thi still converse normally") directly to the user; recent topics are no longer displayed as part of any response
- Removed the unused `section()` helper from `personality.py` after confirming it was not imported or called anywhere in the codebase
- Removed the legacy test suite (`tests/`). Several tests were tied to pre-beta behavior (including the old Observation/Confidence/Why I think this answer format) and no longer reflected the current architecture. Validation is now performed against the active application workflow and current feature set.

Knowledge Subsystem Layout:
```
knowledge/
├── analyzer.py
├── index.py
├── ingest.py
├── project_awareness.py
├── project_memory.py
├── relationship_graph.py
├── source_attribution.py
├── synthesizer.py
├── memory_report.py
├── ranker.py
└── vault.py
```

Core Subsystem Layout:
```
core/
├── assistant.py
├── chat.py
├── cli.py
├── commands.py
├── conversation.py
├── conversation_memory.py
├── intent_detector.py
├── response_builder.py
├── session_memory.py
├── settings.py
└── state_manager.py
```

UI Subsystem Layout:
```
ui/
├── app.py
├── chat_panel.py
├── dialogs.py
├── service.py
├── sidebar.py
└── theme.py
```

## 0.9.0-alpha

Added:
- Crawl statistics reporting for web ingestion operations
- Duplicate-content detection before indexing crawled pages
- Localhost protection to prevent accidental crawling of local machine resources

Changed:
- Refactored the web subsystem into focused modules
- Moved `FetchResult` into `web/models.py`
- Moved crawl statistics into `web/stats.py`
- Moved URL retrieval and extraction into `web/fetcher.py`
- Moved public web search functionality into `web/search.py`
- Consolidated crawling, indexing, and ingestion logic into `web/crawler.py`
- Improved maintainability and auditability through a modular web architecture

Web Subsystem Layout:
```
web/
├── policy.py
├── models.py
├── stats.py
├── fetcher.py
├── search.py
├── crawler.py
```

## 0.8.0-alpha

Added:
- Split the command-line interface into focused modules: commands.py (command handlers), chat.py (interactive shell), and cli.py (argument parser and entry point)
- _clean_sentence() helper in synthesizer.py for readable answer formatting

Changed:
- assistant.py is now a compatibility shim that re-exports the public API, so existing imports such as `from brisart_ai.core.assistant import cmd_chat, main` keep working
- Answer output is now spaced into readable blocks instead of a single wall of text

Fixed:
- Citation numbering is now sequential with no gaps (previously skipped numbers when duplicate passages were removed)
- Removed the noisy tokenized "Context I still have in view" line from answers
- Import and use `__version__` from the brisart_ai package instead of hardcoding the version string. This ensures the USER_AGENT always reflects the actual package version.

## 0.7.0-alpha

Added:
- Knowledge Vault layer built on the existing SQLite index
- Research collections for grouping indexed sources
- Local research notes with search
- Lightweight entity extraction and source-to-entity links
- Timeline view around a topic or term
- Vault report and project/research awareness reports

Fixed:
- Corrected a syntax error in io/readers.py that prevented startup
- Aligned package version number with the actual release

## 0.6.0-alpha

Fixed:
- Running `py brisartai.py` now starts interactive chat instead of showing help.
- Chat mode now accepts normal human input without requiring `py brisartai.py ask`.
- If the user accidentally types `py brisartai.py ask "hello"` inside chat, BrisartAI now cleans it to `hello`.
- Session memory now stores compact topics instead of huge command strings/full assistant outputs.
- Self-knowledge questions like "what do you do" now use a dedicated self-knowledge module instead of saying no indexed files exist.
- Basic command typos such as `statys`, `stats`, `analyse`, and `char` are corrected.

Added:
- `self_knowledge.py`
- `conversation.py`
- `input_cleaner.py`
- `start.bat`

## 0.5.0-alpha

Added:
- Free-form response mode for any typed input
- Clear distinction between indexed-file answers and general fallback responses
- Much wider file type support
- Pure-Python best-effort readers for `.docx`, `.pptx`, `.xlsx`, `.odt`, and `.pdf`
- Expanded scanner policy for more source/data/code/document formats
- General assistant fallback that explains limits instead of going silent

## 0.4.0-alpha

Added:
- Assistant voice/personality layer
- Logical observations in answers
- Evidence explanations with "Why I think this"
- Confidence labels based on retrieval strength
- Suggested next moves
- Local session memory for recent chat context
- More natural analysis and recommendation output

## 0.3.0-alpha

Added:
- Conservative drive/folder scanning
- Scan preview mode
- Hard limits for max files and max file size
- System/cache/dependency folder exclusions
- Recommendation engine based on indexed data
- Duplicate content detection by hash
- Project hygiene recommendations based on indexed filenames

## 0.2.0-alpha

Shifted BrisartAI from crawler-first to data-first architecture.

## 0.1.0-alpha

Initial crawler/index/retrieval prototype.
