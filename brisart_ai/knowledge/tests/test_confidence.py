"""
File: brisart_ai/knowledge/tests/test_confidence.py

Purpose
-------
Unit tests for brisart_ai.knowledge.confidence. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 12 test cases across TestComputeConfidence, TestDetectContradictions, TestDetectNegationContradiction.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.citation_graph (CitationGraph)
- exercises brisart_ai.knowledge.confidence (ChosenSentence, compute_confidence, detect_contradictions, detect_negation_contradiction)

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
- asserts: empty input is zero.
- asserts: single authoritative source nonzero.
- asserts: confidence bounded zero to one.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_confidence.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_confidence.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.citation_graph import CitationGraph
from brisart_ai.knowledge.confidence import (
    ChosenSentence, compute_confidence, detect_contradictions,
    detect_negation_contradiction,
)


class TestComputeConfidence(unittest.TestCase):
    def test_empty_input_is_zero(self):
        self.assertEqual(compute_confidence([]), 0.0)

    def test_single_authoritative_source_nonzero(self):
        chosen = [ChosenSentence(1, "https://en.wikipedia.org/wiki/Microsoft",
                                  "Microsoft was founded in 1975.")]
        confidence = compute_confidence(chosen)
        self.assertGreater(confidence, 0.0)
        self.assertLess(confidence, 1.0)

    def test_multiple_agreeing_sources_score_higher(self):
        single = [ChosenSentence(1, "https://en.wikipedia.org/wiki/Microsoft",
                                  "Microsoft was founded in 1975.")]
        multi = [
            ChosenSentence(1, "https://en.wikipedia.org/wiki/Microsoft", "Microsoft was founded in 1975."),
            ChosenSentence(2, "https://www.reuters.com/x", "Microsoft was founded in 1975."),
            ChosenSentence(3, "https://mit.edu/x", "Microsoft was founded in 1975."),
        ]
        self.assertGreater(compute_confidence(multi), compute_confidence(single))

    def test_contradiction_lowers_confidence(self):
        chosen = [
            ChosenSentence(1, "https://en.wikipedia.org/wiki/Microsoft", "Microsoft was founded in 1975."),
            ChosenSentence(2, "https://example.com/x", "Microsoft was founded in 1981."),
        ]
        with_contradiction = compute_confidence(chosen, contradiction_count=1)
        without = compute_confidence(chosen, contradiction_count=0)
        self.assertLess(with_contradiction, without)

    def test_confidence_bounded_zero_to_one(self):
        chosen = [ChosenSentence(1, "https://mit.edu/x", "A fact.") for _ in range(1)]
        confidence = compute_confidence(chosen)
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

    def test_citation_graph_integration(self):
        graph = CitationGraph()
        graph.add_citation("topic", 1)
        graph.add_citation("topic", 2)
        chosen = [
            ChosenSentence(1, "https://en.wikipedia.org/wiki/X", "Fact one."),
            ChosenSentence(2, "https://www.reuters.com/x", "Fact one."),
        ]
        confidence = compute_confidence(chosen, topic="topic", graph=graph)
        self.assertGreater(confidence, 0.0)


class TestDetectContradictions(unittest.TestCase):
    def test_numeric_contradiction_detected(self):
        chosen = [
            ChosenSentence(1, "https://a.com", "Microsoft was founded in 1975."),
            ChosenSentence(2, "https://b.com", "Microsoft was founded in 1981."),
        ]
        contradictions = detect_contradictions(chosen)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0]["type"], "numeric")

    def test_same_source_never_contradicts_itself(self):
        chosen = [
            ChosenSentence(1, "https://a.com", "Microsoft was founded in 1975."),
            ChosenSentence(1, "https://a.com", "Microsoft was founded in 1981."),
        ]
        self.assertEqual(detect_contradictions(chosen), [])

    def test_agreeing_sentences_no_contradiction(self):
        chosen = [
            ChosenSentence(1, "https://a.com", "Microsoft was founded in 1975."),
            ChosenSentence(2, "https://b.com", "Microsoft was founded in 1975."),
        ]
        self.assertEqual(detect_contradictions(chosen), [])

    def test_empty_input(self):
        self.assertEqual(detect_contradictions([]), [])


class TestDetectNegationContradiction(unittest.TestCase):
    def test_affirm_vs_negate_detected(self):
        chosen = [
            ChosenSentence(1, "https://a.com", "Microsoft was founded by Gates."),
            ChosenSentence(2, "https://b.com", "Microsoft was not founded by Gates alone."),
        ]
        result = detect_negation_contradiction(chosen, "founded")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "negation")

    def test_no_contradiction_when_all_affirm(self):
        chosen = [
            ChosenSentence(1, "https://a.com", "Microsoft was founded by Gates."),
            ChosenSentence(2, "https://b.com", "Microsoft was founded in Albuquerque."),
        ]
        self.assertEqual(detect_negation_contradiction(chosen, "founded"), [])


if __name__ == "__main__":
    unittest.main()


