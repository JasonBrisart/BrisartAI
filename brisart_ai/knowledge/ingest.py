"""Local file and folder ingestion for BrisartAI.

Now also feeds long-term project memory and the relationship graph
during ingestion, so knowledge persists across restarts.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from brisart_ai.io.readers import (
    iter_supported_files,
    read_file,
)
from brisart_ai.util import file_hash

from brisart_ai.knowledge.project_memory import ProjectMemory
from brisart_ai.knowledge.relationship_graph import RelationshipGraph

DEFAULT_MEMORY_PATH = Path("data/project_memory.json")
DEFAULT_GRAPH_PATH = Path("data/relationship_graph.json")

MIN_FACT_LEN = 50
MAX_FACT_LEN = 300


def _extract_facts(
    text: str,
    source: str,
    memory: ProjectMemory,
) -> None:
    """Store medium-length lines as candidate facts."""
    for line in text.splitlines():
        cleaned = line.strip()

        if MIN_FACT_LEN <= len(cleaned) <= MAX_FACT_LEN:
            memory.add_fact(
                fact=cleaned,
                source=source,
                category="indexed",
            )


def _link_imports(
    path: Path,
    text: str,
    graph: RelationshipGraph,
) -> None:
    """Link a Python module to the modules it imports."""
    if path.suffix.lower() != ".py":
        return

    module = path.stem

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith("import "):
            rest = stripped.replace("import ", "", 1)
            for item in rest.split(","):
                name = item.strip().split(" ")[0].split(".")[0]
                if name:
                    graph.add_relationship(module, name)

        elif stripped.startswith("from "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].split(".")[0]
                if name:
                    graph.add_relationship(module, name)


def ingest_paths(
    paths: Iterable[str],
    index,
    memory: ProjectMemory | None = None,
    graph: RelationshipGraph | None = None,
) -> int:
    """Ingest supported files from paths into the supplied index."""
    if memory is None:
        memory = ProjectMemory(DEFAULT_MEMORY_PATH)

    if graph is None:
        graph = RelationshipGraph(DEFAULT_GRAPH_PATH)

    count = 0

    for path in iter_supported_files(paths):
        try:
            text = read_file(path)
            if not text or not text.strip():
                print(f"SKIPPED EMPTY: {path}")
                continue

            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = 0

            try:
                content_hash = file_hash(path)
            except OSError as exc:
                print(f"WARN: could not hash {path}: {exc}")
                content_hash = ""

            indexed = index.add_source(
                source_type="file",
                location=str(path),
                title=path.name,
                text=text,
                content_hash=content_hash,
                size_bytes=size_bytes,
                extension=path.suffix.lower(),
            )

            if indexed:
                count += 1
                print(f"INGESTED: {path}")

                _extract_facts(text, str(path), memory)
                _link_imports(path, text, graph)
            else:
                print(f"SKIPPED EMPTY: {path}")

        except (
            OSError,
            UnicodeError,
            ValueError,
            RuntimeError,
        ) as exc:
            print(f"WARN: could not ingest {path}: {exc}")

        except Exception as exc:
            print(
                f"WARN: unexpected ingestion failure "
                f"for {path}: {exc}"
            )

    # Persist knowledge accumulated during this run.
    graph.save()

    return count


__all__ = ["ingest_paths"]
