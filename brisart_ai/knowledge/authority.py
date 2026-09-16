"""
File: brisart_ai/knowledge/authority.py

Purpose
-------
Classifies a source's host into a fixed authority tier and returns a
bounded ranking multiplier -- a source-TYPE signal, deliberately
independent of and complementary to the Brisart Relevance Engine's
existing term-based signals (rarity/presence/shape/coverage/title/
phrase/proximity/intent, see knowledge/relevance_engine.py and
knowledge/ranker.py). Two documents can score identically on every
term-based signal while one is an encyclopedia article and the other
is an anonymous forum post; authority tiering is the signal that tells
those two apart.

Communication / relationships
------------------------------
- knowledge/ranker.py: intent_adjust() multiplies its running score by
  authority_multiplier(location) as one more bounded factor in the
  standard signal stack -- the same pattern as every other adjustment
  there (title_match_adjust(), generic_concept_title_adjust(),
  phrase_match_adjust(), proximity_adjust(), intent_adjust() itself).
- brisart_ai/knowledge/confidence.py: uses classify_authority_tier()
  to weight a source's contribution to an overall confidence score
  (see that module) -- corroboration from two AUTHORITATIVE_TIER
  sources counts for more than corroboration from two UNKNOWN_TIER
  sources.
- Imports brisart_ai.native.brisart_url.brisart_urlsplit() when
  available (falling back to Python's own urllib.parse.urlsplit() if
  the native module is not present in the caller's environment, so
  this module works standalone too) -- no other brisart_ai dependency.

Settings / parameters
----------------------
- AUTHORITY_TIERS: an ordered (tier_name, multiplier, host_matcher)
  tuple, checked top-to-bottom, first match wins:
  * ENCYCLOPEDIC (1.15x) -- wikipedia.org, britannica.com and similar
    tertiary reference sources.
  * GOVERNMENTAL_ACADEMIC (1.20x) -- .gov, .edu, .mil TLDs, and
    standards bodies (ietf.org, w3.org, iso.org). Scored slightly
    ABOVE encyclopedic sources, since these are primary/official
    sources rather than tertiary summaries.
  * ESTABLISHED_NEWS (1.05x) -- a short, explicit list of long-running
    wire services and major outlets (reuters.com, apnews.com, bbc.com,
    npr.org). Deliberately conservative and short, exactly like
    intent.py's _KNOWN_COMPANIES: an outlet NOT on this list is simply
    left at NEUTRAL, never guessed at from domain age or popularity.
  * NEUTRAL (1.00x) -- the default for any host not matched above; the
    overwhelming majority of the open web.
  * LOW_VALUE (0.85x) -- reuses brisart_ai.blocklist.LOW_VALUE_HOSTS'
    host list conceptually (duplicated here as a small local constant
    to avoid a hard dependency on blocklist.py, so this module can be
    adopted independently) for social platforms/marketplaces whose
    content is user-generated and unmoderated for factual accuracy.
- MULTIPLIER_FLOOR / MULTIPLIER_CEILING (0.85 / 1.20): authority alone
  can never swing a score by more than +/-20%, keeping this signal a
  NUDGE rather than a hard filter or override -- the same "hint, not
  filter" principle the intent layer follows.

Edge cases
----------
- An unparsable location (empty string, no hostname) returns the
  NEUTRAL multiplier (1.0), never raises and never penalizes a
  document just because its location field was malformed.
- Matching is by exact host or host-suffix (".wikipedia.org" matches
  "en.wikipedia.org"), never by substring-anywhere-in-the-URL, to avoid
  a false match like "not-wikipedia.org.evil-site.com".
- A local file source (source_type="file", location is a filesystem
  path rather than a URL) is treated as NEUTRAL, since authority
  tiering is a web-provenance signal and has no defined meaning for a
  user's own imported documents.

Known limitations
-----------------
- Tiering is host-based against finite hand-maintained lists; an
  authoritative source not listed falls to the neutral tier (1.0), a
  safe non-penalizing default rather than a correct classification.
- Establishes provenance by domain only; it cannot judge the quality of
  an individual page within an otherwise-trusted or -untrusted host.
- Multipliers are bounded to [MULTIPLIER_FLOOR, MULTIPLIER_CEILING] so
  authority can never override the term-based score outright.

Examples
--------
    >>> classify_authority_tier("https://en.wikipedia.org/wiki/Cat")
    'encyclopedic'
    >>> authority_multiplier("https://www.reddit.com/r/x")
    0.85
    >>> authority_multiplier("https://example.com")
    1.0
"""
from __future__ import annotations
from typing import Callable, Tuple

try:
    from brisart_ai.native.brisart_url import brisart_urlsplit as _urlsplit
except Exception:  # pragma: no cover - fallback for standalone use
    from urllib.parse import urlsplit as _urlsplit  # type: ignore

TIER_ENCYCLOPEDIC = "encyclopedic"
TIER_GOVERNMENTAL_ACADEMIC = "governmental_academic"
TIER_ESTABLISHED_NEWS = "established_news"
TIER_NEUTRAL = "neutral"
TIER_LOW_VALUE = "low_value"

MULTIPLIER_FLOOR = 0.85
MULTIPLIER_CEILING = 1.20

_ENCYCLOPEDIC_HOSTS = ("wikipedia.org", "britannica.com", "wiktionary.org")
_ACADEMIC_TLDS = (".gov", ".edu", ".mil")
_STANDARDS_HOSTS = ("ietf.org", "w3.org", "iso.org", "nist.gov")
_ESTABLISHED_NEWS_HOSTS = (
    "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk", "npr.org",
    "afp.com",
)
_LOW_VALUE_HOSTS = (
    "youtube.com", "facebook.com", "instagram.com", "tiktok.com",
    "pinterest.com", "x.com", "twitter.com", "reddit.com", "quora.com",
)


def _host_matches(host: str, candidates) -> bool:
    host = host.casefold().strip(".")
    for candidate in candidates:
        candidate = candidate.casefold().strip(".")
        if host == candidate or host.endswith("." + candidate):
            return True
    return False


def _get_hostname(location: str) -> str:
    try:
        parsed = _urlsplit(str(location or ""))
        return (getattr(parsed, "hostname", None) or "").casefold()
    except Exception:
        return ""


def classify_authority_tier(location: str) -> str:
    """Return one of the TIER_* constants for the host in `location`."""
    host = _get_hostname(location)
    if not host:
        return TIER_NEUTRAL
    if _host_matches(host, _STANDARDS_HOSTS):
        return TIER_GOVERNMENTAL_ACADEMIC
    if any(host.endswith(tld) for tld in _ACADEMIC_TLDS):
        return TIER_GOVERNMENTAL_ACADEMIC
    if _host_matches(host, _ENCYCLOPEDIC_HOSTS):
        return TIER_ENCYCLOPEDIC
    if _host_matches(host, _ESTABLISHED_NEWS_HOSTS):
        return TIER_ESTABLISHED_NEWS
    if _host_matches(host, _LOW_VALUE_HOSTS):
        return TIER_LOW_VALUE
    return TIER_NEUTRAL


_TIER_MULTIPLIERS = {
    TIER_GOVERNMENTAL_ACADEMIC: 1.20,
    TIER_ENCYCLOPEDIC: 1.15,
    TIER_ESTABLISHED_NEWS: 1.05,
    TIER_NEUTRAL: 1.00,
    TIER_LOW_VALUE: 0.85,
}


def authority_multiplier(location: str) -> float:
    """Return the bounded ranking multiplier for `location`'s host,
    always within [MULTIPLIER_FLOOR, MULTIPLIER_CEILING]."""
    tier = classify_authority_tier(location)
    multiplier = _TIER_MULTIPLIERS.get(tier, 1.0)
    return max(MULTIPLIER_FLOOR, min(MULTIPLIER_CEILING, multiplier))


def _self_test() -> None:
    assert classify_authority_tier("") == TIER_NEUTRAL
    assert classify_authority_tier("/local/file/path.txt") == TIER_NEUTRAL
    assert classify_authority_tier("https://en.wikipedia.org/wiki/Cat") == TIER_ENCYCLOPEDIC
    assert classify_authority_tier("https://www.nist.gov/x") == TIER_GOVERNMENTAL_ACADEMIC
    assert classify_authority_tier("https://mit.edu/x") == TIER_GOVERNMENTAL_ACADEMIC
    assert classify_authority_tier("https://www.reuters.com/x") == TIER_ESTABLISHED_NEWS
    assert classify_authority_tier("https://www.reddit.com/r/x") == TIER_LOW_VALUE
    assert classify_authority_tier("https://example.com/x") == TIER_NEUTRAL
    # false-match guard
    assert classify_authority_tier("https://not-wikipedia.org.evil-site.com/x") == TIER_NEUTRAL
    assert authority_multiplier("https://en.wikipedia.org/wiki/Cat") == 1.15
    assert authority_multiplier("https://www.reddit.com/x") == 0.85
    assert authority_multiplier("") == 1.0
    assert MULTIPLIER_FLOOR <= authority_multiplier("https://mit.edu/x") <= MULTIPLIER_CEILING


if __name__ == "__main__":
    _self_test()
    print("authority self-test passed.")


__all__ = [
    "TIER_ENCYCLOPEDIC", "TIER_GOVERNMENTAL_ACADEMIC", "TIER_ESTABLISHED_NEWS",
    "TIER_NEUTRAL", "TIER_LOW_VALUE", "MULTIPLIER_FLOOR", "MULTIPLIER_CEILING",
    "classify_authority_tier", "authority_multiplier",
]


