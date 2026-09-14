# brisart_ai/

The BrisartAI Python package — everything the application is made of. This top-level folder holds the seven feature packages plus the small shared modules they all depend on.

> **Note:** in the current repository, this file was accidentally a byte-for-byte copy of `brisart_ai/web/README.md`. This is the corrected, package-level version.

```text
brisart_ai/
├── core/            Answer routing, session memory, persistent settings
├── io/              Reading local files into searchable text
├── knowledge/       SQLite index, ranking, relevance, synthesis, vault
├── native/          The Brisart Native Stack (pure-Python stdlib replacements)
├── ui/              The Tkinter desktop app and its service boundary
├── web/             Optional public web search, fetch, and crawl policy
├── tests/           Tests for the four shared modules below
├── blocklist.py     Shared junk-host / function-word policy
├── intent.py        Query- and answer-intent classification
├── util.py          Shared tokenize / hash / URL / sentence toolbox
└── version_info.py  Loads the canonical version string from version.py
```

Each feature package carries its own `README.md`. Start with [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) for the full request flow and dependency rules; this file covers only the four shared modules that live directly here.

---

## The dependency floor

These four modules sit at the bottom of BrisartAI's *own* import graph. They may be imported from anywhere above; they import nothing from `core/`, `knowledge/`, `io/`, `ui/`, or `web/`. Their only downward dependency is `native/`, which knows nothing about BrisartAI at all.

This is deliberate. It is exactly why `blocklist.py` lives here rather than inside `web/`: `knowledge/index.py` needs to purge junk web rows, and it must be able to do that without the knowledge layer taking a dependency on the web layer.

---

## `util.py`

The one shared, dependency-free toolbox every other layer imports from:

- **`tokenize()`** — lowercases, splits on word boundaries, drops single-character words and a small English stopword set. Returns `[]` for `None` or `""` rather than raising.
- **`stable_hash()` / `file_hash()`** — SHA-256 fingerprints (via the native `brisart_hash`) for stable source keys and file de-duplication. `file_hash()` streams a file in 1 MB chunks rather than reading it whole.
- **`normalize_url()` / `same_site()`** — URL normalization and host comparison (via the native `brisart_url`). A schemeless string is upgraded to `https://` here — that policy decision lives in `util.py`, not in the native URL parser.
- **`split_sentences()`** — sentence splitting for synthesis; sentences outside a 30–700 character band are dropped.
- **`safe_read_text()`** — best-effort multi-encoding read (utf-8 → utf-16 → latin-1, always succeeding via a final `errors="replace"`).

---

## `intent.py`

Question-intent detection and intent-aware scoring. Term-overlap ranking cannot tell "does this mention the query words" from "does this mention them *for the right reason*," so a query is classified into a coarse intent — **founder, inventor, statistic, explanation, comparison, or general** — and each intent carries BOOST and PENALTY vocabularies.

Intent is a **hint, not a filter**: it only nudges scores, never excludes a document. Shared by `knowledge/ranker.py`, `knowledge/synthesizer.py`, and `web/crawler.py`, so web and offline ranking can never diverge on classification. Two vocabularies here — `_KNOWN_COMPANIES` and `_GENERIC_CONCEPT_TITLES` — are intentionally finite and hand-maintained (see KI-004, KI-008 in `docs/KNOWN_ISSUES.md`).

---

## `blocklist.py`

The single source of truth for "should this web page be kept?" Holds the blocked dictionary/definition hosts, low-value hosts, listing-path markers, account-host prefixes, and the canonical bare-function-word set. Consumed by `web/search.py`, `web/crawler.py`, and `knowledge/index.py` (to purge junk rows already stored). Requires an absolute URL with a scheme; an off-topic-wiki check only rejects a page whose title is *exactly* a bare function word unless overridden by the query's own topic terms.

---

## `version_info.py`

Single source of truth for `APP_NAME` (`"BrisartAI"`) and `__version__`. Loads `version.py` from the project root by file path via `importlib.util` (not `import version`, since `version.py` lives outside the package and must not require the project root on `sys.path`). Falls back to `"0.0.0-unknown"` if `version.py` is missing, unreadable, or fails to import — a broken version file can never crash startup.
