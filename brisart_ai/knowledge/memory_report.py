"""
Memory + relationship reporting for BrisartAI.

Gives a human-readable view of what BrisartAI has learned.
Pure Python. No dependencies.
"""

from __future__ import annotations

from pathlib import Path
from collections import Counter

from brisart_ai.knowledge.project_memory import ProjectMemory
from brisart_ai.knowledge.relationship_graph import RelationshipGraph

DEFAULT_MEMORY_PATH = Path("data/project_memory.json")
DEFAULT_GRAPH_PATH = Path("data/relationship_graph.json")


def memory_report(
    memory_path: Path = DEFAULT_MEMORY_PATH,
    graph_path: Path = DEFAULT_GRAPH_PATH,
    top_categories: int = 15,
    top_nodes: int = 15,
) -> str:
    """Return a readable summary of stored memory and relationships."""
    memory = ProjectMemory(memory_path)
    graph = RelationshipGraph(graph_path)

    facts = memory.load()

    lines = [
        "BrisartAI Memory Report",
        "=======================",
        "",
        f"Stored facts: {len(facts)}",
    ]

    if facts:
        category_counts = Counter(
            fact.get("category", "general")
            for fact in facts
        )
        source_counts = Counter(
            fact.get("source", "unknown")
            for fact in facts
        )

        lines.append("")
        lines.append("Fact Categories")
        lines.append("---------------")
        for category, count in category_counts.most_common(
            top_categories
        ):
            lines.append(f"- {category}: {count}")

        lines.append("")
        lines.append("Top Fact Sources")
        lines.append("-----------------")
        for source, count in source_counts.most_common(5):
            lines.append(f"- {source}: {count} fact(s)")

    nodes = graph.nodes()

    lines.append("")
    lines.append("Relationship Graph")
    lines.append("------------------")
    lines.append(f"Nodes: {len(nodes)}")

    if nodes:
        connectivity = sorted(
            nodes,
            key=lambda node: len(graph.get_related(node)),
            reverse=True,
        )

        lines.append("")
        lines.append("Most Connected Nodes")
        lines.append("--------------------")
        for node in connectivity[:top_nodes]:
            related = graph.get_related(node)
            lines.append(
                f"- {node} -> {len(related)} link(s): "
                + ", ".join(related[:6])
            )

    lines.append("")
    lines.append(
        "Suggested next move: ask a question so BrisartAI "
        "can ground its answer in stored memory and sources."
    )

    return "\n".join(lines)


__all__ = ["memory_report"]