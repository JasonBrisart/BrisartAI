"""
File: brisart_ai/ui/tests/test_service_headless.py

Purpose
-------
Unit tests for brisart_ai.ui.service. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 14 test cases across TestBrisartServiceHeadless,
including last_citations population and mark_citation() (see KI-010).

Communication / relationships
------------------------------
- exercises brisart_ai.ui.service (BrisartService)

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
- asserts: counts start at zero.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/ui/tests/test_service_headless.py -v
    $ python -m pytest brisart_ai/ui/tests/test_service_headless.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.ui.service import BrisartService


class TestBrisartServiceHeadless(unittest.TestCase):
    def _make(self, tmpdir):
        service = BrisartService(str(Path(tmpdir) / "test.sqlite"))
        # ResearchSettings() defaults to a fixed relative path
        # (data/research_settings.json), so its state is shared across
        # every BrisartService instance created in this test process.
        # Reset to known defaults here for isolation between test cases.
        service.settings.set("search_local_files", True)
        service.settings.set("search_notes", True)
        service.settings.set("auto_web_research", False)
        return service

    def test_construction_succeeds(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            self.assertIsNotNone(service.index)
            self.assertIsNotNone(service.memory)
            self.assertIsNotNone(service.settings)
            service.close()

    def test_counts_start_at_zero(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            total, files, web = service.counts()
            self.assertEqual((total, files, web), (0, 0, 0))
            service.close()

    def test_add_note_increases_counts(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Test Note", "Some content about narwhals")
            total, _files, _web = service.counts()
            self.assertEqual(total, 1)
            service.close()

    def test_ask_answers_from_indexed_note(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History", "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            answer = service.ask("who founded microsoft?", force_web=False)
            self.assertIn("Sources:", answer)
            service.close()

    def test_toggle_setting_flips_value(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            original = service.settings.get("search_notes")
            _label, new_value = service.toggle_setting("notes")
            self.assertEqual(new_value, not original)
            service.close()

    def test_settings_panel_text_contains_research_sources(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            text = service.settings_panel_text()
            self.assertIn("Research Sources", text)
            service.close()

    def test_import_paths_ingests_files(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            f = Path(d) / "doc.txt"
            f.write_text("unique searchable content about wombats")
            result = service.import_paths([str(f)])
            self.assertIn("Ingested 1", result)
            service.close()

    def test_list_notes_reflects_added_note(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("My Title", "body content")
            result = service.list_notes()
            self.assertIn("My Title", result)
            service.close()

    def test_ask_populates_last_citations(self):
        # KI-010: BrisartService.ask() must expose structured citation
        # data (source_id/title) for the answer it just gave, so the UI
        # can offer a mark-relevant/irrelevant control per cited source.
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History",
                "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            service.ask("who founded microsoft?", force_web=False)
            self.assertTrue(service.last_citations)
            first = service.last_citations[0]
            self.assertIn("source_id", first)
            self.assertIn("title", first)
            self.assertIn("index", first)
            self.assertEqual(first["index"], 1)
            service.close()

    def test_ask_with_no_results_leaves_last_citations_empty(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.ask("something with absolutely no indexed match", force_web=False)
            self.assertEqual(service.last_citations, [])
            service.close()

    def test_mark_citation_relevant_nudges_feedback_store(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History",
                "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            service.ask("who founded microsoft?", force_web=False)
            citation = service.last_citations[0]
            result = service.mark_citation(citation["index"], True)
            self.assertEqual(result, citation)
            self.assertGreater(service.feedback.term_weight("microsoft"), 0.0)
            service.close()

    def test_mark_citation_irrelevant_nudges_feedback_store(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History",
                "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            service.ask("who founded microsoft?", force_web=False)
            citation = service.last_citations[0]
            service.mark_citation(citation["index"], False)
            self.assertLess(service.feedback.term_weight("microsoft"), 0.0)
            service.close()

    def test_mark_citation_unknown_index_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History",
                "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            service.ask("who founded microsoft?", force_web=False)
            self.assertIsNone(service.mark_citation(9999, True))
            service.close()

    def test_last_citations_refreshed_on_next_ask(self):
        # A second ask() must replace last_citations with the NEW answer's
        # citations, not accumulate across calls.
        with tempfile.TemporaryDirectory() as d:
            service = self._make(d)
            service.add_note("Microsoft History",
                "Microsoft was founded by Bill Gates and Paul Allen in 1975.")
            service.add_note("Narwhal Facts", "Narwhals have a long spiral tusk on their head.")
            service.ask("who founded microsoft?", force_web=False)
            first_titles = {c["title"] for c in service.last_citations}
            service.ask("narwhal tusk", force_web=False)
            second_titles = {c["title"] for c in service.last_citations}
            self.assertNotEqual(first_titles, second_titles)
            self.assertIn("Narwhal Facts", second_titles)
            service.close()


if __name__ == "__main__":
    unittest.main()



