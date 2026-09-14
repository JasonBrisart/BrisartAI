"""Tests for brisart_ai/core/session_memory.py -- SessionMemory."""
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
