#!/usr/bin/env python3
"""
File: scripts/debug_search_replay.py

Purpose
-------
Replays the real BrisartAI web search path against live providers and
shows why results survived: which query forms were sent, which
provider answered, which batches were rejected wholesale as unrelated,
and how the survivors ranked -- including each result's own title and
whether a literal phrase match fired, per the 1.0.0-beta.8 title/
phrase-aware ranking change in web/crawler.py. This is a diagnostic
harness, not a test suite; it exercises the genuine provider stack with
no mocks so retrieval-quality regressions are visible.

Communication / relationships
------------------------------
- Imports brisart_ai.intent.{describe_intent, detect_intent},
  brisart_ai.util.normalize_url, brisart_ai.web.crawler.{_should_reject,
  _topic_terms, clean_search_query, explain_ranking, rank_results,
  search_keyword_fallback}, brisart_ai.web.search.search_public_web.
- Standalone script, not imported by any other module; run directly via
  `python3 scripts/debug_search_replay.py`.

Settings / parameters
----------------------
- REGRESSION_QUERIES: the default set of 10 queries replayed when
  --query is not supplied, spanning founder/inventor/statistic/
  explanation intents.
- --query (repeatable): replay one or more specific queries instead of
  the default regression set.
- --limit (default 5): results requested per query.
- --delay (default 45 seconds): pause between queries -- live providers
  rate-limit aggressively, so runs are spaced out by default; lower it
  only for a single-query run.

Edge cases
----------
- Diagnostic stdout from search_public_web() is captured via
  contextlib.redirect_stdout and filtered down to the lines worth
  showing (provider trying/returned/WARN lines, rejected-batch notices)
  rather than dumping the full raw log.
- A KeyboardInterrupt during the loop returns exit code 130 rather than
  propagating a traceback, so an impatient manual run can be cancelled
  cleanly.
- The per-URL scoring detail table intentionally shows base score,
  intent delta, terms matched, and phrase-matched status separately --
  a ranking that cannot be inspected cannot be trusted, and this project
  has previously shipped one confidently wrong diagnosis that a fuller
  breakdown would have caught sooner.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import time
from typing import Dict, List

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from brisart_ai.intent import describe_intent, detect_intent  # noqa: E402
from brisart_ai.util import normalize_url  # noqa: E402
from brisart_ai.web.crawler import (  # noqa: E402
    _should_reject,
    _topic_terms,
    clean_search_query,
    explain_ranking,
    rank_results,
    search_keyword_fallback,
)
from brisart_ai.web.search import search_public_web  # noqa: E402

REGRESSION_QUERIES = (
    "who invented microsoft?",
    "who founded microsoft?",
    "who invented the transistor and when was it invented?",
    "who invented the telephone?",
    "who created linux?",
    "who founded apple?",
    "what is the population of japan?",
    "how many cats are in america?",
    "why do cats purr?",
    "how do solar panels generate electricity?",
)

RULE = "=" * 72


def _run_one(query: str, limit: int) -> bool:
    """Replay a single query. Returns True when usable results survived."""
    print(RULE)
    print(f"ORIGINAL QUERY : {query!r}")

    natural = clean_search_query(query)
    keyword = search_keyword_fallback(query)
    print(f"NATURAL FORM   : {natural!r}")
    if keyword and keyword != natural:
        print(f"KEYWORD FORM   : {keyword!r}")
    else:
        print("KEYWORD FORM   : (same as natural; not searched twice)")

    topics = _topic_terms(natural) | _topic_terms(keyword)
    print(f"TOPIC TERMS    : {sorted(topics)}")

    intent = detect_intent(query)
    print(f"DETECTED INTENT: {describe_intent(intent, query)}")

    collected: List[tuple] = []
    for label, form in (("natural", natural), ("keyword", keyword)):
        if label == "keyword" and (not keyword or keyword == natural):
            continue

        print(f"\n--- provider trace ({label} form: {form!r}) ---")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            found = search_public_web(form, limit=limit, with_titles=True)

        for line in buffer.getvalue().splitlines():
            text = line.strip()
            if not text:
                continue
            if "unrelated" in text:
                print(f"  REJECTED BATCH: {text}")
            elif "trying" in text or "returned" in text or "WARN" in text:
                print(f"  {text}")

        print(f"  raw result count: {len(found)}")
        collected.extend(found)

    if not collected:
        print("\nACCEPTED URLS  : (none -- every provider was unusable)")
        print("FINAL RANKED   : (none)")
        return False

    kept_pairs = [
        (url, title)
        for url, title in collected
        if not _should_reject(url, topics)
    ]
    dropped_pairs = [
        (url, title)
        for url, title in collected
        if _should_reject(url, topics)
    ]

    titles_map: Dict[str, str] = {}
    for url, title in kept_pairs:
        key = normalize_url(url)
        if key and title and key not in titles_map:
            titles_map[key] = title

    kept = [url for url, _title in kept_pairs]
    print(f"\nACCEPTED URLS  : {len(kept)}")
    for url, title in kept_pairs:
        title_note = f"  (title: {title!r})" if title else ""
        print(f"  + {url}{title_note}")

    if dropped_pairs:
        print(f"REJECTED URLS  : {len(dropped_pairs)} (off-topic/definition filter)")
        for url, _title in dropped_pairs:
            print(f"  - {url}")

    final = rank_results(kept, topics, query, titles=titles_map)[:limit]
    print("FINAL RANKED   :")
    for position, url in enumerate(final, start=1):
        title = titles_map.get(normalize_url(url), "")
        title_note = f"  (title: {title!r})" if title else ""
        print(f"  {position}. {url}{title_note}")

    # Per-URL scoring breakdown. A ranking that cannot be inspected
    # cannot be trusted -- this project already shipped one confidently
    # wrong diagnosis, so every component of the score is shown,
    # including whether the result's own title (not just its URL)
    # contributed, and whether a literal phrase match fired.
    print("SCORING DETAIL :")
    print(
        f"  {'score':>6} {'base':>5} {'intent':>6}  "
        f"{'terms':>5}  {'phrase':>6}  url / title / reason"
    )
    for row in explain_ranking(kept, topics, query, titles=titles_map)[:limit]:
        phrase_flag = "yes" if row["phrase_matched"] else "no"
        print(
            f"  {row['score']:>+6d} {row['base_score']:>+5d} "
            f"{row['intent_delta']:>+6d}  {row['terms_matched']:>5}  "
            f"{phrase_flag:>6}  {row['url']}"
        )
        if row["title"]:
            print(f"         title: {row['title']!r}")
        reason = []
        if row["boosts"]:
            reason.append("boost=" + ",".join(row["boosts"]))
        if row["penalties"]:
            reason.append("penalty=" + ",".join(row["penalties"]))
        if not reason:
            reason.append("term overlap only")
        print(f"         reason: {'; '.join(reason)}")

    return bool(final)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay the real search path for debugging.",
    )
    parser.add_argument(
        "--query",
        action="append",
        help="Query to replay; repeatable. Defaults to the regression set.",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--delay",
        type=int,
        default=45,
        help="Seconds between queries; providers rate-limit aggressively.",
    )
    args = parser.parse_args()

    queries = tuple(args.query) if args.query else REGRESSION_QUERIES

    usable = 0
    for position, query in enumerate(queries):
        if position:
            time.sleep(max(0, args.delay))
        try:
            if _run_one(query, args.limit):
                usable += 1
        except KeyboardInterrupt:
            print("\ninterrupted")
            return 130

    print(RULE)
    print(f"SUMMARY: {usable}/{len(queries)} queries returned usable results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
