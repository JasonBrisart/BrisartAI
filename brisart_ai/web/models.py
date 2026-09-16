"""
File: brisart_ai/web/models.py

Purpose
-------
Defines FetchResult, the single return value of one URL fetch attempt.

Communication / relationships
------------------------------
- brisart_ai/web/fetcher.py: constructs FetchResult.
- brisart_ai/web/crawler.py: reads its fields.

Settings / parameters
----------------------
- url, status, content_type, title, text, links, error.

Edge cases
----------
- A non-empty error does not guarantee every other field is blank.

Known limitations
-----------------
- A plain data container (FetchResult) with no behavior beyond holding
  fetch outcome fields.
- No validation of field combinations; producers are trusted to populate
  it consistently.

Examples
--------
    >>> r = FetchResult(url="https://a.com", ok=True, status=200, text="hi")
    >>> r.ok and r.status == 200
    True
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



