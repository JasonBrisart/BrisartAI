"""
Persistent relationship graph for BrisartAI.

Connects concepts, modules, and sources.
Pure Python. No dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set


class RelationshipGraph:
    def __init__(
        self,
        graph_path: Path,
    ) -> None:
        self.graph_path = Path(graph_path)

        self.graph_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.graph: Dict[str, Set[str]] = defaultdict(set)

        self.load()

    def add_relationship(
        self,
        source: str,
        target: str,
    ) -> None:
        source = source.strip()
        target = target.strip()

        if not source or not target:
            return

        if source == target:
            return

        self.graph[source].add(target)

    def get_related(
        self,
        node: str,
    ) -> List[str]:
        return sorted(
            self.graph.get(node, set())
        )

    def nodes(self) -> List[str]:
        return sorted(self.graph.keys())

    def save(self) -> None:
        serializable = {
            key: sorted(values)
            for key, values in self.graph.items()
            if values
        }

        self.graph_path.write_text(
            json.dumps(
                serializable,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def load(self) -> None:
        if not self.graph_path.exists():
            return

        try:
            data = json.loads(
                self.graph_path.read_text(
                    encoding="utf-8"
                )
            )

            for key, values in data.items():
                self.graph[key] = set(values)

        except Exception:
            pass


__all__ = ["RelationshipGraph"]
