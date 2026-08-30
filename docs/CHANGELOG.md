# Changelog

---

## [1.0.0-beta.9] - 2026-08-30

### Fixed

#### Startup Crash on a Locked or Unopenable Database
- `ui/app.py`: `BrisartApp.__init__()` now constructs the backend
  `BrisartService` (and therefore opens the SQLite index and session
  database) **before** the Tk window is created, not after. `run()`
  wraps app construction in a single `try/except` and shows a proper
  `messagebox.showerror()` dialog on failure instead of letting the
  exception propagate into an unhandled console traceback.
  - Root cause: previously the Tk window was built first, and a
    subsequent failure opening the SQLite index (locked by another
    running copy of BrisartAI, a read-only install folder, missing
    file permissions, etc.) raised a raw `sqlite3` exception straight
    out of the constructor. This left a half-built, invisible window
    behind with no dialog ever shown -- the "Database startup errors
    remain raw" limitation documented in `README.md` since beta.2.
  - `ui/service.py`'s `BrisartService.__init__()` is now documented as
    deliberately unguarded: it must be allowed to raise so `run()`'s
    single catch site is the only place startup failures are handled,
    rather than being silently swallowed partway through service setup.
  - Verified with a standalone simulation reproducing the exact
    construction order: on failure, zero window-like objects are ever
    created, confirming `run()`'s `except` branch is reached before any
    UI exists to leave in a broken state; on success, the window is
    still created exactly once, unchanged from prior behavior.

#### Duplicate, Drifted Function-Word List in Web Search
- `web/search.py`: `FUNCTION_WORDS` (used by `_partition_related_results()`
  to decide which query words are "meaningful" for judging whether a
  search result is on-topic) is no longer a second, hand-maintained
  word list -- it now imports the single canonical list from
  `brisart_ai/blocklist.py`.
  - Root cause: this module's local copy had silently drifted from the
    shared list and was missing common words present there (e.g.
    "about", "into", "over"). A query like "give me info about cats"
    treated "about" as a meaningful topic term, so a completely
    off-topic result that merely also contained the word "about" could
    be marked "related" and pass through untouched.
  - This is the same class of bug `blocklist.py`'s own docstring already
    warns about ("previously each kept its own copy and they had
    drifted out of sync") -- it just hadn't been caught here yet.
  - Also removes, as a side effect, a dead two-word `"give me"` entry
    that could never match anything: query terms are tokenized into
    single words before this set is consulted, so a multi-word entry
    was always inert.
  - Verified with a synthetic two-result batch ("All About Cats" /
    "All About Dogs" for the query "give me info about cats"): before
    this fix, both results were incorrectly marked related; after, only
    the genuinely on-topic result is.

#### Founder/Company Recognition Vocabulary Expanded
- `intent.py`: `_KNOWN_COMPANIES` (used to classify a "who
  invented/founded X" question as a founder question rather than the
  generic inventor default) now recognizes an additional ~25 well-known
  single-token company names across streaming, gig-economy, fintech,
  gaming, and productivity software (Twitch, DoorDash, Notion, Figma,
  Palantir, Snowflake, Slack, Zoom, Roblox, and others).
  - Root cause: any company not in this fixed, hand-maintained list
    silently fell back to the inventor-intent default, which uses
    different (and less appropriate) boost/penalty vocabulary for a
    company-history question. This is a vocabulary-only change; an
    unrecognized company still falls back exactly as before -- nothing
    about the fallback behavior itself changed.
  - Verified: `who founded twitch?` / `notion?` / `figma?` / `palantir?`
    / `databricks?` / `roblox?` now all classify as the founder intent
    (previously: inventor).

### Verification
- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero
  regressions (this release does not modify `knowledge/ranker.py`).
- Re-ran the full 1.0.0-beta.8 crawler test suite (title-awareness,
  phrase-awareness, backward compatibility) after the `FUNCTION_WORDS`
  consolidation fix above; all still pass.
- Re-ran the mocked end-to-end pipeline test from beta.8 (search ->
  title-aware rank -> crawl -> index -> synthesize) after all beta.9
  changes; the correct source is still cited and the off-topic page is
  still excluded.

### Known Limitations
- No formal automated unit-test suite or CI pipeline exists yet; the
  replay scripts and the ad hoc verification described in each release
  remain the primary form of regression checking (carried forward from
  earlier releases).
- The crawl-time relevance check is still ranking-based, not a hard
  gate: a page can still enter the index even when it will end up
  ranked last for every query (carried forward from beta.3).

---

## [1.0.0-beta.8] - 2026-08-29

### Added

#### Title- and Phrase-Aware Public Web Ranking
- `web/search.py`: `search_public_web()` now accepts an optional
  `with_titles` parameter. When `True`, it returns `list[tuple[str,
  str]]` of `(url, title)` pairs instead of a bare `list[str]` of URLs
  -- every provider already parsed out a result's displayed title
  internally (to judge relatedness), but it was previously discarded
  before reaching the caller. The default (`with_titles=False`)
  reproduces the exact prior return type and behavior, so no existing
  caller needed to change.
- `web/crawler.py`: `score_result()`, `rank_results()`, and
  `explain_ranking()` all accept an optional `title`/`titles` argument
  and now fold a result's own displayed title into its relevance score
  on equal footing with its hostname -- a topic term found only in the
  title (not the URL) now earns the same credit a hostname match would.
  A literal, contiguous multi-word phrase match against the combined
  URL+title text now also earns a flat scoring bonus, with phrase
  detection delegated to
  `knowledge.ranker.phrase_match_adjust()` so web and offline ranking
  cannot silently disagree about what counts as a "phrase match".
  `web_search_and_ingest()` now requests titles from both the natural-
  phrasing and keyword-fallback searches and threads them through to
  ranking.
  - Root cause / motivation: this closes a limitation documented since
    beta.4 -- "Public web ranking still evaluates URLs only. Page
    titles and search-result snippets are not yet incorporated into
    ranking decisions." Many ordinary result URLs (news articles,
    non-wiki pages) carry an opaque numeric ID or truncated slug with
    none of the query's meaningful words; the words that actually
    answer the question typically live only in the page's title, which
    the URL-only scorer could never see.
  - Verified with a synthetic two-result batch for "how much does a
    blue whale weigh": two identically-shaped opaque numeric-slug URLs
    (`/articles/48213`, `/articles/48214`) scored identically (-2, -2)
    with no title information; once each result's real title was
    supplied, the on-topic result ("How Much Does a Blue Whale Weigh?
    Scientists Reveal the Answer") scored 14 against the off-topic
    result's unchanged -2, and correctly ranked first.
  - Verified the phrase-match bonus separately: a title containing the
    literal contiguous phrase "history of the transistor" scored higher
    (10) than a title containing the identical words in scrambled order,
    "Transistor History Notes and Timeline" (6).
  - Verified full backward compatibility: scoring the same two
    Wikipedia transistor URLs used in prior releases' regression cases,
    with no title supplied, produces the exact same relative ordering
    as before this change.
  - `scripts/debug_search_replay.py` updated to request titles via
    `with_titles=True` and display each result's title, whether a
    phrase match fired, and the full per-component score breakdown, so
    a replay can show whether a result's title -- not just its URL --
    is what moved it up or down.

#### Broader Numeric/Quantity Detection in Answer Synthesis
- `knowledge/synthesizer.py`: `_HAS_QUANTITY` now also recognizes
  currency figures (a leading `$`/`€`/`£` directly against digits, or
  the words "dollars"/"usd"), distances (km, miles, meters, feet),
  mass (kg, pounds, tons), and time units (years, months, weeks, days,
  hours, minutes, seconds), in addition to the original population/
  demographic unit set (million, billion, percent, households, etc.).
  - Root cause: a statistic-style question whose answer is a distance,
    a weight, or a dollar figure rather than a population count (e.g.
    "how much does a blue whale weigh", "what did the Louisiana
    Purchase cost") previously had no unit-word match at all and fell
    back to the much weaker bare-digit signal, which does not
    reliably surface the sentence containing the actual figure.
  - Verified against six representative sentences (population figures,
    currency figures, mass figures, distance figures, a sentence with
    no numbers, and a bare year) -- the broadened pattern correctly
    matches the first four and correctly still does *not* match a bare
    year on its own (which continues to fall back to the pre-existing,
    weaker bare-digit signal, exactly as before).

#### Founder/Company Recognition Vocabulary
- See the 1.0.0-beta.9 entry above -- the company-vocabulary expansion
  originally intended for this release was verified and shipped
  together with beta.9's other fixes to keep this release focused on
  ranking quality.

### Verification
- Re-ran all 4/4 `scripts/debug_offline_replay.py` fixtures; zero
  regressions (this release does not modify `knowledge/ranker.py`
  itself, only reuses one of its existing public functions from
  `web/crawler.py`).
- Full mocked end-to-end pipeline test (search -> title-aware rank ->
  crawl -> index -> synthesize) for "how much does a blue whale weigh":
  confirmed the correctly-titled article is both ranked first and cited
  as the sole source, and the off-topic weather article is excluded
  from the synthesized answer entirely.

### Known Limitations
- Search-result snippets (as opposed to titles) are still not
  incorporated into web ranking; only the displayed anchor title is
  used. Adding snippet text is a natural next step now that the
  plumbing to preserve titles exists.
- The phrase-match bonus in `web/crawler.py` is a flat integer bonus
  (`PHRASE_MATCH_BONUS`), not the multiplicative factor
  `knowledge.ranker.phrase_match_adjust()` itself returns -- this is
  deliberate (see that constant's docstring for why multiplying a
  small, possibly-negative integer heuristic score was judged riskier
  than a flat, easily-explainable addition), but it does mean the two
  ranking paths share phrase *detection* logic without sharing an
  identical phrase *scoring* formula.
- The exact current HTML structure of Mojeek, Brave Search, and
  Startpage remains unverified against a live fetch (carried forward
  from beta.7).

---

## [1.0.0-beta.7] - 2026-08-26

### Fixed

#### Text Extraction
- `io/extractor.py`: `HTMLTextExtractor` no longer leaks MediaWiki-style
  inline citation markers (e.g. Wikipedia's `<sup class="reference">
  [3]</sup>`) into extracted text. Previously these superscript
  footnote markers were extracted as ordinary body text, producing a
  stray `[ 3 ]` fragment glued onto the start of indexed content and,
  visibly, onto the start of quoted answer sentences (observed live on
  the query "what is america?").
  - Scoped narrowly to `<sup>` elements carrying a `reference`,
    `cite-bracket`, or `citation` class, so ordinary superscript text
    (e.g. a unit like "10^2 meters") is left untouched.

#### Startup Crash
- Removed the dependency on a separate `web/search_extra_providers.py`
  module entirely. That split caused a real production crash: the
  companion file existed on disk but was accidentally left empty, and
  `search.py`'s top-level `from ... import search_brave, search_mojeek,
  search_startpage` raised an `ImportError` before the application
  could even start (`ImportError: cannot import name 'search_brave'
  from 'brisart_ai.web.search_extra_providers'`). Every search provider
  now lives directly in `web/search.py`, so there is nothing else that
  needs to exist, nothing else that can be left blank, and nothing else
  to keep in sync.

#### Decoy / Off-Topic Search Results
- `web/search.py`: replaced the whole-batch `_results_look_unrelated()`
  guard with `_partition_related_results()`, which judges each
  `(url, title)` result individually against the query instead of
  asking "does *anything* in this batch match?" A single genuinely
  unrelated result can no longer ride along inside an otherwise-good
  batch.
  - Observed live: a "2025 Tesla vandalism" Wikipedia page surfaced as
    a source for "what is america?", and a "Nikola Tesla" page
    surfaced for a Trump-legislation query -- in both cases sitting
    next to 2-3 genuinely relevant results, which was enough for the
    old whole-batch check to wave the entire batch through unfiltered.
  - The original whole-batch safety valve is preserved as a fallback:
    if partitioning would drop every single result in a batch, that is
    still treated as a throttled/decoy provider response and the whole
    batch is discarded so the next provider gets a chance.

#### Ranking: Generic Words Winning on Title Match
- `knowledge/ranker.py`: `title_match_adjust()` now dampens a fixed set
  of generic instructional/question verbs (`GENERIC_QUERY_VERBS` --
  "explain", "describe", "define", "summarize", etc.) so they
  contribute at most 20% of what an equally-rare specific term
  contributes to the title-match bonus.
  - Root cause: title-match weighting used corpus rarity (IDF) alone.
    In a small or freshly-crawled index, a generic word that happens to
    appear in only one indexed document looks exactly as "rare" by IDF
    as a genuinely specific term -- IDF cannot tell "explain" apart
    from a person's surname when both have a document frequency of 1.
  - Observed live: "explain who jason brisart is and where does he
    live" surfaced a dictionary page titled "Understanding 'Explain' --
    Meaning, Usage, and Examples" instead of the user's own indexed
    research documents, purely because "explain" earned a full,
    undamped title-match bonus.

#### Ranking: Bare Generic-Concept Pages Outranking Specific Answers
- `intent.py`: added `is_bare_generic_concept_title()`, which detects
  when a document's title or URL-derived slug is nothing more than a
  single bare abstract concept word (e.g. `"Law"` or `"Law -
  Wikipedia"`), correctly stripping common `" - Site Name"` suffixes
  before comparison. Extended the generic-concept vocabulary with
  `law`, `legislation`, `politics`, and `government`.
- `knowledge/ranker.py`: added `generic_concept_title_adjust()`, which
  applies a fixed 0.35x penalty to any document matching the above,
  applied unconditionally regardless of detected intent.
  - Root cause: the existing generic-concept-page guard
    (`is_generic_concept_page`, used for the "Invention"/"Invented
    (album)" class of bug) only ever ran inside `score_intent()`,
    which `ranker.py` skips entirely for `INTENT_GENERAL` queries. Any
    ordinary question that didn't classify into one of the five
    specific intents (founder/inventor/statistic/explanation/
    comparison) silently received no protection at all.
  - Observed live: "what laws have been passed since trump became
    president" (classified `INTENT_GENERAL`) surfaced a bare
    `"Law - Wikipedia"` page -- an article about the abstract concept
    of law, not about any Trump-era legislation -- ahead of genuinely
    relevant sources.

#### Ranking: Long Articles Outranking Shorter, More Relevant Ones
- `knowledge/ranker.py`: added BM25-style document-length
  normalization (`LENGTH_NORM_B = 0.6`) to the base TF-IDF scoring
  pass. Each term's raw contribution is now divided by a factor that
  scales with how much longer than the corpus average a document is,
  computed once per query via a single aggregate SQL query
  (`_load_document_lengths()`).
  - Root cause: raw term frequency has no way to distinguish "this
    document is genuinely dense in this topic" from "this is an
    extremely long, broad article that mentions this word a dozen
    times in passing simply because it is long."
  - Observed live: a previously-crawled, very long "South Africa -
    Wikipedia" article (left over from an earlier, unrelated query in
    the same session) surfaced as a source for a Trump/US-laws
    question, because it happened to mention "president" and "law"
    several times across its length.
  - Verified this does not over-correct: a long document that is
    genuinely dense in on-topic terms (high coverage, not just high
    raw frequency) still outranks a shorter, less-detailed relevant
    document, and a long off-topic document still ranks last despite
    its raw term mass.

### Added

- `web/search.py` now includes three additional sequential fallback
  providers -- **Startpage, Brave Search, and Mojeek** -- fully
  self-contained in this single file.
  - Result parsing for these three avoids hardcoded CSS class names.
    Brave's own published scraping notes describe their markup as
    "unlabeled" and something that "shift[s] often"; Startpage has no
    stable public documentation of its markup either. Instead, results
    are identified by domain heuristics (a result's host must differ
    from the search engine's own host and must not be a
    help/support/account/static subdomain of it), so the parser
    degrades gracefully instead of silently breaking outright the next
    time either site's markup changes.
  - Includes a shared bot-challenge / consent-wall detector reused
    across all three new providers.
- **Provider chain reordered by block-risk, not by establishment.** The
  full 7-provider chain now runs **Startpage → Brave Search →
  DuckDuckGo HTML → DuckDuckGo Lite → Bing HTML → Mojeek → Wikipedia
  API** -- from most likely to be blocked/challenged to least likely --
  so the riskiest request is always spent first and each subsequent
  provider is both a fallback for the ones before it and a strictly
  safer bet in its own right. The Wikipedia API remains last as a
  documented, stable, key-free floor on quality.

### Verification

- Re-ran the exact citation-marker repro from the live "what is
  america?" session; confirmed `[ 3 ]` no longer appears in extracted
  or displayed text.
- Confirmed the merged, single-file `web/search.py` imports cleanly
  with zero external dependency beyond its existing four imports
  (`blocklist`, `util`, `web.fetcher`, `web.policy`), and re-verified
  the full 7-provider risk-ordered fallback chain cascades correctly
  end-to-end.
- Re-ran the exact "what is america?" and "what laws have been passed
  since trump became president" batches that previously surfaced the
  Tesla-vandalism and Nikola-Tesla decoys; confirmed both are now
  dropped individually while their genuinely relevant batch-mates are
  kept.
- Rebuilt the exact "Understanding 'Explain'" vs. Jason Brisart
  research-document matchup and confirmed the research document now
  wins.
- Rebuilt the exact "Law - Wikipedia" vs. "Trump Administration
  Accomplishments" matchup and confirmed the relevant page now wins
  (6.44 vs. 0.32 in test scoring).
- Rebuilt a long-vs-short South-Africa/Trump-laws matchup and confirmed
  the short, relevant document now wins; separately confirmed a long
  *and* genuinely relevant document still beats both a short relevant
  document and a long irrelevant one.
- Re-ran all prior beta.6 ranking regression cases (founder-intent
  ordering, specific-term title-match credit, comparison-intent
  classification) with zero regressions introduced by any of the fixes
  in this release.

### Known Limitations

- The exact current HTML structure of Mojeek, Brave Search, and
  Startpage has not been verified against a live fetch from outside
  the development sandbox. If one of these providers returns zero
  results against a query known to have results, it is likely serving
  a challenge/consent page, or its markup has changed enough that the
  generic domain-based extractor can no longer find outbound links.
- The generic-concept-title vocabulary (`law`, `legislation`,
  `politics`, `government`, etc.) is a small, fixed, hand-maintained
  list; a bare-concept page whose topic word isn't yet in that list
  will not receive this penalty.
- Document-length normalization uses total indexed term count as a
  proxy for document length, not a stored character/byte count; this
  is consistent with the rest of the module's term-based arithmetic
  but is an approximation.

---

## [1.0.0-beta.6] 2026-08-26

### Added
- Title-match ranking signal in `knowledge/ranker.py`. A document whose
  own title contains meaningful query terms now receives an explicit
  score multiplier (up to 1.42x), separate from ordinary TF-IDF credit.
  Previously a term appearing once in a short, on-topic title counted
  for no more than the same term buried once in a large, mostly
  unrelated body -- title matches are much stronger relevance evidence
  and are now rewarded as such.
- Phrase-match ranking signal in `knowledge/ranker.py`. When the literal
  query text appears as a contiguous phrase anywhere in a document's
  title, location, or body, the score receives a flat 1.35x multiplier.
  Bag-of-words TF-IDF scoring is blind to word order and adjacency, so a
  search for an exact note title or quoted phrase previously got no
  more credit than a document containing the same words scattered far
  apart. Only applies to multi-word queries; a single meaningful word
  already gets full credit from ordinary term scoring.
- `knowledge/vault.reindex_missing_notes()`, which walks all saved notes
  at startup and indexes any that predate note-mirroring (see below).
  Existing notes silently gain full ranked search the next time the app
  runs -- no re-saving, no new setting, nothing for the user to do.
- `knowledge/ranker.search()` now accepts an optional `source_types`
  parameter (a set of allowed source types, e.g. `{"web", "file",
  "note"}`), used to combine multiple source kinds into a single ranked
  query. The prior single-value `source_type` parameter is unchanged and
  still supported for existing callers.

### Changed
- `knowledge/vault.add_note()` now mirrors every saved note into the
  main `sources` index (`source_type="note"`) in addition to the
  vault's own `notes` table. Notes are no longer a second-class,
  separately-scored data source -- they now receive the exact same
  TF-IDF, coverage, title-match, phrase-match, and intent-aware ranking
  as imported files and crawled web pages.
- `core/conversation.py` no longer merges notes into results via a
  separate substring-count pass. `build_conversation_answer()` now
  builds one `source_types` set from the existing `search_local_files`
  and `search_notes` settings (`web` is always included, `file` and
  `note` are added per-toggle) and passes it directly to
  `knowledge/ranker.search()`, so all local evidence is scored through
  one unified ranking model instead of two different ones.
- `ui/service.py` calls `reindex_missing_notes()` once during
  `BrisartService.__init__()`, alongside the existing stale-web-source
  cleanup, and logs how many notes were backfilled.

### Notes API (unchanged surface, updated behavior)
- `knowledge/vault.search_notes()` and `search_notes_as_documents()` are
  retained as lightweight, dependency-free substring-search helpers for
  direct/CLI callers, but are no longer used by the main conversation
  pipeline. They are documented in-source as the legacy path.

### Verification
- Confirmed a title-matching document ranks above a longer, non-titled
  document containing the same query terms (new title-match signal).
- Confirmed a document containing the literal query phrase ranks above
  a document containing the same words non-contiguously (new
  phrase-match signal).
- Confirmed a note inserted directly into the `notes` table (simulating
  a pre-beta.6 save) is invisible to ranked search until
  `reindex_missing_notes()` runs, then becomes fully ranked with zero
  user action.
- Confirmed a note added through the current `add_note()` is
  immediately ranked with no reindex step required.
- Confirmed the settings surface is unchanged: exactly the same 3
  toggles as beta.5 (`search_local_files`, `search_notes`,
  `auto_web_research`); no new toggle was introduced.
- Confirmed `search_notes` on/off still fully gates whether notes
  surface in an answer, end-to-end through
  `core.conversation.build_conversation_answer()`.
- Re-ran the founder-intent regression case ("who invented microsoft?")
  to confirm the new title-match and phrase-match signals compose
  correctly with the existing intent-aware layer and do not regress it;
  "History of Microsoft" still outranks "Microsoft PowerPoint."
- Confirmed the legacy single-value `source_type` parameter on
  `ranker.search()` (e.g. `source_type="web"`) still works unchanged.

### Known Limitations
- Phrase-match detection is a literal substring check after punctuation
  normalization; it does not account for synonyms, stemming, or word
  reordering within the phrase.
- Title-match and phrase-match bonuses are applied uniformly regardless
  of detected intent; they are not currently intent-scoped the way
  boost/penalty vocabulary is.
- Collections and entity extraction remain implemented in
  `knowledge/vault.py` but are still not exposed through the desktop UI
  (carried forward from earlier releases).

## [1.0.0-beta.5] 2026-08-26

### Added
- New `comparison` intent class in `brisart_ai/intent.py`, shared by both
  web ranking and offline ranking. Questions like "do dogs outlive cats"
  or "which is bigger, a lion or a tiger" were previously invisible to
  the shared intent classifier -- only `knowledge/synthesizer.py` had
  private, duplicate logic for detecting them, and that logic never fed
  into search ranking at all.
- `knowledge/vault.py`: `search_notes_as_documents()`, which converts
  saved vault notes into the same document shape produced by
  `knowledge/ranker.search()` (score, source_type, location, title,
  text, intent fields), so notes can be merged into the same answer
  pipeline as files and web pages.

### Fixed
- `knowledge/synthesizer.py` no longer maintains its own separate
  query-intent detector. `query_wants_quantity()`,
  `query_wants_comparison()`, and `query_wants_reason()` now delegate
  directly to `brisart_ai.intent.detect_intent()` instead of running an
  independent regex-based classifier that could silently disagree with
  the one used for ranking.
- The `search_notes` setting previously had no effect. Saved notes live
  in a separate database table from the main file/web source index and
  were never queried by `core/conversation.py`; turning the toggle on
  changed nothing. `build_conversation_answer()` now merges
  `search_notes_as_documents()` results into the local evidence pool
  whenever the setting is enabled.
- The `search_local_files` setting is now actually applied during
  search. `core/conversation.py` restricts local search to previously
  indexed web pages only when this setting is off, instead of reading
  the setting without using it.

### Removed
- The "Research Collections" toggle in `core/settings.py` and the
  Settings dialog. It rendered as a live checkbox but had no effect --
  there is no "active collection" concept anywhere in the current UI
  for it to restrict. Removed rather than fake-wired; re-add once a
  real collection-scoped search UX exists.

### Changed
- `core/settings.py`: `DEFAULT_SETTINGS` and `TOGGLE_LABELS` reduced
  from four entries to three (`search_local_files`, `search_notes`,
  `auto_web_research`). Existing `data/research_settings.json` files
  with a stale `search_collections` key are read safely; the unknown
  key is simply ignored on load.
- `core/conversation.py`: local search now runs through an internal
  `_gather_docs()` step that applies both the file/web source-type
  filter and the notes merge before checking whether any evidence
  exists, rather than a single unconditional `search()` call.
- Bumped BrisartAI version from `1.0.0-beta.4` to `1.0.0-beta.5`.
- Moved `CHANGELOG.md` to `docs/CHANGELOG.md` to keep documentation
  organized alongside the rest of the docs folder.

### Verification
- Re-ran the existing intent classification cases (founder, inventor,
  statistic, explanation, general) with zero regressions.
- Added and passed 3 new comparison-intent classification cases
  ("do dogs outlive cats?", "cats vs dogs lifespan", "is a lion bigger
  than a tiger").
- Confirmed `query_wants_quantity()` and `query_wants_comparison()` are
  now mutually exclusive per query (previously two independent
  detectors could both fire on the same query).
- Confirmed `search_notes_as_documents()` produces ranker-compatible
  documents and that `synthesize()` consumes merged file/web/note
  results without error.

### Known Limitations
- Notes participate in local search with simple substring/count
  scoring, not the full TF-IDF + intent-adjusted ranking used for
  files and web pages. A note that happens to repeat a query term many
  times can currently outrank a more relevant file or web document.
- Collections and entity extraction remain implemented in
  `knowledge/vault.py` but are still not exposed through the desktop
  UI (carried forward from earlier releases). - 2026-08-26

### Maintenance
- Removed an unused `Iterable` import from `typing` in
  `brisart_ai/knowledge/vault.py`.
- No functional changes to search, ranking, ingestion, GUI, or web
  retrieval behavior.

### Notes
- This release marks BrisartAI's transition from beta to production
  status.
- The change itself is a documentation-organization and lint-cleanup
  release; the underlying 1.0.0 feature set is the intent-aware ranking
  and GUI-only architecture already shipped in the beta.1–beta.4 line.

---

## 1.0.0-beta.4

Added:
- Intent-aware ranking layer shared by both public web search and offline
  document retrieval (`brisart_ai/intent.py`).
- Query intent classification for:
  - founder/company questions
  - inventor/device questions
  - statistics/population questions
  - explanation/mechanism questions
  - general questions
- Intent debugging information exposed through replay tooling, including
  detected intent, boosts, penalties, scores, and ranking rationale
  (`scripts/debug_search_replay.py`).
- `scripts/debug_offline_replay.py` for validating offline retrieval
  behavior using standalone fixture datasets without requiring manual
  index setup.
- Shared intent scoring between `web/crawler.py` and
  `knowledge/ranker.py`, preventing web and offline ranking behavior
  from diverging over time.

Fixed:
- Search relevance no longer relies exclusively on raw keyword overlap.
  Queries are now ranked using both term matches and question intent,
  allowing pages that actually answer the question to outrank pages that
  merely contain the same keywords (`web/crawler.py`,
  `knowledge/ranker.py`).
- Founder questions such as:
  `who invented microsoft`
  now prioritize founder/history/company sources above product,
  account, and generic invention pages.
- Inventor questions such as:
  `who invented the transistor`
  now prioritize inventor/history sources above unrelated pages that
  happen to contain the word "invented".
- Statistics questions such as:
  `how many cats are in america`
  now favor pages containing counts, estimates, demographics,
  populations, and measurable figures over generic topic pages.
- Explanation questions such as:
  `why do cats purr`
  now favor sources explaining causes, mechanisms, and processes rather
  than generic descriptive pages.
- Offline document retrieval now applies the same intent-aware ranking
  logic used by public web search, preventing imported manuals,
  references, and glossary content from outranking more relevant
  evidence purely through term frequency (`knowledge/ranker.py`).
- Fixed article-slug scoring logic that recognized hyphenated article
  titles but ignored underscore-separated titles. This previously
  prevented many Wikipedia history pages from receiving ranking credit
  (`web/crawler.py`).
- Fixed percent-encoded URL handling during ranking. URLs such as:
  `Invented_%28album%29`
  previously bypassed work-of-art relevance penalties and could rank
  unexpectedly high for invention-related questions (`web/crawler.py`).

Changed:
- Retrieval ranking now evaluates why a document matches a query instead
  of only whether it contains matching words.
- Public web search and offline search now share a unified ranking model
  instead of maintaining independent relevance behavior.
- Search replay tooling now exposes ranking decisions in a transparent
  and inspectable format for debugging and validation.
- Ranking adjustments are deliberately bounded so intent acts as a hint
  rather than a hard filter:
  - web ranking uses bounded intent bonuses/penalties
  - offline ranking uses proportional score adjustments
  - boost accumulation is capped to prevent keyword stuffing from
    dominating results

Verification:
- `compileall` and import-smoke validation completed successfully.
- 23/23 intent-classification checks passed.
- 18/18 name-shape checks passed.
- 12/12 generic-concept checks passed.
- Provider-batch guard introduced in beta.3 remains intact.
- All required replay queries validated against live search providers.
- All offline intent fixtures validated through a real SQLite index
  using the production retrieval path.
- Search quality improvements observed during replay validation:
  - `who invented microsoft?`
    - before: 2/5 relevant
    - after: 5/5 relevant
  - `who invented the transistor and when was it invented?`
    - before: 2/5 relevant
    - after: 4/5 relevant
  - `how many cats are in america?`
    - before: 2/5 relevant
    - after: 3/5 relevant

Known Issues carried forward from beta.3:
- No positive relevance check at crawl time -- pages are still accepted
  into the index unless blocked by crawler policy; relevance is
  determined primarily during ranking (`web/crawler.py`).
- No error handling around database/session startup -- failures opening
  SQLite databases still surface as raw exceptions
  (`knowledge/index.py`, `core/session_memory.py`).
- No formal automated unit test suite -- replay validation exists, but
  the project still lacks a dedicated automated testing framework.

New Known Limitations:
- Public web ranking still evaluates URLs only. Page titles and search
  snippets are not yet incorporated into ranking decisions, so a
  strongly named URL can occasionally outperform a better-titled result
  (`web/crawler.py`).
- Founder detection uses a finite company list. Unlisted companies may
  fall back to inventor-style classification.
- Ranking can improve ordering of retrieved sources, but it cannot
  compensate for poor search-provider recall when relevant sources were
  never returned by the search engine.

---

## 1.0.0-beta.3

Fixed:
- The desktop UI no longer freezes during web research. `ui/app.py` now runs
  `BrisartService.ask()` on a background thread and marshals the result back
  onto the Tk main loop via `after()`, instead of blocking the main loop for
  the full duration of the search + crawl (previously 30-90+ seconds on slow
  networks or multiple search-provider fallbacks).
- `knowledge/index.py`'s `Index` and `core/session_memory.py`'s
  `SessionMemory` SQLite connections are now opened with
  `check_same_thread=False`, since answers are produced on a background
  thread while both connections are created on the main thread. Access
  remains serialized at the application level via the existing `_busy` flag,
  so no additional locking was required for correctness.
- The "Automatic Web Research" settings toggle now actually affects typed
  chat questions. Previously `ui/service.py`'s `ask()` always forced
  `force_web=True`, so the toggle had no effect on anything except direct
  backend calls. `ask()` now defaults `force_web` to the current
  `auto_web_research` setting whenever the caller doesn't explicitly
  override it (`ui/service.py`).
- Diagnostic output from the crawler/search/policy/fetcher layers
  (WARN/SKIP/ERROR lines) is no longer console-only. `ui/service.py`
  captures `print()` output during `ask()` via
  `contextlib.redirect_stdout` and exposes the relevant lines through
  `last_diagnostics`; `ui/app.py` surfaces them in the chat transcript as
  system messages after each answer.

Changed:
- The explicit "Research Web" sidebar action now always forces a fresh
  public web search (`force_web=True`) regardless of the Automatic Web
  Research setting, since it represents a direct, deliberate user request.
  Ordinary typed questions in the chat box now respect the setting instead
  of always forcing a web search (`ui/app.py`).
- The status message shown before an answer now distinguishes between
  "Searching the public web and reading the top results..." and "Searching
  your imported files and notes..." depending on whether a web search will
  actually run for that question (`ui/app.py`).

Known Issues carried forward from beta.2 (see README.md):
- No positive relevance check at crawl time -- the crawler still only
  rejects pages via the blocklist; anything not explicitly blocked gets
  indexed, and relevance is only sorted out afterward during ranking
  (`web/crawler.py`).
- No error handling around database/session startup -- if the SQLite index
  file can't be opened (locked, read-only, missing permissions), the app
  still crashes with a raw traceback instead of a clean message
  (`knowledge/index.py`, `core/session_memory.py`).
- No automated test coverage. Ranking, synthesis, and crawler-rejection
  logic are still verified by manual testing only.

Current Subsystem Layout:
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

---

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

Current Subsystem Layout:
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

---

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

---

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

---

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

---

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

---

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

---

## 0.5.0-alpha

Added:
- Free-form response mode for any typed input
- Clear distinction between indexed-file answers and general fallback responses
- Much wider file type support
- Pure-Python best-effort readers for `.docx`, `.pptx`, `.xlsx`, `.odt`, and `.pdf`
- Expanded scanner policy for more source/data/code/document formats
- General assistant fallback that explains limits instead of going silent

---

## 0.4.0-alpha

Added:
- Assistant voice/personality layer
- Logical observations in answers
- Evidence explanations with "Why I think this"
- Confidence labels based on retrieval strength
- Suggested next moves
- Local session memory for recent chat context
- More natural analysis and recommendation output

---

## 0.3.0-alpha

Added:
- Conservative drive/folder scanning
- Scan preview mode
- Hard limits for max files and max file size
- System/cache/dependency folder exclusions
- Recommendation engine based on indexed data
- Duplicate content detection by hash
- Project hygiene recommendations based on indexed filenames

---

## 0.2.0-alpha

Shifted BrisartAI from crawler-first to data-first architecture.

---

## 0.1.0-alpha

Initial crawler/index/retrieval prototype.
