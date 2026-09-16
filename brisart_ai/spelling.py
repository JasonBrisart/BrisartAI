"""
File: brisart_ai/spelling.py

Purpose
-------
Typo detection and spelling suggestion for query terms, using a
from-scratch pure-Python Levenshtein edit-distance implementation (no
difflib, no external fuzzy-matching library) plus a corpus-driven
vocabulary of terms actually seen in the index. This exists so a
one-character typo in a question ("mircosoft", "trasistor") does not
silently fall through to zero results the way a literal term-match
ranker otherwise would.

Communication / relationships
------------------------------
- brisart_ai/knowledge/ranker.py: search() calls suggest_corrections()
  whenever a query term has zero document frequency in the index,
  offering the ranker a corrected term to ALSO search for -- additively,
  exactly like the intent layer's own "hint, not filter" design.
- Imports only the stdlib; no dependency on any other brisart_ai
  module, so it can be dropped into the project without touching
  knowledge/index.py's schema.

Settings / parameters
----------------------
- MAX_EDIT_DISTANCE_BY_LENGTH: the edit-distance budget scales with
  word length -- 0 (no correction attempted) under 4 characters, 1 for
  4-6 characters, 2 for 7+ characters -- since a short word carries too
  little information for a distance-based correction to be reliable
  (e.g. "cat" is edit-distance 1 from "car", "cot", "bat", "cap", ...;
  correcting it would be a coin flip, not a fix).
- levenshtein_distance(a, b): classic dynamic-programming edit distance
  (insertion/deletion/substitution each cost 1), O(len(a) * len(b))
  time, O(min(len(a), len(b))) space via a single rolling row.
- build_vocabulary(term_counts): accepts a term -> document_frequency
  mapping (in the real pipeline, read directly from knowledge/index.py's
  terms table -- no separate corpus scan needed) and filters out terms
  shorter than MIN_VOCAB_TERM_LENGTH as correction candidates.
- MAX_SUGGESTIONS: correction results are capped (default 3) and
  returned ordered by (edit distance, then descending document
  frequency), so a more common term wins a tie over a rarer one.

Edge cases
----------
- suggest_corrections() NEVER replaces the original query term -- the
  literal term the user typed is always searched, and a correction (if
  any) is offered as an ADDITIONAL candidate term, only when the
  literal term is entirely absent from the vocabulary (document
  frequency 0). A term already present in the vocabulary, even if
  rare, is never "corrected" out from under the user.
- A tie among multiple equally-close vocabulary terms returns all of
  them (bounded by MAX_SUGGESTIONS), not an arbitrary single pick.
- Vocabulary terms shorter than MIN_VOCAB_TERM_LENGTH characters are
  excluded as correction candidates (too easy to falsely match one
  another at edit distance 1).
- An empty or whitespace-only term, or an empty vocabulary, returns an
  empty suggestion list rather than raising.

Known limitations
-----------------
- Correction is edit-distance only (no phonetic or context model), so
  among several equally-close real words it returns all of them ordered
  by corpus frequency, not a single context-correct pick.
- Short terms (< 4 chars) get a zero budget and are never corrected, to
  avoid noisy one-edit matches.
- Candidates come only from the supplied vocabulary; a correct spelling
  absent from the corpus cannot be suggested.

Examples
--------
    >>> levenshtein_distance("kitten", "sitting")
    3
    >>> vocab = build_vocabulary({"microsoft": 5, "transistor": 3})
    >>> suggest_corrections("mircosoft", vocab)
    ['microsoft']
"""
from __future__ import annotations
from typing import Dict, List, Tuple

MIN_VOCAB_TERM_LENGTH = 4
MAX_SUGGESTIONS = 3


def levenshtein_distance(a: str, b: str) -> int:
    """Classic single-row dynamic-programming edit distance."""
    a = a or ""
    b = b or ""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    # Ensure `b` is the shorter string, to minimize row width.
    if len(b) > len(a):
        a, b = b, a
    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current_row = [i] + [0] * len(b)
        for j, char_b in enumerate(b, start=1):
            insert_cost = current_row[j - 1] + 1
            delete_cost = previous_row[j] + 1
            substitute_cost = previous_row[j - 1] + (0 if char_a == char_b else 1)
            current_row[j] = min(insert_cost, delete_cost, substitute_cost)
        previous_row = current_row
    return previous_row[-1]


def max_edit_distance_for(term: str) -> int:
    """Length-scaled edit-distance budget. 0 means "do not attempt a
    correction for this term at all"."""
    length = len(term or "")
    if length < 4:
        return 0
    if length <= 6:
        return 1
    return 2


def build_vocabulary(term_counts: Dict[str, int]) -> Dict[str, int]:
    """Filter a raw term -> document_frequency mapping down to terms
    usable as correction candidates (length >= MIN_VOCAB_TERM_LENGTH)."""
    return {
        term: count
        for term, count in (term_counts or {}).items()
        if len(term) >= MIN_VOCAB_TERM_LENGTH and count > 0
    }


def suggest_corrections(
    term: str,
    vocabulary: Dict[str, int],
    max_suggestions: int = MAX_SUGGESTIONS,
) -> List[str]:
    """Suggest spelling corrections for `term` from `vocabulary`.
    Returns [] if `term` is already in the vocabulary (nothing to
    correct), if `term` is too short to attempt correction, or if no
    vocabulary term is within the length-scaled edit-distance budget."""
    cleaned = (term or "").strip().casefold()
    if not cleaned or not vocabulary:
        return []
    if cleaned in vocabulary:
        return []
    budget = max_edit_distance_for(cleaned)
    if budget <= 0:
        return []
    candidates: List[Tuple[int, int, str]] = []  # (distance, -freq, term)
    for vocab_term, frequency in vocabulary.items():
        if vocab_term == cleaned:
            continue
        # Cheap length pre-filter before paying for the DP table.
        if abs(len(vocab_term) - len(cleaned)) > budget:
            continue
        distance = levenshtein_distance(cleaned, vocab_term)
        if distance <= budget:
            candidates.append((distance, -frequency, vocab_term))
    candidates.sort()
    return [term for _dist, _neg_freq, term in candidates[:max_suggestions]]


def is_likely_typo(term: str, vocabulary: Dict[str, int]) -> bool:
    """True when `term` is absent from the vocabulary but at least one
    correction candidate exists within budget -- a convenience
    predicate for callers that just want a yes/no signal."""
    return bool(suggest_corrections(term, vocabulary, max_suggestions=1))


def _self_test() -> None:
    assert levenshtein_distance("", "") == 0
    assert levenshtein_distance("cat", "cat") == 0
    assert levenshtein_distance("cat", "cats") == 1
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("microsoft", "mircosoft") == 2
    assert max_edit_distance_for("cat") == 0   # too short
    assert max_edit_distance_for("cats") == 1
    assert max_edit_distance_for("microsoft") == 2
    vocab = build_vocabulary({"microsoft": 5, "transistor": 3, "ai": 10, "cat": 2})
    assert "ai" not in vocab  # too short
    assert "cat" not in vocab  # too short (3 chars)
    suggestions = suggest_corrections("mircosoft", vocab)
    assert suggestions == ["microsoft"]
    assert suggest_corrections("microsoft", vocab) == []  # already known
    assert suggest_corrections("cat", vocab) == []  # too short to attempt
    assert is_likely_typo("trasistor", vocab) is True
    assert is_likely_typo("banana", vocab) is False


if __name__ == "__main__":
    _self_test()
    print("spelling self-test passed.")


__all__ = [
    "MIN_VOCAB_TERM_LENGTH", "MAX_SUGGESTIONS",
    "levenshtein_distance", "max_edit_distance_for", "build_vocabulary",
    "suggest_corrections", "is_likely_typo",
]


