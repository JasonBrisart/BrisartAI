"""brisart_ai/web/stats.py

`CrawlStats`: five counters for one crawl run (requested / indexed /
duplicate / empty / error) plus a `print_summary()` for an end-of-run
report. web/crawler.py owns the only instance, incrementing fields as
it processes each URL. All fields default to 0, so a fresh
`CrawlStats()` prints an honest all-zero summary rather than raising.
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
