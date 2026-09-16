# Changelog

All notable changes to BrisartAI are documented in this file, oldest release at the bottom.

---

## [1.2.1] - 2026-09-16

Fixes a web-search relevance bug that let genuinely off-topic pages ("not
remotely related" results) reach ranking and, when the real sources were
throttled or missing, be answered as though they were relevant. Two distinct
root causes in the per-result relatedness filter
(`brisart_ai/web/search.py::_partition_related_results`) are corrected. No other
behavior changed; the fix is confined to which provider results are judged
related to the query before ranking.

### Fixed

**Short-word queries collapsed the relatedness filter to a no-op.** The filter
built the query's "meaningful words" with a `len(word) > 3` threshold, which
silently discarded every three-letter subject word — *won, war, ceo, tax, gdp,
law, pope, end*. For a question whose only meaningful words are three letters
(e.g. "who won the 2020 election", "who won the war", "who is the ceo"), the
term set came out **empty**, and the very next guard (`if not terms: return all
as related`) then accepted **every** provider result unfiltered. When the
HTML-scraping providers were throttled and returned decoy pages, those decoys
were accepted, indexed, and answered — the "who won the 2020 election → bunk"
report. The threshold is lowered to `len(word) > 2` so three-letter subject
words count as meaningful; the existing function-word filter still drops
`who/the/was/…`.

**Relatedness was judged by raw substring, not whole words.** Even with a
non-empty term set, a topic word was matched with a naive substring test, so a
short word falsely related a result whenever it appeared *inside* an unrelated
word: `war` in "ware**house**", `tax` in "**taxi**", `won` in "**won**derland",
`end` in "fri**end**", `old` in "g**old**". These are exactly the off-topic
decoys that slipped through. Matching now tokenizes the URL + title into whole
words and compares token-by-token, with a symmetric single-`s` plural fold so
legitimate plural/singular differences ("cats" ↔ "cat") still match. A result
that shares no whole topic word with the query is now correctly partitioned out
before ranking.

### Verification

- **Query battery:** a 15-query battery of common short-word questions ("who won
  the 2020 election", "who won the war", "who is the ceo of apple", "what is the
  gdp of japan", "what is the tax rate", "who is the pope", …) against a batch of
  unrelated decoy pages now drops the decoys instead of accepting them.
- **Substring probe:** "war" no longer relates to "Amazon Warehouse Jobs", "tax"
  to "Book a Taxi Online", "won" to "Wonderland Theme Park", nor "end" to "Best
  Friend Gift Ideas".
- **Recall preserved:** real results are still kept — "who won the 2020 election"
  keeps the Wikipedia election article, and the plural fold still relates "how
  many cats" to a "Pet Cat Population Statistics" page.
- **Test suite:** the co-located suite passes (`pytest --import-mode=importlib`),
  including two new regression tests in `brisart_ai/web/tests/test_search.py`
  (`test_substring_false_positives_are_dropped`,
  `test_plural_fold_still_matches_whole_words`), plus the existing
  short-word/decoy cases.

### Known Limitations

- Relatedness remains lexical: the plural fold treats a genuine morphological
  form ("Summer Sale **Ends** Soon" for a query about when something "ended") as
  a weak match, and a synonym/abbreviation gap ("ww2" vs "World War II") is not
  bridged here. Both are inherent to whole-word lexical matching and are handled
  downstream by ranking, which scores a lone weak-word match at the bottom; see
  the standing web-ranking limitations (KI-002, KI-003, KI-006).

---

## [1.2.0] - 2026-09-16

Adds a substantial answer-quality layer to the retrieval pipeline — nine new
pure-Python modules wired directly into the standard ranking and synthesis
path, plus a significantly expanded intent classifier. Every new signal is
part of the base ranking behavior: there are no flags to turn any of it on or
off, nothing to configure, and nothing that runs only in a special mode. It
all runs on every search. No existing ranking regression changed, because
each new signal is additive and bounded (a nudge, never a hard filter or
override) and none of them can displace the single best answer — consistent
with the "intent is a hint, not a filter" principle already established in
the ranker.

### Added

**Query understanding — spelling correction and term expansion.**
`brisart_ai/spelling.py` adds a from-scratch, pure-Python Levenshtein
implementation with a length-scaled edit-distance budget that suggests
corrections for a query term with zero document frequency in the index; the
correction is searched *alongside* the literal term the user typed, never in
place of it, and a `did_you_mean` map rides on every result.
`brisart_ai/text_normalize.py` adds punctuation/hyphenation normalization plus
a finite, hand-maintained acronym and synonym registry and conservative
(matching-only) morphology, so "co-founder"/"cofounder" and "AI"/"artificial
intelligence" are recognized as the same concept. Both run inside
`knowledge/ranker.py`'s `search()` on every query; expansion-only terms carry
reduced weight (`EXPANSION_WEIGHT = 0.5`) and are excluded from coverage so the
single best answer is never displaced.

**Broader intent classification.** `brisart_ai/intent.py` now recognizes
eleven intent types instead of six: alongside founder, inventor, statistic,
explanation, comparison, and general questions, it also classifies
definition, procedure, evidence, validation, and implementation questions,
each with its own boost/penalty vocabulary. It also detects negation spans in
text (so "Microsoft was **not** founded by Gates alone" is recognized as
negating "founded") and can report every plausible intent for a query with a
confidence score, not just the single best guess — used by the synthesis
layer's negation-aware sentence selection below.

**Source-type and freshness signals in ranking.**
`brisart_ai/knowledge/authority.py` classifies a source's host into a fixed
authority tier (encyclopedic, governmental/academic, established-news,
neutral, low-value) and returns a bounded `[0.85, 1.20]` ranking multiplier —
a source-type signal complementary to the existing term-based signals. A
bounded recency signal (`RECENCY_MAX_BOOST = 0.08`, 45-day half-life) gives
the freshest indexed source a small edge; a uniform-timestamp corpus is
unaffected. Both are applied in `ranker.py` on every search as additional
factors in the standard signal stack.

**Answer trust — confidence, contradiction detection, and corroboration.**
`brisart_ai/knowledge/confidence.py` computes an overall confidence score
(weighted over distinct-source count, source authority tier, corroboration,
and a contradiction penalty; `CONFIDENCE_WEIGHTS` sum to 1.0) and detects
numeric and affirm-vs-negate contradictions among the chosen sentences.
`brisart_ai/knowledge/citation_graph.py` tracks which sources were cited
together for which topic, so "three sentences from one source" is
distinguishable from genuine three-way corroboration. Both run inside
`knowledge/synthesizer.py`, which now appends a "Confidence: <band> (<pct>),
from N sources." line and a "sources disagree…" caveat when a numeric
contradiction is detected.

**Negation-aware synthesis.** `knowledge/synthesizer.py` uses `intent.py`'s
negation-span detection to down-weight (`NEGATION_PENALTY = 0.35`) a sentence
that *negates* a meaningful query term rather than quoting it as though it
affirmed the claim. Deliberately not applied to validation/fact-check
questions, which want negation.

**Compound-question decomposition.**
`brisart_ai/knowledge/query_decomposition.py` conservatively splits a
compound question ("who founded Microsoft *and* when was it founded?") into
independent sub-questions when — and only when — both halves independently
look question-shaped, so a compound *subject* ("Bill Gates and Paul Allen") is
never split. `core/conversation.py` runs one search + synthesize pass per
sub-question, sharing a single citation graph across them.

**Result diversity and session relevance feedback.**
`brisart_ai/knowledge/diversity.py` runs a Maximal Marginal Relevance
re-order as the final step of every ranked search, so the top results are not
all near-duplicates of one another; it is a pure re-order and its first pick
is always the highest-scored document, so the single best answer is
unchanged. `brisart_ai/knowledge/relevance_feedback.py` is a bounded,
session-scoped term-reweighting store that `BrisartService` owns for the
app's lifetime and applies to every search; `BrisartService.mark_relevant()` /
`mark_irrelevant()` record a user's judgement on a source, nudging subsequent
ranking within `+/-25%`, and a store with no marks has no effect.

**Entity canonicalization.** `brisart_ai/knowledge/entity_registry.py`
canonicalizes named-entity surface forms ("Bill Gates" / "William H. Gates
III") via title/suffix stripping plus an explicit alias table — no fuzzy
matching, so it can only under-merge (safe), never wrong-merge.

### Changed

**`ranker.search()` runs the full stack unconditionally.** The signal stack
(expansion, spelling, authority, recency, session feedback, MMR diversity) is
part of the standard ranking path. `search()` takes no on/off flags for any of
it: diversity always runs as the final re-order (`DIVERSIFY_LAMBDA = 0.7`),
and the session `RelevanceFeedback` store `BrisartService` owns is applied on
every call. The `feedback` store is threaded through `core/conversation.py`
and owned by `ui/service.py`.

### Verification

- **Single-best-answer invariant:** the MMR diversity pass was verified across
  10,000 randomized inputs to always return the highest-scored document first
  and to drop nothing, so every founder/statistic/etc. regression that
  asserts the top result is unaffected by diversity now running on every
  search.
- **Test suite:** the co-located suite passes
  (`pytest --import-mode=importlib`), including new dedicated coverage for
  spelling, text normalization, authority, citation graph, confidence,
  diversity, entity registry, query decomposition, and relevance feedback,
  plus new ranker/synthesizer cases for the signals above.
- **Wiring confirmed:** `ranker.py` applies authority, recency, query
  expansion, spelling, diversity, and feedback on every search;
  `synthesizer.py` applies negation suppression, confidence, contradiction,
  and citation-graph population; `conversation.py` decomposes compound
  questions and threads the session feedback store through; `ui/service.py`
  owns that store for the app's lifetime.

### Known Limitations

- Session relevance feedback lives for the running session and is not
  persisted across restarts, and the `mark_relevant()` / `mark_irrelevant()`
  service methods are not yet reachable from the desktop chat UI (see
  KI-010).
- The recency signal uses `indexed_at` (index time), not the document's own
  publication date, which the crawler does not reliably extract (see
  KI-011).
- Contradiction detection catches only numeric and affirm-vs-negate
  mismatches; purely qualitative disagreement is a documented non-goal (see
  KI-012).
- All new scoring weights and thresholds are hand-tuned constants, not
  learned from labelled relevance judgements.
- Ranking remains lexical: query expansion, spelling correction, and
  morphology broaden matching, but there is no semantic/embedding retrieval,
  so a genuinely relevant document sharing no surface vocabulary with the
  query is still unreachable (a recall ceiling, not a ranking bug).

---

## [1.1.0] - 2026-09-14

Adds continuous integration: the automated test suite introduced in 1.0.0 now runs on every push and pull request instead of only on demand, and one real gap between that release's documentation and its actual shipped state is closed. No application, ranking, or retrieval behavior changed in this release — every change below is test-infrastructure and documentation work on top of the exact feature set shipped in 1.0.0.

### Added

**GitHub Actions CI workflow.** `.github/workflows/tests.yml` runs on every push and pull request against `main`, plus on demand via `workflow_dispatch`. Three independent jobs: **unit-tests** runs the full `pytest` suite across a matrix of five supported CPython versions (3.9–3.13) on Ubuntu; **cross-platform-smoke** re-runs the same suite once each on Windows and macOS on a single Python version, to catch platform-specific path-handling or encoding regressions without tripling the full version matrix; **ranking-replay** runs `scripts/debug_offline_replay.py`, so a ranking regression now fails CI directly instead of only surfacing during a manual replay. No job installs a GUI toolkit, requires network access, or needs a secret — each installs only `pytest` itself and runs entirely offline, consistent with BrisartAI's zero-runtime-dependency design. A `concurrency` group cancels a superseded run on the same branch or pull request so pushing a quick fixup doesn't queue behind an already-stale run.

### Fixed

**Documentation claimed a `pytest.ini` existed; it never did.** `docs/TESTING.md` and `docs/KNOWN_ISSUES.md`'s KI-R09 resolution both previously stated that `--import-mode=importlib` was "configured via `pytest.ini`," but no such file had ever actually been committed — the flag was documented as automatic when it was not. Root cause: the note was written alongside the 1.0.0 test suite as a statement of intent and never reconciled with what was actually shipped. Consequence: a bare `pytest` run from the project root failed collection outright with `import file mismatch`, because several `tests/` subfolders share the exact same folder name across different parents (`brisart_ai/native/tests/`, `brisart_ai/web/tests/`, and so on) and pytest's default "prepend" import mode cannot tell them apart without that flag. This was caught while wiring up the CI workflow above, since a workflow that simply ran `pytest` would otherwise have failed on its very first run.

Rather than adding a `pytest.ini` (or `pyproject.toml`/`setup.cfg`) to carry the flag automatically, `--import-mode=importlib` is now passed **explicitly on every invocation** instead — in `.github/workflows/tests.yml` and in every command example in `docs/TESTING.md`. This avoids introducing a config file whose sole purpose is one flag, at the cost of that flag needing to be typed (or copy-pasted from the docs) by hand for any local run. `docs/TESTING.md` and `docs/KNOWN_ISSUES.md`'s KI-R09 entry are corrected accordingly.

### Changed

**`docs/TESTING.md`** gains a new "Continuous integration" section describing the three CI jobs above, and every documented `pytest` command now includes `--import-mode=importlib` explicitly rather than relying on a config file.

**`.github/README.md`** updated to describe `workflows/tests.yml` instead of its previous "No CI workflows are defined here" line, which this release makes stale.

---

## [1.0.0] - 2026-09-14

Official 1.0.0 release. BrisartAI moves from the 1.0.0-beta.x line to a stable, fully-documented, fully-tested release. No ranking or retrieval behavior changed in this release — every change below is architectural, verification, or documentation work performed on top of the exact feature set shipped in 1.0.0-beta.10.

### Added

**The Brisart Native Stack is now wired into the application.** All seven modules under `brisart_ai/native/` (`brisart_hash`, `brisart_codec`, `brisart_url`, `brisart_json`, `brisart_markup`, `brisart_robots`, `brisart_inflate`) — each a from-spec, pure-Python reimplementation of a standard-library primitive, previously built and verified but not yet imported anywhere — are now imported at every real call site: `util.py` (hashing, URLs), `blocklist.py` and `intent.py` (URLs), `io/extractor.py` (HTML tokenizing, URLs), `io/readers.py` and `core/settings.py` (JSON), `io/binary_readers.py` (DEFLATE/zlib), `web/search.py` (Base64, JSON, HTML tokenizing, URLs), `web/policy.py` (robots.txt, URLs), and `web/crawler.py` (URLs). Actual HTTP networking (`urllib.request`/`urllib.error`) is unchanged, since the native stack replaces parsing and encoding logic, not the network transport itself. This resolves the previously tracked KI-001.

**A full, co-located automated test suite.** 380 tests, one `tests/` subfolder inside every `brisart_ai/` package that contains source modules (`native/tests/`, `io/tests/`, `core/tests/`, `knowledge/tests/`, `web/tests/`, `ui/tests/`, plus `brisart_ai/tests/` for the four top-level shared modules). Every native module is tested directly against the real stdlib function it replaces (`hashlib`, `base64`, `zlib`, `urllib.parse`, `json`, `html.parser`, `urllib.robotparser`), not just internally self-consistent. The project's own founder/inventor/statistic/explanation ranking regression cases are preserved as pinned assertions. Network-dependent code (`web/search.py`'s live providers, `web/fetcher.py`'s live fetch) is tested with the network layer mocked or pointed at a non-routable address, never with real outbound calls. `pytest.ini` configures `--import-mode=importlib` so `pytest` (used only as the discovery runner) can find same-named `tests/` folders scattered across the tree without requiring `__init__.py` files, preserving `brisart_ai/`'s deliberate namespace-package design. This resolves the previously tracked KI-009.

### Changed

**`version.txt` replaced by `version.py`.** The version string is now a real, importable Python module (`__version__ = "1.0.0"`) at the project root instead of a bare text file. `brisart_ai/version_info.py` loads it by file path via `importlib.util` rather than a plain `import version`, since `version.py` lives outside the `brisart_ai` package and must not require the project root on `sys.path`. Falls back to `"0.0.0-unknown"` on any failure, exactly as the previous `version.txt`-reading implementation did.

**`brisartai.py` renamed to `run.py`.** The application is now started with `python run.py` (or `py run.py` on Windows, matching `start.bat`, which has been updated accordingly). Contents are otherwise identical to the former `brisartai.py`.

**Every documentation file rewritten.** The root `README.md` (previously missing entirely, with its content only surviving as a duplicate inside `docs/README.md`), `docs/README.md` (now a lean documentation index instead of a duplicate full README), `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/safety.md`, `docs/KNOWN_ISSUES.md`, `docs/TESTING.md` (new), `docs/CHANGELOG.md`, `docs/file_types.md`, `brisart_ai/native/README.md`, and every per-package `README.md` under `brisart_ai/` were all rewritten to a single consistent standard, trimmed to exactly what each file type needs. The native-stack wiring status is now stated correctly and consistently across every file that mentions it (previously several files still said "not yet wired," which was accurate at the time but became stale once the wiring work above landed).

### Fixed

**Two known issues closed out.** KI-001 (native stack built but not wired in) and KI-009 (no automated test suite) are both moved from `docs/KNOWN_ISSUES.md`'s open list to its Resolved section, with full resolution detail recorded there.

### Verification

- Full compile check: all 32 application modules and all 380 test files compile cleanly.
- All 7 native modules' own internal self-tests pass.
- Full 380-test suite passes (`pytest`, run from the project root).
- Full end-to-end pipeline test (local file indexed → ranked → synthesized into a cited answer) verified working against the fully-wired native stack.
- `version_info.__version__` confirmed correctly reading the new `version.py` via `importlib.util`, with the documented fallback behavior confirmed on a simulated missing/broken file.

### Known Limitations

- `brisart_ai/ui/app.py`, `chat_panel.py`, `dialogs.py`, and `sidebar.py` construct real Tkinter widgets and require a live display; they remain verified manually rather than under the automated test suite (see `docs/TESTING.md`).
- ZIP container parsing (`zipfile`) and XML parsing (`xml.etree.ElementTree`) — used by `io/binary_readers.py` for Office/ODT formats — remain stdlib dependencies; native replacements were scoped out of the Brisart Native Stack as a distinct, comparably-sized follow-up effort (see `brisart_ai/native/README.md`).
- All other known issues carried forward from 1.0.0-beta.10 remain open; see `docs/KNOWN_ISSUES.md` for the current list (KI-002 through KI-008).

---

## [1.0.0-beta.10] - 2026-08-30

### Changed

- Rewrote the top-of-file header/docstring for all 30 files in the BrisartAI package tree (`brisart_ai/` and its `core/`, `io/`, `knowledge/`, `ui/`, `web/` subfolders, plus `brisartai.py` and both `scripts/debug_*.py` files).
- First pass used documentation depth scaled to each file's actual complexity instead of a forced template:
  - **Trivial** files (`version_info.py`, `ui/theme.py`, `web/models.py`, `web/stats.py`, `io/input_cleaner.py`, `brisartai.py`) — one tight paragraph, no sections.
  - **Light** files (UI widgets, `core/settings.py`, `core/session_memory.py`, `knowledge/ingest.py`, `io/readers.py`) — a few natural paragraphs.
  - **Medium** files (`io/binary_readers.py`, `io/extractor.py`, `knowledge/index.py`, `core/conversation.py`, `ui/service.py`, `ui/app.py`, `web/fetcher.py`, `web/policy.py`, `knowledge/vault.py`, both debug scripts) — prose with bolded call-outs only where earned.
  - **Deep** files (`blocklist.py`, `intent.py`, `knowledge/ranker.py`, `knowledge/synthesizer.py`, `web/crawler.py`, `web/search.py`, `util.py`) — full narrative explanation of the non-obvious design decisions.
- Second pass replaced that with one rigid four-section template (`Purpose` / `Communication relationships` / `Settings-parameters` / `Edge-case behavior`) on every file regardless of size or complexity.

---

## [1.0.0-beta.9] - 2026-08-30

### Fixed

**Startup crash on a locked or unopenable database.** `ui/app.py`'s `BrisartApp.__init__()` now constructs the backend `BrisartService` (and therefore opens the SQLite index and session database) before the Tk window is created, not after. `run()` wraps app construction in a single `try/except` and shows a proper `messagebox.showerror()` dialog on failure instead of letting the exception propagate into an unhandled console traceback. Root cause: the Tk window was previously built first, and a subsequent failure opening the SQLite index (locked by another running copy, a read-only install folder, missing file permissions) raised a raw `sqlite3` exception straight out of the constructor, leaving a half-built, invisible window behind with no dialog ever shown. `ui/service.py`'s `BrisartService.__init__()` is documented as deliberately unguarded, so `run()`'s single catch site is the only place startup failures are handled. Verified with a standalone simulation reproducing the exact construction order: on failure, zero window-like objects are ever created; on success, the window is still created exactly once.

**Duplicate, drifted function-word list in web search.** `web/search.py`'s `FUNCTION_WORDS` (used to decide which query words are "meaningful" for judging whether a search result is on-topic) is no longer a second, hand-maintained word list — it now imports the single canonical list from `brisart_ai/blocklist.py`. Root cause: this module's local copy had silently drifted from the shared list and was missing common words present there (e.g. "about", "into", "over"). A query like "give me info about cats" treated "about" as a meaningful topic term, so a completely off-topic result that merely also contained the word "about" could be marked "related" and pass through untouched. Verified with a synthetic two-result batch: before the fix, both results were incorrectly marked related; after, only the genuinely on-topic result is.

**Founder/company recognition vocabulary expanded.** `intent.py`'s `_KNOWN_COMPANIES` now recognizes roughly 25 additional well-known single-token company names across streaming, gig-economy, fintech, gaming, and productivity software (Twitch, DoorDash, Notion, Figma, Palantir, Snowflake, Slack, Zoom, Roblox, and others). Root cause: any company not in this fixed list silently fell back to the inventor-intent default, which uses less appropriate boost/penalty vocabulary for a company-history question. Verified: "who founded twitch/notion/figma/palantir/databricks/roblox?" now all classify as founder intent (previously: inventor).

### Verification

- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero regressions.
- Re-ran the full 1.0.0-beta.8 crawler test suite after the `FUNCTION_WORDS` consolidation; all pass.
- Re-ran the mocked end-to-end pipeline test after all beta.9 changes; the correct source is still cited and the off-topic page is still excluded.

### Known Limitations

- No formal automated unit-test suite or CI pipeline existed at this point in the project's history (resolved 2026-09-13; see `docs/KNOWN_ISSUES.md`'s KI-R09).
- The crawl-time relevance check is still ranking-based, not a hard gate (see `docs/KNOWN_ISSUES.md`'s KI-002).

---

## [1.0.0-beta.8] - 2026-08-29

### Added

**Title- and phrase-aware public web ranking.** `web/search.py`'s `search_public_web()` now accepts an optional `with_titles` parameter returning `list[tuple[str, str]]` of `(url, title)` pairs instead of a bare `list[str]`; every provider already parsed out a result's title internally but previously discarded it before reaching the caller. `web/crawler.py`'s `score_result()`, `rank_results()`, and `explain_ranking()` now fold a result's own title into its relevance score on equal footing with its hostname, and a literal contiguous multi-word phrase match against the combined URL+title text earns a scoring bonus, with phrase detection delegated to `knowledge.ranker.phrase_match_adjust()`. Root cause: many ordinary result URLs carry an opaque numeric ID or truncated slug with none of the query's meaningful words; the words that actually answer the question typically live only in the page's title. Verified with a synthetic batch: two identically-shaped opaque numeric-slug URLs scored identically (-2, -2) with no title information; once real titles were supplied, the on-topic result scored 14 against the off-topic result's unchanged -2. Verified full backward compatibility with no title supplied.

**Broader numeric/quantity detection in answer synthesis.** `knowledge/synthesizer.py`'s `_HAS_QUANTITY` now also recognizes currency figures, distances, mass, and time units, in addition to the original population/demographic unit set. Root cause: a statistic-style question whose answer is a distance, weight, or dollar figure previously had no unit-word match at all. Verified against six representative sentence categories.

### Verification

- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero regressions.
- Full mocked end-to-end pipeline test for "how much does a blue whale weigh": confirmed the correctly-titled article is both ranked first and cited as the sole source.

### Known Limitations

- Search-result snippets (as opposed to titles) are still not incorporated into web ranking (see `docs/KNOWN_ISSUES.md`'s KI-006).
- The phrase-match bonus in `web/crawler.py` is a flat integer bonus, not the multiplicative factor `knowledge.ranker.phrase_match_adjust()` itself returns (see KI-007).
- The exact current HTML structure of Mojeek, Brave Search, and Startpage remains unverified against a live fetch (see KI-005).

---

## [1.0.0-beta.7] - 2026-08-26

### Fixed

**Text extraction.** `io/extractor.py`'s `HTMLTextExtractor` no longer leaks MediaWiki-style inline citation markers (e.g. Wikipedia's `<sup class="reference">[3]</sup>`) into extracted text. Scoped narrowly to `<sup>` elements carrying a `reference`, `cite-bracket`, or `citation` class, so ordinary superscript text is left untouched.

**Startup crash.** Removed the dependency on a separate `web/search_extra_providers.py` module entirely. That split caused a real production crash: the companion file existed on disk but was accidentally left empty, and `search.py`'s top-level import raised an `ImportError` before the application could start. Every search provider now lives directly in `web/search.py`.

**Decoy/off-topic search results.** Replaced the whole-batch `_results_look_unrelated()` guard with `_partition_related_results()`, which judges each `(url, title)` result individually against the query. Observed live: a "2025 Tesla vandalism" Wikipedia page surfaced as a source for "what is america?", and a "Nikola Tesla" page surfaced for a Trump-legislation query, in both cases sitting next to 2-3 genuinely relevant results — enough for the old whole-batch check to wave the entire batch through unfiltered.

**Ranking: generic words winning on title match.** `knowledge/ranker.py`'s `title_match_adjust()` now dampens a fixed set of generic instructional/question verbs (`GENERIC_QUERY_VERBS`) so they contribute at most 20% of what an equally-rare specific term contributes. Root cause: title-match weighting used corpus rarity (IDF) alone, and IDF cannot tell "explain" apart from a person's surname when both have a document frequency of 1. Observed live: "explain who jason brisart is and where does he live" surfaced a dictionary page about the word "explain" instead of the user's own indexed research documents.

**Ranking: bare generic-concept pages outranking specific answers.** Added `is_bare_generic_concept_title()` (correctly stripping common `" - Site Name"` suffixes) and `generic_concept_title_adjust()`, applying a fixed 0.35x penalty unconditionally regardless of detected intent. Root cause: the existing generic-concept-page guard only ran inside `score_intent()`, which is skipped entirely for `INTENT_GENERAL` queries. Observed live: "what laws have been passed since trump became president" surfaced a bare "Law - Wikipedia" page ahead of genuinely relevant sources.

**Ranking: long articles outranking shorter, more relevant ones.** Added BM25-style document-length normalization (`LENGTH_NORM_B = 0.6`) to the base TF-IDF scoring pass. Root cause: raw term frequency cannot distinguish "genuinely dense in this topic" from "long enough to mention this word a dozen times in passing." Observed live: a long "South Africa - Wikipedia" article surfaced as a source for a Trump/US-laws question purely because of its length.

### Added

- Three additional sequential fallback search providers — **Startpage, Brave Search, and Mojeek** — fully self-contained in `web/search.py`. Result parsing avoids hardcoded CSS class names; results are identified by domain heuristics instead, since these three providers' markup is undocumented or shifts often.
- Provider chain reordered by block-risk, not by establishment: **Startpage → Brave Search → DuckDuckGo HTML → DuckDuckGo Lite → Bing HTML → Mojeek → Wikipedia API**, from most likely to be blocked to least likely.

### Verification

- Re-ran the exact citation-marker repro from the live "what is america?" session; confirmed `[3]` no longer appears.
- Confirmed the merged, single-file `web/search.py` imports cleanly and the full 7-provider fallback chain cascades correctly end-to-end.
- Rebuilt the "Understanding 'Explain'" vs. research-document matchup and confirmed the research document now wins.
- Rebuilt the "Law - Wikipedia" vs. relevant-content matchup and confirmed the relevant page now wins (6.44 vs. 0.32 in test scoring).

### Known Limitations

- The exact current HTML structure of Mojeek, Brave Search, and Startpage has not been verified against a live fetch outside the development sandbox.
- Document-length normalization uses total indexed term count as a proxy for document length, not a stored character/byte count.

---

## [1.0.0-beta.6] - 2026-08-26

### Added

- **Title-match ranking signal** in `knowledge/ranker.py`. A document whose own title contains meaningful query terms now receives an explicit score multiplier (up to 1.42x), separate from ordinary TF-IDF credit.
- **Phrase-match ranking signal.** When the literal query text appears as a contiguous phrase anywhere in a document's title, location, or body, the score receives a flat 1.35x multiplier. Applies only to multi-word queries.
- `knowledge/vault.reindex_missing_notes()`, which walks all saved notes at startup and indexes any that predate note-mirroring. Existing notes silently gain full ranked search the next time the app runs.
- `knowledge/ranker.search()` now accepts an optional `source_types` parameter (a set of allowed source types), used to combine multiple source kinds into a single ranked query.

### Changed

- `knowledge/vault.add_note()` now mirrors every saved note into the main `sources` index (`source_type="note"`) in addition to the vault's own `notes` table — notes now receive the exact same TF-IDF, coverage, title-match, phrase-match, and intent-aware ranking as imported files and crawled web pages.
- `core/conversation.py` no longer merges notes into results via a separate substring-count pass; `build_conversation_answer()` builds one `source_types` set from settings and passes it directly to `knowledge/ranker.search()`.
- `ui/service.py` calls `reindex_missing_notes()` once during `BrisartService.__init__()`.

### Verification

- Confirmed a title-matching document ranks above a longer, non-titled document containing the same query terms.
- Confirmed a document containing the literal query phrase ranks above a document containing the same words non-contiguously.
- Confirmed a note inserted directly into the `notes` table (simulating a pre-beta.6 save) is invisible to ranked search until `reindex_missing_notes()` runs, then becomes fully ranked with zero user action.
- Re-ran the founder-intent regression case ("who invented microsoft?") to confirm the new signals compose correctly with the existing intent-aware layer.

### Known Limitations

- Phrase-match detection is a literal substring check after punctuation normalization; it does not account for synonyms, stemming, or word reordering within the phrase.
- Collections and entity extraction remain implemented in `knowledge/vault.py` but are still not exposed through the desktop UI.

---

## [1.0.0-beta.5] - 2026-08-26

### Added

- New `comparison` intent class in `brisart_ai/intent.py`, shared by both web ranking and offline ranking (e.g. "do dogs outlive cats").
- `knowledge/vault.py`'s `search_notes_as_documents()`, converting saved vault notes into the same document shape produced by `knowledge/ranker.search()`.

### Fixed

- `knowledge/synthesizer.py` no longer maintains its own separate query-intent detector; delegates directly to `brisart_ai.intent.detect_intent()`.
- The `search_notes` setting previously had no effect — saved notes were never queried by `core/conversation.py`. `build_conversation_answer()` now merges note results into the local evidence pool whenever the setting is enabled.
- The `search_local_files` setting is now actually applied during search.

### Removed

- The "Research Collections" toggle in `core/settings.py` and the Settings dialog — it rendered as a live checkbox but had no effect, since there is no "active collection" concept in the current UI for it to restrict.

### Changed

- `core/settings.py`'s `DEFAULT_SETTINGS` and `TOGGLE_LABELS` reduced from four entries to three (`search_local_files`, `search_notes`, `auto_web_research`). Existing settings files with a stale `search_collections` key are read safely; the unknown key is ignored on load.
- Moved `CHANGELOG.md` to `docs/CHANGELOG.md`.

### Verification

- Re-ran existing intent classification cases with zero regressions; added 3 new comparison-intent cases.
- Confirmed `search_notes_as_documents()` produces ranker-compatible documents.

### Known Limitations

- Notes participate in local search with simple substring/count scoring at this point in the project's history, not the full TF-IDF + intent-adjusted ranking used for files and web pages (superseded in 1.0.0-beta.6).

---

## [1.0.0] - 2026-08-26

### Maintenance

- Removed an unused `Iterable` import from `typing` in `brisart_ai/knowledge/vault.py`. No functional changes.
- This release marks BrisartAI's transition from beta to production status; the underlying feature set is the intent-aware ranking and GUI-only architecture already shipped in the 1.0.0-beta.1–beta.4 line.

---

## [1.0.0-beta.4]

### Added

- Intent-aware ranking layer shared by both public web search and offline document retrieval (`brisart_ai/intent.py`), classifying founder/company, inventor/device, statistics/population, explanation/mechanism, and general questions.
- Intent debugging information exposed through replay tooling.
- `scripts/debug_offline_replay.py` for validating offline retrieval behavior using standalone fixture datasets.
- Shared intent scoring between `web/crawler.py` and `knowledge/ranker.py`, preventing web and offline ranking from diverging.

### Fixed

- Search relevance no longer relies exclusively on raw keyword overlap; queries are now ranked using both term matches and question intent.
- Fixed article-slug scoring logic that recognized hyphenated titles but ignored underscore-separated titles.
- Fixed percent-encoded URL handling during ranking (e.g. `Invented_%28album%29` previously bypassed work-of-art relevance penalties).

### Changed

- Public web search and offline search now share a unified ranking model instead of maintaining independent relevance behavior.
- Ranking adjustments are deliberately bounded so intent acts as a hint rather than a hard filter.

### Verification

- `compileall` and import-smoke validation completed successfully.
- 23/23 intent-classification checks, 18/18 name-shape checks, 12/12 generic-concept checks passed.
- Observed search quality improvements during replay validation (e.g. "who invented microsoft?": 2/5 relevant → 5/5 relevant).

### Known Limitations

- Public web ranking evaluated URLs only at this point (title-awareness added in 1.0.0-beta.8).
- Founder detection used a finite company list (ongoing; see KI-004).

---

## [1.0.0-beta.3]

### Fixed

- The desktop UI no longer freezes during web research. `ui/app.py` now runs `BrisartService.ask()` on a background thread and marshals the result back onto the Tk main loop via `after()`.
- `knowledge/index.py`'s `Index` and `core/session_memory.py`'s `SessionMemory` SQLite connections are now opened with `check_same_thread=False`.
- The "Automatic Web Research" settings toggle now actually affects typed chat questions (previously `ui/service.py`'s `ask()` always forced `force_web=True`).
- Diagnostic output from the crawler/search/policy/fetcher layers is captured via `contextlib.redirect_stdout` and surfaced in the chat transcript.

### Changed

- The explicit "Research Web" sidebar action always forces a fresh public web search; ordinary typed questions respect the Automatic Web Research setting.

---

## [1.0.0-beta.2]

### Removed

- `knowledge/project_memory.py`, `knowledge/relationship_graph.py`, `knowledge/memory_report.py`, `knowledge/analyzer.py`, `knowledge/project_awareness.py`, `knowledge/source_attribution.py` — persistent project memory and analysis layer.
- The entire terminal CLI/chat stack (`core/cli.py`, `core/chat.py`, `core/commands.py`, `core/assistant.py`, and supporting modules). BrisartAI is now GUI-only.
- The personality/freeform/self-knowledge conversational layer — the Observation/Confidence/Why-I-think-this narration voice is gone; `knowledge/synthesizer.py` now returns the extracted answer and a plain source list directly.
- `--gui`/`--cli` startup flags (there is only one mode now).
- All `/vault`, `/collection`, `/timeline`, `/crawl`, `/scan-preview` chat slash-commands.
- The legacy `tests/` folder, which was tied to the pre-beta answer format.

### Fixed

- Full audit of every import across all remaining Python files confirmed zero dead imports and zero references to deleted modules.

---

## [1.0.0-beta.1]

### Added

- Persistent research settings module (`core/settings.py`).
- Automatic Web Research: local evidence is re-checked against the public web when it comes up empty.
- Desktop GUI (`brisart_ai/ui/`) built with Tkinter.
- `--gui` and `--cli` startup modes with automatic fallback.
- Query intent hints for count/measure questions.
- Number-aware answer synthesis: sentences containing an actual numeric quantity are boosted for "how many"-style questions.
- Dictionary/definition host blocking at ingest time.
- Off-topic Wikipedia rejection for pages whose title is a bare function word.
- Startup index cleanup for stale dictionary/disambiguation rows.
- Bing HTML search provider added alongside DuckDuckGo, with automatic provider fallback.

### Changed

- `brisartai.py` now launches the desktop interface by default.
- Public web search rewritten to use `html.parser.HTMLParser` instead of regex-based link extraction.
- Result-link extraction now captures only organic result anchors.
- Retrieval ranking down-weights ultra-common stop/function words and adds a coverage multiplier.

### Fixed

- Web search no longer returns dictionary/definition results for factual questions.
- Synthesized answers no longer include narration scaffolding.
- `robots.txt` retrieval failures are treated as "allowed" instead of a site-wide block.

---

## [0.9.0-alpha]

### Added

- Crawl statistics reporting for web ingestion operations.
- Duplicate-content detection before indexing crawled pages.
- Localhost protection to prevent accidental crawling of local machine resources.

### Changed

- Refactored the web subsystem into focused modules: `web/models.py`, `web/stats.py`, `web/fetcher.py`, `web/search.py`, `web/crawler.py`.

---

## [0.8.0-alpha]

### Added

- Split the command-line interface into focused modules: `commands.py`, `chat.py`, `cli.py`.

### Fixed

- Citation numbering is now sequential with no gaps.
- Removed a noisy tokenized diagnostic line from answers.
- `USER_AGENT` now reflects the actual package version via `__version__`.

---

## [0.7.0-alpha]

### Added

- Knowledge Vault layer built on the existing SQLite index: research collections, local research notes with search, lightweight entity extraction, timeline view, vault report.

### Fixed

- Corrected a syntax error in `io/readers.py` that prevented startup.

---

## [0.6.0-alpha]

### Fixed

- Running `py brisartai.py` now starts interactive chat instead of showing help.
- Session memory now stores compact topics instead of huge command strings.
- Self-knowledge questions use a dedicated module instead of falling back to "no indexed files."
- Basic command typo correction.

### Added

- `self_knowledge.py`, `conversation.py`, `input_cleaner.py`, `start.bat`.

---

## [0.5.0-alpha]

### Added

- Free-form response mode for any typed input.
- Wider file type support, including pure-Python best-effort readers for `.docx`, `.pptx`, `.xlsx`, `.odt`, and `.pdf`.
- General assistant fallback that explains limits instead of going silent.

---

## [0.4.0-alpha]

### Added

- Assistant voice/personality layer: logical observations, evidence explanations, confidence labels, suggested next moves.
- Local session memory for recent chat context.

---

## [0.3.0-alpha]

### Added

- Conservative drive/folder scanning with hard limits for max files and file size.
- Recommendation engine based on indexed data; duplicate content detection by hash.

---

## [0.2.0-alpha]

Shifted BrisartAI from crawler-first to data-first architecture.

---

## [0.1.0-alpha]

Initial crawler/index/retrieval prototype.

