"""
File: brisart_ai/tests/test_spelling.py

Purpose
-------
Unit tests for brisart_ai.spelling. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 15 test cases across TestLevenshteinDistance, TestMaxEditDistanceFor, TestVocabularyAndCorrections.

Communication / relationships
------------------------------
- exercises brisart_ai.spelling (build_vocabulary, is_likely_typo, levenshtein_distance, max_edit_distance_for, suggest_corrections)

Settings / parameters
---------------------
- Standard unittest.TestCase suite; run with pytest
  (--import-mode=importlib) or `python -m pytest`.
- Uses only in-memory / temp-dir fixtures where any state is
  needed; no network, no external services, no shared global state.
- No tunable parameters of its own; assertions pin the behavior
  and point values defined in the module under test.

Edge cases
----------
- asserts: empty strings.
- asserts: single substitution.
- asserts: single transposition counts as two.
- asserts: short word gets zero budget.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_spelling.py -v
    $ python -m pytest brisart_ai/tests/test_spelling.py --import-mode=importlib
"""
import unittest

from brisart_ai.spelling import (
    build_vocabulary, is_likely_typo, levenshtein_distance,
    max_edit_distance_for, suggest_corrections,
)


class TestLevenshteinDistance(unittest.TestCase):
    def test_identical_strings(self):
        self.assertEqual(levenshtein_distance("microsoft", "microsoft"), 0)

    def test_empty_strings(self):
        self.assertEqual(levenshtein_distance("", ""), 0)
        self.assertEqual(levenshtein_distance("abc", ""), 3)
        self.assertEqual(levenshtein_distance("", "abc"), 3)

    def test_classic_example(self):
        self.assertEqual(levenshtein_distance("kitten", "sitting"), 3)

    def test_single_substitution(self):
        self.assertEqual(levenshtein_distance("cat", "cot"), 1)

    def test_single_transposition_counts_as_two(self):
        # Plain Levenshtein (no transposition op) counts a swap as 2 edits.
        self.assertEqual(levenshtein_distance("ab", "ba"), 2)


class TestMaxEditDistanceFor(unittest.TestCase):
    def test_short_word_gets_zero_budget(self):
        self.assertEqual(max_edit_distance_for("cat"), 0)

    def test_medium_word_gets_one(self):
        self.assertEqual(max_edit_distance_for("cats"), 1)

    def test_long_word_gets_two(self):
        self.assertEqual(max_edit_distance_for("microsoft"), 2)


class TestVocabularyAndCorrections(unittest.TestCase):
    def setUp(self):
        self.vocab = build_vocabulary({
            "microsoft": 5, "transistor": 3, "telephone": 2, "ai": 10, "cat": 2,
        })

    def test_short_terms_excluded_from_vocabulary(self):
        self.assertNotIn("ai", self.vocab)
        self.assertNotIn("cat", self.vocab)

    def test_suggests_known_typo(self):
        self.assertEqual(suggest_corrections("mircosoft", self.vocab), ["microsoft"])

    def test_no_suggestion_for_known_term(self):
        self.assertEqual(suggest_corrections("microsoft", self.vocab), [])

    def test_no_suggestion_for_short_term(self):
        self.assertEqual(suggest_corrections("cot", self.vocab), [])

    def test_no_suggestion_beyond_budget(self):
        self.assertEqual(suggest_corrections("zzzzzzzzz", self.vocab), [])

    def test_is_likely_typo(self):
        self.assertTrue(is_likely_typo("trasistor", self.vocab))
        self.assertFalse(is_likely_typo("banana", self.vocab))

    def test_empty_vocabulary(self):
        self.assertEqual(suggest_corrections("microsoft", {}), [])


if __name__ == "__main__":
    unittest.main()



