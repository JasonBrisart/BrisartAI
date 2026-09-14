# brisart_ai/web/

Public web search, crawling, fetching, and the safety policy that governs what BrisartAI is allowed to fetch. **Optional** — disabled entirely when Automatic Web Research is off and "Research Web" is never used, the intended posture for air-gapped environments.

```text
web/
├── search.py     Dependency-free search across 7 providers
├── crawler.py    The single chokepoint every web page passes through to get indexed
├── fetcher.py    Single-URL retrieval
├── policy.py     Robots.txt + local/private-host safety policy
├── models.py     FetchResult data model
└── stats.py      CrawlStats counters for one crawl run
```

---

## `search.py`

Seven providers, tried in order from most likely to be blocked to least likely: **Startpage → Brave Search → DuckDuckGo HTML → DuckDuckGo Lite → Bing HTML → Mojeek → Wikipedia API.** Every provider before the Wikipedia API is an HTML scraper, fragile in a different way (bot detection, challenge pages, rate-limiting, undocumented markup) — the chain deliberately spends its riskiest request first, so each subsequent provider is both a fallback for the ones before it and a strictly safer bet. The Wikipedia API runs last as a stable, key-free floor on quality.

Two extraction strategies: DuckDuckGo/Bing use known result-link CSS classes or `<h2>`/`<h3>` heading structure; Mojeek/Brave/Startpage (whose markup is undocumented or shifts often) use domain-based heuristics instead — a result's host must simply differ from the search engine's own host and not be a help/account/static subdomain of it.

`_partition_related_results()` judges each `(url, title)` pair **individually** against the query's meaningful terms, rather than a whole-batch check that could let a single good result wave through an entire batch of garbage.

HTML parsing, JSON decoding, Base64 unwrapping, and URL handling throughout this module use the Brisart Native Stack (`brisart_ai.native.*`) rather than `html.parser`/`json`/`base64`/`urllib.parse` directly.

---

## `crawler.py`

The single chokepoint every web page must pass through to get indexed: normalize the query, rank the resulting URLs, filter out known-junk hosts and off-topic disambiguation pages, respect robots.txt, fetch and de-duplicate content, and add the survivors to the index.

A question keeps its natural phrasing when sent to search (`clean_search_query()`) — that phrasing is what matches pages actually containing the answer. A keyword-only form (`search_keyword_fallback()`) is searched too, and results from both are merged.

`score_result()` / `_score_detail()` is a small, hand-tuned integer heuristic, not a learned model: `+3` per topic term in the path (strongest signal), `+2` per topic term in the hostname or title, `+2` for an article-shaped slug, `+4` for a literal phrase match, `-4` for a low-value host or an account/login portal, `-3` for a listing/search page, `-2` for zero topic terms matched, plus a folded-in intent adjustment.

---

## `policy.py`

`RobotsCache` fetches and caches `robots.txt` per site (never re-fetched twice in one run) using the native `brisart_robots` (replacing `urllib.robotparser.RobotFileParser`). If `robots.txt` is missing, unreachable, too large, malformed, or returns 401/403, crawling is **allowed**, not blocked — a retrieval failure must never be read as an explicit site-wide denial.

`is_local_or_private_host()` recognizes localhost and its variants, `.local`/`.localhost`-suffixed hosts, and any IP address `ipaddress` classifies as private/loopback/link-local/multicast/reserved/unspecified — checked before any network access at all. `USER_AGENT` is version-stamped via `version_info.__version__`.

---

## `fetcher.py`, `models.py`, `stats.py`

- **`fetcher.py`** — `fetch_url()` fetches one normalized URL, caps response size at `MAX_PAGE_BYTES` (2,000,000), decodes using the declared/detected charset, and hands HTML off to `io/extractor.py`'s `html_to_text()`. Every failure mode is captured into the returned `FetchResult` rather than raised.
- **`models.py`** — `FetchResult`, the single return value of one URL fetch attempt.
- **`stats.py`** — `CrawlStats`, five counters (requested, indexed, duplicates, empty, errors) plus `print_summary()` for an end-of-run diagnostic report.
