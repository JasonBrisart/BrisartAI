"""brisart_ai/web/models.py

`FetchResult`: the return value of one URL fetch attempt (see
web/fetcher.py), consumed by web/crawler.py to decide whether a page
gets indexed, skipped as empty, or logged as a failure. A non-empty
`error` doesn't guarantee everything else is blank -- `status` may
still carry a real HTTP code (e.g. 404) even on an error path, since
the two fields are set at different points during the fetch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class FetchResult:
    """Result of one public URL fetch."""

    url: str
    status: int
    content_type: str
    title: str
    text: str
    links: List[str]
    error: str = ""
