# BrisartAI Architecture

A macro-to-micro map of BrisartAI: what each layer is responsible for, how a question flows through the system end to end, and where to look when you need to change something.

BrisartAI is **pure Python, standard-library only, local-first, GUI-only**. It is a retrieval-and-extraction system, not a neural model: it finds indexed evidence, ranks it, and quotes it back with citations. It never invents facts.

## 1. The one-sentence model

> Files, notes, and (optionally) crawled web pages are indexed into a local SQLite store, ranked by the Brisart Relevance Engine plus an intent-aware signal stack, and the best passages are quoted back with sources.

```
Files / Notes / Web pages
        |
        v
Local SQLite index              (knowledge/index.py)
        |
        v
Brisart Relevance Engine         (knowledge/relevance_engine.py)
  + signal stack                 (knowledge/ranker.py, intent.py)
        |
        v
Source-grounded synthesis        (knowledge/synthesizer.py)
        |
        v
Cited answer in the GUI          (ui/)
```

## 2. Layer responsibilities

| Layer | Package | Owns | Must NOT |
|---|---|---|---|
| Entry | `brisartai.py` | Launch the desktop app | Contain logic |
| UI | `brisart_ai/ui/` | Tkinter window, transcript, dialogs, sidebar, background threading | Storage, ranking, or validation logic |
| Service facade | `brisart_ai/ui/service.py` | The single backend entry point every widget calls | Direct Tk calls |
| Orchestration | `brisart_ai/core/` | Answer routing, settings, session memory | Parsing HTML, scoring documents |
| Knowledge | `brisart_ai/knowledge/` | SQLite index, ingestion, ranking, synthesis, vault | Networking, Tk |
| IO | `brisart_ai/io/` | Read local files into searchable text | Ranking, networking |
| Web | `brisart_ai/web/` | Search providers, fetch, robots policy, crawl into the index | Tk, storage schema |
| Native | `brisart_ai/native/` | From-spec stdlib-equivalent primitives (hash, URL, JSON, HTML, robots, DEFLATE) | Anything BrisartAI-specific — this layer knows nothing about sources, ranking, or the UI |
| Shared | `brisart_ai/{util,intent,blocklist}.py` | Tokens/hashes/URLs, query-intent, junk-host policy | Depend on any single feature layer |

**Dependency rule:** dependencies point inward and downward. `web/` and `knowledge/` may import the shared layer; the shared layer imports nothing from `web/`, `knowledge/`, `ui/`, or `core/`. `native/` sits lowest of all — a dependency of `util.py`, `web/`, `io/`, and `core/settings.py`, but depends on nothing else in the project. This is why `blocklist.py` lives at the top level rather than inside `web/`: `knowledge/index.py` can purge junk web rows without the knowledge layer taking a dependency on the web layer.

## 3. Request flow

A typed question travels this exact path:

1. **`ui/app.py`** — captures the text, spawns a daemon thread so the Tk loop never freezes, and calls the service.
2. **`ui/service.py` → `BrisartService.ask()`** — captures diagnostic `print()` output, resolves the "should I search the web?" decision from settings, and delegates.
3. **`core/conversation.py` → `build_conversation_answer()`** — cleans the input (`io/input_cleaner.py`), builds the allowed `source_types` set from settings, runs local ranked search, optionally triggers one web search, and hands surviving evidence to synthesis.
4. **`knowledge/ranker.py` → `search()`** — the ranking core (§4).
5. **`knowledge/synthesizer.py` → `synthesize()`** — selects the most relevant sentences (intent-aware) and formats the cited answer.
6. Back up through the service (which appends diagnostics) to the transcript.

A web question additionally passes through `web/crawler.py` (`web_search_and_ingest`) → `web/search.py` (7-provider chain) → `web/fetcher.py` → `io/extractor.py`, with every candidate URL scored and filtered before it is ever indexed.

## 4. The ranking core

`knowledge/ranker.py::search()` layers signals on top of a base score computed by the **Brisart Relevance Engine** (`knowledge/relevance_engine.py`), and every stage returns *why* it fired so the replay scripts can explain a result:

1. **Base term score.** For each matched term: `presence_points(term_frequency) × rarity_weight(document_frequency, total_documents)` — a fixed presence schedule (capped at 1.6) times a fixed four-tier rarity weight (common/typical/notable/distinctive, by corpus-share). Replaces `1 + log(tf)` and log-based IDF.
2. **Shape adjustment.** The document's score is scaled by `shape_multiplier()` — a fixed bracket by length-vs-corpus-average that actively *boosts* a document shorter than 75% of the corpus average, rather than merely declining to penalize it.
3. **Coverage** — a document matching more distinct meaningful query terms is multiplied up (floor `COVERAGE_FLOOR`).
4. **Title match** — meaningful query terms in the title earn a rarity-weighted bonus, damped for generic instructional verbs.
5. **Generic-concept-title penalty** — a document titled nothing but a bare abstract concept word (e.g. "Law") is demoted, unconditionally, regardless of detected intent.
6. **Phrase match** — a verbatim contiguous query match earns a flat multiplier.
7. **Proximity** — matched query terms found within a fixed character window of each other earn a bounded bonus. No TF-IDF/BM25 equivalent: bag-of-words scoring cannot see word position.
8. **Intent** — for non-general intents, `intent.py` supplies the "does this answer the reason behind the question" signal.

Intent classification is deliberately a **hint, not a filter**: nothing is ever excluded for lacking an expected intent term; scores are only nudged, so the worst case is "slightly wrong order," never "correct answer deleted."

## 5. Storage schema

Two tables in one SQLite file (`brisart_ai_index.sqlite3`), plus vault tables:

- **`sources`** — `(source_key, source_type, location, title, text, content_hash, size_bytes, extension, indexed_at)`. `source_key` is `sha256(source_type + "|" + location)`, so re-adding a file or re-crawling a URL **upserts** rather than duplicating.
- **`terms`** — `(term, source_id, tf)`, read directly by the ranker.
- **vault** (`knowledge/vault.py`) — collections, notes, entities, timeline. Notes are mirrored into `sources` (`source_type="note"`) so they rank through the same model as files and web pages.

`source_type` is the universal scoping key: `"file"`, `"web"`, `"note"`.

## 6. Concurrency and failure model

- **One request at a time.** `ui/app.py`'s `_busy` flag serializes requests; a second question typed mid-answer is ignored, not queued.
- **Background thread.** Search/crawl runs off the Tk main loop; results are marshalled back via `self.after(0, ...)`.
- **`check_same_thread=False`** on both SQLite connections, safe because `_busy` prevents overlapping access.
- **Startup failure is caught in exactly one place.** `BrisartService` is constructed before the Tk window, so a locked or read-only database raises out of `__init__` and `run()`'s single `try/except` shows a friendly dialog instead of a raw traceback.
- **Networking never denies on ambiguity.** `web/policy.py` treats a missing/unreachable/malformed `robots.txt` as *allowed*; only a successfully parsed explicit `Disallow` blocks a fetch.

## 7. The native layer

`brisart_ai/native/` is architecturally distinct from every other package: it is the only layer with zero knowledge of BrisartAI's domain (sources, ranking, intent, the UI). Each module is a faithful, independently-verified stand-in for one stdlib module:

| Native module | Replaces | Used by |
|---|---|---|
| `brisart_hash.py` | `hashlib` | `util.py` |
| `brisart_url.py` | `urllib.parse` | `util.py`, `blocklist.py`, `intent.py`, `io/extractor.py`, `web/*` |
| `brisart_json.py` | `json` | `core/settings.py`, `io/readers.py`, `web/search.py` |
| `brisart_codec.py` | `base64` | `web/search.py` |
| `brisart_markup.py` | `html.parser.HTMLParser` | `io/extractor.py`, `web/search.py` |
| `brisart_robots.py` | `urllib.robotparser` | `web/policy.py` |
| `brisart_inflate.py` | `zlib` | `io/binary_readers.py` |

All seven modules are wired into the call sites above; actual HTTP networking (`urllib.request`/`urllib.error`) is unchanged, since the native stack replaces parsing logic, not the network transport itself. See `brisart_ai/native/README.md` for each module's verification results.

## 8. Where to make a change

| I want to… | Open |
|---|---|
| Change how a question is classified | `brisart_ai/intent.py` |
| Change the base term-scoring math | `brisart_ai/knowledge/relevance_engine.py` |
| Change the signal stack on top of the base score | `brisart_ai/knowledge/ranker.py` |
| Change which sentences are quoted | `brisart_ai/knowledge/synthesizer.py` |
| Add a supported file type | `brisart_ai/io/readers.py` (+ `binary_readers.py`) |
| Add/blocklist a web host | `brisart_ai/blocklist.py` |
| Add a search provider | `brisart_ai/web/search.py` |
| Change the storage schema | `brisart_ai/knowledge/index.py` |
| Change a research toggle | `brisart_ai/core/settings.py` |
| Restyle the UI | `brisart_ai/ui/theme.py` |
| Replace a stdlib call with a native equivalent | `brisart_ai/native/README.md` |

## 9. Testing surface

Tests are co-located with source: every folder under `brisart_ai/` with source modules has its own `tests/` subfolder right beside it (379 tests total). See `docs/TESTING.md` for layout and how to run them. `scripts/debug_offline_replay.py` and `scripts/debug_search_replay.py` remain the primary tools for validating *ranking quality* specifically — they exercise the real retrieval path with full per-component score breakdowns, which a pass/fail assertion alone would not surface.
