"""
File: brisart_ai/knowledge/tests/test_synthesizer.py

Purpose
-------
Unit tests for brisart_ai.knowledge.synthesizer. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 17 test cases across TestModes, TestSentenceScore, TestSynthesize,
including the citation_sink structured-citation-capture behavior used by
BrisartService.ask() (see KI-010) for a UI mark-relevant/irrelevant control.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.synthesizer (format_source, query_wants_comparison, query_wants_quantity, query_wants_reason, sentence_score, synthesize)
- exercises brisart_ai.knowledge.citation_graph (CitationGraph)

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
- asserts: no overlap.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_synthesizer.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_synthesizer.py --import-mode=importlib
"""
import unittest
from brisart_ai.knowledge.synthesizer import (format_source, query_wants_comparison,
    query_wants_quantity, query_wants_reason, sentence_score, synthesize)
from brisart_ai.knowledge.citation_graph import CitationGraph

class TestModes(unittest.TestCase):
    def test_quantity(self): self.assertTrue(query_wants_quantity("how many cats are in america?"))
    def test_comparison(self): self.assertTrue(query_wants_comparison("do dogs outlive cats?"))
    def test_reason(self): self.assertTrue(query_wants_reason("why do cats purr?"))

class TestSentenceScore(unittest.TestCase):
    def test_no_overlap(self): self.assertEqual(sentence_score("unrelated content", {"zebra"}), 0.0)
    def test_overlap(self): self.assertGreater(sentence_score("the zebra ran fast", {"zebra"}), 0.0)
    def test_quantity_boost(self):
        self.assertGreater(sentence_score("an estimated 73.8 million cats live here", {"cats"}, quantity_mode=True),
                           sentence_score("cats are independent animals", {"cats"}, quantity_mode=True))

class TestSynthesize(unittest.TestCase):
    def test_empty(self): self.assertIn("don't have any indexed information", synthesize("x", []))
    def test_no_match(self):
        docs=[{"source_type":"file","location":"/a","title":"A","text":"completely unrelated filler content padding out this sentence to pass the length filter here"}]
        self.assertIn("none of them", synthesize("zzzznonexistent", docs).lower())
    def test_cited(self):
        docs=[{"id":1,"source_type":"file","location":"/a","title":"MS","text":"Microsoft was founded by Bill Gates and Paul Allen in nineteen seventy five in Albuquerque."}]
        r = synthesize("who founded microsoft", docs); self.assertIn("Sources:", r); self.assertIn("Gates", r)
    def test_confidence_line(self):
        docs=[{"id":1,"source_type":"web","location":"https://en.wikipedia.org/x","title":"A","text":"Microsoft was founded by Gates and Allen in 1975 in Albuquerque New Mexico."}]
        self.assertIn("Confidence:", synthesize("who founded microsoft", docs))
    def test_contradiction_flag(self):
        docs=[{"id":1,"source_type":"web","location":"https://a.com","title":"A","text":"Microsoft was founded in 1975 by Gates and Allen in Albuquerque."},
              {"id":2,"source_type":"web","location":"https://b.com","title":"B","text":"Microsoft was founded in 1981 according to this account of Gates and Allen."}]
        self.assertIn("disagree", synthesize("when was microsoft founded", docs))
    def test_negation_ranked_below(self):
        docs=[{"id":1,"source_type":"web","location":"https://a.com","title":"A","text":"Microsoft was founded by Bill Gates and Paul Allen in 1975 in Albuquerque."},
              {"id":2,"source_type":"web","location":"https://b.com","title":"B","text":"Some claim Microsoft was not founded by Gates alone and the whole story is disputed today."}]
        r = synthesize("who founded microsoft", docs)
        self.assertLess(r.index("[1]"), r.index("[2]"))
        self.assertIn("founded by Bill Gates", r.split("[2]")[0])
    def test_citation_graph_populated(self):
        g = CitationGraph()
        docs=[{"id":7,"source_type":"web","location":"https://a.com","title":"A","text":"Microsoft was founded by Gates and Allen in 1975 in Albuquerque New Mexico here."}]
        synthesize("who founded microsoft", docs, citation_graph=g)
        self.assertGreaterEqual(g.corroboration_count("founded microsoft"), 1)

    def test_citation_sink_populated_with_source_id_and_title(self):
        # KI-010: structured citation capture, so a UI can offer a
        # mark-relevant/irrelevant control per cited source without
        # parsing the answer text.
        docs=[{"id":42,"source_type":"file","location":"/a.txt","title":"History of Microsoft",
               "text":"Microsoft was founded by Bill Gates and Paul Allen in 1975 in Albuquerque."}]
        sink = []
        synthesize("who founded microsoft", docs, citation_sink=sink)
        self.assertEqual(len(sink), 1)
        self.assertEqual(sink[0]["source_id"], 42)
        self.assertEqual(sink[0]["title"], "History of Microsoft")
        self.assertEqual(sink[0]["display"], 1)

    def test_citation_sink_default_none_is_noop(self):
        # Purely additive: omitting citation_sink changes nothing about
        # the returned answer string.
        docs=[{"id":1,"source_type":"file","location":"/a.txt","title":"A",
               "text":"Microsoft was founded by Bill Gates and Paul Allen in 1975."}]
        with_sink = synthesize("who founded microsoft", docs, citation_sink=[])
        without_sink = synthesize("who founded microsoft", docs)
        self.assertEqual(with_sink, without_sink)

    def test_citation_sink_order_matches_sources_list(self):
        docs=[
            {"id":1,"source_type":"file","location":"/a.txt","title":"First Source",
             "text":"Microsoft was founded by Bill Gates and Paul Allen in 1975 here."},
            {"id":2,"source_type":"file","location":"/b.txt","title":"Second Source",
             "text":"Microsoft was founded in Albuquerque New Mexico by two young men."},
        ]
        sink = []
        synthesize("who founded microsoft", docs, citation_sink=sink)
        self.assertEqual(len(sink), 2)
        self.assertEqual({c["source_id"] for c in sink}, {1, 2})
        self.assertEqual([c["display"] for c in sink], [1, 2])

    def test_citation_sink_empty_when_no_documents(self):
        sink = []
        synthesize("x", [], citation_sink=sink)
        self.assertEqual(sink, [])

if __name__ == "__main__": unittest.main()



