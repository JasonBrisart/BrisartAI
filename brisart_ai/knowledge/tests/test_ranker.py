"""
File: brisart_ai/knowledge/tests/test_ranker.py

Purpose
-------
Unit tests for brisart_ai.knowledge.ranker. Verifies the module's public
behavior and its documented edge cases so regressions are caught before
release, including that the full standard signal stack (query expansion,
spelling, authority, recency, session feedback, MMR diversity) never
displaces the single best answer.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.index (Index)
- exercises brisart_ai.knowledge.ranker (generic_concept_title_adjust,
  phrase_match_adjust, search, title_match_adjust)
- exercises brisart_ai.knowledge.relevance_feedback (RelevanceFeedback)

Settings / parameters
---------------------
- Standard unittest.TestCase suite; run with pytest
  (--import-mode=importlib) or `python -m pytest`.
- Uses only in-memory / temp-dir fixtures; no network, no shared state.
- No tunable parameters of its own.

Edge cases
----------
- asserts: empty query.
- asserts: no match.
- asserts: the standard feedback + diversity path preserves the top result.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here may be
  covered elsewhere.
- Deterministic and offline by design.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_ranker.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_ranker.py --import-mode=importlib
"""
import tempfile, unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ranker import (generic_concept_title_adjust, phrase_match_adjust,
                                          search, title_match_adjust)
from brisart_ai.knowledge.relevance_feedback import RelevanceFeedback


class TestSearch(unittest.TestCase):
    def _mk(self, d): return Index(str(Path(d)/"t.sqlite"))

    def test_empty_query(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/a.txt","A","hello world")
            self.assertEqual(search(i,""), []); i.close()

    def test_no_match(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/a.txt","A","hello world")
            self.assertEqual(search(i,"zzzznonexistentterm"), []); i.close()

    def test_match(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/a.txt","A","the giraffe is tall")
            r = search(i,"giraffe"); self.assertEqual(len(r),1); i.close()

    def test_source_types(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d)
            i.add_source("file","/a.txt","A","unique zephyr content")
            i.add_source("web","https://x.com","X","unique zephyr content")
            r = search(i,"zephyr", source_types={"file"})
            self.assertEqual(len(r),1); self.assertEqual(r[0]["source_type"],"file"); i.close()

    def test_founder_regression(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d)
            i.add_source("file","/pp.txt","Microsoft PowerPoint","Microsoft PowerPoint is a presentation program. Slides can include text and images. Available for Windows and macOS.")
            i.add_source("file","/h.txt","History of Microsoft","Microsoft was founded by Bill Gates and Paul Allen on April 4, 1975, in Albuquerque, New Mexico.")
            r = search(i,"who invented microsoft?")
            self.assertEqual(r[0]["title"],"History of Microsoft"); i.close()

    def test_statistic_regression(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d)
            i.add_source("file","/b.txt","Cat breeds","There are many recognised cat breeds like the Siamese and Persian.")
            i.add_source("file","/s.txt","Pet cat population statistics","An estimated 73.8 million pet cats live in the United States according to survey data.")
            r = search(i,"how many cats are in america?")
            self.assertEqual(r[0]["title"],"Pet cat population statistics"); i.close()

    def test_fields(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/a.txt","A","unique searchable term xyzzy")
            doc = search(i,"xyzzy")[0]
            for f in ("id","score","source_type","location","title","text","intent","intent_boosts","intent_penalties","did_you_mean"):
                self.assertIn(f, doc)
            i.close()

    def test_limit(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d)
            for k in range(10): i.add_source("file",f"/d{k}.txt",f"Doc {k}",f"document number {k} discusses widgets extensively")
            self.assertLessEqual(len(search(i,"widgets",limit=3)),3); i.close()

    def test_spelling_correction(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/m.txt","Microsoft history","Microsoft was founded in 1975.")
            r = search(i,"mircosoft")
            self.assertEqual(len(r),1); self.assertIn("microsoft", r[0]["did_you_mean"].get("mircosoft",[])); i.close()

    def test_acronym_expansion(self):
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d); i.add_source("file","/ai.txt","Artificial intelligence overview","Artificial intelligence simulates human intelligence.")
            self.assertEqual(len(search(i,"what is ai")),1); i.close()

    def test_standard_feedback_and_diversity_preserve_top_result(self):
        # Feedback and MMR diversity are part of the standard ranking path,
        # not flags. A feedback store still preserves the single best answer,
        # and diversity's first pick is always the top-scored document.
        with tempfile.TemporaryDirectory() as d:
            i = self._mk(d)
            i.add_source("file","/a.txt","History of Microsoft","Microsoft was founded in 1975 by Gates.")
            i.add_source("file","/b.txt","Microsoft account login","Sign in to your Microsoft account.")
            fb = RelevanceFeedback(); fb.mark_irrelevant(2,"Microsoft account login")
            r = search(i,"microsoft", feedback=fb)
            self.assertTrue(len(r) >= 1)
            self.assertEqual(r[0]["title"], "History of Microsoft")
            i.close()


class TestAdjusters(unittest.TestCase):
    def test_title_match(self):
        f,_ = title_match_adjust("All About Cats", {"cats"}); self.assertGreater(f,1.0)
    def test_generic_penalty(self):
        f,_ = generic_concept_title_adjust("Law","/wiki/Law"); self.assertLess(f,1.0)
    def test_phrase(self):
        f,_ = phrase_match_adjust("history of the transistor","covers the history of the transistor in depth"); self.assertGreater(f,1.0)
    def test_phrase_single_word(self):
        f,_ = phrase_match_adjust("cats","all about cats"); self.assertEqual(f,1.0)


if __name__ == "__main__": unittest.main()



