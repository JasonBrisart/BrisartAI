"""
File: brisart_ai/knowledge/tests/test_relevance_feedback.py

Purpose
-------
Unit tests for brisart_ai.knowledge.relevance_feedback. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 7 test cases across TestRelevanceFeedback.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.relevance_feedback (FEEDBACK_MAX_ADJUSTMENT, MAX_TERM_WEIGHT, MIN_TERM_WEIGHT, RelevanceFeedback)

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
- asserts: neutral multiplier with no feedback.
- asserts: weights clamp at bounds.
- asserts: apply feedback bounded.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_relevance_feedback.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_relevance_feedback.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.relevance_feedback import (
    FEEDBACK_MAX_ADJUSTMENT, MAX_TERM_WEIGHT, MIN_TERM_WEIGHT, RelevanceFeedback,
)


class TestRelevanceFeedback(unittest.TestCase):
    def setUp(self):
        self.fb = RelevanceFeedback()

    def test_neutral_multiplier_with_no_feedback(self):
        self.assertEqual(self.fb.feedback_multiplier("History of Microsoft"), 1.0)

    def test_mark_relevant_boosts_multiplier(self):
        self.fb.mark_relevant(1, "History of Microsoft")
        self.assertGreater(self.fb.feedback_multiplier("History of Microsoft"), 1.0)

    def test_mark_irrelevant_lowers_multiplier(self):
        self.fb.mark_irrelevant(2, "Microsoft Account Login")
        self.assertLess(self.fb.feedback_multiplier("Microsoft Account Login"), 1.0)

    def test_weights_clamp_at_bounds(self):
        for _ in range(50):
            self.fb.mark_relevant(1, "Microsoft")
        self.assertLessEqual(self.fb.term_weight("microsoft"), MAX_TERM_WEIGHT)
        for _ in range(50):
            self.fb.mark_irrelevant(2, "Microsoft")
        self.assertGreaterEqual(self.fb.term_weight("microsoft"), MIN_TERM_WEIGHT)

    def test_apply_feedback_bounded(self):
        self.fb.mark_relevant(1, "History of Microsoft")
        self.fb.mark_irrelevant(2, "Microsoft Account Login")
        scores = {1: 10.0, 2: 10.0, 3: 10.0}
        titles = {1: "History of Microsoft", 2: "Microsoft Account Login", 3: "Unrelated"}
        adjusted = self.fb.apply_feedback(scores, titles)
        self.assertGreater(adjusted[1], 10.0)
        self.assertLess(adjusted[2], 10.0)
        self.assertEqual(adjusted[3], 10.0)
        for source_id, score in adjusted.items():
            multiplier = score / scores[source_id]
            self.assertGreaterEqual(multiplier, 1 - FEEDBACK_MAX_ADJUSTMENT - 1e-9)
            self.assertLessEqual(multiplier, 1 + FEEDBACK_MAX_ADJUSTMENT + 1e-9)

    def test_reset_clears_all_state(self):
        self.fb.mark_relevant(1, "Microsoft")
        self.fb.reset()
        self.assertEqual(self.fb.feedback_multiplier("Microsoft"), 1.0)

    def test_empty_title_ignored(self):
        self.fb.mark_relevant(1, "")
        self.assertEqual(self.fb.feedback_multiplier("anything"), 1.0)


if __name__ == "__main__":
    unittest.main()


