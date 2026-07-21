"""Whole-drive and folder scanning for BrisartAI.

The scanner discovers supported files and can either preview them or ingest them.
It uses conservative defaults so users do not accidentally index noisy system areas.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator, List

from .ingest import ingest_paths
from .scan_policy import DEFAULT_MAX_FILE_BYTES, should_skip_dir, should_skip_file


def default_scan_roots() -> List[str]:
    """Return likely user-data roots without assuming a specific OS."""
    roots = []
    home = Path.home()
    if home.exists():
        roots.append(str(home))

    # Windows-style drive roots. Only include existing ones.
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:/")
        if drive.exists():
            roots.append(str(drive))

    # POSIX-style root fallback, useful for Linux/macOS/containers.
    if Path("/").exists() and not roots:
        roots.append("/")

    # Preserve order, remove duplicates.
    seen = set()
    out = []
    for root in roots:
        key = str(Path(root).resolve()) if Path(root).exists() else root
        if key not in seen:
            seen.add(key)
            out.append(root)
    return out


def iter_scan_files(roots: Iterable[str], include_hidden: bool = False, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES, max_files: int = 10000) -> Iterator[Path]:
    yielded = 0
    for raw_root in roots:
        root = Path(raw_root).expanduser()
        if not root.exists():
            print(f"WARN: scan root does not exist: {root}")
            continue
        if root.is_file():
            if not should_skip_file(root, include_hidden=include_hidden, max_bytes=max_file_bytes):
                yield root.resolve()
            continue

        for current, dirnames, filenames in os.walk(root):
            current_path = Path(current)

            # Modify dirnames in-place so os.walk does not descend into skipped directories.
            kept_dirs = []
            for dirname in dirnames:
                candidate = current_path / dirname
                if should_skip_dir(candidate, include_hidden=include_hidden):
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            for filename in filenames:
                candidate = current_path / filename
                if should_skip_file(candidate, include_hidden=include_hidden, max_bytes=max_file_bytes):
                    continue
                yield candidate.resolve()
                yielded += 1
                if yielded >= max_files:
                    return


def scan_preview(roots: Iterable[str], include_hidden: bool = False, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES, max_files: int = 10000) -> str:
    files = list(iter_scan_files(roots, include_hidden=include_hidden, max_file_bytes=max_file_bytes, max_files=max_files))
    by_ext = {}
    total_bytes = 0
    for path in files:
        ext = path.suffix.lower() or "(none)"
        by_ext[ext] = by_ext.get(ext, 0) + 1
        try:
            total_bytes += path.stat().st_size
        except OSError:
            pass

    lines = []
    lines.append("BrisartAI Scan Preview")
    lines.append("")
    lines.append(f"Candidate files: {len(files)}")
    lines.append(f"Approx bytes: {total_bytes}")
    lines.append("\nFile types:")
    for ext, count in sorted(by_ext.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {ext}: {count}")
    lines.append("\nSample files:")
    for path in files[:25]:
        lines.append(f"- {path}")
    if len(files) > 25:
        lines.append(f"- ... {len(files) - 25} more")
    return "\n".join(lines)


def scan_and_ingest(roots: Iterable[str], index, include_hidden: bool = False, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES, max_files: int = 10000) -> int:
    files = [str(path) for path in iter_scan_files(roots, include_hidden=include_hidden, max_file_bytes=max_file_bytes, max_files=max_files)]
    if not files:
        print("No supported files found for ingestion.")
        return 0
    return ingest_paths(files, index)
