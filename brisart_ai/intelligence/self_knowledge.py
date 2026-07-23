"""Self-knowledge responses for BrisartAI.

BrisartAI can explain:
- who it is
- what it can do
- what it remembers
- how it works
- its architecture
- its limits
"""

from __future__ import annotations

from typing import Iterable, List

from brisart_ai import APP_NAME, __version__
from brisart_ai.intelligence.personality import next_step
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
        lines.append("BrisartAI Memory")
        lines.append("")

        if recent_topics:
            lines.append("Recent Topics:")
            for topic in list(recent_topics)[:10]:
                lines.append(f"- {topic}")
        else:
            lines.append("No recent topics available.")

        lines.append("")
        lines.append(
            "Session memory stores compact conversation topics "
            "to help maintain context."
        )

        return "\n".join(lines)

    if "limit" in lowered:
        return (
            "BrisartAI Limits\n\n"
            "- Cannot know information that has not been indexed\n"
            "- Cannot invent evidence\n"
            "- Retrieval quality depends on imported data\n"
            "- Internet access is optional\n"
            "- Not a large neural model\n\n"
            "Primary strength:\n"
            "Local, inspectable, source-grounded reasoning."
        )

    if "think" in lowered or "reasoning" in lowered:
        return (
            "Reasoning Model\n\n"
            "1. Receive input\n"
            "2. Normalize text\n"
            "3. Check self-knowledge\n"
            "4. Search indexed data\n"
            "5. Rank evidence\n"
            "6. Build answer\n"
            "7. Explain conclusions\n\n"
            "BrisartAI attempts to remain explainable and "
            "evidence-driven whenever possible."
        )

    if "architecture" in lowered or "system" in lowered:
        return (
            "BrisartAI Architecture\n\n"
            "Input\n"
            "  ->\n"
            "Ingestion\n"
            "  ->\n"
            "SQLite Index\n"
            "  ->\n"
            "Retrieval\n"
            "  ->\n"
            "Synthesis\n"
            "  ->\n"
            "Response\n\n"
            "Major Modules:\n"
            "- brisart_ai/io/readers.py\n"
            "- brisart_ai/knowledge/ingest.py\n"
            "- brisart_ai/knowledge/index.py\n"
            "- brisart_ai/knowledge/ranker.py\n"
            "- brisart_ai/knowledge/synthesizer.py\n"
            "- brisart_ai/core/conversation.py\n"
            "- brisart_ai/intelligence/self_knowledge.py\n"
        )

    lines.append(f"{APP_NAME} {__version__}")
    lines.append("")
    lines.append("Identity")
    lines.append("--------")
    lines.append("Pure-Python local-first research assistant.")
    lines.append("")
    lines.append("Environment")
    lines.append("-----------")
    lines.append(f"Indexed Sources: {total}")
    lines.append(f"Local Files: {files}")
    lines.append(f"Web Pages: {web}")
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

    if recent_topics:
        topics = list(recent_topics)[:5]

        if topics:
            lines.append("")
            lines.append("Memory")
            lines.append("------")
            for topic in topics:
                lines.append(f"- {topic}")

    lines.append("")
    lines.append(
        next_step(
            "Ask about memory, architecture, capabilities, reasoning, or limits."
        )
    )

    return "\n".join(lines)
