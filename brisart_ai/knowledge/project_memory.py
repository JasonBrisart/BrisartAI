"""
Persistent project memory for BrisartAI.

Stores discovered facts from indexed content.
Pure Python. No dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List


class ProjectMemory:
    def __init__(
        self,
        memory_path: Path,
    ) -> None:
        self.memory_path = Path(memory_path)

        self.memory_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.memory_path.exists():
            self.save([])

    def load(self) -> List[Dict]:
        try:
            return json.loads(
                self.memory_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return []

    def save(
        self,
        facts: List[Dict],
    ) -> None:
        self.memory_path.write_text(
            json.dumps(
                facts,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def add_fact(
        self,
        fact: str,
        source: str,
        category: str = "general",
    ) -> None:
        fact = fact.strip()

        if not fact:
            return

        facts = self.load()

        entry = {
            "fact": fact,
            "source": source,
            "category": category,
        }

        if entry not in facts:
            facts.append(entry)
            self.save(facts)

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict]:
        query = query.lower()

        results = []

        for fact in self.load():
            text = str(
                fact.get("fact", "")
            ).lower()

            if query in text:
                results.append(fact)

        return results[:limit]

    def count(self) -> int:
        return len(self.load())

    def categories(self) -> List[str]:
        categories = set()

        for fact in self.load():
            categories.add(
                fact.get(
                    "category",
                    "general",
                )
            )

        return sorted(categories)


__all__ = ["ProjectMemory"]