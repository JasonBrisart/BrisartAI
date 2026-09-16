"""
File: brisart_ai/text_normalize.py

Purpose
-------
Query and document text normalization for the Brisart Relevance Engine:
hyphenation/punctuation normalization, acronym expansion, an explicit
synonym/alias registry, and conservative morphology (singular/plural,
light suffix folding). All four exist for the same reason: a literal
term-match ranker (rarity + presence, see knowledge/relevance_engine.py)
cannot see that "co-founder", "cofounder", and "co founder" are the same
concept, or that "AI" means "artificial intelligence", unless something
upstream tells it so. This module is that "something" -- it never
touches scoring math itself, it only expands/canonicalizes the term set
a query or document contributes into the ranker.

Communication / relationships
------------------------------
- brisart_ai/knowledge/ranker.py: search() calls expand_query_terms() to
  build the term set passed into scoring, as an addition alongside
  raw tokenize() -- never a replacement for it. expand_query_terms()
  itself calls normalize_punctuation() first, internally, before
  tokenizing and layering on hyphenation/acronym/synonym/morphology
  variants -- so "Who's the CEO?" and "who is the ceo" resolve to the
  same expanded term set.
- Imports only brisart_ai.util.tokenize() and the stdlib (re, unicodedata).
  Adding this module introduces NO new dependency on the rest of the
  codebase -- it is safe to drop in without touching
  knowledge/relevance_engine.py or knowledge/ranker.py's existing tests.

Settings / parameters
----------------------
- _DASH_CHARS / _QUOTE_CHARS: the set of Unicode dash and quote
  characters normalized down to ASCII "-" and "'"/'"' respectively,
  since a pasted question copied from a web page or a word processor
  routinely carries en-dashes, em-dashes, or curly quotes that a plain
  ASCII tokenizer would otherwise treat as unknown punctuation.
- ACRONYM_REGISTRY: a fixed, hand-maintained {acronym: (expansions,)}
  table. Deliberately finite and conservative (the same design
  philosophy as intent.py's _KNOWN_COMPANIES, tracked the same way in
  KNOWN_ISSUES.md) -- an acronym NOT in this table is left exactly as
  typed, never guessed at from surface form (e.g. never assuming every
  all-caps 2-4 letter token is an acronym).
- SYNONYM_REGISTRY: a fixed {canonical_term: (synonyms,)} table,
  expanded bidirectionally by build_synonym_lookup() so looking up any
  member of a synonym group returns every other member.
- MORPHOLOGY_SUFFIXES: an ordered, conservative suffix-stripping table
  used ONLY to decide "do these two surface forms refer to the same
  term for matching purposes" -- it is never applied to change what
  gets stored in the index, only what gets compared during a query.
  Deliberately narrower than a real stemmer (e.g. Porter/Snowball):
  no vowel-consonant pattern rules, no double-consonant handling,
  just a short list of high-confidence suffixes with a minimum stem
  length guard, so it never over-strips a short word into nonsense
  ("bus" -> "bu" is refused; "cats" -> "cat" is allowed).

Edge cases
----------
- expand_query_terms() never REMOVES a term the user typed; it only
  ADDS variants, exactly like the intent layer's "nudge, never filter"
  design principle documented in knowledge/ranker.py.
- Acronym and synonym lookups are case-insensitive; hyphenation
  variant generation preserves the original casing of the matched
  span internally is not attempted -- normalization always lowercases,
  since these variants exist purely for term-matching, not display.
- Empty/whitespace-only input returns an empty set/string, never
  raises, matching brisart_ai.util.tokenize()'s own None/"" contract.
- normalize_punctuation() is idempotent: running it twice on its own
  output produces the same result, so callers never need to guard
  against double-normalization.

Known limitations
-----------------
- ACRONYM_REGISTRY and SYNONYM_REGISTRY are finite hand-maintained
  tables; an unlisted acronym/synonym is passed through unchanged.
- morphology handling is a conservative suffix stripper with a minimum
  stem-length guard, not a real stemmer; irregular forms ("mice",
  "children") are not normalized.
- Expansion is purely additive -- it never removes a typed term -- so it
  can broaden recall but cannot correct a wrong term (see spelling.py).

Examples
--------
    >>> normalize_punctuation("Who\u2019s the CEO\u2014now?")
    "Who's the CEO-now?"
    >>> "cofounder" in hyphen_variants("co-founder")
    True
    >>> "chief" in expand_query_terms("who is the ceo")
    True
"""
from __future__ import annotations
import re
import unicodedata
from typing import Dict, FrozenSet, Set, Tuple

from brisart_ai.util import tokenize

# ---------------------------------------------------------------------------
# 1. Punctuation / hyphenation normalization
# ---------------------------------------------------------------------------

_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"  # hyphen..minus sign
_QUOTE_CHARS_SINGLE = "\u2018\u2019\u201a\u201b\u2032"
_QUOTE_CHARS_DOUBLE = "\u201c\u201d\u201e\u201f\u2033"
_DASH_TABLE = {ord(c): "-" for c in _DASH_CHARS}
_QUOTE_TABLE = {ord(c): "'" for c in _QUOTE_CHARS_SINGLE}
_QUOTE_TABLE.update({ord(c): '"' for c in _QUOTE_CHARS_DOUBLE})
_WHITESPACE_RE = re.compile(r"\s+")
_REPEATED_PUNCT_RE = re.compile(r"([!?.,;:])\1{1,}")


def normalize_punctuation(text: str) -> str:
    """Fold Unicode dashes/quotes to ASCII, collapse whitespace and
    repeated punctuation. Idempotent: re-running on its own output is
    a no-op."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(_DASH_TABLE).translate(_QUOTE_TABLE)
    normalized = _REPEATED_PUNCT_RE.sub(r"\1", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def hyphen_variants(term: str) -> Set[str]:
    """For a term containing '-' or an internal space, return the
    hyphenated/joined/spaced surface forms so any one of them in a
    query matches any of them in an indexed document. A term with
    neither returns just itself."""
    if not term:
        return set()
    cleaned = term.strip().casefold()
    if "-" not in cleaned and " " not in cleaned:
        return {cleaned}
    parts = re.split(r"[-\s]+", cleaned)
    parts = [p for p in parts if p]
    if not parts:
        return {cleaned}
    return {
        "-".join(parts),
        "".join(parts),
        " ".join(parts),
    }


# ---------------------------------------------------------------------------
# 2. Acronym expansion
# ---------------------------------------------------------------------------

ACRONYM_REGISTRY: Dict[str, Tuple[str, ...]] = {
    "ai": ("artificial intelligence",),
    "ml": ("machine learning",),
    "api": ("application programming interface",),
    "ceo": ("chief executive officer",),
    "cfo": ("chief financial officer",),
    "cto": ("chief technology officer",),
    "coo": ("chief operating officer",),
    "pi": ("principal investigator",),
    "r&d": ("research and development",),
    "faq": ("frequently asked questions",),
    "os": ("operating system",),
    "ui": ("user interface",),
    "ux": ("user experience",),
    "url": ("uniform resource locator",),
    "html": ("hypertext markup language",),
    "http": ("hypertext transfer protocol",),
    "json": ("javascript object notation",),
    "sql": ("structured query language",),
    "gui": ("graphical user interface",),
    "cli": ("command line interface",),
    "cpu": ("central processing unit",),
    "gpu": ("graphics processing unit",),
    "ram": ("random access memory",),
    "ipo": ("initial public offering",),
    "gdp": ("gross domestic product",),
    "us": ("united states",),
    "usa": ("united states", "united states of america"),
    "uk": ("united kingdom",),
    "eu": ("european union",),
    "un": ("united nations",),
    "nasa": ("national aeronautics and space administration",),
    "fbi": ("federal bureau of investigation",),
    "cia": ("central intelligence agency",),
    "nato": ("north atlantic treaty organization",),
    "who": ("world health organization",),
    "vc": ("venture capital", "venture capitalist"),
    "ipo": ("initial public offering",),
    "b2b": ("business to business",),
    "b2c": ("business to consumer",),
    "saas": ("software as a service",),
    "llm": ("large language model",),
    "nlp": ("natural language processing",),
    "www": ("world wide web",),
}


def _acronym_lookup() -> Dict[str, FrozenSet[str]]:
    table: Dict[str, Set[str]] = {}
    for acronym, expansions in ACRONYM_REGISTRY.items():
        bucket = table.setdefault(acronym, set())
        bucket.update(expansions)
        for expansion in expansions:
            reverse = table.setdefault(expansion, set())
            reverse.add(acronym)
    return {key: frozenset(value) for key, value in table.items()}


_ACRONYM_LOOKUP = _acronym_lookup()


def expand_acronyms(terms: Set[str]) -> Set[str]:
    """Add acronym expansions (and reverse: expansion -> acronym) for
    any term present in ACRONYM_REGISTRY. Multi-word expansions are
    added as their own tokenized terms, not as a single joined blob,
    so they participate in ordinary term matching."""
    expanded: Set[str] = set(terms)
    for term in terms:
        for match in _ACRONYM_LOOKUP.get(term.casefold(), ()):
            expanded.update(tokenize(match))
            expanded.add(match.casefold())
    return expanded


# ---------------------------------------------------------------------------
# 3. Explicit synonym / alias registry
# ---------------------------------------------------------------------------

SYNONYM_REGISTRY: Dict[str, Tuple[str, ...]] = {
    "founder": ("co-founder", "cofounder", "started", "began", "established"),
    "invented": ("created", "developed", "designed", "devised", "pioneered"),
    "population": ("residents", "inhabitants", "people", "populace"),
    "explain": ("describe", "clarify", "elaborate", "detail"),
    "purchase": ("buy", "acquire", "obtain"),
    "help": ("assist", "aid", "support"),
    "problem": ("issue", "bug", "defect", "fault"),
    "fix": ("repair", "resolve", "patch", "correct"),
    "fast": ("quick", "rapid", "speedy"),
    "slow": ("sluggish", "laggy"),
    "big": ("large", "huge", "sizable"),
    "small": ("tiny", "little", "compact"),
    "cheap": ("inexpensive", "affordable", "low-cost"),
    "expensive": ("costly", "pricey"),
    "die": ("death", "passed away", "deceased"),
    "start": ("begin", "commence", "launch"),
    "end": ("finish", "conclude", "terminate"),
    "increase": ("rise", "grow", "climb"),
    "decrease": ("decline", "drop", "fall"),
    "guide": ("tutorial", "walkthrough", "howto"),
}


def build_synonym_lookup() -> Dict[str, FrozenSet[str]]:
    """Bidirectional expansion of SYNONYM_REGISTRY: looking up any
    member of a synonym group returns every other member of that
    group (never the term itself)."""
    groups = []
    for canonical, synonyms in SYNONYM_REGISTRY.items():
        groups.append({canonical.casefold()} | {s.casefold() for s in synonyms})
    lookup: Dict[str, Set[str]] = {}
    for group in groups:
        for term in group:
            lookup.setdefault(term, set()).update(group - {term})
    return {key: frozenset(value) for key, value in lookup.items()}


_SYNONYM_LOOKUP = build_synonym_lookup()


def expand_synonyms(terms: Set[str]) -> Set[str]:
    """Add every registered synonym for each term present in the
    registry. Multi-word synonyms are tokenized so they participate in
    ordinary term matching."""
    expanded: Set[str] = set(terms)
    for term in terms:
        for synonym in _SYNONYM_LOOKUP.get(term.casefold(), ()):
            expanded.update(tokenize(synonym))
            expanded.add(synonym)
    return expanded


# ---------------------------------------------------------------------------
# 4. Conservative morphology handling
# ---------------------------------------------------------------------------

# (suffix, minimum_stem_length) -- minimum_stem_length guards against
# over-stripping short words (e.g. "as" is never touched; "bus" is
# never stripped to "bu").
MORPHOLOGY_SUFFIXES: Tuple[Tuple[str, int], ...] = (
    ("ies", 3),   # companies -> compan (+y handled by _restore_y)
    ("es", 3),    # boxes -> box
    ("s", 3),     # cats -> cat
    ("ing", 4),   # running -> runn (kept crude; matching-only use)
    ("ed", 3),    # invented -> invent
)


def _strip_one_suffix(word: str) -> str:
    for suffix, min_len in MORPHOLOGY_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_len:
            stem = word[: -len(suffix)]
            if suffix == "ies":
                return stem + "y"
            return stem
    return word


def normalize_for_match(term: str) -> str:
    """Return a conservative morphological stem of `term`, used ONLY
    to decide whether two surface forms should be treated as the same
    term when matching a query against an index -- never used to
    rewrite what gets stored."""
    cleaned = term.strip().casefold()
    if len(cleaned) < 4:
        return cleaned
    return _strip_one_suffix(cleaned)


def morphology_variants(terms: Set[str]) -> Set[str]:
    """Add the conservative morphological stem of each term (e.g. a
    query for 'cats' also matches a document that only contains
    'cat')."""
    expanded: Set[str] = set(terms)
    for term in terms:
        stem = normalize_for_match(term)
        if stem != term.casefold():
            expanded.add(stem)
    return expanded


# ---------------------------------------------------------------------------
# Combined entry point
# ---------------------------------------------------------------------------

def expand_query_terms(query: str) -> Set[str]:
    """The single entry point: normalize punctuation, tokenize, then
    layer hyphenation variants, acronym expansion, synonym expansion,
    and conservative morphology on top -- additively, never removing
    any term the user actually typed."""
    normalized = normalize_punctuation(query)
    base_terms = set(tokenize(normalized))
    expanded = set(base_terms)
    for term in base_terms:
        expanded |= hyphen_variants(term)
    expanded = expand_acronyms(expanded)
    expanded = expand_synonyms(expanded)
    expanded = morphology_variants(expanded)
    return expanded


def _self_test() -> None:
    assert normalize_punctuation("Who\u2019s the CEO\u2014now?") == "Who's the CEO-now?"
    assert normalize_punctuation("a!!! b??") == "a! b?"
    assert hyphen_variants("co-founder") == {"co-founder", "cofounder", "co founder"}
    assert hyphen_variants("microsoft") == {"microsoft"}
    expanded = expand_acronyms({"ai"})
    assert "artificial" in expanded and "intelligence" in expanded
    expanded_syn = expand_synonyms({"founder"})
    assert "cofounder" in expanded_syn or "co-founder" in expanded_syn
    assert normalize_for_match("cats") == "cat"
    assert normalize_for_match("as") == "as"  # too short to touch
    assert normalize_for_match("bus") == "bus"  # guarded: no over-strip
    terms = expand_query_terms("Who is the CEO and co-founder?")
    assert "ceo" in terms
    assert "chief" in terms  # from acronym expansion
    assert "cofounder" in terms or "co-founder" in terms


if __name__ == "__main__":
    _self_test()
    print("text_normalize self-test passed.")


__all__ = [
    "ACRONYM_REGISTRY", "SYNONYM_REGISTRY", "MORPHOLOGY_SUFFIXES",
    "normalize_punctuation", "hyphen_variants", "expand_acronyms",
    "build_synonym_lookup", "expand_synonyms", "normalize_for_match",
    "morphology_variants", "expand_query_terms",
]



