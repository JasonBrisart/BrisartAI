"""Tests for brisart_ai/knowledge/vault.py -- notes, collections, entities, timeline."""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.vault import (
    add_note, add_sources_to_collection, create_collection, extract_entities_from_text,
    list_collections, list_notes, reindex_missing_notes, search_notes, search_notes_as_documents,
    vault_report,
)


class TestVault(unittest.TestCase):
    def _make(self, tmpdir):
        return Index(str(Path(tmpdir) / "test.sqlite"))

    def test_create_collection(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = create_collection(idx, "research")
            self.assertIn("research", result)
            idx.close()

    def test_list_collections_empty(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = list_collections(idx)
            self.assertIn("No collections", result)
            idx.close()

    def test_add_note_saves_and_mirrors_into_index(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = add_note(idx, "My Note", "Some searchable content about narwhals")
            self.assertIn("My Note", result)
            self.assertEqual(idx.source_count("note"), 1)
            idx.close()

    def test_add_note_empty_body_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            result = add_note(idx, "Title", "   ")
            self.assertIn("cannot be empty", result)
            idx.close()

    def test_list_notes_shows_saved_note(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Test Note", "Note body text here")
            result = list_notes(idx)
            self.assertIn("Test Note", result)
            idx.close()

    def test_search_notes_finds_matching_note(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Zebra Facts", "Zebras have distinctive stripes")
            result = search_notes(idx, "zebra")
            self.assertIn("Zebra Facts", result)
            idx.close()

    def test_search_notes_as_documents_returns_document_shape(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Note Title", "unique searchable content xyzzy")
            docs = search_notes_as_documents(idx, "xyzzy")
            self.assertEqual(len(docs), 1)
            self.assertIn("score", docs[0])
            self.assertIn("text", docs[0])
            idx.close()

    def test_reindex_missing_notes_backfills_old_notes(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            # Simulate a note saved before mirroring existed: insert directly
            # into the notes table, bypassing add_note()'s mirroring step.
            from brisart_ai.knowledge.vault import init_vault_schema
            init_vault_schema(idx)
            with idx.conn:
                idx.conn.execute(
                    "INSERT INTO notes(title, body, collection_id, created_at, updated_at) VALUES(?,?,?,?,?)",
                    ("Old Note", "old note body content", None, 0, 0),
                )
            self.assertEqual(idx.source_count("note"), 0)
            reindexed = reindex_missing_notes(idx)
            self.assertEqual(reindexed, 1)
            self.assertEqual(idx.source_count("note"), 1)
            idx.close()

    def test_reindex_missing_notes_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            add_note(idx, "Already Indexed", "content here")
            first = reindex_missing_notes(idx)
            self.assertEqual(first, 0)  # already indexed via add_note()
            idx.close()

    def test_extract_entities_from_text(self):
        entities = extract_entities_from_text("Bill Gates founded Microsoft in Albuquerque.")
        self.assertTrue(any("Bill Gates" in e or "Gates" in e for e in entities))

    def test_extract_entities_short_names_excluded(self):
        entities = extract_entities_from_text("A B is not a real entity but Full Name is.")
        self.assertNotIn("A", entities)

    def test_vault_report_includes_counts(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="hello")
            report = vault_report(idx)
            self.assertIn("Indexed sources", report)
            self.assertIn("1", report)
            idx.close()

    def test_add_sources_to_collection_matches_by_term(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A", text="unique term aardvark here")
            result = add_sources_to_collection(idx, "my_collection", "aardvark")
            self.assertIn("1", result)
            idx.close()


if __name__ == "__main__":
    unittest.main()
