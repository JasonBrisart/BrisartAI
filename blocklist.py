"""
File: brisart_ai/blocklist.py

Purpose
-------
Web-source blocking policy for BrisartAI -- the single source of truth
for "should this web page be kept?" Every module that needs to decide
this imports from here, so the policy lives in exactly ONE file.

This lives at the top level (next to util.py) rather than inside web/
so that knowledge/index.py can import it without the knowledge layer
having to depend on the web layer.

Communication / relationships
------------------------------
- brisart_ai/web/search.py: drops blocked hosts from search results.
- brisart_ai/web/crawler.py: refuses blocked hosts + off-topic wikis at
  ingest time via is_junk_web_source().
- brisart_ai/knowledge/index.py: purges any blocked/off-topic rows
  already in the database via purge_junk_web_sources().
- Imports brisart_ai.native.brisart_url's brisart_urlsplit()/
  brisart_unquote() (replacing urllib.parse.urlsplit()/unquote())
  -- see brisart_ai/native/README.md for how this module was
  independently verified against the real stdlib before being wired
  in. Otherwise imports only re.

Settings / parameters
----------------------
- BLOCKED_WEB_HOSTS: dictionary/thesaurus/definition sites.
- LOW_VALUE_HOSTS: hosts ranked down, not blocked outright.
- LISTING_PATH_MARKERS: path fragments marking listing/search pages.
- ACCOUNT_HOST_PREFIXES: product/account landing-page host prefixes.
- FUNCTION_WORDS: bare English function/question words.

Edge cases
----------
- is_blocked_web_host() requires an absolute URL with a scheme.
- is_offtopic_wiki() only rejects a wiki page whose title is EXACTLY a
  bare function word, unless overridden by topic_terms.

Known limitations
-----------------
- The blocked/low-value host lists and listing-path markers are finite,
  hand-maintained constants; a junk host not yet listed passes through.
- Matching is host- and path-substring based, not content based; a
  useful page on a blocked host is still blocked, and a junk page on an
  allowed host is not caught here.
- is_offtopic_wiki() only recognizes single-word function-word titles;
  a multi-word off-topic title is not flagged.

Examples
--------
    >>> is_blocked_web_host("https://www.merriam-webster.com/dictionary/cat")
    True
    >>> is_junk_web_source("https://en.wikipedia.org/wiki/the")
    True
    >>> is_junk_web_source("https://example.com/article")
    False
"""
from __future__ import annotations

import re
from typing import Optional, Set

from brisart_ai.native.brisart_url import brisart_unquote, brisart_urlsplit

BLOCKED_WEB_HOSTS = (
    "merriam-webster.com", "dictionary.cambridge.org", "dictionary.com",
    "thesaurus.com", "collinsdictionary.com", "vocabulary.com", "wordnik.com",
    "yourdictionary.com", "definitions.net", "wordreference.com",
    "urbandictionary.com", "ldoceonline.com", "macmillandictionary.com",
    "usdictionary.com", "thefreedictionary.com", "freedictionary.com",
    "definitions.uslegal.com", "en.wiktionary.org", "wiktionary.org",
    "britannica.com", "wordhippo.com", "powerthesaurus.org",
)

LOW_VALUE_HOSTS = (
    "youtube.com", "m.youtube.com", "youtu.be", "support.google.com",
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.com", "x.com",
    "twitter.com", "reddit.com", "quora.com", "amazon.com", "ebay.com",
    "etsy.com", "petfinder.com", "manychat.com",
)

LISTING_PATH_MARKERS = (
    "/search", "/tag/", "/tags/", "/category/", "/categories/",
    "/browse", "/shop", "/products", "/adoption", "/for-adoption",
    "/breed-list", "breed-list", "-breeds", "/breeds", "/watch",
    "/playlist", "/login", "/signup", "/pricing", "/contact",
)

ACCOUNT_HOST_PREFIXES = (
    "myaccount.", "account.", "accounts.", "login.", "signin.",
    "signup.", "auth.", "portal.",
)

FUNCTION_WORDS: Set[str] = {
    "a", "about", "an", "and", "are", "as", "at", "be", "by", "can",
    "could", "did", "do", "does", "find", "for", "from", "get", "give",
    "how", "i", "in", "into", "is", "it", "its", "know", "list", "many",
    "me", "much", "need", "of", "on", "or", "over", "please", "s",
    "should", "show", "some", "tell", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "to", "under",
    "us", "want", "was", "we", "were", "what", "whats", "when", "where",
    "which", "who", "whom", "why", "will", "with", "would", "you",
    "your",
}

_WIKI_TITLE_RE = re.compile(r"/wiki/([^/#?]+)")


def is_blocked_web_host(location: str) -> bool:
    """Return True when a URL/location points at a blocked dictionary host."""
    try:
        host = brisart_urlsplit(str(location or "")).hostname or ""
    except ValueError:
        return False
    host = host.casefold().strip(".")
    if not host:
        return False
    return any(
        host == blocked or host.endswith("." + blocked)
        for blocked in BLOCKED_WEB_HOSTS
    )


def is_offtopic_wiki(
    location: str,
    topic_terms: Optional[Set[str]] = None,
) -> bool:
    """Return True for a Wikipedia page whose title is a bare function word."""
    try:
        parsed = brisart_urlsplit(str(location or ""))
    except ValueError:
        return False
    if "wikipedia.org" not in (parsed.hostname or "").casefold():
        return False
    match = _WIKI_TITLE_RE.search(parsed.path)
    if not match:
        return False
    title = (
        brisart_unquote(match.group(1))
        .replace("_", " ")
        .strip()
        .casefold()
    )
    if title not in FUNCTION_WORDS:
        return False
    if topic_terms and title in topic_terms:
        return False
    return True


def is_junk_web_source(
    location: str,
    topic_terms: Optional[Set[str]] = None,
) -> bool:
    """Combined check: blocked dictionary host OR off-topic wiki page."""
    return is_blocked_web_host(location) or is_offtopic_wiki(
        location, topic_terms
    )


__all__ = [
    "BLOCKED_WEB_HOSTS",
    "FUNCTION_WORDS",
    "LOW_VALUE_HOSTS",
    "LISTING_PATH_MARKERS",
    "ACCOUNT_HOST_PREFIXES",
    "is_blocked_web_host",
    "is_offtopic_wiki",
    "is_junk_web_source",
]



