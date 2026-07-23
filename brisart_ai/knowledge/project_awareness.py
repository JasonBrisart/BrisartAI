"""Project awareness tools for BrisartAI.

This module analyzes indexed repositories and project folders. It does not
try to guess hidden intent. It reports only visible structure from indexed
sources and metadata.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from brisart_ai.util import tokenize


PROJECT_DOC_NAMES = {
    "readme",
    "license",
    "changelog",
    "contributing",
    "architecture",
    "commands",
    "safety",
}


def _all_file_sources(index) -> List[Tuple[int, str, str, str, int, str]]:
    rows = index.conn.execute(
        """
        SELECT id, title, location, extension, size_bytes, text
        FROM sources
        WHERE source_type='file'
        ORDER BY location ASC
        """
    ).fetchall()
    return rows


def _common_root(paths: List[str]) -> str:
    if not paths:
        return ""
    try:
        return os.path.commonpath(paths)
    except Exception:
        return str(Path(paths[0]).parent)


def _path_parts(location: str, root: str) -> List[str]:
    try:
        rel = os.path.relpath(location, root)
    except Exception:
        rel = location
    return [part for part in Path(rel).parts if part not in {".", ""}]


def _detect_entry_points(paths: List[str]) -> List[str]:
    names = {
        "main.py",
        "app.py",
        "run.py",
        "cli.py",
        "start.py",
        "manage.py",
        "brisartai.py",
    }

    hits = []
    for path in paths:
        name = Path(path).name.lower()
        if name in names:
            hits.append(path)

    return hits


def _detect_project_docs(paths: List[str]) -> Dict[str, bool]:
    result = {name: False for name in PROJECT_DOC_NAMES}

    for path in paths:
        stem = Path(path).stem.lower()
        name = Path(path).name.lower()

        for wanted in PROJECT_DOC_NAMES:
            if stem == wanted or name == wanted:
                result[wanted] = True

    return result


def _major_folders(paths: List[str], root: str, limit: int = 20) -> List[Tuple[str, int]]:
    counts = Counter()

    for path in paths:
        parts = _path_parts(path, root)
        if len(parts) >= 2:
            counts[parts[0]] += 1

    return counts.most_common(limit)


def _python_imports(index, limit: int = 50) -> List[Tuple[str, int]]:
    imports = Counter()

    rows = index.conn.execute(
        """
        SELECT title, text
        FROM sources
        WHERE source_type='file' AND extension='.py'
        """
    ).fetchall()

    for _title, text in rows:
        for line in str(text).splitlines():
            stripped = line.strip()

            if stripped.startswith("import "):
                rest = stripped.replace("import ", "", 1)
                for item in rest.split(","):
                    name = item.strip().split(" ")[0].split(".")[0]
                    if name:
                        imports[name] += 1

            elif stripped.startswith("from "):
                parts = stripped.split()
                if len(parts) >= 2:
                    name = parts[1].split(".")[0]
                    if name:
                        imports[name] += 1

    return imports.most_common(limit)


def project_report(index) -> str:
    """Create a project awareness report from indexed files."""
    file_rows = _all_file_sources(index)

    lines = []
    lines.append("Project Awareness Report")
    lines.append("========================")
    lines.append("")

    if not file_rows:
        lines.append("No indexed local files are available.")
        lines.append("")
        lines.append("Run:")
        lines.append("python brisartai.py ingest ./your_project")
        return "\n".join(lines)

    paths = [row[2] for row in file_rows]
    root = _common_root(paths)

    ext_counts = Counter()
    total_bytes = 0
    line_estimate = 0

    for _id, _title, _location, extension, size_bytes, text in file_rows:
        ext_counts[extension or "(none)"] += 1
        total_bytes += int(size_bytes or 0)
        line_estimate += len(str(text).splitlines())

    docs = _detect_project_docs(paths)
    entries = _detect_entry_points(paths)
    folders = _major_folders(paths, root)
    imports = _python_imports(index)

    lines.append("Project Root")
    lines.append("------------")
    lines.append(root or "(unknown)")
    lines.append("")

    lines.append("Visible Size")
    lines.append("------------")
    lines.append(f"Indexed local files: {len(file_rows)}")
    lines.append(f"Approx indexed bytes: {total_bytes}")
    lines.append(f"Approx extracted text lines: {line_estimate}")
    lines.append("")

    lines.append("File Types")
    lines.append("----------")
    for ext, count in ext_counts.most_common():
        lines.append(f"- {ext}: {count}")
    lines.append("")

    lines.append("Major Folders")
    lines.append("-------------")
    if folders:
        for folder, count in folders:
            lines.append(f"- {folder}: {count} indexed file(s)")
    else:
        lines.append("- No nested folders detected.")
    lines.append("")

    lines.append("Entry Points")
    lines.append("------------")
    if entries:
        for entry in entries:
            lines.append(f"- {entry}")
    else:
        lines.append("- No common entry point detected.")
    lines.append("")

    lines.append("Project Documents")
    lines.append("-----------------")
    for name in sorted(docs):
        label = "present" if docs[name] else "not indexed"
        lines.append(f"- {name}: {label}")
    lines.append("")

    lines.append("Python Imports")
    lines.append("--------------")
    if imports:
        for name, count in imports:
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- No Python imports detected.")
    lines.append("")

    lines.append("Interpretation")
    lines.append("--------------")

    if ext_counts.get(".py", 0) > 0:
        lines.append(
            "This appears to include Python source code based on indexed file extensions."
        )

    if docs.get("readme"):
        lines.append("A README-like project document is indexed.")
    else:
        lines.append("No README-like project document was identified in the indexed files.")

    if docs.get("license"):
        lines.append("A license-like document is indexed.")
    else:
        lines.append("No license-like document was identified in the indexed files.")

    if entries:
        lines.append("One or more likely executable entry points were identified.")

    lines.append("")
    lines.append(
        "Suggested next move: run a project-specific question such as "
        "`ask \"what is this project trying to accomplish\"`."
    )

    return "\n".join(lines)


def research_report(index, top_terms: int = 35) -> str:
    """Generate a broader research report from indexed local and web data."""
    total = index.source_count()
    files = index.source_count("file")
    web = index.source_count("web")

    lines = []
    lines.append("Research Intelligence Report")
    lines.append("============================")
    lines.append("")
    lines.append("Index Scope")
    lines.append("-----------")
    lines.append(f"Indexed sources: {total}")
    lines.append(f"Local files: {files}")
    lines.append(f"Web pages: {web}")
    lines.append("")

    if total == 0:
        lines.append("No indexed data exists yet.")
        return "\n".join(lines)

    term_rows = index.conn.execute(
        """
        SELECT term, SUM(tf) AS total_tf
        FROM terms
        GROUP BY term
        ORDER BY total_tf DESC
        LIMIT ?
        """,
        (top_terms,),
    ).fetchall()

    source_type_rows = index.conn.execute(
        """
        SELECT source_type, COUNT(*)
        FROM sources
        GROUP BY source_type
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    ext_rows = index.conn.execute(
        """
        SELECT extension, COUNT(*), SUM(size_bytes)
        FROM sources
        WHERE source_type='file'
        GROUP BY extension
        ORDER BY COUNT(*) DESC
        """
    ).fetchall()

    recent_rows = index.conn.execute(
        """
        SELECT source_type, title, location
        FROM sources
        ORDER BY indexed_at DESC
        LIMIT 15
        """
    ).fetchall()

    lines.append("Source Types")
    lines.append("------------")
    for source_type, count in source_type_rows:
        lines.append(f"- {source_type}: {count}")
    lines.append("")

    if ext_rows:
        lines.append("Local File Distribution")
        lines.append("-----------------------")
        for ext, count, size in ext_rows:
            lines.append(f"- {ext or '(none)'}: {count} file(s), {size or 0} bytes")
        lines.append("")

    if term_rows:
        lines.append("Dominant Terms")
        lines.append("--------------")
        for term, tf in term_rows:
            lines.append(f"- {term}: {tf}")
        lines.append("")

        themes = ", ".join(term for term, _tf in term_rows[:10])
        lines.append("Visible Theme Cluster")
        lines.append("---------------------")
        lines.append(themes)
        lines.append("")

    if recent_rows:
        lines.append("Recently Indexed Sources")
        lines.append("------------------------")
        for source_type, title, location in recent_rows:
            lines.append(f"- {source_type}: {title or location}")
        lines.append("")

    lines.append("Interpretation")
    lines.append("--------------")

    if files and not web:
        lines.append(
            "The current knowledge base is local-only. That is ideal for offline "
            "or air-gapped research workflows."
        )
    elif files and web:
        lines.append(
            "The current knowledge base contains both local files and optional web context."
        )
    elif web and not files:
        lines.append(
            "The current knowledge base is web-heavy. Add local files if you want "
            "BrisartAI to prioritize private evidence."
        )

    lines.append("")
    lines.append(
        "Suggested next move: use `project`, `vault`, `timeline TOPIC`, "
        "or `collection create NAME` to organize this knowledge."
    )

    return "\n".join(lines)
