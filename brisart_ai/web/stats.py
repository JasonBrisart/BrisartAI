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