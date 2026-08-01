# BrisartAI

**Pure Python. Zero Dependencies. Local-First. Inspectable.**

BrisartAI is a local research assistant that transforms files, folders, notes, and optional public web research into a searchable knowledge system through a lightweight Tkinter desktop application.

Every component is written with the Python standard library. BrisartAI stores its data locally, keeps retrieval behavior inspectable, and does not depend on a hidden model or third-party package ecosystem.

---

## Philosophy

BrisartAI is built around a simple principle:

> Your data should remain your data.

The project prioritizes:

- Local-first operation
- Source-grounded answers
- Explainable retrieval
- Inspectable code
- Pure Python implementation
- Zero third-party dependencies
- Optional internet access
- Air-gap friendly operation

Local information is treated as the primary source of truth. Public web access is optional and exists only to provide additional research context when needed.

---

## What BrisartAI Is

BrisartAI is not a large neural language model.

It is a local information retrieval and extractive answer system:

    Files, Notes, and Web Pages
                  |
                  v
          Local SQLite Index
                  |
                  v
       Term and Intent Ranking
                  |
                  v
        Source-Grounded Answer

When relevant evidence exists, BrisartAI retrieves source text, ranks the available evidence, selects useful passages, and presents an answer with citations.

It does not generate unsupported facts from a hidden model.

---

## Core Features

### Local Knowledge Indexing

BrisartAI can ingest:

- Local files
- Folders
- Source code
- Notes
- Documentation
- Configuration files
- Saved web pages
- Crawled public web pages

Indexed content is stored in a local SQLite database:

`brisart_ai_index.sqlite3`

### Public Web Research

When public web research is enabled, BrisartAI can:

- Search public web providers
- Detect provider challenge and rate-limit pages
- Reject provider batches that appear unrelated to the query
- Crawl permitted result pages
- Extract usable text
- Reject known junk sources
- Index retrieved evidence
- Rank the results
- Produce a cited answer

The current search provider sequence includes:

- DuckDuckGo HTML
- DuckDuckGo Lite
- Bing HTML
- Wikipedia API fallback

### Source-Grounded Answers

BrisartAI answers from indexed evidence and includes a plain source list.

Responses are intentionally direct:

    Answer text

    Sources:
    [1] Source title
    [2] Source title

There is no personality wrapper, confidence narration, or hidden reasoning scaffold.

### Intent-Aware Ranking

BrisartAI evaluates both:

- Whether a source matches the query terms
- Whether the source matches the reason behind the question

The shared intent layer currently recognizes:

- Founder and company questions
- Inventor and device questions
- Statistics and population questions
- Explanation and mechanism questions
- General questions

For example, the question:

`who invented microsoft?`

is treated as a founder or company-history question. Founder pages and company-history sources are favored over Microsoft product manuals, account pages, or generic invention articles.

The question:

`who invented the transistor?`

is treated as an inventor or device-history question. Invention history, Bell Labs, and inventor-related sources are favored over unrelated pages that merely contain the word `invented`.

The question:

`how many cats are in america?`

is treated as a statistics question. Sources containing counts, estimates, populations, percentages, and demographic figures are favored over generic cat pages.

The question:

`why do cats purr?`

is treated as an explanation question. Sources describing causes, mechanisms, processes, and reasons are favored over generic descriptive pages.

The intent system is shared by web retrieval and offline document retrieval through:

`brisart_ai/intent.py`

Intent is a ranking hint, not a hard filter. A source is not excluded solely because it lacks an expected intent term.

### Offline Document Retrieval

Imported files, saved notes, and previously indexed content use the same retrieval principles as public web sources.

Offline retrieval includes:

- TF-IDF-style term scoring
- Stopword down-weighting
- Meaningful-term coverage scoring
- Intent-aware score adjustment
- Source-grounded answer synthesis

This keeps offline retrieval and public web retrieval aligned.

### Knowledge Vault

BrisartAI includes a local vault layer supporting:

- Research notes
- Research collections
- Lightweight entity extraction
- Topic timelines
- Vault summary reports

Some vault functions remain available in source but are not fully exposed through the current desktop interface.

### Search Diagnostics

Search and crawler diagnostics are shown in the desktop transcript.

Diagnostics may include:

- Provider failures
- Challenge or rate-limit detection
- Rejected provider batches
- Robots.txt decisions
- Blocked sources
- Duplicate-content skips
- Fetch failures

### Debug and Replay Tools

BrisartAI includes inspectable replay tools:

- `scripts/debug_search_replay.py`
- `scripts/debug_offline_replay.py`

The web replay tool can display:

- Original query
- Natural query form
- Keyword fallback form
- Detected intent
- Topic terms
- Provider activity
- Accepted URLs
- Intent boosts
- Intent penalties
- Final ranking

The offline replay tool validates ranking behavior against controlled document fixtures through the real SQLite retrieval path.

---

## Supported File Types

### Text and Documentation

- `.txt`
- `.md`
- `.markdown`
- `.rst`
- `.rtf`
- `.log`

### Data Formats

- `.csv`
- `.tsv`
- `.json`
- `.jsonl`
- `.xml`
- `.yaml`
- `.yml`
- `.toml`
- `.ini`
- `.cfg`
- `.conf`

### Source Code

- `.py`
- `.js`
- `.ts`
- `.jsx`
- `.tsx`
- `.java`
- `.c`
- `.cpp`
- `.h`
- `.cs`
- `.go`
- `.rs`
- `.sh`
- `.ps1`
- `.bat`
- `.sql`

### Web Content

- `.html`
- `.htm`
- `.css`
- `.svg`

### Office Documents

Best-effort pure-Python extraction is available for:

- `.docx`
- `.pptx`
- `.xlsx`
- `.odt`

### PDF

Best-effort pure-Python text extraction is available for:

- `.pdf`

The PDF reader aims to recover searchable text. It is not intended to reproduce page layout or visual formatting.

---

## Quick Start

BrisartAI is GUI-only.

Run:

    python brisartai.py

On Windows, you can also run:

    start.bat

The desktop application provides actions for:

- Importing files and folders
- Adding notes
- Asking questions
- Running public web research
- Changing research settings
- Viewing help

You can also type a question directly into the chat box and press Enter.

---

## Project Structure

    brisart_ai/
    ├── core/
    │   ├── conversation.py      Answer routing
    │   ├── session_memory.py    Lightweight recent-topic memory
    │   └── settings.py          Persistent research settings
    ├── io/
    │   ├── binary_readers.py    Office and PDF text extraction
    │   ├── extractor.py         HTML extraction and CSV conversion
    │   ├── input_cleaner.py     Input normalization
    │   └── readers.py           File dispatch and folder walking
    ├── knowledge/
    │   ├── index.py             SQLite source and term index
    │   ├── ingest.py            Local file ingestion
    │   ├── ranker.py            TF-IDF-style and intent-aware ranking
    │   ├── synthesizer.py       Source-grounded answer synthesis
    │   └── vault.py             Notes, collections, entities, timelines
    ├── ui/
    │   ├── app.py               Desktop application
    │   ├── chat_panel.py        Transcript and input box
    │   ├── dialogs.py           Import, note, and settings dialogs
    │   ├── service.py           Shared backend service
    │   ├── sidebar.py           Navigation sidebar
    │   └── theme.py             Visual theme constants
    ├── web/
    │   ├── crawler.py           Search, crawl, rank, and ingest pipeline
    │   ├── fetcher.py           Single-URL retrieval
    │   ├── models.py            FetchResult data model
    │   ├── policy.py            Robots.txt and private-host policy
    │   ├── search.py            Public search providers
    │   └── stats.py             Crawl statistics
    ├── blocklist.py             Shared source-blocking policy
    ├── intent.py                Query-intent detection and scoring
    └── util.py                  Tokens, hashes, paths, and URLs

    data/
    └── research_settings.json   Persisted research settings

    docs/
    ├── file_types.md
    └── safety.md

    scripts/
    ├── debug_offline_replay.py  Offline retrieval fixtures
    └── debug_search_replay.py   Live provider replay and diagnostics

---

## Pure Python Design

BrisartAI uses only the Python standard library.

Major components use:

- `tkinter` for the desktop interface
- `sqlite3` for local storage
- `urllib` for HTTP requests
- `html.parser` for HTML parsing
- `zipfile` and `xml.etree.ElementTree` for Office and ODT extraction
- `re` and `zlib` for best-effort PDF extraction
- `math` and standard Python collections for retrieval ranking
- `threading` for responsive web research in the desktop application

BrisartAI does not require:

- `requests`
- `beautifulsoup4`
- `numpy`
- `pandas`
- `scikit-learn`
- `python-docx`
- `openpyxl`
- `PyPDF2`
- An embeddings framework
- A vector database
- A language-model runtime

No dependency installation step is required.

---

## Current Limitations

BrisartAI is intentionally narrow and inspectable.

Current limitations include:

- BrisartAI is not a neural language model.
- BrisartAI cannot know information that has not been indexed or retrieved.
- Answer quality depends on source quality.
- Ranking cannot recover a useful page that a search provider never returned.
- Public web search depends on provider availability and HTML behavior.
- Web ranking still relies heavily on URL-derived text.
- Page titles and search-result snippets are not fully incorporated into final web ranking.
- Founder classification uses a finite list of known company terms.
- Office and PDF extraction is best-effort.
- Scanned image-only documents require OCR, which BrisartAI does not currently provide.
- Internet research is unavailable in fully air-gapped environments.
- Database startup failures are not yet presented through a friendly error dialog.
- There is no formal automated unit-test suite yet.

---

## Known Issues

### Individual off-topic pages can still enter the index

BrisartAI blocks known junk sources and rejects provider batches that appear unrelated to the query.

It does not yet perform a full positive relevance validation on every individual page before indexing. Fine-grained relevance is primarily handled during ranking.

### Web ranking remains URL-heavy

Intent-aware web scoring primarily evaluates URL-derived text.

A strongly named URL may occasionally outrank a better page whose title or snippet contains stronger evidence.

### Provider recall limits retrieval

BrisartAI can improve the order of retrieved sources, but it cannot rank a source that was never returned by a provider.

### Company classification is finite

Questions about known companies can be treated as founder questions. Unlisted companies may fall back to inventor-style classification.

### Replay checks are not a formal test suite

The replay scripts provide repeatable validation for web and offline ranking, but the repository does not currently include a dedicated unit-test framework or automated CI suite.

### Database startup errors remain raw

If the SQLite index or session database cannot be opened because of locking, permissions, or a read-only path, BrisartAI may display a raw traceback.

---

## Recent Improvements

### 1.0.0-beta.4

- Added shared intent-aware ranking for web and offline retrieval
- Added founder, inventor, statistic, explanation, and general intent classes
- Added `brisart_ai/intent.py`
- Added offline ranking replay fixtures
- Added intent reasoning to the web replay tool
- Fixed underscore-separated Wikipedia article scoring
- Fixed percent-encoded URL handling during intent scoring
- Preserved the provider-batch sanity guard from beta.3
- Improved measured relevance for founder, inventor, and statistics queries

### 1.0.0-beta.3

- Moved web research onto a background thread
- Fixed desktop freezing during long web research operations
- Fixed the Automatic Web Research setting for typed questions
- Surfaced search and crawler diagnostics in the desktop transcript
- Added distinct status messages for web and offline retrieval

For the complete release history, see `CHANGELOG.md`.

---

## Documentation

Additional documentation is available in:

- `docs/file_types.md`
- `docs/safety.md`

---

## Design Goals

BrisartAI aims to remain:

- Local
- Transparent
- Maintainable
- Explainable
- Air-gap friendly
- Dependency free
- Easy to audit

The project favors clarity and inspectability over hidden complexity.

---

## License

See `LICENSE` for licensing information.
