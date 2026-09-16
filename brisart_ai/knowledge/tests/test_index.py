"""
File: brisart_ai/knowledge/tests/test_index.py

Purpose
-------
Unit tests for brisart_ai.knowledge.index. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 10 test cases across TestIndex.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.index (Index)

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
- asserts: empty text returns false not added.
- asserts: missing source type raises.
- asserts: missing location raises.
- asserts: readding same source upserts not duplicates.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_index.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_index.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index


class TestIndex(unittest.TestCase):
    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_add_source_and_count(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            self.assertEqual(idx.source_count(), 0)
            added = idx.add_source(source_type="file", location="/a.txt", title="A", text="hello world")
            self.assertTrue(added)
            self.assertEqual(idx.source_count(), 1)
            idx.close()

    def test_empty_text_returns_false_not_added(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            added = idx.add_source(source_type="file", location="/a.txt", title="A", text="   ")
            self.assertFalse(added)
            self.assertEqual(idx.source_count(), 0)
            idx.close()

    def test_missing_source_type_raises(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            with self.assertRaises(ValueError):
                idx.add_source(source_type="", location="/a.txt", title="A", text="hello")
            idx.close()

    def test_missing_location_raises(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            with self.assertRaises(ValueError):
                idx.add_source(source_type="file", location="", title="A", text="hello")
            idx.close()

    def test_readding_same_source_upserts_not_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="version one")
            idx.add_source(source_type="file", location="/a.txt", title="A", text="version two")
            self.assertEqual(idx.source_count(), 1)
            idx.close()

    def test_source_count_by_type(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            idx.add_source(source_type="web", location="https://x.com", title="X", text="world")
            self.assertEqual(idx.source_count("file"), 1)
            self.assertEqual(idx.source_count("web"), 1)
            self.assertEqual(idx.source_count(), 2)
            idx.close()

    def test_purge_junk_web_sources_removes_blocked_hosts(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="web", location="https://merriam-webster.com/x", title="Def", text="a definition")
            idx.add_source(source_type="web", location="https://example.com/x", title="Good", text="real content")
            removed = idx.purge_junk_web_sources()
            self.assertEqual(removed, 1)
            self.assertEqual(idx.source_count("web"), 1)
            idx.close()

    def test_purge_only_affects_web_sources(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/dictionary-notes.txt", title="X", text="local text")
            idx.purge_junk_web_sources()
            self.assertEqual(idx.source_count("file"), 1)
            idx.close()

    def test_clear_removes_all_sources(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            idx.clear()
            self.assertEqual(idx.source_count(), 0)
            idx.close()

    def test_context_manager_closes_connection(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "ctx.sqlite")
            with Index(path) as idx:
                idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            # Connection should be usable again via a fresh instance.
            idx2 = Index(path)
            self.assertEqual(idx2.source_count(), 1)
            idx2.close()


if __name__ == "__main__":
    unittest.main()


