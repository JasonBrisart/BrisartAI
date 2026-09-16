"""
File: brisart_ai/knowledge/tests/test_citation_graph.py

Purpose
-------
Unit tests for brisart_ai.knowledge.citation_graph. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 8 test cases across TestTopicKey, TestCitationGraph.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.citation_graph (CitationGraph, topic_key)

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
- asserts: empty topic.
- asserts: zero citations initially.
- asserts: is single source topic.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_citation_graph.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_citation_graph.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.citation_graph import CitationGraph, topic_key


class TestTopicKey(unittest.TestCase):
    def test_normalizes_whitespace_and_case(self):
        self.assertEqual(topic_key("Microsoft  Founders"), topic_key("microsoft founders"))

    def test_empty_topic(self):
        self.assertEqual(topic_key(""), "")


class TestCitationGraph(unittest.TestCase):
    def setUp(self):
        self.graph = CitationGraph()

    def test_zero_citations_initially(self):
        self.assertEqual(self.graph.corroboration_count("anything"), 0)

    def test_add_citation_increments_count(self):
        self.graph.add_citation("Microsoft Founders", 1)
        self.graph.add_citation("Microsoft Founders", 2)
        self.assertEqual(self.graph.corroboration_count("microsoft founders"), 2)

    def test_idempotent_citation(self):
        self.graph.add_citation("Topic", 1)
        self.graph.add_citation("Topic", 1)
        self.assertEqual(self.graph.corroboration_count("Topic"), 1)

    def test_is_single_source_topic(self):
        self.graph.add_citation("Solo Topic", 1)
        self.assertTrue(self.graph.is_single_source_topic("Solo Topic"))
        self.graph.add_citation("Solo Topic", 2)
        self.assertFalse(self.graph.is_single_source_topic("Solo Topic"))

    def test_get_related_sources(self):
        self.graph.add_citation("Topic A", 1)
        self.graph.add_citation("Topic A", 2)
        related = self.graph.get_related_sources(1)
        self.assertIn(2, related)
        self.assertNotIn(1, related)

    def test_ignores_empty_topic_or_falsy_source(self):
        self.graph.add_citation("", 99)
        self.graph.add_citation("some topic", None)
        self.assertEqual(self.graph.corroboration_count(""), 0)
        self.assertEqual(self.graph.corroboration_count("some topic"), 0)


if __name__ == "__main__":
    unittest.main()



