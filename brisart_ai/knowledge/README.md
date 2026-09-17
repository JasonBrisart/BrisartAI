# brisart_ai/knowledge/

The heart of BrisartAI: the SQLite index every source lands in, the ranking engine that decides what's relevant, and the synthesis step that turns ranked documents into a cited answer.

```
knowledge/
├── index.py             SQLite source + term index (sources, terms tables)
├── ingest.py             Local file/folder ingestion
├── ranker.py             Retrieval and ranking — five signals on top of a base score
├── relevance_engine.py   The Brisart Relevance Engine — the base term-scoring math
├── synthesizer.py        Turns ranked documents into a cited answer
└── vault.py              Notes, collections, entity extraction, timelines
```

## `index.py`

Two tables: `sources` (type, location, title, full text, content hash, size, extension, timestamp) and `terms` (flat term-frequency rows keyed by `(term, source_id)`, read directly by `ranker.py` for scoring). `DEFAULT_DB` is anchored to the project root so the database always lands at `<project root>/brisart_ai_index.sqlite3` regardless of the working directory the app was launched from.

`add_source()`'s `source_key` is a stable hash (via the Brisart Native Stack's `brisart_hash`) of `source_type + location`, so re-adding the same file or re-crawling the same URL always fully replaces both the `sources` row and every `terms` row for it. Raises `ValueError` for a missing type/location, but just returns `False` for empty text.

`purge_junk_web_sources()` sweeps stale dictionary/definition pages out of the index using the shared `blocklist.py` policy, run once at service startup, and only ever touches `source_type = 'web'` rows.

## `ranker.py` + `relevance_engine.py`

The base term-scoring math is the **Brisart Relevance Engine** (`relevance_engine.py`) — a fully custom, non-TF-IDF/BM25 scoring engine built specifically for this project's corpus shape (a few hundred to a few thousand local files, notes, and crawled pages, not a million-document web index). It replaces every job classic TF-IDF/BM25 used to do with a small, named, fixed-value lookup table instead of a continuous curve:

- **Rarity** (`RARITY_TIERS`) — a term's corpus-share is bucketed into four fixed tiers (common/typical/notable/distinctive), replacing log-based IDF.
- **Presence** (`PRESENCE_SCHEDULE`) — how many times a term repeats in one document earns one of four fixed point values, capped, replacing `1 + log(tf)`.
- **Shape** (`SHAPE_BRACKETS`) — a document's length relative to the corpus average is bucketed into a fixed multiplier, replacing BM25's length norm — and unlike BM25, the shortest bracket actively *boosts* rather than merely declining to penalize.
- **Proximity** — an entirely new signal with no TF-IDF/BM25 equivalent: matched query terms found physically close together in the text earn a bounded bonus.

`ranker.py` layers five more signals on top of that base score: coverage (rewards matching more distinct meaningful query terms), title match (damped for generic instructional verbs like "explain"), generic-concept-title penalty (a document titled nothing but a bare abstract concept word is demoted, applied unconditionally even without a specific detected intent), phrase match (the literal query text as a contiguous phrase earns a flat multiplier), and intent (`intent.py` supplies the "why does this mention the query's words" signal).

Every stage returns the exact signal(s) that fired, so `scripts/debug_offline_replay.py` can show precisely why a document ranked where it did.

## `synthesizer.py`

Turns ranked documents into an answer by extracting the most relevant sentences and presenting them directly, followed by a plain source list — no narration scaffolding.

A question's phrasing hints at the *kind* of sentence that answers it: `detect_intent()` (shared with `ranker.py` and `web/crawler.py`) drives three boost modes — quantity (a real number, for "how many"-style questions), comparison (comparative language, for "vs"/"outlive"-style questions), and reason (causal language like "because"/"due to", for "why"-style questions). These boosts only apply to sentences that already share at least one query term.

## `vault.py`

Structure layered on top of the raw SQLite index: research collections, local notes, lightweight capitalized-phrase entity extraction (a regex heuristic, not machine learning), source-to-entity links, a topic timeline, and a vault summary report.

Notes are mirrored into the main `sources` table (`source_type="note"`) so they get ranked by the exact same model as files and web pages. `reindex_missing_notes()` runs once at service startup to bring notes saved before this mirroring existed up to date; it's idempotent, so re-running it costs nothing on an already-current vault.

Collections, entity extraction, and the timeline view remain implemented here but are not currently exposed through the desktop UI (`ui/service.py` only calls `add_note`, `list_notes`, `reindex_missing_notes`, and `search_notes`).

## `ingest.py`

`ingest_paths()` is the thin glue between `io/readers.py`'s `iter_supported_files()`/`read_file()` and `index.py`'s `add_source()`: reads, hashes, and adds. A hash failure is logged but doesn't block indexing; a read/index failure for one file is caught and logged so a single bad file never aborts a whole folder import. Called by exactly one place: `ui/service.py`'s `BrisartService.import_paths()`.
