"""
File: brisart_ai/knowledge/tests/test_vault.py

Purpose
-------
Unit tests for brisart_ai.knowledge.vault. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 13 test cases across TestVault.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.index (Index)
- exercises brisart_ai.knowledge.vault (add_note, add_sources_to_collection, create_collection, extract_entities_from_text, list_collections, list_notes)
- exercises brisart_ai.knowledge.vault (init_vault_schema)

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
- asserts: list collections empty.
- asserts: add note empty body rejected.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_vault.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_vault.py --import-mode=importlib
"""
import tempfile
import unittest
from pathlib import Path
from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.vault import (
    add_note, add_sources_to_collection, create_collection, extract_entities_from_text,
    list_collections, list_notes, rebuild_entities, reindex_missing_notes, search_notes,
    search_notes_as_documents, vault_report,
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

    def test_rebuild_entities_collapses_aliases_via_entity_registry(self):
        # "Bill Gates" and "William Gates" both resolve to the same
        # canonical entity via knowledge.entity_registry.resolve_entity_name(),
        # so rebuild_entities() must store one row for them, not two.
        with tempfile.TemporaryDirectory() as d:
            idx = self._make(d)
            idx.add_source(source_type="file", location="/a.txt", title="A",
                text="Bill Gates and William Gates are the same person in different sentences here.")
            rebuild_entities(idx)
            names = {row[0] for row in idx.conn.execute("SELECT name FROM entities").fetchall()}
            self.assertIn("Bill Gates", names)
            self.assertNotIn("William Gates", names)
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


