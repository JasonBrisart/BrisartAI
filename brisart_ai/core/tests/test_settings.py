"""
File: brisart_ai/core/tests/test_settings.py

Purpose
-------
Unit tests for brisart_ai.core.settings. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 10 test cases across TestResearchSettings.

Communication / relationships
------------------------------
- exercises brisart_ai.core.settings (DEFAULT_SETTINGS, ResearchSettings)

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
- asserts: defaults applied when no file exists.
- asserts: set unknown key raises.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/core/tests/test_settings.py -v
    $ python -m pytest brisart_ai/core/tests/test_settings.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.settings import DEFAULT_SETTINGS, ResearchSettings


class TestResearchSettings(unittest.TestCase):
    def _make(self, tmpdir):
        return ResearchSettings(path=Path(tmpdir) / "settings.json")

    def test_defaults_applied_when_no_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            for key, value in DEFAULT_SETTINGS.items():
                self.assertEqual(s.get(key), value)

    def test_settings_file_created_on_first_use(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            ResearchSettings(path=path)
            self.assertTrue(path.exists())

    def test_set_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            s1 = ResearchSettings(path=path)
            s1.set("auto_web_research", True)
            s2 = ResearchSettings(path=path)
            self.assertTrue(s2.get("auto_web_research"))

    def test_toggle_flips_value(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            original = s.get("search_notes")
            new_value = s.toggle("search_notes")
            self.assertEqual(new_value, not original)
            self.assertEqual(s.get("search_notes"), not original)

    def test_set_unknown_key_raises(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            with self.assertRaises(KeyError):
                s.set("nonexistent_setting", True)

    def test_corrupt_settings_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not valid json!!")
            s = ResearchSettings(path=path)
            self.assertEqual(s.get("search_local_files"), DEFAULT_SETTINGS["search_local_files"])

    def test_stale_unknown_key_in_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"search_collections": true, "search_notes": true}')
            s = ResearchSettings(path=path)
            self.assertFalse(hasattr(s, "search_collections"))
            self.assertTrue(s.get("search_notes"))

    def test_resolve_key_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            self.assertEqual(s.resolve_key("web"), "auto_web_research")
            self.assertEqual(s.resolve_key("local"), "search_local_files")
            self.assertEqual(s.resolve_key("notes"), "search_notes")

    def test_resolve_key_unknown_raises(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            with self.assertRaises(KeyError):
                s.resolve_key("bogus")

    def test_render_produces_readable_text(self):
        with tempfile.TemporaryDirectory() as d:
            s = self._make(d)
            text = s.render()
            self.assertIn("Research Sources", text)


if __name__ == "__main__":
    unittest.main()



