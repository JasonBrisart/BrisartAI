"""Explainable recommendations from indexed BrisartAI data."""

from __future__ import annotations

from brisart_ai.intelligence.personality import (
    limitation,
    next_step,
    observation,
    reasoning_bullets,
)


def recommend(
    index,
    top_terms: int = 20,
) -> str:
    """Generate recommendations from visible indexed patterns."""

    try:
        term_limit = max(1, int(top_terms))
    except (TypeError, ValueError):
        term_limit = 20

    total = index.source_count()
    files = index.source_count("file")
    web = index.source_count("web")

    lines = [
        "BrisartAI Recommendations",
        (
            "BrisartAI: I reviewed the indexed data "
            "and generated recommendations from the "
            "patterns I can actually see."
        ),
        "",
    ]

    if total == 0:
        lines.append("No indexed data found yet.")
        lines.append(
            limitation(
                "Recommendations require indexed local "
                "files or web pages."
            )
        )
        lines.append(
            next_step(
                "Preview a folder scan, then ingest "
                "the data you want BrisartAI to study."
            )
        )
        return "\n".join(lines)

    lines.extend(
        [
            "Reviewed data:",
            f"- Indexed sources: {total}",
            f"- Local files: {files}",
            f"- Web pages: {web}",
        ]
    )

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

    large_rows = index.conn.execute(
        """
        SELECT
            title,
            location,
            size_bytes
        FROM sources
        WHERE source_type = 'file'
        ORDER BY size_bytes DESC
        LIMIT 10
        """
    ).fetchall()

    duplicate_hash_rows = index.conn.execute(
        """
        SELECT
            content_hash,
            COUNT(*)
        FROM sources
        WHERE source_type = 'file'
          AND content_hash != ''
        GROUP BY content_hash
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
        LIMIT 10
        """
    ).fetchall()

    actions = []

    if files == 0:
        actions.append(
            "Ingest local files first. BrisartAI is "
            "designed to treat controlled local data "
            "as its primary evidence layer."
        )
    else:
        actions.append(
            "Keep local-first ingestion as the baseline. "
            "The strongest inspectable answers come from "
            "files you control."
        )

    if web == 0:
        actions.append(
            "Keep internet indexing disabled in "
            "air-gapped mode. Enable it only when outside "
            "context is intentionally permitted."
        )
    else:
        actions.append(
            "Keep web-indexed sources labeled separately "
            "from local files to preserve evidence origin."
        )

    if duplicate_hash_rows:
        duplicate_groups = len(
            duplicate_hash_rows
        )

        duplicate_entries = sum(
            int(row[1] or 0)
            for row in duplicate_hash_rows
        )

        actions.append(
            "Review possible duplicate files. "
            f"I found {duplicate_groups} duplicate "
            "content group"
            f"{'s' if duplicate_groups != 1 else ''} "
            f"covering {duplicate_entries} indexed "
            "file entries."
        )

    if large_rows:
        largest_size = int(
            large_rows[0][2]
            or 0
        )

        if largest_size > 1_000_000:
            actions.append(
                "Consider splitting unusually large logs "
                "or exports into smaller dated records to "
                "improve focused retrieval."
            )

    if extension_rows:
        common_extension = (
            extension_rows[0][0]
            or "(none)"
        )

        actions.append(
            "Optimize ingestion and analysis around "
            f"`{common_extension}` files first because "
            "they are currently the most common indexed "
            "local format."
        )

    title_rows = index.conn.execute(
        """
        SELECT title
        FROM sources
        WHERE source_type = 'file'
        """
    ).fetchall()

    titles = [
        str(row[0]).casefold()
        for row in title_rows
        if row[0]
    ]

    title_blob = "\n".join(titles)

    if "readme" not in title_blob:
        actions.append(
            "Add a README-like file if this indexed "
            "material represents a project, lab archive, "
            "or software tool."
        )

    if (
        "changelog" not in title_blob
        and "change" not in title_blob
    ):
        actions.append(
            "Add a changelog-like file if the indexed "
            "material changes over time."
        )

    if "license" not in title_blob:
        actions.append(
            "Add a license or usage-terms file before "
            "sharing the repository or dataset."
        )

    lines.append("")
    lines.append("Recommendations:")

    for action in actions:
        lines.append(f"- {action}")

    if term_rows:
        top_words = ", ".join(
            str(term)
            for term, _frequency
            in term_rows[:8]
        )

        lines.append("")
        lines.append(
            observation(
                "The strongest recurring terms are: "
                f"{top_words}. This indicates that the "
                "indexed material has a visible thematic "
                "center."
            )
        )

        lines.append("")
        lines.append("Top indexed terms:")

        for term, frequency in term_rows:
            lines.append(
                f"- {term}: {int(frequency or 0)}"
            )

    if large_rows:
        lines.append("")
        lines.append("Largest indexed local files:")

        for title, location, size in large_rows:
            lines.append(
                f"- {title or location}: "
                f"{int(size or 0)} bytes :: {location}"
            )

    reasons = [
        (
            "I checked whether the index is primarily "
            "local, web-based, or mixed."
        ),
        (
            "I checked duplicate content hashes, large "
            "files, dominant formats, project documents, "
            "and recurring terms."
        ),
        (
            "Recommendations are tied to indexed metadata "
            "or indexed text patterns."
        ),
    ]

    lines.append("")
    lines.extend(
        reasoning_bullets(reasons)
    )

    lines.append("")
    lines.append(
        next_step(
            "Ask about one recommendation if you want "
            "BrisartAI to explain its supporting evidence."
        )
    )

    return "\n".join(lines)


__all__ = [
    "recommend",
]
