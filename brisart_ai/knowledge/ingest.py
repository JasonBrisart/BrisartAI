"""Local data ingestion."""

from __future__ import annotations

from typing import Iterable

from .readers import iter_supported_files, read_file
from .util import file_hash


def ingest_paths(paths: Iterable[str], index) -> int:
    count = 0
    for path in iter_supported_files(paths):
        try:
            text = read_file(path)
            index.add_source(
                source_type="file",
                location=str(path),
                title=path.name,
                text=text,
                content_hash=file_hash(path),
                size_bytes=path.stat().st_size,
                extension=path.suffix.lower(),
            )
            count += 1
            print(f"INGESTED: {path}")
        except Exception as exc:
            print(f"WARN: could not ingest {path}: {exc}")
    return count
