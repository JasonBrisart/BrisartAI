"""
File: brisart_ai/knowledge/tests/test_diversity.py

Purpose
-------
Unit tests for brisart_ai.knowledge.diversity. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 12 test cases across TestJaccardSimilarity, TestDocumentSimilarity, TestDiversifyResults.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.diversity (diversify_results, document_similarity, jaccard_similarity)

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
- asserts: empty set.
- asserts: missing metadata scores zero.
- asserts: empty input.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_diversity.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_diversity.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.diversity import diversify_results, document_similarity, jaccard_similarity


class TestJaccardSimilarity(unittest.TestCase):
    def test_identical_sets(self):
        self.assertEqual(jaccard_similarity({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint_sets(self):
        self.assertEqual(jaccard_similarity({"a"}, {"b"}), 0.0)

    def test_empty_set(self):
        self.assertEqual(jaccard_similarity(set(), {"a"}), 0.0)


class TestDocumentSimilarity(unittest.TestCase):
    def test_same_host_contributes_base_similarity(self):
        a = {"location": "https://en.wikipedia.org/wiki/A", "title": "Alpha"}
        b = {"location": "https://en.wikipedia.org/wiki/B", "title": "Zeta"}
        self.assertGreater(document_similarity(a, b), 0.0)

    def test_missing_metadata_scores_zero(self):
        a = {}
        b = {"location": "https://example.com", "title": "Something"}
        self.assertEqual(document_similarity(a, b), 0.0)


class TestDiversifyResults(unittest.TestCase):
    def setUp(self):
        self.docs = [
            {"id": 1, "score": 10.0, "title": "History of Microsoft",
             "location": "https://en.wikipedia.org/wiki/Microsoft"},
            {"id": 2, "score": 9.0, "title": "History of Microsoft Corp",
             "location": "https://en.wikipedia.org/wiki/Microsoft_history"},
            {"id": 3, "score": 8.5, "title": "Bill Gates Biography",
             "location": "https://example.com/gates"},
            {"id": 4, "score": 8.0, "title": "Paul Allen Biography",
             "location": "https://example.org/allen"},
        ]

    def test_empty_input(self):
        self.assertEqual(diversify_results([]), [])

    def test_single_input_unchanged(self):
        single = [self.docs[0]]
        self.assertEqual(diversify_results(single), single)

    def test_top_result_always_highest_scored(self):
        result = diversify_results(self.docs, lambda_param=0.5)
        self.assertEqual(result[0]["id"], 1)

    def test_nothing_dropped(self):
        result = diversify_results(self.docs, lambda_param=0.5)
        self.assertEqual({d["id"] for d in result}, {1, 2, 3, 4})

    def test_pure_relevance_at_lambda_one(self):
        result = diversify_results(self.docs, lambda_param=1.0)
        self.assertEqual([d["id"] for d in result], [1, 2, 3, 4])

    def test_near_duplicate_pushed_down_at_low_lambda(self):
        result = diversify_results(self.docs, lambda_param=0.3)
        ids = [d["id"] for d in result]
        self.assertGreater(ids.index(2), 1)

    def test_max_results_does_not_drop_documents(self):
        result = diversify_results(self.docs, lambda_param=0.5, max_results=2)
        self.assertEqual(len(result), 4)


if __name__ == "__main__":
    unittest.main()



