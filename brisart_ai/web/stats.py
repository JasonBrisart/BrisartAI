"""
File: brisart_ai/web/stats.py

Purpose
-------
Defines CrawlStats, six counters for one crawl run plus print_summary().

Communication / relationships
------------------------------
- brisart_ai/web/crawler.py: owns the single CrawlStats() instance.

Settings / parameters
----------------------
- requested, indexed, skipped_duplicates, skipped_empty,
  skipped_offtopic, errors.

Edge cases
----------
- All fields default to 0.

Known limitations
-----------------
- CrawlStats is an in-memory counter object for one crawl run; it is not
  persisted and resets each run.
- Counts are advisory instrumentation, not a guarantee of exact-once
  accounting under concurrent updates.

Examples
--------
    >>> st = CrawlStats()
    >>> st.indexed += 1
    >>> st.print_summary()                        # doctest: +SKIP
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrawlStats:
    requested: int = 0
    indexed: int = 0
    skipped_duplicates: int = 0
    skipped_empty: int = 0
    skipped_offtopic: int = 0
    errors: int = 0

    def print_summary(self) -> None:
        print()
        print("Web Crawl Summary")
        print("=================")
        print(f"Requested: {self.requested}")
        print(f"Indexed: {self.indexed}")
        print(f"Duplicates: {self.skipped_duplicates}")
        print(f"Empty pages: {self.skipped_empty}")
        print(f"Off-topic pages: {self.skipped_offtopic}")
        print(f"Errors: {self.errors}")
