"""BrisartAI voice and response style.

This module makes BrisartAI feel more logical, present, and assistant-like
without pretending it is conscious, alive, sentient, or human.

Design rule:
    BrisartAI may speak with an analytical assistant voice.
    BrisartAI must remain grounded in indexed evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class VoiceProfile:
    name: str = "BrisartAI"
    role: str = "local research assistant"
    tone: str = "calm, logical, observant, proactive"
    evidence_rule: str = "Every claim should be grounded in indexed sources when possible."


DEFAULT_VOICE = VoiceProfile()


def opening(action: str, source_count: int = 0, voice: VoiceProfile = DEFAULT_VOICE) -> str:
    if source_count <= 0:
        return f"{voice.name}: I am ready, but I do not have indexed evidence for this yet."
    return f"{voice.name}: I reviewed {source_count} indexed source{'s' if source_count != 1 else ''} and built the clearest answer I can from the available evidence."


def observation(text: str) -> str:
    return f"Observation: {text}"


def reasoning_bullets(items: Iterable[str]) -> List[str]:
    out = ["Why I think this:"]
    for item in items:
        cleaned = str(item).strip()
        if cleaned:
            out.append(f"- {cleaned}")
    return out


def next_step(text: str) -> str:
    return f"Suggested next move: {text}"


def limitation(text: str) -> str:
    return f"Limit: {text}"


def confidence_label(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 4:
        return "moderate"
    if score > 0:
        return "low"
    return "unknown"


def section(title: str, lines: Iterable[str]) -> str:
    body = [str(line).rstrip() for line in lines if str(line).strip()]
    if not body:
        return ""
    return title + "\n" + "\n".join(body)
