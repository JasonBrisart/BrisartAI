"""Local index analysis with an observant assistant voice."""

from __future__ import annotations

from .personality import next_step, observation, reasoning_bullets


def analyze_index(index, top_terms: int = 25) -> str:
    total = index.source_count()
    files = index.source_count("file")
    web = index.source_count("web")

    lines = []
    lines.append("BrisartAI: I finished reviewing the current index.")
    lines.append("")
    lines.append("Index summary:")
    lines.append(f"- Total indexed sources: {total}")
    lines.append(f"- Local files: {files}")
    lines.append(f"- Web pages: {web}")

    if total == 0:
        lines.append("")
        lines.append(observation("There is nothing indexed yet, so I cannot infer patterns from your data."))
        lines.append(next_step("Run `python brisartai.py ingest ./your_folder` or preview a broader scan with `python brisartai.py scan-drive ./ --preview`."))
        return "\n".join(lines)

    ext_rows = index.conn.execute(
        "SELECT extension, COUNT(*), SUM(size_bytes) FROM sources WHERE source_type='file' GROUP BY extension ORDER BY COUNT(*) DESC"
    ).fetchall()
    if ext_rows:
        lines.append("\nFile type distribution:")
        for ext, count, size in ext_rows:
            lines.append(f"- {ext or '(none)'}: {count} files, {size or 0} bytes")
        common_ext, common_count, _ = ext_rows[0]
        lines.append(observation(f"The most common local file type is `{common_ext or '(none)'}`, appearing {common_count} time{'s' if common_count != 1 else ''}."))

    term_rows = index.conn.execute(
        "SELECT term, SUM(tf) AS total_tf FROM terms GROUP BY term ORDER BY total_tf DESC LIMIT ?",
        (top_terms,),
    ).fetchall()
    if term_rows:
        lines.append("\nDominant terms:")
        for term, tf in term_rows:
            lines.append(f"- {term}: {tf}")
        top_terms_text = ", ".join(term for term, _ in term_rows[:8])
        lines.append(observation(f"The strongest visible themes currently cluster around: {top_terms_text}."))

    recent_rows = index.conn.execute(
        "SELECT source_type, title, location FROM sources ORDER BY indexed_at DESC LIMIT 10"
    ).fetchall()
    if recent_rows:
        lines.append("\nRecent sources reviewed:")
        for source_type, title, location in recent_rows:
            lines.append(f"- {source_type}: {title or location}")

    reasons = []
    reasons.append("I counted indexed sources by type to separate local evidence from optional web context.")
    if ext_rows:
        reasons.append("I grouped local files by extension to identify the dominant data formats.")
    if term_rows:
        reasons.append("I ranked terms by total frequency to identify recurring topics in the index.")
    lines.append("")
    lines.extend(reasoning_bullets(reasons))
    lines.append("")
    lines.append(next_step("Run `python brisartai.py recommend` if you want me to turn these observations into action items."))
    return "\n".join(lines)
