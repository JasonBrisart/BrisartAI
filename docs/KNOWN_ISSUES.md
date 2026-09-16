# Known Issues

This file tracks open, non-trivial issues in BrisartAI that are not yet
resolved. Each entry follows a standardized bug-report template (modeled on
GitHub Issues / Jira) so severity, scope, and next steps stay consistent and
easy to scan.

For the deeper, ongoing design tradeoffs that apply to the whole project by
choice (lexical-only ranking with no semantic/embedding retrieval, the
recency signal using index time rather than true publication date,
contradiction detection being limited to numeric/negation mismatches, finite
hand-maintained vocabularies for intent/authority classification, etc.), see
[`docs/ARCHITECTURE.md`](ARCHITECTURE.md) instead — those are documented,
accepted design tradeoffs, not open bugs.

Fully fixed issues are moved to the **Resolved** section at the bottom of
this file rather than edited in place, so the open-issues list above always
reflects only what is genuinely still outstanding.

KI numbers are one continuous sequence assigned in the order an issue was
originally reported, regardless of whether it is later resolved — gaps
between the open list and the Resolved section are expected, not an error.

---

## KI-001: Founder/company classification is a finite, hand-maintained list

- **Reported date:** 2026-08-25 (carried forward; vocabulary last expanded 2026-08-30)
- **Severity:** Low
- **Environment:** All platforms; affects intent classification only.
- **Component:** `brisart_ai/intent.py` (`_KNOWN_COMPANIES`)
- **Steps to Reproduce:**
  1. Ask a founder-style question ("who founded X?") about a real company
     not present in `_KNOWN_COMPANIES`.
  2. Observe the intent `detect_intent()` assigns to the query.
- **Expected behavior:** The query should classify as `INTENT_FOUNDER` so
  company-history boost terms apply during ranking.
- **Actual behavior:** An unrecognized company name falls through to
  `INTENT_INVENTOR` classification instead — a safe, deliberate fallback
  (inventor boost terms still favor history/origin pages), not a crash or an
  obviously wrong result, but not the intended intent either.
- **Tried / Ruled out:** Guessing "is this token a company?" from surface
  form (capitalization, position in the sentence) alone was considered and
  rejected as unreliable; a wrong guess sends the query to the wrong intent
  entirely, which is worse than the current safe fallback. See
  `brisart_ai/tests/test_intent.py::TestDetectIntent::test_product_to_inventor`
  for the documented fallback behavior this relies on.
- **Next step:** Continue expanding `_KNOWN_COMPANIES` as real gaps are
  observed in practice.

---

## KI-002: Individual off-topic pages can still enter the index

- **Reported date:** 2026-08-26 (carried forward across multiple releases)
- **Severity:** Low
- **Environment:** All platforms; affects web ingestion only (`force_web`
  research and background crawling).
- **Component:** `brisart_ai/web/crawler.py`, `brisart_ai/web/search.py`
- **Steps to Reproduce:**
  1. Run a web search whose provider batch contains one on-topic-shaped but
     ultimately marginal page alongside genuinely relevant results.
  2. Observe that the marginal page is ingested rather than dropped.
- **Expected behavior:** N/A — fine-grained per-page relevance is a ranking
  concern to be resolved by scoring, not an ingestion-time hard filter.
- **Actual behavior:** Known dictionary/junk hosts and wholesale-unrelated
  provider batches are rejected at ingest time
  (`_partition_related_results()` judges each result individually, not the
  batch as a whole — see its resolution history below), but there is no
  positive per-page relevance gate; a marginal page can still be indexed and
  then simply rank last at query time.
- **Tried / Ruled out:** Per-result (not per-batch) relatedness partitioning
  was added specifically to remove the largest class of decoys (see KI-005
  in Resolved). A hard per-page ingestion gate was considered and deferred,
  to avoid discarding a page that is genuinely useful for a later, different
  query than the one that surfaced it.
- **Next step:** An optional positive relevance check at crawl time, gated
  so it never drops a page sharing real topic vocabulary with the query that
  found it.

---

## KI-003: Mojeek, Brave Search, and Startpage markup is unverified against a live fetch

- **Reported date:** 2026-08-26 (carried forward)
- **Severity:** Low
- **Environment:** Network-enabled runs only; affects these three search
  providers specifically (of the seven `web/search.py` tries).
- **Component:** `brisart_ai/web/search.py` (`_run_extra_provider`,
  `_extract_result_links`)
- **Steps to Reproduce:**
  1. Run a web search that falls through the provider chain to Mojeek, Brave
     Search, or Startpage.
  2. Compare the number of results returned against what a manual browser
     search for the same query returns.
- **Expected behavior:** The generic, domain-heuristic extractor (chosen
  because these three providers' markup is undocumented or shifts often)
  returns organic result links matching what a human would see.
- **Actual behavior:** The exact current HTML structure of these three has
  not been verified against a live fetch from outside the development
  sandbox. Zero results for a query known to have results most likely
  indicates a challenge/consent page, or markup drift the generic extractor
  can no longer see through.
- **Tried / Ruled out:** The domain-heuristic approach was chosen precisely
  so the parser degrades gracefully instead of breaking outright when markup
  changes, but graceful degradation was never confirmed against a real, live
  response from any of the three.
- **Next step:** Validate against a live fetch for all three providers (see
  `scripts/debug_provider_health.py`) and pin representative fixtures once
  confirmed.

---

## KI-004: Generic-concept-title vocabulary is a small, fixed list

- **Reported date:** 2026-08-26 (carried forward; vocabulary last expanded 2026-08-26)
- **Severity:** Low
- **Environment:** All platforms; affects ranking only.
- **Component:** `brisart_ai/intent.py` (`_GENERIC_CONCEPT_TITLES`,
  `is_bare_generic_concept_title()`)
- **Steps to Reproduce:**
  1. Ask a question whose best source is a bare-concept-titled page (e.g.
     `"X - Wikipedia"`) for a concept word not yet in
     `_GENERIC_CONCEPT_TITLES`.
  2. Observe that `generic_concept_title_adjust()` does not penalize it.
- **Expected behavior:** A page that is purely about an abstract concept in
  general (not the specific thing the query asked about) should be
  down-weighted relative to a specific answer.
- **Actual behavior:** The generic-concept-title penalty only fires for
  words on this fixed, hand-maintained list. A bare-concept page whose topic
  word isn't yet listed receives no penalty and can outrank a more specific
  source.
- **Tried / Ruled out:** N/A — the vocabulary-based approach was chosen
  deliberately for explainability over a general-purpose "is this page about
  an abstract concept?" classifier, which would require the kind of language
  understanding this project does not attempt.
- **Next step:** Continue expanding `_GENERIC_CONCEPT_TITLES` as real gaps
  are observed.

---

## KI-008: Recency ranking signal uses index time, not document publication date

- **Reported date:** 2026-09-16
- **Severity:** Low
- **Environment:** All platforms; affects ranking only, and only for
  corpora with a real mixture of source ages (a uniform-timestamp bulk
  import makes this signal inert by construction).
- **Component:** `brisart_ai/knowledge/ranker.py` (`_recency_multiplier`,
  `RECENCY_MAX_BOOST`, `RECENCY_HALFLIFE_DAYS`), `brisart_ai/web/crawler.py`
- **Steps to Reproduce:**
  1. Index a document with old real-world content today (`indexed_at` =
     now).
  2. Index a document with genuinely newer real-world content earlier
     (`indexed_at` = in the past).
  3. Ask a question both documents can answer and compare their recency
     multiplier.
- **Expected behavior:** The freshest genuinely-published source should
  receive the recency boost.
- **Actual behavior:** The recency multiplier (up to `+8%`, 45-day
  half-life) is computed from a source's `indexed_at` timestamp — when it
  entered the local index — not from the document's own publication or
  last-modified date. A stale document imported today reads as "fresh," and
  a genuinely recent document indexed weeks ago reads as "old."
- **Tried / Ruled out:** Using a real publication date was considered and
  deferred: `web/crawler.py` and `io/` do not reliably extract a
  trustworthy per-document date across the formats and pages BrisartAI
  ingests, and a *wrong* date is worse than a consistent, explainable
  index-time proxy. The multiplier is deliberately bounded
  (`RECENCY_MAX_BOOST = 0.08`) so this can never override the underlying
  term-based score even when it is wrong.
- **Next step:** Extract a document publication/last-modified date where
  one is reliably available (HTTP `Last-Modified`, common HTML meta tags,
  filesystem mtime for local files), store it alongside `indexed_at`, and
  prefer it for the recency signal when present — falling back to
  `indexed_at` otherwise.

---

## Template

Use this template for new entries:

```markdown
## KI-XXX: <short title>

- **Reported date:** YYYY-MM-DD
- **Severity:** Critical / High / Medium / Low
- **Environment:** <OS / Python version / affected module or provider>
- **Component:** <file(s) or module(s)>
- **Steps to Reproduce:**
  1. ...
- **Expected behavior:** ...
- **Actual behavior:** ...
- **Tried / Ruled out:** ...
- **Next step:** ...
```

A new entry is added HERE, in the open list, first — never directly to
Resolved. Before adding one, confirm it has a genuine, concrete next step;
a deliberate design decision or documented non-goal with no planned action
is not a known issue — it belongs in `docs/ARCHITECTURE.md` instead.

---

## Resolved

Closed issues are kept here (rather than deleted) so there is a durable
record of what used to be broken and how/when it was fixed. Each entry keeps
its original fields, with **Next step** replaced by **Resolved date** and
**Resolution** once the fix has actually landed.

### KI-005: Search-result snippets were not used in web ranking — RESOLVED

- **Reported date:** 2026-08-27
- **Severity:** Low
- **Environment:** All platforms; affected web ranking only.
- **Component:** `brisart_ai/web/crawler.py`, `brisart_ai/web/search.py`
- **Steps to Reproduce:** Inspect `score_result()` / `_score_detail()` in
  `web/crawler.py` prior to this fix; ask "what is the capital of france"
  and observe that "Paris - Wikipedia" (a bare entity-name title sharing no
  word with the query) is discarded before ranking ever sees it.
- **Expected behavior:** A result's description/snippet text, which most
  providers return alongside the title, should be available to relatedness
  judging and ranking, not just the URL and displayed title.
- **Actual behavior:** Only a result's URL and displayed anchor title were
  incorporated into web ranking and relatedness judging; the snippet text
  was parsed by some providers' extractors but discarded before it ever
  reached `_partition_related_results()` or `score_result()`.
- **Tried / Ruled out:** Title-awareness (URL + displayed title) was added
  and verified first, since the plumbing to preserve titles through the
  provider layer had to exist before snippets could be added on top of it.
- **Resolved date:** 2026-09-16
- **Resolution:** `web/search.py`'s `_ResultLinkParser` now captures a
  bounded (300-character) snippet of trailing description text for every
  one of the seven providers uniformly. `search_public_web()` gained an
  additive `with_snippets=True` return shape; the prior `with_titles=True`
  and bare-`list[str]` default shapes are byte-identical to previous
  behavior for every existing caller. `_partition_related_results()` now
  accepts either `(url, title)` pairs or `(url, title, snippet)` triples and
  folds the snippet into its whole-word relatedness check when present.
  `web/crawler.py`'s `score_result()` / `_score_detail()` / `rank_results()`
  / `explain_ranking()` all gained an optional snippet (or snippets map)
  parameter, weighting a snippet-only term match below a title match. Root
  caused against a direct reproduction of "what is the capital of france"
  incorrectly discarding "Paris - Wikipedia," which showed this was very
  likely the primary driver of BrisartAI's reported difficulty with generic
  web questions, not merely a low-severity nuance. Verified with 9 new tests
  across `web/tests/test_search.py` and `web/tests/test_crawler.py`,
  including explicit backward-compatibility checks confirming that omitting
  the new parameter reproduces prior scoring exactly.

### KI-007: Relevance feedback was wired into ranking but had no UI affordance to mark results — RESOLVED

- **Reported date:** 2026-09-16
- **Severity:** Low
- **Environment:** All platforms; affected the desktop UI only (the ranking
  engine itself was already applying feedback on every search).
- **Component:** `brisart_ai/knowledge/relevance_feedback.py`,
  `brisart_ai/ui/service.py`, `brisart_ai/ui/chat_panel.py`,
  `brisart_ai/ui/app.py`, `brisart_ai/knowledge/synthesizer.py`,
  `brisart_ai/core/conversation.py`
- **Steps to Reproduce:**
  1. Run the app and ask a question.
  2. Look for any control to tell BrisartAI a cited source was relevant or
     irrelevant.
- **Expected behavior:** A user marks a cited source good/bad, and
  subsequent searches in the same session nudge similar sources up or down.
- **Actual behavior:** `BrisartService` owned a single session-lifetime
  `RelevanceFeedback` store and applied it to every ranked search, and
  `BrisartService.mark_relevant()` / `mark_irrelevant()` existed and worked
  correctly in isolation, but `ui/chat_panel.py` rendered the transcript as
  plain text with no control that ever called them. The feedback loop was
  fully wired on the engine side but unreachable from the GUI, so the store
  stayed empty in normal use and had no effect on ranking.
- **Tried / Ruled out:** The store was deliberately built engine-first and
  bounded (`+/-25%`, clamped per term) so it was safe to always apply before
  any UI existed; wiring it into ranking without a trigger was the intended
  first step, not an oversight in the ranking layer itself.
- **Resolved date:** 2026-09-16
- **Resolution:**
  1. `knowledge/synthesizer.py`'s `synthesize()` and
     `core/conversation.py`'s `build_conversation_answer()` both gained an
     additive `citation_sink` list parameter that captures each cited
     source's `source_id` / `title` / `location` (and, for a compound
     question, which sub-question it belongs to) alongside the existing
     plain-text answer, with zero change to the return value when the
     parameter is omitted.
  2. `BrisartService.ask()` now refreshes `self.last_citations` on every
     call, each entry carrying a globally-unique 1-based `index`, and a new
     `mark_citation(index, relevant)` method resolves that index straight
     to the existing `mark_relevant()` / `mark_irrelevant()` calls.
  3. `ui/chat_panel.py`'s `ChatPanel` gained `render_citation_controls()`,
     embedding a small Relevant/Irrelevant button row under every cited
     answer via `Text.window_create()`; `ui/app.py`'s background answer
     worker now captures `last_citations` and wires button presses to
     `mark_citation()`.
  <br>
  Verified end to end offline: `mark_citation()` measurably shifts
  `RelevanceFeedback`'s term weight in the correct direction, and a compound
  question's citation indices stay globally unique even though each
  sub-answer's own in-text `[N]` bracket numbering independently restarts at
  1. 13 new tests added across `knowledge/tests/test_synthesizer.py`,
  `core/tests/test_conversation.py`, and `ui/tests/test_service_headless.py`.
  The three Tkinter-only widget methods this touches
  (`render_citation_controls`, `_on_answer_ready`, `_on_mark_citation`)
  remain outside the automated suite, consistent with every other Tkinter
  widget in the project, and were instead verified by exercising the exact
  same headless service-layer path the UI calls into.

### KI-006: The Brisart Native Stack was built and verified but not wired in — RESOLVED

- **Reported date:** 2026-09-13
- **Severity:** Medium
- **Environment:** All platforms.
- **Component:** `brisart_ai/native/*.py`; call sites in `util.py`,
  `blocklist.py`, `intent.py`, `web/search.py`, `web/policy.py`,
  `io/binary_readers.py`, `io/extractor.py`, `io/readers.py`,
  `core/settings.py`, `web/crawler.py`
- **Steps to Reproduce:** Inspect `util.py`'s hashing/URL functions,
  `web/search.py`'s JSON/Base64 handling, `web/policy.py`'s robots.txt
  handling, and `io/binary_readers.py`'s zlib decompression prior to this
  fix.
- **Expected behavior:** The seven modules under `native/` (each
  independently verified against the real stdlib function it replaces) are
  imported and used at the call sites they were built to replace.
- **Actual behavior:** The native modules existed on disk and passed their
  own self-tests, but nothing in the rest of `brisart_ai/` imported from
  `brisart_ai.native.*` — the stdlib equivalents were still in use
  everywhere.
- **Tried / Ruled out:** N/A — this was a completed-but-not-integrated
  feature, not a defect in either the stdlib call sites or the native
  modules themselves.
- **Resolved date:** 2026-09-13
- **Resolution:** All nine call sites now import their Brisart Native Stack
  equivalent. Actual HTTP networking (`urllib.request` / `urllib.error`) is
  unchanged, since the native stack replaces parsing logic, not the
  transport. Verified via a full compile check, all seven native modules'
  own self-tests, and zero regressions across the offline ranking replay
  fixtures.
