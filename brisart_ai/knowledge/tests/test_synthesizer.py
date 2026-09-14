"""Tests for brisart_ai/knowledge/synthesizer.py -- source-grounded answer synthesis."""
import unittest
from brisart_ai.knowledge.synthesizer import (
    format_source, query_wants_comparison, query_wants_quantity, query_wants_reason, sentence_score, synthesize,
)


class TestQueryIntentDelegation(unittest.TestCase):
    def test_wants_quantity_for_how_many(self):
        self.assertTrue(query_wants_quantity("how many cats are in america?"))

    def test_wants_comparison_for_outlive(self):
        self.assertTrue(query_wants_comparison("do dogs outlive cats?"))

    def test_wants_reason_for_why(self):
        self.assertTrue(query_wants_reason("why do cats purr?"))

    def test_general_query_wants_none_of_them(self):
        self.assertFalse(query_wants_quantity("tell me about cats"))
        self.assertFalse(query_wants_comparison("tell me about cats"))
        self.assertFalse(query_wants_reason("tell me about cats"))


class TestSentenceScore(unittest.TestCase):
    def test_no_overlap_scores_zero(self):
        self.assertEqual(sentence_score("completely unrelated content here", {"zebra"}), 0.0)

    def test_overlap_scores_positive(self):
        self.assertGreater(sentence_score("the zebra ran quickly across the field", {"zebra"}), 0.0)

    def test_quantity_mode_boosts_numeric_sentence(self):
        numeric = sentence_score("an estimated 73.8 million cats live here", {"cats"}, quantity_mode=True)
        non_numeric = sentence_score("cats are generally independent animals", {"cats"}, quantity_mode=True)
        self.assertGreater(numeric, non_numeric)

    def test_comparison_mode_boosts_comparative_sentence(self):
        comparative = sentence_score("dogs usually outlive cats in captivity", {"dogs", "cats"}, comparison_mode=True)
        plain = sentence_score("dogs and cats are both popular pets", {"dogs", "cats"}, comparison_mode=True)
        self.assertGreater(comparative, plain)

    def test_reason_mode_boosts_causal_sentence(self):
        causal = sentence_score("cats purr because of muscle twitching in the larynx", {"cats", "purr"}, reason_mode=True)
        plain = sentence_score("cats purr often while resting comfortably", {"cats", "purr"}, reason_mode=True)
        self.assertGreater(causal, plain)


class TestFormatSource(unittest.TestCase):
    def test_formats_with_title_and_location(self):
        doc = {"source_type": "file", "location": "/a.txt", "title": "My Doc"}
        self.assertEqual(format_source(doc), "file: My Doc :: /a.txt")

    def test_falls_back_to_location_when_no_title(self):
        doc = {"source_type": "web", "location": "https://x.com"}
        result = format_source(doc)
        self.assertIn("https://x.com", result)


class TestSynthesize(unittest.TestCase):
    def test_empty_docs_returns_no_information_message(self):
        result = synthesize("anything", [])
        self.assertIn("don't have any indexed information", result)

    def test_docs_with_no_matching_sentences_returns_distinct_message(self):
        docs = [{"source_type": "file", "location": "/a.txt", "title": "A", "text": "completely unrelated filler content padding out this sentence to be long enough"}]
        result = synthesize("zzzznonexistentterm", docs)
        self.assertIn("none of them", result.lower())
        # Distinct from the "no docs at all" message.
        self.assertNotIn("don't have any indexed information", result)

    def test_matching_docs_produce_cited_answer(self):
        docs = [{"source_type": "file", "location": "/a.txt", "title": "Microsoft History",
                 "text": "Microsoft was founded by Bill Gates and Paul Allen in nineteen seventy five in Albuquerque."}]
        result = synthesize("who founded microsoft", docs)
        self.assertIn("Sources:", result)
        self.assertIn("Gates", result)

    def test_citations_are_sequential_with_no_gaps(self):
        docs = [
            {"source_type": "file", "location": "/a.txt", "title": "Doc A", "text": "widget alpha appears in this sentence about widgets here today."},
            {"source_type": "file", "location": "/b.txt", "title": "Doc B", "text": "widget beta appears in this other sentence about widgets here too."},
        ]
        result = synthesize("widget", docs)
        self.assertIn("[1]", result)
        # If two sources both contribute, citation numbers should be sequential.
        if "[2]" in result:
            self.assertNotIn("[3]", result.split("Sources:")[0])


if __name__ == "__main__":
    unittest.main()
