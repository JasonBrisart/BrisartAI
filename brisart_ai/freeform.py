"""Free-form response fallback for BrisartAI.

This lets BrisartAI respond to anything the user types while clearly stating
whether the answer is grounded in indexed files or general local assistant logic.
"""

from __future__ import annotations

from typing import Iterable, List

from .personality import next_step, observation, reasoning_bullets
from .util import tokenize


def _classify_intent(text: str) -> str:
    terms = set(tokenize(text))
    lowered = text.lower()
    if not terms:
        return "empty"
    if terms & {"hello", "hi", "hey", "yo"}:
        return "greeting"
    if terms & {"help", "commands", "command", "usage"}:
        return "help"
    if terms & {"recommend", "recommendation", "suggest", "suggestion", "improve"}:
        return "recommend"
    if terms & {"analyze", "analysis", "summary", "summarize", "overview"}:
        return "analyze"
    if terms & {"scan", "index", "ingest", "import", "files", "folder", "drive"}:
        return "data"
    if any(p in lowered for p in ["can you", "should i", "what if", "why", "how"]):
        return "general_question"
    return "general"


def freeform_response(user_text: str, index=None, recent_topics: Iterable[str] | None = None) -> str:
    intent = _classify_intent(user_text)
    total = index.source_count() if index is not None else 0
    files = index.source_count("file") if index is not None else 0
    web = index.source_count("web") if index is not None else 0

    lines: List[str] = []
    lines.append("BrisartAI: I can answer that conversationally. I will also tell you whether I am using imported evidence.")

    if recent_topics:
        topics = [t for t in recent_topics if t][:3]
        if topics:
            lines.append(f"Recent context: {' | '.join(topics)}")

    if total > 0:
        lines.append(observation(f"I have {total} indexed source{'s' if total != 1 else ''} available: {files} local file{'s' if files != 1 else ''} and {web} web page{'s' if web != 1 else ''}. No strong source match was found for this exact message."))
    else:
        lines.append(observation("No imported files are indexed yet. This response is general assistant behavior, not a claim about your data."))

    lines.append("")

    if intent == "empty":
        lines.append("Answer: I am here. Type a question or command and I will respond.")
        lines.append(next_step("Try `what can you do`, `/status`, or `/ingest PATH`."))
    elif intent == "greeting":
        lines.append("Answer: Hey. I am running locally and ready. You can talk to me normally, or you can import files so I can answer from your actual data.")
        lines.append(next_step("Ask `what can you do`, or import a folder with `/ingest PATH`."))
    elif intent == "help":
        lines.append("Answer: You can talk to me normally. Commands are optional shortcuts.")
        lines.append("Useful commands:")
        lines.append("- /ingest PATH")
        lines.append("- /scan-preview PATH")
        lines.append("- /analyze")
        lines.append("- /recommend")
        lines.append("- /web QUERY")
        lines.append("- /status")
        lines.append("- /exit")
    elif intent == "recommend":
        lines.append("Answer: I can recommend next moves. With no matching indexed evidence, my general recommendation is to import the folder you care about, analyze it, then ask for specific improvements.")
        lines.append(next_step("Run `/ingest PATH`, then `/recommend`."))
    elif intent == "analyze":
        lines.append("Answer: I can analyze indexed files for recurring terms, file types, duplicate content hashes, large files, and documentation gaps.")
        lines.append(next_step("Run `/analyze` after importing files."))
    elif intent == "data":
        lines.append("Answer: My best mode is data-first. Once files are imported, I search those files before giving an answer. If nothing matches, I switch to normal conversation and say so.")
        lines.append(next_step("Use `/scan-preview PATH` first if you want to inspect what would be indexed."))
    elif intent == "general_question":
        lines.append("Answer: Yes, I can respond normally without you manually writing a canned response for every possible question. This version uses a self-knowledge layer, a free-form fallback layer, recent session memory, and the local file index. It is not a trained language model, so it will be simpler than Copilot, but it should no longer feel stuck just because the index is empty.")
        lines.append(next_step("Keep talking normally in chat mode, then import files when you want grounded answers."))
    else:
        lines.append("Answer: I can keep the conversation going. If the question is about imported files, I need matching indexed evidence. If it is a general question, I can answer from built-in assistant logic and clearly label it as general.")
        lines.append(next_step("Ask a normal follow-up, or import data if you want source-grounded answers."))

    lines.append("")
    lines.extend(reasoning_bullets([
        "I checked the local index before falling back to general conversation.",
        "I identified the rough intent of your message.",
        "I avoided pretending that unsupported general responses came from imported files.",
    ]))
    return "\n".join(lines)
