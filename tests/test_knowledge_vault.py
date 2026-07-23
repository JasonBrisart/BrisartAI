
import tempfile
import unittest
from pathlib import Path

from brisart_ai.knowledge.index import Index
from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.knowledge.project_awareness import project_report, research_report
from brisart_ai.knowledge.vault import (
    add_note,
    add_sources_to_collection,
    create_collection,
    list_collections,
    list_notes,
    rebuild_entities,
    search_notes,
    timeline,
    vault_report,
)


class KnowledgeVaultTests(unittest.TestCase):
    def test_vault_collections_notes_and_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "test.sqlite3"

            (root / "README.md").write_text(
                "BrisartAI is a local research assistant for archives.",
                encoding="utf-8",
            )
            (root / "architecture.md").write_text(
                "The system uses a SQLite index, retrieval, and synthesis.",
                encoding="utf-8",
            )

            index = Index(str(db))

            try:
                count = ingest_paths([str(root)], index)
                self.assertEqual(count, 2)

                self.assertIn(
                    "Collection ready",
                    create_collection(index, "archive_research"),
                )

                added = add_sources_to_collection(
                    index,
                    "archive_research",
                    "archive research",
                )
                self.assertIn("Matched sources added", added)

                collections = list_collections(index)
                self.assertIn("archive_research", collections)

                note_result = add_note(
                    index,
                    "Archive note",
                    "Preservation research should keep local evidence inspectable.",
                    "archive_research",
                )
                self.assertIn("Note saved", note_result)

                notes = list_notes(index)
                self.assertIn("Archive note", notes)

                note_search = search_notes(index, "preservation")
                self.assertIn("Archive note", note_search)

                vault = vault_report(index)
                self.assertIn("BrisartAI Knowledge Vault", vault)

                rebuilt = rebuild_entities(index)
                self.assertIn("Entity index rebuilt", rebuilt)

                project = project_report(index)
                self.assertIn("Project Awareness Report", project)

                report = research_report(index)
                self.assertIn("Research Intelligence Report", report)

                tl = timeline(index, "BrisartAI")
                self.assertIn("Timeline", tl)

            finally:
                index.close()


if __name__ == "__main__":
    unittest.main()