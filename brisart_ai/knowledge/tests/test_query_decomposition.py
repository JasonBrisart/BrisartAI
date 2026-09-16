"""
File: brisart_ai/knowledge/tests/test_query_decomposition.py

Purpose
-------
Unit tests for brisart_ai.knowledge.query_decomposition. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 9 test cases across TestIsQuestionShaped, TestDecomposeQuery.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.query_decomposition (decompose_query, is_question_shaped)

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
- asserts: empty fragment.
- asserts: does not split compound subject.
- asserts: single question unchanged.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_query_decomposition.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_query_decomposition.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.query_decomposition import decompose_query, is_question_shaped


class TestIsQuestionShaped(unittest.TestCase):
    def test_wh_lead_word(self):
        self.assertTrue(is_question_shaped("who founded microsoft"))

    def test_non_question_fragment(self):
        self.assertFalse(is_question_shaped("bread and butter"))

    def test_empty_fragment(self):
        self.assertFalse(is_question_shaped(""))


class TestDecomposeQuery(unittest.TestCase):
    def test_splits_genuine_compound_question(self):
        result = decompose_query("who founded microsoft and when was it founded?")
        self.assertEqual(len(result), 2)
        self.assertIn("who founded microsoft", result[0].casefold())
        self.assertTrue(result[1].endswith("?"))

    def test_does_not_split_compound_subject(self):
        result = decompose_query("bill gates and paul allen founded microsoft")
        self.assertEqual(result, ["bill gates and paul allen founded microsoft"])

    def test_single_question_unchanged(self):
        result = decompose_query("who founded microsoft?")
        self.assertEqual(result, ["who founded microsoft?"])

    def test_or_is_never_a_split_point(self):
        result = decompose_query("who founded microsoft or apple?")
        self.assertEqual(result, ["who founded microsoft or apple?"])

    def test_empty_input(self):
        self.assertEqual(decompose_query(""), [""])
        self.assertEqual(decompose_query("   "), [""])

    def test_always_returns_nonempty_list(self):
        for query in ["", "a", "who founded microsoft and when?", "just words here"]:
            result = decompose_query(query)
            self.assertTrue(len(result) >= 1)


if __name__ == "__main__":
    unittest.main()


