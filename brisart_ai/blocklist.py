"""Web-source blocking policy for BrisartAI -- the single source of truth.

Every module that needs to decide "should this web page be kept?" imports
from here, so the policy lives in exactly ONE file. To add or remove a
blocked site, edit BLOCKED_WEB_HOSTS below and every consumer updates
automatically.

Consumers:
  * web/search.py   -- drops blocked hosts from search results
  * web/crawler.py  -- refuses blocked hosts + off-topic wikis at ingest
  * knowledge/index.py -- purges any such rows already in the database

This lives at the top level (next to util.py) rather than inside web/ so
that knowledge/index.py can import it without the knowledge layer having
to depend on the web layer.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Optional, Set

# Dictionary / thesaurus / definition sites. Pages from these hosts are
# almost never the answer to a factual research question (asking "how
# many cats are in america" should not return the definition of the word
# "many"). Add or remove entries here and all consumers pick it up.
BLOCKED_WEB_HOSTS = (
    "merriam-webster.com",
    "dictionary.cambridge.org",
    "dictionary.com",
    "thesaurus.com",
    "collinsdictionary.com",
    "vocabulary.com",
    "wordnik.com",
    "yourdictionary.com",
    "definitions.net",
    "wordreference.com",
    "urbandictionary.com",
    "ldoceonline.com",
    "macmillandictionary.com",
    "usdictionary.com",
    "thefreedictionary.com",
    "freedictionary.com",
    "definitions.uslegal.com",
    "en.wiktionary.org",
    "wiktionary.org",
    "britannica.com",
    "wordhippo.com",
    "powerthesaurus.org",
)

# Hosts that are rarely the answer to a factual research question, but
# which search-result scraping surfaces constantly: video and social
# platforms, vendor help desks, and shopping/adoption listings. These are
# NOT blocked outright -- a YouTube page can legitimately be the subject
# of a query -- they are only ranked down by score_result(). This is the
# difference between the blocklist (never ingest) and this list (prefer
# something better if it exists).
LOW_VALUE_HOSTS = (
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "support.google.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "pinterest.com",
    "x.com",
    "twitter.com",
    "reddit.com",
    "quora.com",
    "amazon.com",
    "ebay.com",
    "etsy.com",
    "petfinder.com",
    "manychat.com",
)

# Path fragments that mark a listing/search/category page rather than a
# page of prose that answers something. Matched as case-insensitive
# SUBSTRINGS of the path, so entries without a leading slash (e.g.
# "-breeds") intentionally catch mid-segment forms like "/cat-breeds".
LISTING_PATH_MARKERS = (
    "/search", "/tag/", "/tags/", "/category/", "/categories/",
    "/browse", "/shop", "/products", "/adoption", "/for-adoption",
    "/breed-list", "breed-list", "-breeds", "/breeds", "/watch",
    "/playlist", "/login", "/signup",
    "/pricing", "/contact",
)

# Product/account landing hosts. A brand's own sign-in portal matches the
# brand term ("microsoft" in myaccount.microsoft.com) but never answers a
# question about the brand, so it must not outrank an article.
ACCOUNT_HOST_PREFIXES = (
    "myaccount.", "account.", "accounts.", "login.", "signin.",
    "signup.", "auth.", "portal.",
)

# Bare English function/question words. Used two ways:
#   1. Stripped out of a query before it is sent to a search engine
#      (so "how many cats" doesn't trigger a dictionary card for "many").
#   2. To detect a Wikipedia page that is ABOUT one of these words
#      (e.g. /wiki/Many is the disambiguation page for "many" -- never
#      the answer to a question about cats).
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
    """Return True when a URL/location points at a blocked dictionary host.

    ``location`` must be an absolute URL with a scheme
    ("https://thefreedictionary.com/x"). A bare hostname
    ("thefreedictionary.com") has no scheme, so urlsplit() exposes no
    hostname and this returns False. Both callers pass normalized
    absolute URLs; pass a full URL, not a host, or the check silently
    does nothing.
    """
    try:
        host = urllib.parse.urlsplit(str(location or "")).hostname or ""
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
    """Return True for a Wikipedia page whose title is a bare function word.

    A page like /wiki/Many is the disambiguation entry for the WORD
    "many" -- it is never the answer to a question about cats. Such a
    page is rejected unless that exact word is genuinely part of the
    topic being searched for.
    """
    try:
        parsed = urllib.parse.urlsplit(str(location or ""))
    except ValueError:
        return False
    if "wikipedia.org" not in (parsed.hostname or "").casefold():
        return False
    match = _WIKI_TITLE_RE.search(parsed.path)
    if not match:
        return False
    title = (
        urllib.parse.unquote(match.group(1))
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
