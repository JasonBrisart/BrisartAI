"""Local recommendations based on indexed BrisartAI data.

The recommendation engine is intentionally explainable. It does not claim to
know intent. It points out patterns that are visible in the indexed data.
"""

from __future__ import annotations

from .personality import limitation, next_step, observation, reasoning_bullets


def recommend(index, top_terms: int = 20) -> str:
    total = index.source_count()
    files = index.source_count("file")
    web = index.source_count("web")

    lines = []
    lines.append("BrisartAI Recommendations")
    lines.append("BrisartAI: I reviewed the indexed data and generated recommendations from the patterns I can actually see.")
    lines.append("")

    if total == 0:
        lines.append("No indexed data found yet.")
        lines.append(limitation("Recommendations require indexed local files or web pages."))
        lines.append(next_step("Run `python brisartai.py scan-drive ./ --preview`, then ingest the data you want me to study."))
        return "\n".join(lines)

    lines.append("Reviewed data:")
    lines.append(f"- Indexed sources: {total}")
    lines.append(f"- Local files: {files}")
    lines.append(f"- Web pages: {web}")

    ext_rows = index.conn.execute(
        "SELECT extension, COUNT(*), SUM(size_bytes) FROM sources WHERE source_type='file' GROUP BY extension ORDER BY COUNT(*) DESC"
    ).fetchall()
    term_rows = index.conn.execute(
        "SELECT term, SUM(tf) AS total_tf FROM terms GROUP BY term ORDER BY total_tf DESC LIMIT ?",
        (top_terms,),
    ).fetchall()
    large_rows = index.conn.execute(
        "SELECT title, location, size_bytes FROM sources WHERE source_type='file' ORDER BY size_bytes DESC LIMIT 10"
    ).fetchall()
    duplicate_hash_rows = index.conn.execute(
        "SELECT content_hash, COUNT(*) FROM sources WHERE source_type='file' AND content_hash != '' GROUP BY content_hash HAVING COUNT(*) > 1 ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()

    actions = []
    if files == 0:
        actions.append("Ingest local files first. BrisartAI is designed to treat your own data as the primary evidence layer.")
    else:
        actions.append("Keep local-first ingestion as the baseline. The strongest answers will come from files you control and can inspect.")

    if web == 0:
        actions.append("Leave internet indexing off in air-gapped mode. Use web mode only when you intentionally want outside context.")
    else:
        actions.append("Keep web-indexed sources labeled separately from local files so outside context does not get mistaken for internal evidence.")

    if duplicate_hash_rows:
        duplicate_groups = len(duplicate_hash_rows)
        duplicate_entries = sum(row[1] for row in duplicate_hash_rows)
        actions.append(f"Review possible duplicate files. I found {duplicate_groups} duplicate content group{'s' if duplicate_groups != 1 else ''} covering {duplicate_entries} indexed file entries.")

    if large_rows:
        largest = large_rows[0]
        if largest[2] and largest[2] > 1_000_000:
            actions.append("Split unusually large logs or exports into smaller dated records. That will make search and recommendations cleaner.")

    if ext_rows:
        common_ext, common_count, _size = ext_rows[0]
        actions.append(f"Optimize around `{common_ext or '(none)'}` files first because they are the most common indexed local format.")

    titles = [row[0].lower() for row in index.conn.execute("SELECT title FROM sources WHERE source_type='file'").fetchall() if row[0]]
    title_blob = "\n".join(titles)
    if "readme" not in title_blob:
        actions.append("Add a README-like file if this indexed data represents a project, lab archive, or tool." )
    if "changelog" not in title_blob and "change" not in title_blob:
        actions.append("Add a changelog-like file if the indexed data changes over time." )
    if "license" not in title_blob:
        actions.append("Add a license or usage terms before sharing this repository or dataset." )

    lines.append("\nRecommendations:")
    for item in actions:
        lines.append(f"- {item}")

    if term_rows:
        top_words = ", ".join(term for term, _tf in term_rows[:8])
        lines.append("")
        lines.append(observation(f"The strongest recurring terms are: {top_words}. This suggests the indexed material has a recognizable thematic center."))
        lines.append("\nTop indexed terms:")
        for term, tf in term_rows[:top_terms]:
            lines.append(f"- {term}: {tf}")

    if large_rows:
        lines.append("\nLargest indexed local files:")
        for title, location, size in large_rows:
            lines.append(f"- {title}: {size or 0} bytes :: {location}")

    reasons = [
        "I checked whether the index is mostly local, mostly web, or mixed.",
        "I looked for duplicate content hashes, large files, dominant file formats, missing project documents, and recurring terms.",
        "I only made recommendations that can be tied back to indexed metadata or indexed text patterns.",
    ]
    lines.append("")
    lines.extend(reasoning_bullets(reasons))
    lines.append("")
    lines.append(next_step("Ask `why this recommendation?` with a specific item if you want me to drill into the evidence behind it."))
    return "\n".join(lines)
