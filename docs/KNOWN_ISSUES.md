# Known Issues

This file tracks open, non-trivial issues in BrisartAI that are not yet resolved. Each entry follows a standardized bug-report template (modeled on GitHub Issues / Jira) so severity, scope, and next steps stay consistent and easy to scan.

Fully fixed issues are moved to the **Resolved** section at the bottom of this file rather than edited in place, so the open-issues list above always reflects only what is genuinely still outstanding.

---

## KI-002: Individual off-topic pages can still enter the index

- **Reported date:** 2026-08-26 (carried forward across multiple releases)
- **Severity:** Low (documented limitation, not a defect)
- **Environment:** All platforms; web ingestion only.
- **Component:** `brisart_ai/web/crawler.py`, `brisart_ai/web/search.py`
- **Steps to Reproduce:** Run a web search whose provider batch contains one on-topic-shaped but ultimately marginal page alongside genuinely relevant results.
- **Expected behavior:** N/A — fine-grained relevance is a ranking concern, not an ingestion-time filter.
- **Actual behavior:** Known dictionary/junk hosts and wholesale-unrelated batches are rejected at ingest time (`_partition_related_results()` judges each result individually, not just the batch as a whole), but there is no positive per-page relevance gate; a marginal page can still be indexed and then simply rank last.
- **Tried / Ruled out:** Per-result (not per-batch) relatedness partitioning was added specifically to remove the largest class of decoys. A hard per-page gate was considered and deferred, to avoid discarding a page that is genuinely useful for a later, different query.
- **Next step:** An optional positive relevance check at crawl time, gated so it never drops a page sharing real topic vocabulary with the query.

---

## KI-003: Provider recall limits retrieval

- **Reported date:** 2026-08-25 (carried forward)
- **Severity:** Low (inherent limitation, not a defect)
- **Environment:** All platforms; web research only.
- **Component:** `brisart_ai/web/search.py`
- **Steps to Reproduce:** Ask a question whose best source is never returned by any of the seven search providers.
- **Expected behavior:** N/A.
- **Actual behavior:** Ranking can only reorder sources that were actually retrieved; it cannot surface a source no provider returned in the first place.
- **Tried / Ruled out:** N/A — inherent to any ranking-over-retrieval design.
- **Next step:** None planned; noted here so it is not mistaken for a ranking defect.

---

## KI-004: Founder/company classification is a finite, hand-maintained list

- **Reported date:** 2026-08-25 (carried forward; vocabulary last expanded 2026-08-30)
- **Severity:** Low
- **Environment:** All platforms; intent classification only.
- **Component:** `brisart_ai/intent.py` (`_KNOWN_COMPANIES`)
- **Steps to Reproduce:** Ask a founder-style question about a real company not present in `_KNOWN_COMPANIES`.
- **Expected behavior:** N/A — the list is documented as intentionally finite.
- **Actual behavior:** An unrecognized company name falls through to inventor-style classification instead of founder classification — a safe, deliberate fallback, not a crash or an obviously wrong result.
- **Tried / Ruled out:** Guessing "is this token a company?" from surface form alone was considered and rejected as unreliable; a wrong guess sends the query to the wrong intent entirely, which is worse than a safe fallback.
- **Next step:** Continue expanding `_KNOWN_COMPANIES` as real gaps are observed.

---

## KI-005: Mojeek, Brave Search, and Startpage markup is unverified against a live fetch

- **Reported date:** 2026-08-26 (carried forward)
- **Severity:** Low
- **Environment:** Network-enabled runs only; these three providers specifically.
- **Component:** `brisart_ai/web/search.py`
- **Steps to Reproduce:** Run a web search that falls through to Mojeek, Brave Search, or Startpage.
- **Expected behavior:** The generic, domain-heuristic extractor (chosen because these three providers' markup is undocumented or shifts often) returns organic result links.
- **Actual behavior:** The exact current HTML structure of these three has not been verified against a live fetch from outside the development sandbox. Zero results for a query known to have results most likely indicates a challenge/consent page, or markup drift the generic extractor can no longer see through.
- **Tried / Ruled out:** The domain-heuristic approach was chosen precisely so the parser degrades gracefully instead of breaking outright when markup changes, but graceful degradation was never confirmed against a real, live response.
- **Next step:** Validate against a live fetch for all three providers and pin representative fixtures.

---

## KI-006: Search-result snippets are not used in web ranking

- **Reported date:** 2026-08-27 (carried forward)
- **Severity:** Low
- **Environment:** All platforms; web ranking only.
- **Component:** `brisart_ai/web/crawler.py`, `brisart_ai/web/search.py`
- **Steps to Reproduce:** Inspect `score_result()`/`_score_detail()` in `web/crawler.py`.
- **Expected behavior:** N/A.
- **Actual behavior:** Only a result's URL and displayed anchor title are incorporated into web ranking; the snippet/description text most providers also return is discarded.
- **Tried / Ruled out:** Title-awareness (URL + displayed title) was added and verified first, since the plumbing to preserve titles through the provider layer had to exist before snippets could be added on top of it.
- **Next step:** A natural follow-up now that title plumbing exists: fold snippet text into the same scoring pass.

---

## KI-007: Phrase-match scoring differs slightly between web and offline ranking

- **Reported date:** 2026-08-27 (carried forward)
- **Severity:** Low
- **Environment:** All platforms.
- **Component:** `brisart_ai/web/crawler.py` (`PHRASE_MATCH_BONUS`), `brisart_ai/knowledge/ranker.py` (`phrase_match_adjust()`)
- **Steps to Reproduce:** Compare how a phrase match is scored in `web/crawler.py` (a flat integer bonus added to a heuristic score) versus `knowledge/ranker.py` (a multiplicative factor applied to a Brisart Relevance Engine score).
- **Expected behavior:** N/A — deliberate, documented divergence, not an oversight.
- **Actual behavior:** Both paths share the same phrase-match *detection* logic (`knowledge.ranker.phrase_match_adjust()` is imported directly by `web/crawler.py`), but web ranking's own scoring scale is a small hand-tuned integer heuristic, where multiplying by a possibly-negative score was judged riskier than a flat, easily-explainable addition.
- **Tried / Ruled out:** Reusing the exact multiplicative factor in `web/crawler.py`'s integer-heuristic scoring was considered and rejected as riskier than the current flat-bonus approach.
- **Next step:** None currently planned; documented so the difference is never mistaken for a bug during future ranking work.

---

## KI-008: Generic-concept-title vocabulary is a small, fixed list

- **Reported date:** 2026-08-26 (carried forward; vocabulary last expanded 2026-08-26)
- **Severity:** Low
- **Environment:** All platforms; ranking only.
- **Component:** `brisart_ai/intent.py` (`_GENERIC_CONCEPT_TITLES`)
- **Steps to Reproduce:** Ask a question whose best source is a bare-concept-titled page (e.g. `"X - Wikipedia"`) for a concept word not yet in `_GENERIC_CONCEPT_TITLES`.
- **Expected behavior:** N/A.
- **Actual behavior:** The generic-concept-title penalty only fires for words on this fixed, hand-maintained list. A bare-concept page whose topic word isn't yet listed will not receive the penalty.
- **Tried / Ruled out:** N/A — vocabulary-based approach chosen deliberately for explainability over a general-purpose "is this page about an abstract concept" classifier.
- **Next step:** Continue expanding the list as real gaps are observed.

---

## Template

Use this template for new entries:

```markdown
## KI-XXX: <short title>
- **Reported date:** YYYY-MM-DD
- **Severity:** Critical / High / Medium / Low
- **Environment:** <OS / Python version / affected feature>
- **Component:** <file(s) or module(s)>
- **Steps to Reproduce:**
  1. ...
- **Expected behavior:** ...
- **Actual behavior:** ...
- **Tried / Ruled out:** ...
- **Next step:** ...
```

---

## Resolved

Closed issues are kept here (rather than deleted) so there is a durable record of what used to be broken and how/when it was fixed. Each entry keeps its original fields, with **Next step** replaced by **Resolved date** and **Resolution** once the fix has actually landed.

### KI-001: The Brisart Native Stack was built and verified but not wired in — RESOLVED

- **Reported date:** 2026-09-13
- **Severity:** Medium
- **Environment:** All platforms.
- **Component:** `brisart_ai/native/*.py`; call sites in `util.py`, `blocklist.py`, `intent.py`, `web/search.py`, `web/policy.py`, `io/binary_readers.py`, `io/extractor.py`, `io/readers.py`, `core/settings.py`, `web/crawler.py`
- **Steps to Reproduce:** Inspect `brisart_ai/util.py`'s hashing/URL functions, `web/search.py`'s JSON/Base64 handling, `web/policy.py`'s robots.txt handling, and `io/binary_readers.py`'s zlib decompression.
- **Expected behavior:** The seven modules under `brisart_ai/native/` (each independently verified against the real stdlib function it replaces) are imported and used at the call sites they were built to replace.
- **Actual behavior:** The native modules existed on disk but nothing in the rest of `brisart_ai/` imported from `brisart_ai.native.*`.
- **Tried / Ruled out:** N/A — this was a completed-but-not-integrated feature, not a defect in either the stdlib call sites or the native modules themselves.
- **Resolved date:** 2026-09-13
- **Resolution:** All 9 call sites now import their Brisart Native Stack equivalent: `util.py` (hashing + URL), `blocklist.py` and `intent.py` (URL), `io/extractor.py` (markup + URL), `io/readers.py` and `core/settings.py` (JSON), `io/binary_readers.py` (DEFLATE/zlib), `web/search.py` (Base64 + JSON + markup + URL), `web/policy.py` (robots + URL), and `web/crawler.py` (URL). Actual HTTP networking (`urllib.request`/`urllib.error`) is unchanged, since the native stack replaces parsing logic, not the network transport. Verified via full compile check, all 7 native modules' own self-tests, and zero regressions across the offline ranking replay fixtures.

### KI-R01: Startup crash on a locked or unopenable database — RESOLVED

- **Reported date:** 2026-08-30
- **Severity:** High
- **Environment:** All platforms.
- **Component:** `brisart_ai/ui/app.py`, `brisart_ai/ui/service.py`
- **Steps to Reproduce:** Launch BrisartAI while another copy already holds the index file, or from a read-only install folder.
- **Expected behavior:** A clear error dialog explaining the problem.
- **Actual behavior:** The Tk window was constructed before the backend, so a subsequent `sqlite3` failure opening the index raised a raw exception out of the constructor, leaving a half-built, invisible window behind with no dialog ever shown.
- **Tried / Ruled out:** N/A — root cause was construction order, not the exception handling itself.
- **Resolved date:** 2026-08-30
- **Resolution:** `BrisartApp.__init__()` now constructs `BrisartService` (and therefore opens the SQLite index) **before** the Tk window is created. `run()` wraps app construction in a single `try/except` and shows a `messagebox.showerror()` dialog on failure. Verified with a standalone simulation confirming zero window-like objects are created on the failure path.

### KI-R02: Duplicate, drifted function-word list in web search — RESOLVED

- **Reported date:** 2026-08-30
- **Severity:** Medium
- **Environment:** All platforms; web search only.
- **Component:** `brisart_ai/web/search.py`, `brisart_ai/blocklist.py`
- **Steps to Reproduce:** Compare `web/search.py`'s own `FUNCTION_WORDS` list against `blocklist.py`'s canonical list.
- **Expected behavior:** One canonical list, imported everywhere it's needed.
- **Actual behavior:** `web/search.py` maintained its own second, hand-copied `FUNCTION_WORDS` list that could silently drift out of sync with `blocklist.py`'s canonical version, letting a genuinely off-topic result be marked "related."
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-30
- **Resolution:** `web/search.py` now imports `FUNCTION_WORDS` directly from `blocklist.py`.

### KI-R03: MediaWiki-style citation markers leaking into extracted text — RESOLVED

- **Reported date:** 2026-08-26
- **Severity:** Medium
- **Environment:** All platforms; HTML extraction.
- **Component:** `brisart_ai/io/extractor.py`
- **Steps to Reproduce:** Extract text from a Wikipedia (or Wikipedia-mirror) page containing an inline citation marker, e.g. `<sup class="reference">[3]</sup>`.
- **Expected behavior:** The footnote marker should not appear as ordinary body text.
- **Actual behavior:** Observed live on the query "what is america?" — a stray `[ 3 ]` fragment was glued onto the start of extracted content and, visibly, onto the start of quoted answer sentences.
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-26
- **Resolution:** `HTMLTextExtractor` now skips `<sup>` elements carrying a `reference`, `cite-bracket`, or `citation` class, scoped narrowly enough that an ordinary superscript (e.g. "10^2") is untouched.

### KI-R04: Decoy/off-topic search results riding alongside genuinely relevant ones — RESOLVED

- **Reported date:** 2026-08-26
- **Severity:** Medium
- **Environment:** All platforms; web search only.
- **Component:** `brisart_ai/web/search.py`
- **Steps to Reproduce:** Observed live: a "2025 Tesla vandalism" Wikipedia page surfaced as a source for "what is america?"; a "Nikola Tesla" page surfaced for a Trump-legislation query — in both cases sitting next to 2-3 genuinely relevant results.
- **Expected behavior:** A single unrelated result should not ride along inside an otherwise-good batch.
- **Actual behavior:** The prior whole-batch guard only asked "does *anything* in this batch match?", which a couple of genuinely relevant results was enough to satisfy.
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-26
- **Resolution:** Replaced with `_partition_related_results()`, judging each `(url, title)` result individually. The original whole-batch safety valve is preserved as a fallback: if partitioning would drop every result, that is still treated as a throttled/decoy response and the whole batch is discarded.

### KI-R05: Generic instructional verbs winning on title match — RESOLVED

- **Reported date:** 2026-08-26
- **Severity:** Medium
- **Environment:** All platforms; ranking only.
- **Component:** `brisart_ai/knowledge/ranker.py`
- **Steps to Reproduce:** Observed live: "explain who jason brisart is and where does he live" surfaced a dictionary page titled "Understanding 'Explain' — Meaning, Usage, and Examples" instead of the user's own indexed research documents.
- **Expected behavior:** A generic instructional verb like "explain" should not out-compete a genuinely specific, rare term for title-match credit.
- **Actual behavior:** Title-match weighting used corpus rarity (IDF) alone; in a small or freshly-crawled index, a generic word appearing in only one document looks exactly as "rare" as a genuinely specific term.
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-26
- **Resolution:** `title_match_adjust()` now dampens a fixed set of generic instructional/question verbs (`GENERIC_QUERY_VERBS`) to at most 20% of what an equally-rare specific term contributes.

### KI-R06: Bare generic-concept pages outranking specific answers — RESOLVED

- **Reported date:** 2026-08-26
- **Severity:** Medium
- **Environment:** All platforms; ranking only.
- **Component:** `brisart_ai/intent.py`, `brisart_ai/knowledge/ranker.py`
- **Steps to Reproduce:** Observed live: "what laws have been passed since trump became president" (classified `INTENT_GENERAL`) surfaced a bare "Law - Wikipedia" page ahead of genuinely relevant sources.
- **Expected behavior:** A page about the abstract concept of law in general should not outrank a page about specific, relevant legislation.
- **Actual behavior:** The existing generic-concept-page guard only ran inside `score_intent()`, which is skipped entirely for `INTENT_GENERAL` queries — so any question not classified into one of the five specific intents received no protection at all.
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-26
- **Resolution:** Added `is_bare_generic_concept_title()` (correctly stripping " - Site Name" suffixes) and `generic_concept_title_adjust()`, applied unconditionally regardless of detected intent.

### KI-R07: Long articles outranking shorter, more relevant ones — RESOLVED

- **Reported date:** 2026-08-26
- **Severity:** Medium
- **Environment:** All platforms; ranking only.
- **Component:** `brisart_ai/knowledge/ranker.py` (superseded by `brisart_ai/knowledge/relevance_engine.py`)
- **Steps to Reproduce:** Observed live: a previously-crawled, very long "South Africa - Wikipedia" article surfaced as a source for a Trump/US-laws question, because it happened to mention "president" and "law" several times across its length.
- **Expected behavior:** Raw term frequency should not let an extremely long, broad article outrank a short, genuinely on-topic document.
- **Actual behavior:** Raw term frequency could not distinguish "genuinely dense in this topic" from "long enough to mention this word a dozen times in passing."
- **Tried / Ruled out:** N/A.
- **Resolved date:** 2026-08-26 (BM25-style length normalization); superseded by the Brisart Relevance Engine's shape brackets, which go further and actively boost short, focused documents rather than only declining to penalize long ones.
- **Resolution:** Verified a long-vs-short South-Africa/Trump-laws matchup: the short, relevant document wins; a long *and* genuinely relevant document still beats both a short relevant document and a long irrelevant one.

### KI-R09: No formal automated unit-test suite — RESOLVED

- **Reported date:** 2026-08-25 (carried forward across every release through 1.0.0-beta.10)
- **Severity:** Medium
- **Environment:** All platforms; whole-repository.
- **Component:** Repository-wide.
- **Steps to Reproduce:** Look for a `tests/` directory, `pytest`/`unittest` configuration, or CI workflow.
- **Expected behavior:** Core logic (tokenization, intent, blocklist, indexing, ranking, synthesis) would ideally have automated regression coverage.
- **Actual behavior:** `scripts/debug_offline_replay.py` and `scripts/debug_search_replay.py` provided repeatable, inspectable validation, but neither was a `unittest`/`pytest` suite.
- **Tried / Ruled out:** The replay scripts were judged sufficient for the project's solo-maintained scale at the time, but did not substitute for automated coverage of non-ranking logic (parsers, blocklist, settings, vault).
- **Resolved date:** 2026-09-13
- **Resolution:** Added a 379-test suite, co-located with source (one `tests/` subfolder per `brisart_ai/` package). Pure `unittest.TestCase` classes with zero external test dependencies; `pytest` (configured via `pytest.ini`) is used only as the discovery runner, since `brisart_ai/`'s deliberate lack of `__init__.py` files conflicts with `unittest discover`'s recursive package requirement. See `docs/TESTING.md`.
