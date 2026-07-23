from __future__ import annotations

import queue
import time

from typing import Sequence, Set, Tuple

from brisart_ai.util import (
    normalize_url,
    same_site,
    stable_hash,
)

from brisart_ai.web.fetcher import fetch_url
from brisart_ai.web.search import search_public_web
from brisart_ai.web.policy import RobotsCache
from brisart_ai.web.stats import CrawlStats

DEFAULT_DELAY_SECONDS = 1.0


def content_exists(
    index,
    content_hash: str,
) -> bool:
    """
    Return True if identical content
    already exists in the index.
    """

    try:
        row = index.conn.execute(
            """
            SELECT 1
            FROM sources
            WHERE content_hash = ?
            LIMIT 1
            """,
            (content_hash,),
        ).fetchone()

        return row is not None

    except Exception:
        return False


def crawl_urls_to_index(
    urls: Sequence[str],
    index,
    limit: int = 20,
    depth: int = 0,
    delay: float = DEFAULT_DELAY_SECONDS,
    same_domain_only: bool = True,
) -> int:
    """
    Crawl public URLs and add extracted text
    to the BrisartAI index.
    """

    try:
        crawl_limit = max(
            1,
            int(limit),
        )
    except (TypeError, ValueError):
        crawl_limit = 20

    try:
        crawl_depth = max(
            0,
            int(depth),
        )
    except (TypeError, ValueError):
        crawl_depth = 0

    try:
        crawl_delay = max(
            0.0,
            float(delay),
        )
    except (TypeError, ValueError):
        crawl_delay = DEFAULT_DELAY_SECONDS

    stats = CrawlStats()

    robots = RobotsCache()

    pending: queue.Queue[
        Tuple[str, int, str]
    ] = queue.Queue()

    seen: Set[str] = set()

    for raw_url in urls:
        normalized = normalize_url(raw_url)

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(normalized)

        pending.put(
            (
                normalized,
                0,
                normalized,
            )
        )

    crawled = 0

    while (
        not pending.empty()
        and crawled < crawl_limit
    ):
        current_url, level, root_url = (
            pending.get()
        )

        stats.requested += 1

        if not robots.allowed(
            current_url
        ):
            print(
                f"SKIP robots.txt: {current_url}"
            )
            continue

        print(
            f"WEB FETCH depth={level}: "
            f"{current_url}"
        )

        result = fetch_url(
            current_url
        )

        if result.error:
            stats.errors += 1

            print(
                f"  WARN: {result.error}"
            )

            continue

        if not result.text.strip():
            stats.skipped_empty += 1

            print(
                "  WARN: page contained no "
                "extractable text"
            )

            continue

        content_hash = stable_hash(
            result.text
        )

        if content_exists(
            index,
            content_hash,
        ):
            stats.skipped_duplicates += 1

            print(
                "  SKIP duplicate content"
            )

        else:
            indexed = index.add_source(
                source_type="web",
                location=result.url,
                title=result.title,
                text=result.text,
                content_hash=content_hash,
                size_bytes=len(
                    result.text.encode(
                        "utf-8",
                        errors="replace",
                    )
                ),
                extension=".html",
            )

            if indexed:
                crawled += 1
                stats.indexed += 1

                print(
                    f"  OK: {len(result.text)} chars, "
                    f"{len(result.links)} links"
                )

        if level < crawl_depth:
            for link in result.links:
                normalized_link = normalize_url(
                    link
                )

                if not normalized_link:
                    continue

                if (
                    same_domain_only
                    and not same_site(
                        root_url,
                        normalized_link,
                    )
                ):
                    continue

                if normalized_link in seen:
                    continue

                seen.add(
                    normalized_link
                )

                pending.put(
                    (
                        normalized_link,
                        level + 1,
                        root_url,
                    )
                )

        if crawl_delay:
            time.sleep(
                crawl_delay
            )

    stats.print_summary()

    return crawled


def web_search_and_ingest(
    query: str,
    index,
    limit: int = 5,
    crawl_depth: int = 0,
) -> int:
    """
    Search the web and ingest results.
    """

    links = search_public_web(
        query,
        limit=limit,
    )

    if not links:
        print(
            "No public search results found "
            "or provider unavailable."
        )
        return 0

    print(
        "Search results:"
    )

    for number, link in enumerate(
        links,
        start=1,
    ):
        print(
            f"[{number}] {link}"
        )

    return crawl_urls_to_index(
        links,
        index,
        limit=limit,
        depth=crawl_depth,
        same_domain_only=True,
    )


__all__ = [
    "DEFAULT_DELAY_SECONDS",
    "content_exists",
    "crawl_urls_to_index",
    "web_search_and_ingest",
]