"""
File: brisart_ai/tests/test_text_normalize.py

Purpose
-------
Unit tests for brisart_ai.text_normalize. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 21 test cases across TestNormalizePunctuation, TestHyphenVariants, TestAcronymExpansion, TestSynonymExpansion, TestMorphology, TestExpandQueryTerms.

Communication / relationships
------------------------------
- exercises brisart_ai.text_normalize (expand_acronyms, expand_query_terms, expand_synonyms, hyphen_variants, morphology_variants, normalize_for_match)

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
- asserts: empty input.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_text_normalize.py -v
    $ python -m pytest brisart_ai/tests/test_text_normalize.py --import-mode=importlib
"""
import unittest

from brisart_ai.text_normalize import (
    expand_acronyms, expand_query_terms, expand_synonyms, hyphen_variants,
    morphology_variants, normalize_for_match, normalize_punctuation,
)


class TestNormalizePunctuation(unittest.TestCase):
    def test_curly_quotes_folded_to_ascii(self):
        self.assertEqual(normalize_punctuation("Who\u2019s here?"), "Who's here?")

    def test_em_dash_folded_to_hyphen(self):
        self.assertEqual(normalize_punctuation("a\u2014b"), "a-b")

    def test_repeated_punctuation_collapsed(self):
        self.assertEqual(normalize_punctuation("wow!!!"), "wow!")

    def test_whitespace_collapsed(self):
        self.assertEqual(normalize_punctuation("a   b"), "a b")

    def test_idempotent(self):
        once = normalize_punctuation("Who\u2019s the CEO\u2014now???")
        twice = normalize_punctuation(once)
        self.assertEqual(once, twice)

    def test_empty_input(self):
        self.assertEqual(normalize_punctuation(""), "")


class TestHyphenVariants(unittest.TestCase):
    def test_hyphenated_term_expands_to_three_forms(self):
        variants = hyphen_variants("co-founder")
        self.assertEqual(variants, {"co-founder", "cofounder", "co founder"})

    def test_plain_term_returns_itself_only(self):
        self.assertEqual(hyphen_variants("microsoft"), {"microsoft"})

    def test_empty_term(self):
        self.assertEqual(hyphen_variants(""), set())


class TestAcronymExpansion(unittest.TestCase):
    def test_known_acronym_expands(self):
        expanded = expand_acronyms({"ceo"})
        self.assertIn("chief", expanded)
        self.assertIn("executive", expanded)

    def test_unknown_acronym_left_untouched(self):
        expanded = expand_acronyms({"xyzzy"})
        self.assertEqual(expanded, {"xyzzy"})

    def test_reverse_expansion_expansion_to_acronym(self):
        expanded = expand_acronyms({"artificial intelligence"})
        self.assertIn("ai", expanded)


class TestSynonymExpansion(unittest.TestCase):
    def test_known_synonym_group_expands(self):
        expanded = expand_synonyms({"founder"})
        self.assertTrue({"started", "began", "established"} & expanded)

    def test_unregistered_term_unaffected(self):
        expanded = expand_synonyms({"xyzzy"})
        self.assertEqual(expanded, {"xyzzy"})


class TestMorphology(unittest.TestCase):
    def test_plural_stripped(self):
        self.assertEqual(normalize_for_match("cats"), "cat")

    def test_short_word_untouched(self):
        self.assertEqual(normalize_for_match("as"), "as")

    def test_no_over_stripping(self):
        self.assertEqual(normalize_for_match("bus"), "bus")

    def test_morphology_variants_adds_stem(self):
        variants = morphology_variants({"cats"})
        self.assertIn("cat", variants)
        self.assertIn("cats", variants)


class TestExpandQueryTerms(unittest.TestCase):
    def test_combines_all_four_expansions(self):
        terms = expand_query_terms("Who is the CEO and co-founder?")
        self.assertIn("ceo", terms)
        self.assertIn("chief", terms)  # acronym expansion
        self.assertTrue({"cofounder", "co-founder"} & terms)  # hyphen variant

    def test_never_drops_original_terms(self):
        terms = expand_query_terms("transistor")
        self.assertIn("transistor", terms)

    def test_empty_query(self):
        self.assertEqual(expand_query_terms(""), set())


if __name__ == "__main__":
    unittest.main()


