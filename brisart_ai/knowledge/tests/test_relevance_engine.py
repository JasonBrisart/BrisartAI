"""Tests for brisart_ai/knowledge/relevance_engine.py -- the Brisart Relevance Engine."""
import unittest
from brisart_ai.knowledge.relevance_engine import (
    presence_points, proximity_bonus, rarity_weight, shape_multiplier, term_contribution,
)


class TestRarityWeight(unittest.TestCase):
    def test_zero_document_frequency_returns_zero(self):
        self.assertEqual(rarity_weight(0, 100), 0.0)

    def test_zero_total_documents_returns_zero(self):
        self.assertEqual(rarity_weight(5, 0), 0.0)

    def test_common_term_gets_lowest_tier(self):
        # 25% share -> "common" tier (weight 0.4)
        self.assertEqual(rarity_weight(25, 100), 0.4)

    def test_distinctive_term_gets_highest_tier(self):
        # under 1% share -> "distinctive" tier (weight 2.6)
        self.assertEqual(rarity_weight(1, 1000), 2.6)

    def test_tier_boundaries_are_fixed_regardless_of_scale(self):
        # Same share (5%) should give same weight regardless of corpus size.
        self.assertEqual(rarity_weight(5, 100), rarity_weight(500, 10000))


class TestPresencePoints(unittest.TestCase):
    def test_zero_occurrences_is_zero(self):
        self.assertEqual(presence_points(0), 0.0)

    def test_single_occurrence_gets_baseline(self):
        self.assertEqual(presence_points(1), 1.0)

    def test_many_occurrences_capped(self):
        # Going from 8 to 800 occurrences should not increase the score further.
        self.assertEqual(presence_points(8), presence_points(800))

    def test_more_occurrences_never_scores_lower(self):
        self.assertLessEqual(presence_points(1), presence_points(2))
        self.assertLessEqual(presence_points(2), presence_points(4))
        self.assertLessEqual(presence_points(4), presence_points(8))


class TestTermContribution(unittest.TestCase):
    def test_combines_presence_and_rarity(self):
        expected = presence_points(3) * rarity_weight(2, 100)
        self.assertEqual(term_contribution(3, 2, 100), expected)


class TestShapeMultiplier(unittest.TestCase):
    def test_zero_average_length_returns_neutral(self):
        self.assertEqual(shape_multiplier(100, 0), 1.0)

    def test_typical_length_gets_full_credit(self):
        self.assertEqual(shape_multiplier(100, 100), 1.00)

    def test_short_document_is_boosted_above_neutral(self):
        # Unlike BM25, a notably short document is boosted, not just spared.
        self.assertGreater(shape_multiplier(10, 100), 1.0)

    def test_long_document_is_diluted(self):
        self.assertLess(shape_multiplier(300, 100), 1.0)

    def test_much_longer_document_diluted_more_than_slightly_longer(self):
        self.assertLess(shape_multiplier(300, 100), shape_multiplier(160, 100))


class TestProximityBonus(unittest.TestCase):
    def test_single_term_returns_neutral(self):
        bonus, signals = proximity_bonus("some text here", ["term"])
        self.assertEqual(bonus, 1.0)
        self.assertEqual(signals, [])

    def test_no_terms_returns_neutral(self):
        bonus, signals = proximity_bonus("some text here", [])
        self.assertEqual(bonus, 1.0)

    def test_terms_close_together_get_bonus(self):
        text = "the quick brown fox jumps"
        bonus, signals = proximity_bonus(text, ["quick", "fox"])
        self.assertGreater(bonus, 1.0)
        self.assertTrue(any("proximity" in s for s in signals))

    def test_terms_far_apart_get_no_bonus(self):
        text = "quick " + ("filler word " * 50) + "fox"
        bonus, signals = proximity_bonus(text, ["quick", "fox"])
        self.assertEqual(bonus, 1.0)

    def test_bonus_is_capped(self):
        # Many overlapping close terms should not exceed the documented cap.
        text = "alpha beta gamma delta epsilon zeta"
        bonus, _signals = proximity_bonus(text, ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"])
        self.assertLessEqual(bonus, 1.6)  # 1.0 + PROXIMITY_BONUS_CAP (0.6)

    def test_terms_matched_case_insensitively(self):
        text = "Quick Brown FOX"
        bonus, _signals = proximity_bonus(text, ["quick", "fox"])
        self.assertGreater(bonus, 1.0)


if __name__ == "__main__":
    unittest.main()
