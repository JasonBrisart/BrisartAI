"""Self-knowledge responses for BrisartAI.

This is the part of BrisartAI that knows what BrisartAI is.
It allows normal conversational questions like:

- who are you
- what do you do
- can you speak normally
- what can you access
- how do you work

These answers do not require imported files because they describe the assistant itself.
"""

from __future__ import annotations

from typing import Iterable, List

from . import APP_NAME, __version__
from .personality import next_step, observation, reasoning_bullets
from .util import tokenize


SELF_TERMS = {
    "who", "what", "you", "your", "yourself", "brisartai", "do", "doing",
    "work", "living", "purpose", "capabilities", "capability", "can", "speak",
    "normally", "normal", "talk", "respond", "generic", "access", "data", "files",
    "index", "memory", "alive", "conscious", "sentient", "how"
}


def looks_like_self_question(text: str) -> bool:
    terms = set(tokenize(text))
    lowered = text.lower().strip()
    phrases = [
        "who are you", "what are you", "what do you do", "what can you do",
        "what do you do for a living", "how do you work", "can you speak normally",
        "can you respond", "do you have access", "what data", "are you alive",
        "are you conscious", "are you sentient", "what is brisartai",
    ]
    if any(p in lowered for p in phrases):
        return True
    return bool(terms & SELF_TERMS) and ("you" in terms or "brisartai" in terms)


def self_response(user_text: str, index=None, recent_topics: Iterable[str] | None = None) -> str:
    total = index.source_count() if index is not None else 0
    files = index.source_count("file") if index is not None else 0
    web = index.source_count("web") if index is not None else 0
    lowered = user_text.lower()

    lines: List[str] = []
    lines.append(f"{APP_NAME}: I am a pure-Python local research assistant, version {__version__}.")

    if recent_topics:
        topics = [t for t in recent_topics if t][:3]
        if topics:
            lines.append(f"Context I still have in view: {' | '.join(topics)}")

    if "alive" in lowered or "conscious" in lowered or "sentient" in lowered:
        lines.append(observation("I can feel responsive and present, but I am not conscious, sentient, or human. I am a local assistant program that reasons through indexed data and built-in logic."))
    else:
        lines.append(observation("I can speak normally from my built-in assistant logic, and when you import files, I can ground answers in those files."))

    lines.append("")
    lines.append("What I do:")
    lines.append("- I ingest local files and folders.")
    lines.append("- I build a local SQLite search index.")
    lines.append("- I answer questions from imported files when matching evidence exists.")
    lines.append("- I scan folders or drives with conservative safety rules.")
    lines.append("- I analyze indexed data and generate recommendations.")
    lines.append("- I can optionally search/crawl public web pages when you explicitly use web mode.")
    lines.append("- I can still hold a normal conversation when no imported files match, but I label that clearly.")

    lines.append("")
    lines.append("What I can currently see:")
    lines.append(f"- Indexed sources: {total}")
    lines.append(f"- Local files: {files}")
    lines.append(f"- Web pages: {web}")

    lines.append("")
    lines.extend(reasoning_bullets([
        "This answer comes from my built-in self-knowledge module, not from your imported files.",
        "If your question is about your actual data, I will search the local index first and cite matching sources.",
        "If no source matches, I can still respond generally instead of repeating that the index is empty.",
    ]))
    lines.append("")
    if total == 0:
        lines.append(next_step("Import a folder with `/ingest PATH`, or just keep talking to me normally."))
    else:
        lines.append(next_step("Ask me about your indexed data, or run `/analyze` or `/recommend`."))
    return "\n".join(lines)
