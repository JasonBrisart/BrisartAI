"""Conversation router for BrisartAI.

Order of logic:
1. Clean accidental shell syntax from chat input.
2. Answer self-knowledge questions directly.
3. Search indexed data.
4. If evidence exists, synthesize a sourced answer.
5. If no evidence exists, answer conversationally with a clear grounding label.
"""

from __future__ import annotations

from .freeform import freeform_response
from .input_cleaner import normalize_shellish_input
from .ranker import search
from .self_knowledge import looks_like_self_question, self_response
from .synthesizer import synthesize


def build_conversation_answer(query: str, index, memory, limit: int = 8) -> str:
    cleaned = normalize_shellish_input(query)
    recent = memory.recent_topics(limit=4)

    if looks_like_self_question(cleaned):
        answer = self_response(cleaned, index=index, recent_topics=recent)
        memory.add("user", cleaned)
        memory.add("assistant", answer)
        return answer

    docs = search(index, cleaned, limit=limit)
    if docs:
        answer = synthesize(cleaned, docs, recent_topics=recent)
    else:
        answer = freeform_response(cleaned, index=index, recent_topics=recent)

    memory.add("user", cleaned)
    memory.add("assistant", answer)
    return answer
