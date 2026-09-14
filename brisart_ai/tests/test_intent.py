"""Tests for brisart_ai/intent.py -- question-intent detection and scoring."""
import unittest
from brisart_ai.intent import (
    INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_FOUNDER, INTENT_GENERAL, INTENT_INVENTOR,
    INTENT_STATISTIC, describe_intent, detect_intent, is_bare_generic_concept_title,
    looks_like_person_name, name_candidates, score_intent,
)


class TestDetectIntent(unittest.TestCase):
    def test_founder_intent_for_known_company(self):
        self.assertEqual(detect_intent("who invented microsoft?"), INTENT_FOUNDER)

    def test_inventor_intent_for_device(self):
        self.assertEqual(detect_intent("who invented the transistor and when was it invented?"), INTENT_INVENTOR)

    def test_statistic_intent_for_how_many(self):
        self.assertEqual(detect_intent("how many cats are in america?"), INTENT_STATISTIC)

    def test_explanation_intent_for_why(self):
        self.assertEqual(detect_intent("why do cats purr?"), INTENT_EXPLANATION)

    def test_comparison_intent_for_outlive(self):
        self.assertEqual(detect_intent("do dogs outlive cats?"), INTENT_COMPARISON)

    def test_general_intent_for_bare_noun(self):
        self.assertEqual(detect_intent("transistor"), INTENT_GENERAL)

    def test_empty_query_is_general(self):
        self.assertEqual(detect_intent(""), INTENT_GENERAL)

    def test_product_word_routes_to_inventor_not_founder(self):
        self.assertEqual(detect_intent("who invented microsoft powerpoint?"), INTENT_INVENTOR)

    def test_unknown_company_falls_back_to_inventor(self):
        self.assertEqual(detect_intent("who founded some totally unknown company xyz?"), INTENT_INVENTOR)


class TestNameCandidates(unittest.TestCase):
    def test_plain_text_returns_itself(self):
        self.assertEqual(name_candidates("Bill Gates"), ["Bill Gates"])

    def test_url_path_segment_extracted(self):
        candidates = name_candidates("https://en.wikipedia.org/wiki/Bill_Gates")
        self.assertIn("Bill_Gates", candidates)

    def test_empty_input_returns_empty_list(self):
        self.assertEqual(name_candidates(""), [])


class TestIsBareGenericConceptTitle(unittest.TestCase):
    def test_bare_concept_word(self):
        self.assertTrue(is_bare_generic_concept_title("Law"))

    def test_specific_title_is_not_generic(self):
        self.assertFalse(is_bare_generic_concept_title("History of the Transistor"))

    def test_empty_string_is_not_generic(self):
        self.assertFalse(is_bare_generic_concept_title(""))

    def test_law_of_south_africa_is_not_bare(self):
        self.assertFalse(is_bare_generic_concept_title("Law of South Africa"))


class TestLooksLikePersonName(unittest.TestCase):
    def test_two_word_name(self):
        self.assertTrue(looks_like_person_name("Bill Gates"))

    def test_three_word_name_with_middle_initial(self):
        self.assertTrue(looks_like_person_name("John F Kennedy"))

    def test_organizational_word_rejected(self):
        self.assertFalse(looks_like_person_name("Microsoft Corporation"))

    def test_single_word_rejected(self):
        self.assertFalse(looks_like_person_name("Microsoft"))

    def test_contains_digit_rejected(self):
        self.assertFalse(looks_like_person_name("Windows 95"))


class TestScoreIntent(unittest.TestCase):
    def test_founder_boost_terms_increase_score(self):
        delta, boosts, penalties = score_intent(
            "Microsoft was founded by Bill Gates and Paul Allen", INTENT_FOUNDER, "who founded microsoft"
        )
        self.assertGreater(delta, 0)
        self.assertTrue(len(boosts) > 0)

    def test_penalty_terms_decrease_score(self):
        delta, boosts, penalties = score_intent(
            "Sign in to your Microsoft account for support", INTENT_FOUNDER, "who founded microsoft"
        )
        self.assertLess(delta, 0)
        self.assertTrue(len(penalties) > 0)

    def test_empty_text_returns_zero_delta(self):
        delta, boosts, penalties = score_intent("", INTENT_FOUNDER, "who founded microsoft")
        self.assertEqual(delta, 0.0)
        self.assertEqual(boosts, [])
        self.assertEqual(penalties, [])

    def test_work_of_art_qualifier_penalized(self):
        delta, boosts, penalties = score_intent(
            "Invented (album) is a music release", INTENT_INVENTOR, "who invented the transistor"
        )
        self.assertTrue(any("work-of-art" in p for p in penalties))


class TestDescribeIntent(unittest.TestCase):
    def test_general_intent_description(self):
        desc = describe_intent(INTENT_GENERAL)
        self.assertIn("general", desc)

    def test_specific_intent_description_includes_name(self):
        desc = describe_intent(INTENT_FOUNDER, "who founded microsoft")
        self.assertIn("founder", desc)


if __name__ == "__main__":
    unittest.main()
