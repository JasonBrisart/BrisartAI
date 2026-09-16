"""
File: brisart_ai/knowledge/entity_registry.py

Purpose
-------
Canonicalizes named-entity surface forms so "Bill Gates", "William
Gates", and "William H. Gates III" are recognized as the SAME entity
rather than three unrelated capitalized-phrase hits. knowledge/vault.py's
extract_entities_from_text() already pulls capitalized phrases out of
indexed text (a regex heuristic, not machine learning, by design -- see
vault.py's own docstring), but it has no concept of aliasing: every
distinct surface form becomes its own row in the entities table today.
This module sits on top of that extraction step and resolves a raw
extracted name down to one canonical identity before it is stored or
counted, so entity-frequency reporting (vault_report()'s "Top
Entities" section) and citation-graph corroboration counting (see
citation_graph.py) are not silently fragmented across aliases.

Communication / relationships
------------------------------
- knowledge/vault.py: rebuild_entities() calls resolve_entity_name() on
  every name extract_entities_from_text() finds, right before the
  INSERT OR IGNORE INTO entities(...) step, so aliases of the same
  person collapse to a single entity row instead of fragmenting across
  surface forms.
- Imports only the stdlib (re); no dependency on any other brisart_ai
  module.

Settings / parameters
----------------------
- _TITLE_PREFIXES / _SUFFIX_TOKENS: stripped from a name before
  comparison -- "Mr.", "Mrs.", "Dr.", "Prof." as leading titles; "Jr.",
  "Sr.", "II", "III", "IV" as trailing generational suffixes -- since
  these are the single largest source of spurious non-matches between
  otherwise-identical names ("Dr. Jane Smith" vs "Jane Smith").
  Deliberately small and conservative rather than an exhaustive title
  list.
- ALIAS_REGISTRY: an explicit, hand-maintained
  {canonical_name: (aliases,)} table for well-known name variations
  that title/suffix stripping alone cannot bridge (e.g. "Bill Gates"
  vs "William Gates" -- different given-name forms, not just extra
  titles). Deliberately finite, following the same "explicit and
  reviewable beats guessed and wrong" philosophy as intent.py's
  _KNOWN_COMPANIES.
- register_alias(canonical, alias): lets a caller add a new alias pair
  at runtime (e.g. from a user-confirmed merge in a future UI), without
  needing a code change for every new entity encountered.
- SIMILARITY consideration: this module deliberately does NOT attempt
  fuzzy/edit-distance name matching (that risk belongs to
  brisart_ai/spelling.py's typo-correction use case, which operates on
  short query terms, not proper names) -- merging two DIFFERENT
  people's names because they are edit-distance 2 apart is a much
  worse failure mode than leaving two aliases of the same person
  unmerged, so this module only merges via title/suffix stripping and
  the explicit ALIAS_REGISTRY.

Edge cases
----------
- resolve_entity_name() is idempotent: resolving an already-canonical
  name returns it unchanged.
- A name not covered by title/suffix stripping or ALIAS_REGISTRY
  returns exactly as given (title-cased whitespace normalization only)
  -- never guessed at.
- Comparison is case-insensitive but the RETURNED canonical form
  preserves standard title-case, since these are used for display,
  not just internal matching.
- Empty/whitespace-only input returns "" rather than raising.

Known limitations
-----------------
- Aliasing is explicit-list plus title/suffix stripping only; there is
  deliberately NO fuzzy name matching, so an unlisted nickname or
  misspelling is not merged (a safe under-merge, never a wrong merge).
- ALIAS_REGISTRY is finite and hand-maintained; new entities need a new
  entry or a runtime register_alias() call.
- Runtime register_alias() additions are not persisted across restarts.

Examples
--------
    >>> resolve_entity_name("William H. Gates III")
    'Bill Gates'
    >>> are_same_entity("Bill Gates", "William Gates")
    True
    >>> dedupe_entity_names(["Bill Gates", "William Gates", "Paul Allen"])
    {'Bill Gates', 'Paul Allen'}
"""
from __future__ import annotations
import re
from typing import Dict, Set

_TITLE_PREFIXES = (
    "mr.", "mr", "mrs.", "mrs", "ms.", "ms", "dr.", "dr", "prof.", "prof",
    "sir", "dame", "hon.", "hon",
)
_SUFFIX_TOKENS = ("jr.", "jr", "sr.", "sr", "ii", "iii", "iv", "v")

ALIAS_REGISTRY: Dict[str, tuple] = {
    "Bill Gates": ("William Gates", "William H. Gates III", "William H Gates"),
    "Paul Allen": ("Paul G. Allen", "Paul G Allen"),
    "Steve Jobs": ("Steven Jobs", "Steven P. Jobs"),
    "Larry Page": ("Lawrence Page", "Lawrence E. Page"),
    "Jeff Bezos": ("Jeffrey Bezos", "Jeffrey P. Bezos"),
    "Larry Ellison": ("Lawrence Ellison", "Lawrence J. Ellison"),
    "Bob Miner": ("Robert Miner", "Robert N. Miner"),
}

_WHITESPACE_RE = re.compile(r"\s+")


def _build_alias_lookup() -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for canonical, aliases in ALIAS_REGISTRY.items():
        lookup[canonical.casefold()] = canonical
        for alias in aliases:
            lookup[alias.casefold()] = canonical
    return lookup


_ALIAS_LOOKUP = _build_alias_lookup()


def register_alias(canonical: str, alias: str) -> None:
    """Register a new alias -> canonical mapping at runtime. Does not
    persist across process restarts; a caller wanting persistence is
    responsible for writing the pair back to ALIAS_REGISTRY or an
    external store."""
    if not canonical or not alias:
        return
    _ALIAS_LOOKUP[alias.strip().casefold()] = canonical.strip()
    _ALIAS_LOOKUP.setdefault(canonical.strip().casefold(), canonical.strip())


def _strip_titles_and_suffixes(name: str) -> str:
    tokens = name.split()
    while tokens and tokens[0].casefold().rstrip(".") in {
        t.rstrip(".") for t in _TITLE_PREFIXES
    }:
        tokens.pop(0)
    while tokens and tokens[-1].casefold().rstrip(".") in {
        t.rstrip(".") for t in _SUFFIX_TOKENS
    }:
        tokens.pop()
    return " ".join(tokens)


def resolve_entity_name(name: str) -> str:
    """Return the canonical form of `name`: title/suffix stripped, then
    checked against ALIAS_REGISTRY (case-insensitively). Falls back to
    the whitespace-normalized, title/suffix-stripped input when no
    alias entry applies."""
    if not name or not name.strip():
        return ""
    normalized = _WHITESPACE_RE.sub(" ", name).strip()
    stripped = _strip_titles_and_suffixes(normalized)
    if not stripped:
        stripped = normalized
    canonical = _ALIAS_LOOKUP.get(stripped.casefold())
    if canonical:
        return canonical
    # Also try the un-stripped original, in case an alias entry itself
    # includes a title/suffix (unusual, but not assumed impossible).
    canonical = _ALIAS_LOOKUP.get(normalized.casefold())
    if canonical:
        return canonical
    return stripped


def are_same_entity(name_a: str, name_b: str) -> bool:
    """True when both names resolve to the same canonical identity."""
    return bool(name_a) and bool(name_b) and (
        resolve_entity_name(name_a).casefold() == resolve_entity_name(name_b).casefold()
    )


def dedupe_entity_names(names) -> Set[str]:
    """Collapse an iterable of raw extracted names down to the set of
    distinct canonical identities."""
    return {resolve_entity_name(name) for name in names if name and name.strip()}


def _self_test() -> None:
    assert resolve_entity_name("") == ""
    assert resolve_entity_name("   ") == ""
    assert resolve_entity_name("Bill Gates") == "Bill Gates"
    assert resolve_entity_name("William Gates") == "Bill Gates"
    assert resolve_entity_name("William H. Gates III") == "Bill Gates"
    assert resolve_entity_name("Dr. Bill Gates") == "Bill Gates"
    assert are_same_entity("Bill Gates", "William H. Gates III")
    assert not are_same_entity("Bill Gates", "Paul Allen")
    assert resolve_entity_name("Jane Doe") == "Jane Doe"  # not in registry, unchanged
    register_alias("Jane Doe", "J. Doe")
    assert resolve_entity_name("J. Doe") == "Jane Doe"
    names = ["Bill Gates", "William Gates", "Paul Allen", "Paul G. Allen"]
    assert dedupe_entity_names(names) == {"Bill Gates", "Paul Allen"}


if __name__ == "__main__":
    _self_test()
    print("entity_registry self-test passed.")


__all__ = [
    "ALIAS_REGISTRY", "register_alias", "resolve_entity_name",
    "are_same_entity", "dedupe_entity_names",
]


