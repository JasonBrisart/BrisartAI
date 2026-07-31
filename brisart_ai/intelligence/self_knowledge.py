"""Self-knowledge responses for BrisartAI.
BrisartAI can explain:
- who it is
- what it can do
- what it remembers
- how it works
- its architecture
- its limits

Single-fact statements (limits, observations, suggested actions) route
through personality.py so this module's voice matches the rest of the
assistant instead of hardcoding its own labels.
"""
from __future__ import annotations

from typing import Iterable, List

from brisart_ai import APP_NAME, __version__
from brisart_ai.intelligence.personality import limitation, next_step, observation
from brisart_ai.util import tokenize

SELF_TERMS = {
    "who",
    "what",
    "you",
    "your",
    "yourself",
    "brisartai",
    "do",
    "work",
    "purpose",
    "abilities",
    "capabilities",
    "memory",
    "remember",
    "architecture",
    "system",
    "limits",
    "think",
    "thinking",
    "reasoning",
    "access",
}


def looks_like_self_question(text: str) -> bool:
    """Return True if the question appears to be about BrisartAI itself."""
    lowered = text.lower().strip()
    phrases = [
        "who are you",
        "what are you",
        "what can you do",
        "what do you do",
        "what do you remember",
        "what is your memory",
        "how do you work",
        "how do you think",
        "what are your limits",
        "what are your capabilities",
        "show architecture",
        "show system",
        "what can you access",
    ]
    if any(p in lowered for p in phrases):
        return True
    terms = set(tokenize(lowered))
    return bool(terms & SELF_TERMS)


def self_response(
    user_text: str,
    index=None,
    recent_topics: Iterable[str] | None = None,
) -> str:
    """Return BrisartAI self-knowledge response."""
    lowered = user_text.lower()
    total = index.source_count() if index else 0
    files = index.source_count("file") if index else 0
    web = index.source_count("web") if index else 0
    lines: List[str] = []

    if "memory" in lowered or "remember" in lowered:
        return "\n".join(
            [
                "BrisartAI Memory",
                "",
                observation(
                    "Session memory stores compact conversation topics "
                    "internally to help maintain context during a "
                    "session."
                ),
                limitation(
                    "Stored memory is not displayed back to you as part "
                    "of normal answers."
                ),
            ]
        )

    if "limit" in lowered:
        limits = [
            "Cannot know information that has not been indexed",
            "Cannot invent evidence",
            "Retrieval quality depends on imported data",
            "Internet access is optional",
            "Not a large neural model",
        ]
        lines = ["BrisartAI Limits", ""]
        for item in limits:
            lines.append(limitation(item))
        lines.append("")
        lines.append(
            observation(
                "Primary strength: local, inspectable, source-grounded "
                "reasoning."
            )
        )
        lines.append("")
        lines.append(
            next_step(
                "Ingest more data to reduce these limits, or ask about "
                "capabilities and architecture."
            )
        )
        return "\n".join(lines)

    if "think" in lowered or "reasoning" in lowered:
        lines = [
            "Reasoning Model",
            "",
            "1. Receive input",
            "2. Normalize text",
            "3. Check self-knowledge",
            "4. Search indexed data",
            "5. Rank evidence",
            "6. Build answer",
            "7. Explain conclusions",
            "",
            observation(
                "BrisartAI attempts to remain explainable and "
                "evidence-driven whenever possible."
            ),
            "",
        ]
        lines.append(
            next_step(
                "Ask about capabilities, memory, limits, or "
                "architecture for more detail."
            )
        )
        return "\n".join(lines)

    if "architecture" in lowered or "system" in lowered:
        lines = [
            "BrisartAI Architecture",
            "",
            "Input",
            "  ->",
            "Ingestion",
            "  ->",
            "SQLite Index",
            "  ->",
            "Retrieval",
            "  ->",
            "Synthesis",
            "  ->",
            "Response",
            "",
            "Major Modules:",
            "- brisart_ai/io/readers.py",
            "- brisart_ai/knowledge/ingest.py",
            "- brisart_ai/knowledge/index.py",
            "- brisart_ai/knowledge/ranker.py",
            "- brisart_ai/knowledge/synthesizer.py",
            "- brisart_ai/core/conversation.py",
            "- brisart_ai/intelligence/self_knowledge.py",
            "",
        ]
        lines.append(
            next_step(
                "Ask about capabilities, reasoning, or limits for more "
                "detail."
            )
        )
        return "\n".join(lines)

    lines.append(f"{APP_NAME} {__version__}")
    lines.append("")
    lines.append("Identity")
    lines.append("--------")
    lines.append("Pure-Python local-first research assistant.")
    lines.append("")
    lines.append("Environment")
    lines.append("-----------")
    lines.append(
        observation(
            f"Indexed Sources: {total} ({files} local files, "
            f"{web} web pages)."
        )
    )
    lines.append("")
    lines.append("Capabilities")
    lines.append("------------")
    lines.append("")
    lines.append("Research")
    lines.append("- Search indexed data")
    lines.append("- Analyze repositories")
    lines.append("- Summarize content")
    lines.append("")
    lines.append("Knowledge")
    lines.append("- Build SQLite knowledge base")
    lines.append("- Retrieve evidence")
    lines.append("- Explain conclusions")
    lines.append("")
    lines.append("Internet")
    lines.append("- Optional web search")
    lines.append("- Optional website crawling")
    lines.append("")
    lines.append("Local Operations")
    lines.append("- File ingestion")
    lines.append("- Folder scanning")
    lines.append("- Recommendation generation")
    lines.append("")
    lines.append(
        next_step(
            "Ask about memory, architecture, capabilities, reasoning, "
            "or limits."
        )
    )
    return "\n".join(lines)