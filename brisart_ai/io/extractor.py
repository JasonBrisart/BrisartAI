"""brisart_ai/io/extractor.py

Two text-extraction helpers: `html_to_text()` and `csv_to_text()`.
web/fetcher.py calls `html_to_text()` on every fetched web page;
io/readers.py calls it for local .html/.htm/.svg files and calls
`csv_to_text()` for local .csv files.

`HTMLTextExtractor` is an `html.parser.HTMLParser` subclass that skips
`<script>`/`<style>`/`<svg>`/etc. entirely, inserts a newline at block-
level tag boundaries so paragraphs and list items don't run together,
and collects `<a href>` targets (resolved against `base_url`, de-duped,
http(s)-only) as a side channel of discovered links for the crawler to
follow.

One deliberate special case: `<sup class="reference">[3]</sup>` -- the
MediaWiki-style footnote marker Wikipedia and its mirrors use -- is
skipped too. Without this, extracted article text and quoted answers
would occasionally have a stray "[ 3 ]" glued onto the start of a
sentence. It's scoped narrowly to `<sup>` tags carrying a
reference/citation class, so an ordinary superscript like "10^2" is
untouched.

`csv_to_text()` converts each row to a pipe-separated line via
`csv.reader`, falling back to a naive comma-to-pipe line split if the
CSV is malformed enough to make `csv.reader` choke -- some searchable
text is better than none.
"""
from __future__ import annotations

import csv
import html
import io
import re
import urllib.parse
from html.parser import HTMLParser
from typing import List, Optional, Tuple

from brisart_ai.util import normalize_url


class HTMLTextExtractor(HTMLParser):
    """Extract readable text, page titles, and links from HTML."""

    SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}

    BLOCK_TAGS = {
        "p", "div", "section", "article", "aside", "header", "footer",
        "main", "nav", "br", "li", "ul", "ol", "table", "tr", "td",
        "th", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6",
    }

    # MediaWiki-style citation markers, e.g. <sup class="reference">[3]</sup>.
    # Scoped to <sup> only, so an unrelated superscript is left alone.
    REFERENCE_MARKER_TAGS = {"sup"}
    REFERENCE_MARKER_CLASSES = {"reference", "cite-bracket", "citation"}

    def __init__(self, base_url: str = ""):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: List[str] = []
        self.text_parts: List[str] = []
        self.links: List[str] = []
        self._skip_depth = 0
        self._reference_skip_depth = 0
        self._in_title = False

    def _is_reference_marker(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> bool:
        if tag not in self.REFERENCE_MARKER_TAGS:
            return False
        for name, value in attrs:
            if name.casefold() != "class" or not value:
                continue
            classes = {token.casefold() for token in value.split()}
            if classes & self.REFERENCE_MARKER_CLASSES:
                return True
        return False

    def handle_starttag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if self._is_reference_marker(tag, attrs):
            self._reference_skip_depth += 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                absolute = urllib.parse.urljoin(self.base_url, href)
                link = normalize_url(absolute)
                if link.startswith(("http://", "https://")):
                    self.links.append(link)
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_startendtag(
        self, tag: str, attrs: List[Tuple[str, Optional[str]]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.SKIP_TAGS:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self.REFERENCE_MARKER_TAGS and self._reference_skip_depth:
            self._reference_skip_depth -= 1
            return
        if self._reference_skip_depth:
            return
        if tag == "title":
            self._in_title = False
        if tag in self.BLOCK_TAGS:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._reference_skip_depth:
            return
        cleaned = html.unescape(data)
        cleaned = re.sub(r"[ \t\r\f\v]+", " ", cleaned).strip()
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        self.text_parts.append(cleaned + " ")

    def result(self) -> Tuple[str, str, List[str]]:
        title = " ".join(self.title_parts).strip()
        text = "".join(self.text_parts)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        unique_links: List[str] = []
        seen = set()
        for link in self.links:
            if link and link not in seen:
                seen.add(link)
                unique_links.append(link)
        return title, text, unique_links


def html_to_text(source: str, base_url: str = "") -> Tuple[str, str, List[str]]:
    """Convert HTML into a title, readable text, and discovered links."""
    parser = HTMLTextExtractor(base_url=base_url)
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        pass
    return parser.result()


def csv_to_text(source: str) -> str:
    """Convert CSV text into searchable pipe-separated text."""
    output: List[str] = []
    try:
        reader = csv.reader(io.StringIO(source))
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if any(cleaned):
                output.append(" | ".join(cleaned))
        return "\n".join(output)
    except (csv.Error, UnicodeError):
        pass
    for raw_line in source.splitlines():
        line = raw_line.strip()
        if line:
            output.append(line.replace(",", " | "))
    return "\n".join(output)
