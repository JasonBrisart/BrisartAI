"""brisart_ai/blocklist.py

Web-source blocking policy, in three tiers of severity:

- **Blocked outright** (`BLOCKED_WEB_HOSTS`): dictionary/thesaurus/
  definition sites. A question like "how many cats are in america"
  should never come back with the dictionary definition of the word
  "many" -- these hosts are refused at ingest time, full stop.
- **Ranked down, not blocked** (`LOW_VALUE_HOSTS`): video/social/vendor-
  help-desk/shopping sites. A YouTube page can legitimately be the
  subject of a query, so these only lose points in web/crawler.py's
  `score_result()`, they're never refused.
- **Off-topic disambiguation pages** (`is_offtopic_wiki`): a Wikipedia
  page whose title is itself a bare function word -- `/wiki/Many` is
  the disambiguation entry for the *word* "many," never the answer to a
  question about cats. Rejected unless that exact word is genuinely
  part of the query's own topic.

Also defines `LISTING_PATH_MARKERS` (path fragments that mark a
listing/search/category page rather than prose) and
`ACCOUNT_HOST_PREFIXES` (a brand's own sign-in portal, which matches the
brand name in a query but never answers a question about it), both used
by web/crawler.py's scoring.

This lives at the top level, not inside web/, specifically so
knowledge/index.py can import `is_junk_web_source()` to purge stale rows
from the local index without the knowledge layer depending on the web
layer.

`is_blocked_web_host()` needs an absolute URL with a scheme -- a bare
hostname exposes no `.hostname` via `urlsplit()` and silently returns
`False`. Every caller here already passes normalized absolute URLs, so
that's a documented constraint, not a bug. Malformed URLs that raise
`ValueError` are treated as "not blocked" rather than propagating --
that's the crawler's problem to catch elsewhere.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Optional, Set

BLOCKED_WEB_HOSTS = (
    "merriam-webster.com", "dictionary.cambridge.org", "dictionary.com",
    "thesaurus.com", "collinsdictionary.com", "vocabulary.com",
    "wordnik.com", "yourdictionary.com", "definitions.net",
    "wordreference.com", "urbandictionary.com", "ldoceonline.com",
    "macmillandictionary.com", "usdictionary.com", "thefreedictionary.com",
    "freedictionary.com", "definitions.uslegal.com", "en.wiktionary.org",
    "wiktionary.org", "britannica.com", "wordhippo.com",
    "powerthesaurus.org",
)

LOW_VALUE_HOSTS = (
    "youtube.com", "m.youtube.com", "youtu.be", "support.google.com",
    "facebook.com", "instagram.com", "tiktok.com", "pinterest.com",
    "x.com", "twitter.com", "reddit.com", "quora.com", "amazon.com",
    "ebay.com", "etsy.com", "petfinder.com", "manychat.com",
)

# Path fragments (case-insensitive substrings) marking a listing/search/
# category page rather than prose. Entries without a leading slash
# (e.g. "-breeds") intentionally catch mid-segment forms like
# "/cat-breeds".
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

# Bare English function/question words. Stripped from queries before
# search, and used to detect a Wikipedia page ABOUT one of these words
# rather than the user's actual topic.
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
    """True when a URL points at a blocked dictionary/definition host.

    Requires a full URL with a scheme; a bare hostname has no scheme, so
    `urlsplit()` exposes no `.hostname` and this silently returns False.
    """
    try:
        host = urllib.parse.urlsplit(str(location or "")).hostname or ""
    except ValueError:
        return False
    host = host.casefold().strip(".")
    if not host:
        return False
    return any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_WEB_HOSTS)


def is_offtopic_wiki(location: str, topic_terms: Optional[Set[str]] = None) -> bool:
    """True for a Wikipedia page whose title is a bare function word.

    Rejected unless that exact word is genuinely part of the query's
    own topic terms, so a real query about the word "many" (rare, but
    possible) isn't wrongly rejected.
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
    title = urllib.parse.unquote(match.group(1)).replace("_", " ").strip().casefold()
    if title not in FUNCTION_WORDS:
        return False
    if topic_terms and title in topic_terms:
        return False
    return True


def is_junk_web_source(location: str, topic_terms: Optional[Set[str]] = None) -> bool:
    """Combined check: blocked dictionary host OR off-topic wiki page."""
    return is_blocked_web_host(location) or is_offtopic_wiki(location, topic_terms)


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
