"""
File: brisart_ai/web/stats.py

Purpose
-------
Defines CrawlStats, five counters for one crawl run plus a
print_summary() for an end-of-run diagnostic report shown in the
service's captured stdout.

Communication / relationships
------------------------------
- brisart_ai/web/crawler.py: owns the single CrawlStats() instance per
  crawl_urls_to_index() call, incrementing fields as each URL is
  processed, then calls .print_summary() once at the end of the run.
- Imports nothing from elsewhere in brisart_ai; only dataclasses.

Settings / parameters
----------------------
- requested: URLs dequeued and attempted this run.
- indexed: pages successfully added to the index.
- skipped_duplicates: pages whose content hash already existed.
- skipped_empty: pages that fetched successfully but extracted no text.
- errors: fetch failures (network errors, HTTP errors, oversized pages).

Edge cases
----------
- All fields default to 0, so a fresh CrawlStats() prints an honest
  all-zero summary rather than raising if print_summary() is called
  before any URL was processed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CrawlStats:
    requested: int = 0
    indexed: int = 0
    skipped_duplicates: int = 0
    skipped_empty: int = 0
    errors: int = 0

    def print_summary(self) -> None:
        print()
        print("Web Crawl Summary")
        print("=================")
        print(f"Requested: {self.requested}")
        print(f"Indexed: {self.indexed}")
        print(f"Duplicates: {self.skipped_duplicates}")
        print(f"Empty pages: {self.skipped_empty}")
        print(f"Errors: {self.errors}")
