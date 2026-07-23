"""Conservative local-drive and folder scanning for BrisartAI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator, List

from brisart_ai.knowledge.ingest import ingest_paths
from brisart_ai.scanning.scan_policy import (
    DEFAULT_MAX_FILE_BYTES,
    should_skip_dir,
    should_skip_file,
)


def default_scan_roots() -> List[str]:
    """Return likely local user-data roots."""

    roots: List[str] = []
    home = Path.home()

    if home.exists():
        roots.append(str(home))

    if os.name == "nt":
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:/")

            if drive.exists():
                roots.append(str(drive))
    elif not roots and Path("/").exists():
        roots.append("/")

    seen = set()
    output: List[str] = []

    for root in roots:
        path = Path(root)

        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)

        normalized_key = os.path.normcase(key)

        if normalized_key in seen:
            continue

        seen.add(normalized_key)
        output.append(root)

    return output


def iter_scan_files(
    roots: Iterable[str],
    include_hidden: bool = False,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_files: int = 10_000,
) -> Iterator[Path]:
    """Yield supported files found under the supplied roots."""

    try:
        file_limit = max(1, int(max_files))
    except (TypeError, ValueError):
        file_limit = 10_000

    try:
        byte_limit = max(1, int(max_file_bytes))
    except (TypeError, ValueError):
        byte_limit = DEFAULT_MAX_FILE_BYTES

    yielded = 0
    seen = set()

    for raw_root in roots:
        root = Path(raw_root).expanduser()

        if not root.exists():
            print(
                f"WARN: scan root does not exist: {root}"
            )
            continue

        if root.is_file():
            if should_skip_file(
                root,
                include_hidden=include_hidden,
                max_bytes=byte_limit,
            ):
                continue

            try:
                resolved = root.resolve()
            except OSError:
                resolved = root

            key = os.path.normcase(str(resolved))

            if key not in seen:
                seen.add(key)
                yield resolved
                yielded += 1

            if yielded >= file_limit:
                return

            continue

        for current, dirnames, filenames in os.walk(
            root,
            topdown=True,
        ):
            current_path = Path(current)
            kept_directories = []

            for directory_name in dirnames:
                candidate = (
                    current_path
                    / directory_name
                )

                if should_skip_dir(
                    candidate,
                    include_hidden=include_hidden,
                ):
                    continue

                kept_directories.append(
                    directory_name
                )

            dirnames[:] = kept_directories

            for filename in filenames:
                candidate = current_path / filename

                if should_skip_file(
                    candidate,
                    include_hidden=include_hidden,
                    max_bytes=byte_limit,
                ):
                    continue

                try:
                    resolved = candidate.resolve()
                except OSError:
                    resolved = candidate

                key = os.path.normcase(
                    str(resolved)
                )

                if key in seen:
                    continue

                seen.add(key)
                yield resolved

                yielded += 1

                if yielded >= file_limit:
                    return


def scan_preview(
    roots: Iterable[str],
    include_hidden: bool = False,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_files: int = 10_000,
) -> str:
    """Return a non-destructive preview of scan candidates."""

    files = list(
        iter_scan_files(
            roots,
            include_hidden=include_hidden,
            max_file_bytes=max_file_bytes,
            max_files=max_files,
        )
    )

    by_extension = {}
    total_bytes = 0

    for path in files:
        extension = (
            path.suffix.lower()
            or "(none)"
        )

        by_extension[extension] = (
            by_extension.get(extension, 0)
            + 1
        )

        try:
            total_bytes += path.stat().st_size
        except OSError:
            continue

    lines = [
        "BrisartAI Scan Preview",
        "",
        f"Candidate files: {len(files)}",
        f"Approx bytes: {total_bytes}",
        "",
        "File types:",
    ]

    if by_extension:
        for extension, count in sorted(
            by_extension.items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):
            lines.append(
                f"- {extension}: {count}"
            )
    else:
        lines.append("- No supported files found.")

    lines.append("")
    lines.append("Sample files:")

    if files:
        for path in files[:25]:
            lines.append(f"- {path}")

        if len(files) > 25:
            lines.append(
                f"- ... {len(files) - 25} more"
            )
    else:
        lines.append("- No candidate files.")

    return "\n".join(lines)


def scan_and_ingest(
    roots: Iterable[str],
    index,
    include_hidden: bool = False,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_files: int = 10_000,
) -> int:
    """Scan roots and ingest discovered supported files."""

    files = [
        str(path)
        for path in iter_scan_files(
            roots,
            include_hidden=include_hidden,
            max_file_bytes=max_file_bytes,
            max_files=max_files,
        )
    ]

    if not files:
        print(
            "No supported files found for ingestion."
        )
        return 0

    return ingest_paths(
        files,
        index,
    )


__all__ = [
    "default_scan_roots",
    "iter_scan_files",
    "scan_and_ingest",
    "scan_preview",
]
