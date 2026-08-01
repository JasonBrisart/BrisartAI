# BrisartAI

**Pure Python. No Dependencies. Local-First. Inspectable.**

BrisartAI is a local research assistant that transforms files, folders, notes,
and public web research into a searchable knowledge system, accessed through
a small Tkinter desktop app.

Unlike cloud-based AI systems, BrisartAI is designed to run locally, store
data locally, and remain fully inspectable. Every component is written in
standard Python and can be reviewed, modified, and audited.

---

## Philosophy

BrisartAI was built around a simple principle:

```text
Your data should remain your data.
```

The project prioritizes:

- Local-first operation
- Explainable behavior
- Source-grounded answers
- Inspectable code
- Pure Python implementation
- Zero third-party dependencies
- Optional internet access

Local information is treated as the primary source of truth. Internet access
is optional and exists only to provide additional research context when a
question needs it.

## Core Workflow

```
Files, Notes                Public Web
     │                           │
     ▼                           ▼
        BrisartAI Desktop App
                 │
                 ▼
        Local SQLite Index
                 │
                 ▼
      Ranking + Synthesis
                 │
                 ▼
      Source-Grounded Answer
```

## Features

### Knowledge Indexing

BrisartAI can ingest:

- Local files and folders
- Source code
- Notes and documentation
- Configuration files
- Saved / crawled web pages

All indexed content is stored in a local SQLite database
(`brisart_ai_index.sqlite3`).

### Ask a Question

Type a question in the desktop chat box. By default, BrisartAI performs a
fresh public web search for every question, crawls the relevant non-junk
results, and answers directly inline with cited sources -- no separate
command or toggle required. Imported files and saved notes are searched the
exact same way.

### Source-Grounded Responses

When evidence exists, BrisartAI answers using indexed sources directly,
followed by a plain source list. There is no "Confidence:" or "Observation:"
narration -- just the answer and where it came from.

### Knowledge Vault

Beyond the raw search index, BrisartAI maintains a vault layer with:

- Research collections
- Local notes
- Lightweight entity extraction
- Topic timelines
- Vault summary reports

### Quality Filtering for Web Research

Public web search results are filtered before they ever reach the index:

- Dictionary/thesaurus/definition sites are blocked outright
  (`brisart_ai/blocklist.py`)
- Off-topic Wikipedia disambiguation pages (e.g. `/wiki/Many`) are rejected
- `robots.txt` is always honored
- Local/private network destinations are always refused

## Supported File Types

### Text and Documentation
- .txt, .md, .markdown, .rst, .rtf, .log

### Data Formats
- .csv, .tsv, .json, .jsonl, .xml, .yaml, .yml, .toml, .ini, .cfg, .conf

### Source Code
- .py, .js, .ts, .jsx, .tsx, .java, .c, .cpp, .h, .cs, .go, .rs, .sh, .ps1,
  .bat, .sql

### Web Content
- .html, .htm, .css, .svg

### Office Documents (best-effort, pure-Python extraction)
- .docx, .pptx, .xlsx, .odt

### PDF (best-effort, pure-Python extraction)
- .pdf -- the objective is searchable text extraction, not perfect
  rendering.

## Quick Start

BrisartAI is GUI-only. There are no command-line subcommands.

```
python brisartai.py
```

or

```
start.bat
```

This launches the desktop window. From there:

- **Import Files** -- bring local files or a folder into the knowledge base
- **Add Note** -- save a short note into the knowledge base
- **Research Web** -- search the public web and answer a question
- **Settings** -- view/toggle research sources
- **Help** -- show in-app help text

Or just type a question directly into the chat box and press Enter.

## Project Structure

```
brisart_ai/
├── core/
│   ├── conversation.py      conversation/answer routing
│   ├── session_memory.py    lightweight recent-topic memory
│   └── settings.py          persistent research settings
├── io/
│   ├── binary_readers.py    docx/pptx/xlsx/odt/pdf best-effort extraction
│   ├── extractor.py         HTML text/link extraction, CSV conversion
│   ├── input_cleaner.py     chat input normalization
│   └── readers.py           file type dispatch + folder walking
├── knowledge/
│   ├── index.py             SQLite source + term index
│   ├── ingest.py            local file ingestion
│   ├── ranker.py            TF-IDF style retrieval + ranking
│   ├── synthesizer.py       source-grounded answer synthesis
│   └── vault.py             collections, notes, entities, timeline
├── ui/
│   ├── app.py               desktop application window
│   ├── chat_panel.py        chat transcript + input box
│   ├── dialogs.py           import/note/settings dialogs
│   ├── service.py           shared backend service layer
│   ├── sidebar.py           navigation sidebar
│   └── theme.py             visual theme constants
├── web/
│   ├── crawler.py           web search + crawl + ingest pipeline
│   ├── fetcher.py           single-URL fetch
│   ├── models.py            FetchResult dataclass
│   ├── policy.py            robots.txt + local/private host policy
│   ├── search.py            DuckDuckGo / Bing HTML search providers
│   └── stats.py             crawl run statistics
├── blocklist.py             shared web-source blocking policy
└── util.py                  tokenizing, hashing, URL normalization

data/
└── research_settings.json   persisted research toggle state

docs/
├── file_types.md
└── safety.md
```

This structure keeps subsystems isolated, inspectable, and easy to maintain.

## Limitations

BrisartAI is intentionally simple. Current limitations include:

- Not a large neural model
- Cannot know information that has not been indexed
- Retrieval quality depends on indexed content
- Office and PDF parsing are best-effort
- Internet access may be unavailable in air-gapped environments

## Documentation

Additional documentation is available in `docs/`:

```
docs/
├── file_types.md
└── safety.md
```

## Design Goals

BrisartAI aims to be:

- Local
- Transparent
- Maintainable
- Explainable
- Air-gap friendly
- Dependency free
- Easy to audit

The project favors simplicity and inspectability over complexity and hidden
behavior.

## License

See LICENSE for licensing information.

## Known Issues

BrisartAI is under active nightly development. This is a running list of
known gaps and rough edges -- not blockers to using it, but things to be
aware of before you rely on it for something important. These get worked
down over successive patches; nothing here is a surprise to the maintainer.

- **Web crawler indexes off-topic results.** The crawler currently only
  rejects pages via a blocklist (dictionary/thesaurus hosts, bare-function-
  word Wikipedia disambiguation pages). It has no positive relevance check
  at crawl time -- anything not explicitly blocked gets indexed, and
  relevance is only sorted out afterward during ranking. Expect some
  irrelevant pages to make it into the index on ambiguous queries.
- **The desktop UI freezes during web research.** There is no background
  threading yet. Asking a question that triggers a web search blocks the
  Tk main loop until search + crawl finish, with no progress indicator and
  no way to cancel. On slow networks or multiple search-provider fallbacks,
  this can take 30-90+ seconds.
- **The "Automatic Web Research" settings toggle has no effect on typed
  questions.** The desktop chat box always forces a fresh web search
  (`force_web=True`) regardless of that setting. The toggle currently only
  matters if you call the backend service directly with
  `force_web=False`.
- **No automated test coverage.** The legacy test suite was removed for
  testing pre-beta behavior that no longer applies. Ranking, synthesis, and
  crawler-rejection logic are currently verified by manual testing only.
- **No error handling around database/session startup.** If the SQLite
  index file can't be opened (locked, read-only, missing permissions),
  the app will crash with a raw traceback instead of a clean message.
- **Diagnostics only print to console.** Search-provider failures,
  robots.txt rejections, and filtered results are logged with `print()`
  and are not surfaced anywhere in the Tkinter UI itself.