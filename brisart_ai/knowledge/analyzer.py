"""Local knowledge-index analysis for BrisartAI."""

from __future__ import annotations

from brisart_ai.intelligence.personality import (
    next_step,
    observation,
    reasoning_bullets,
)


def analyze_index(
    index,
    top_terms: int = 25,
) -> str:
    """Analyze the current BrisartAI source index."""

    try:
        term_limit = max(1, int(top_terms))
    except (TypeError, ValueError):
        term_limit = 25

    total = index.source_count()
    files = index.source_count("file")
    web = index.source_count("web")

    lines = [
        (
            "BrisartAI: I finished reviewing "
            "the current index."
        ),
        "",
        "Index summary:",
        f"- Total indexed sources: {total}",
        f"- Local files: {files}",
        f"- Web pages: {web}",
    ]

    if total == 0:
        lines.append("")
        lines.append(
            observation(
                "There is nothing indexed yet, so I "
                "cannot infer patterns from your data."
            )
        )
        lines.append(
            next_step(
                "Ingest a project folder or preview "
                "a conservative folder scan."
            )
        )
        return "\n".join(lines)

    extension_rows = index.conn.execute(
        """
        SELECT
            extension,
            COUNT(*),
            SUM(size_bytes)
        FROM sources
        WHERE source_type = 'file'
        GROUP BY extension
        ORDER BY COUNT(*) DESC, extension ASC
        """
    ).fetchall()

    if extension_rows:
        lines.append("")
        lines.append("File type distribution:")

        for extension, count, size in extension_rows:
            label = extension or "(none)"
            lines.append(
                f"- {label}: {count} files, "
                f"{int(size or 0)} bytes"
            )

        most_common_extension = (
            extension_rows[0][0]
            or "(none)"
        )

        most_common_count = int(
            extension_rows[0][1]
            or 0
        )

        lines.append(
            observation(
                "The most common local file type is "
                f"`{most_common_extension}`, appearing "
                f"{most_common_count} "
                f"time{'s' if most_common_count != 1 else ''}."
            )
        )

    term_rows = index.conn.execute(
        """
        SELECT
            term,
            SUM(tf) AS total_tf
        FROM terms
        GROUP BY term
        ORDER BY total_tf DESC, term ASC
        LIMIT ?
        """,
        (term_limit,),
    ).fetchall()

    if term_rows:
        lines.append("")
        lines.append("Dominant terms:")

        for term, frequency in term_rows:
            lines.append(
                f"- {term}: {int(frequency or 0)}"
            )

        top_terms_text = ", ".join(
            str(term)
            for term, _frequency
            in term_rows[:8]
        )

        lines.append(
            observation(
                "The strongest visible themes currently "
                f"cluster around: {top_terms_text}."
            )
        )

    recent_rows = index.conn.execute(
        """
        SELECT
            source_type,
            title,
            location
        FROM sources
        ORDER BY indexed_at DESC
        LIMIT 10
        """
    ).fetchall()

    if recent_rows:
        lines.append("")
        lines.append("Recent sources reviewed:")

        for source_type, title, location in recent_rows:
            lines.append(
                f"- {source_type}: "
                f"{title or location}"
            )

    reasons = [
        (
            "I counted indexed sources by type to "
            "separate local evidence from optional "
            "web context."
        )
    ]

    if extension_rows:
        reasons.append(
            "I grouped local files by extension to "
            "identify the dominant data formats."
        )

    if term_rows:
        reasons.append(
            "I ranked terms by total frequency to "
            "identify recurring topics in the index."
        )

    lines.append("")
    lines.extend(
        reasoning_bullets(reasons)
    )

    lines.append("")
    lines.append(
        next_step(
            "Run the recommendation command to turn "
            "these observations into action items."
        )
    )

    return "\n".join(lines)


__all__ = [
    "analyze_index",
]
