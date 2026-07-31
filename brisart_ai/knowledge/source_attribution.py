"""
Source attribution helpers for BrisartAI.

Turns raw source locations into a clean, readable block.
Pure Python. No dependencies.
"""

from __future__ import annotations

from typing import List


def format_sources(
    sources: List[str],
) -> str:
    unique = sorted(
        set(
            source
            for source in sources
            if source
        )
    )

    if not unique:
        return ""

    lines = [
        "",
        "Sources:",
    ]

    for source in unique:
        lines.append(f"- {source}")

    return "\n".join(lines)


__all__ = ["format_sources"]