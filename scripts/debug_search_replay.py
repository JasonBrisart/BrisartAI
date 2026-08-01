#!/usr/bin/env python3
"""Replay the real BrisartAI search path and show why results survived.

This is a diagnostic harness, not a test suite. It exercises the genuine
provider stack (no mocks) so retrieval-quality regressions are visible:
which query forms were sent, which provider answered, which batches were
rejected wholesale as unrelated, and how the survivors ranked.

Live providers rate-limit aggressively. Runs are spaced by --delay
seconds by default; lower it only for a single-query run.

Usage:
    python3 scripts/debug_search_replay.py
    python3 scripts/debug_search_replay.py --query "why do cats purr"
    python3 scripts/debug_search_replay.py --limit 8 --delay 60
"""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
import time
from typing import List

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from brisart_ai.intent import describe_intent, detect_intent  # noqa: E402
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

    collected: List[str] = []
    for label, form in (("natural", natural), ("keyword", keyword)):
        if label == "keyword" and (not keyword or keyword == natural):
            continue
        print(f"\n--- provider trace ({label} form: {form!r}) ---")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            found = search_public_web(form, limit=limit)
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

    kept = [url for url in collected if not _should_reject(url, topics)]
    dropped = [url for url in collected if _should_reject(url, topics)]

    print(f"\nACCEPTED URLS  : {len(kept)}")
    for url in kept:
        print(f"  + {url}")
    if dropped:
        print(f"REJECTED URLS  : {len(dropped)} (off-topic/definition filter)")
        for url in dropped:
            print(f"  - {url}")

    final = rank_results(kept, topics, query)[:limit]
    print("FINAL RANKED   :")
    for position, url in enumerate(final, start=1):
        print(f"  {position}. {url}")

    # Per-URL scoring breakdown. A ranking that cannot be inspected
    # cannot be trusted -- this project already shipped one confidently
    # wrong diagnosis, so every component of the score is shown.
    print("SCORING DETAIL :")
    print(
        f"  {'score':>6} {'base':>5} {'intent':>6}  "
        f"{'terms':>5}  url / reason"
    )
    for row in explain_ranking(kept, topics, query)[:limit]:
        print(
            f"  {row['score']:>+6d} {row['base_score']:>+5d} "
            f"{row['intent_delta']:>+6d}  {row['terms_matched']:>5}  "
            f"{row['url']}"
        )
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
