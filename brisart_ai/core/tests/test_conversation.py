"""Tests for brisart_ai/core/conversation.py -- build_conversation_answer()."""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.core.conversation import build_conversation_answer
from brisart_ai.core.session_memory import SessionMemory
from brisart_ai.core.settings import ResearchSettings
from brisart_ai.knowledge.index import Index


class TestBuildConversationAnswer(unittest.TestCase):
    def _make(self, tmpdir):
        db_path = str(Path(tmpdir) / "test.sqlite")
        index = Index(db_path)
        memory = SessionMemory(db_path)
        settings = ResearchSettings(path=Path(tmpdir) / "settings.json")
        return index, memory, settings

    def test_answers_from_indexed_file_source(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            index.add_source(source_type="file", location="/docs/microsoft-history.txt",
                title="History of Microsoft",
                text="Microsoft was founded by Bill Gates and Paul Allen in 1975 in Albuquerque, New Mexico.",
                extension="txt", size_bytes=100)
            answer = build_conversation_answer("who founded microsoft?", index, memory, settings=settings)
            self.assertIn("Sources:", answer)
            self.assertTrue("Gates" in answer or "Allen" in answer)
            index.close(); memory.close()

    def test_empty_index_returns_no_information_message(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            answer = build_conversation_answer("what is the meaning of life?", index, memory, settings=settings)
            self.assertIn("don't have any indexed information", answer)
            index.close(); memory.close()

    def test_local_files_toggle_off_excludes_file_sources(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            settings.set("search_local_files", False)
            index.add_source(source_type="file", location="/x.txt", title="X",
                text="unique searchable content about zebras", extension="txt", size_bytes=10)
            answer = build_conversation_answer("zebras", index, memory, settings=settings)
            self.assertIn("don't have any indexed information", answer)
            index.close(); memory.close()

    def test_notes_toggle_off_excludes_note_sources(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            settings.set("search_notes", False)
            index.add_source(source_type="note", location="note:1", title="N",
                text="unique searchable content about narwhals", extension="")
            answer = build_conversation_answer("narwhals", index, memory, settings=settings)
            self.assertIn("don't have any indexed information", answer)
            index.close(); memory.close()

    def test_records_question_and_answer_to_memory(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            build_conversation_answer("hello there", index, memory, settings=settings)
            topics = memory.recent_topics(limit=5)
            self.assertTrue(len(topics) >= 1)
            index.close(); memory.close()

    def test_web_source_always_searched_regardless_of_local_files_toggle(self):
        with tempfile.TemporaryDirectory() as d:
            index, memory, settings = self._make(d)
            settings.set("search_local_files", False)
            index.add_source(source_type="web", location="https://example.com/x", title="Web Page",
                text="unique searchable content about pangolins", extension=".html")
            answer = build_conversation_answer("pangolins", index, memory, settings=settings)
            self.assertIn("Sources:", answer)
            index.close(); memory.close()


if __name__ == "__main__":
    unittest.main()
