"""
File: brisart_ai/tests/test_intent.py

Purpose
-------
Unit tests for brisart_ai.intent. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 38 test cases across TestDetectIntent, TestNameHeuristics, TestScoreIntent, TestDescribeIntent, TestNegation, TestMultiIntent.

Communication / relationships
------------------------------
- exercises brisart_ai.intent (INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_FOUNDER, INTENT_GENERAL, INTENT_INVENTOR, INTENT_STATISTIC)

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
- asserts: founder.
- asserts: inventor.
- asserts: statistic.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/tests/test_intent.py -v
    $ python -m pytest brisart_ai/tests/test_intent.py --import-mode=importlib
"""
import unittest
from brisart_ai.intent import (
    INTENT_COMPARISON, INTENT_EXPLANATION, INTENT_FOUNDER, INTENT_GENERAL,
    INTENT_INVENTOR, INTENT_STATISTIC, INTENT_DEFINITION, INTENT_PROCEDURE,
    INTENT_VALIDATION, INTENT_IMPLEMENTATION, describe_intent, detect_intent,
    detect_intents, detect_negation_spans, is_bare_generic_concept_title,
    is_position_negated, looks_like_person_name, name_candidates, score_intent,
    term_is_negated,
)

class TestDetectIntent(unittest.TestCase):
    def test_founder(self): self.assertEqual(detect_intent("who invented microsoft?"), INTENT_FOUNDER)
    def test_inventor(self): self.assertEqual(detect_intent("who invented the transistor and when was it invented?"), INTENT_INVENTOR)
    def test_statistic(self): self.assertEqual(detect_intent("how many cats are in america?"), INTENT_STATISTIC)
    def test_explanation(self): self.assertEqual(detect_intent("why do cats purr?"), INTENT_EXPLANATION)
    def test_comparison(self): self.assertEqual(detect_intent("do dogs outlive cats?"), INTENT_COMPARISON)
    def test_general(self): self.assertEqual(detect_intent("transistor"), INTENT_GENERAL)
    def test_empty(self): self.assertEqual(detect_intent(""), INTENT_GENERAL)
    def test_product_to_inventor(self): self.assertEqual(detect_intent("who invented microsoft powerpoint?"), INTENT_INVENTOR)

class TestNameHeuristics(unittest.TestCase):
    def test_name_candidates_plain(self): self.assertEqual(name_candidates("Bill Gates"), ["Bill Gates"])
    def test_name_candidates_url(self): self.assertIn("Bill_Gates", name_candidates("https://en.wikipedia.org/wiki/Bill_Gates"))
    def test_name_candidates_empty(self): self.assertEqual(name_candidates(""), [])
    def test_bare_concept(self): self.assertTrue(is_bare_generic_concept_title("Law"))
    def test_specific_not_concept(self): self.assertFalse(is_bare_generic_concept_title("History of the Transistor"))
    def test_law_of_sa(self): self.assertFalse(is_bare_generic_concept_title("Law of South Africa"))
    def test_person_two(self): self.assertTrue(looks_like_person_name("Bill Gates"))
    def test_person_middle(self): self.assertTrue(looks_like_person_name("John F Kennedy"))
    def test_org_not_person(self): self.assertFalse(looks_like_person_name("Microsoft Corporation"))
    def test_digit_not_person(self): self.assertFalse(looks_like_person_name("Windows 95"))

class TestScoreIntent(unittest.TestCase):
    def test_boost(self):
        d, b, p = score_intent("Microsoft was founded by Bill Gates and Paul Allen", INTENT_FOUNDER, "who founded microsoft")
        self.assertGreater(d, 0); self.assertTrue(b)
    def test_penalty(self):
        d, b, p = score_intent("Sign in to your Microsoft account for support", INTENT_FOUNDER, "who founded microsoft")
        self.assertLess(d, 0); self.assertTrue(p)
    def test_empty(self):
        self.assertEqual(score_intent("", INTENT_FOUNDER, "who founded microsoft"), (0.0, [], []))
    def test_work_of_art_penalized(self):
        d, b, p = score_intent("Invented (album) is a music release", INTENT_INVENTOR, "who invented the transistor")
        self.assertTrue(any("work-of-art" in x for x in p))

class TestDescribeIntent(unittest.TestCase):
    def test_general(self): self.assertIn("general", describe_intent(INTENT_GENERAL))
    def test_founder(self): self.assertIn("founder", describe_intent(INTENT_FOUNDER, "who founded microsoft"))

class TestNegation(unittest.TestCase):
    def test_detects(self): self.assertTrue(detect_negation_spans("Microsoft was not founded by Gates alone."))
    def test_none(self): self.assertEqual(detect_negation_spans("Microsoft was founded by Gates."), [])
    def test_empty(self): self.assertEqual(detect_negation_spans(""), [])
    def test_contracted(self): self.assertTrue(detect_negation_spans("This isn't correct at all."))
    def test_term_negated_true(self): self.assertTrue(term_is_negated("Microsoft was not founded by Gates alone.", "founded"))
    def test_term_negated_false(self): self.assertFalse(term_is_negated("Microsoft was founded by Gates.", "founded"))
    def test_position(self):
        self.assertTrue(is_position_negated(10, [(5, 20)])); self.assertFalse(is_position_negated(30, [(5, 20)]))

class TestMultiIntent(unittest.TestCase):
    def test_primary_first(self): self.assertEqual(detect_intents("who founded microsoft?")[0], ("founder", 1.0))
    def test_definition(self): self.assertIn(INTENT_DEFINITION, [i for i, _ in detect_intents("what is a transistor?")])
    def test_procedure(self): self.assertIn(INTENT_PROCEDURE, [i for i, _ in detect_intents("how do i install python?")])
    def test_validation(self): self.assertIn(INTENT_VALIDATION, [i for i, _ in detect_intents("is it true that cats purr?")])
    def test_implementation(self): self.assertIn(INTENT_IMPLEMENTATION, [i for i, _ in detect_intents("write a function to sort a list")])
    def test_empty(self): self.assertEqual(detect_intents(""), [(INTENT_GENERAL, 1.0)])
    def test_sorted(self):
        scores = [s for _l, s in detect_intents("what is a transistor?")]
        self.assertEqual(scores, sorted(scores, reverse=True))

if __name__ == "__main__": unittest.main()



