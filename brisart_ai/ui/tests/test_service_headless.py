"""Tests for brisart_ai/ui/service.py -- BrisartService (headless, no Tk display required).

BrisartService itself has no Tk dependency (it's a pure backend facade
over Index/SessionMemory/ResearchSettings), so it can be constructed and
exercised in a fully headless test environment. app.py, chat_panel.py,
dialogs.py, and sidebar.py DO require a live Tk display and are outside
the scope of headless unit testing -- they are verified manually.
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


if __name__ == "__main__":
    unittest.main()
