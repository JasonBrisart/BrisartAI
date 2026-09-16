"""
File: brisart_ai/core/tests/test_session_memory.py

Purpose
-------
Unit tests for brisart_ai.core.session_memory. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 6 test cases across TestSessionMemory.

Communication / relationships
------------------------------
- exercises brisart_ai.core.session_memory (SessionMemory)

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
- asserts: empty content is dropped.
- asserts: duplicate topics deduplicated.
- asserts: limit respected.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/core/tests/test_session_memory.py -v
    $ python -m pytest brisart_ai/core/tests/test_session_memory.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.session_memory import SessionMemory


class TestSessionMemory(unittest.TestCase):
    def _make(self, tmpdir):
        return SessionMemory(str(Path(tmpdir) / "mem.sqlite3"))

    def test_add_and_recent_topics(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "who invented microsoft")
            topics = mem.recent_topics(limit=5)
            self.assertTrue(len(topics) >= 1)
            mem.close()

    def test_both_added_topics_are_present(self):
        # now_ts() has 1-second resolution, so two adds in the same test
        # run don't reliably produce distinguishable ORDER BY timestamps --
        # this checks both topics survive, not strict insertion order.
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "first question about cats")
            mem.add("user", "second question about dogs")
            topics = mem.recent_topics(limit=5)
            joined = " ".join(topics)
            self.assertIn("cats", joined)
            self.assertIn("dogs", joined)
            mem.close()

    def test_empty_content_is_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "   ")
            self.assertEqual(mem.recent_topics(limit=5), [])
            mem.close()

    def test_content_compressed_to_tokens(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "This is a very long sentence with many stop words like the and of in a row")
            topics = mem.recent_topics(limit=5)
            self.assertEqual(len(topics), 1)
            # Compressed topic should be shorter than the original sentence.
            self.assertLess(len(topics[0]), len("This is a very long sentence with many stop words like the and of in a row"))
            mem.close()

    def test_duplicate_topics_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            mem.add("user", "cats")
            mem.add("user", "cats")
            topics = mem.recent_topics(limit=5)
            self.assertEqual(len(topics), len(set(topics)))
            mem.close()

    def test_limit_respected(self):
        with tempfile.TemporaryDirectory() as d:
            mem = self._make(d)
            for i in range(10):
                mem.add("user", f"unique topic number {i}")
            topics = mem.recent_topics(limit=3)
            self.assertLessEqual(len(topics), 3)
            mem.close()


if __name__ == "__main__":
    unittest.main()



