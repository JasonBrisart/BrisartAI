"""
File: brisart_ai/knowledge/ingest.py

Purpose
-------
Local file/folder ingestion: reads every supported file under one or
more paths and adds each to the index. All file-type dispatch lives in
io/readers.py -- this module just reads, hashes, and adds.

Communication / relationships
------------------------------
- brisart_ai/ui/service.py: BrisartService.import_paths() is the sole
  caller, invoked from the "Import Files" sidebar action.
- Calls brisart_ai.io.readers.iter_supported_files() and read_file(),
  brisart_ai.util.file_hash(), and index.add_source() on the Index
  instance passed in.

Settings / parameters
----------------------
- No module-level constants; behavior is driven entirely by the paths
  and index passed to ingest_paths().

Edge cases
----------
- A file that reads as empty text is skipped and not counted toward the
  returned total.
- A hash failure (OSError while reading for hashing) is logged but does
  not block indexing -- the file is still added with an empty
  content_hash, since the hash is only used for duplicate detection, not
  as a requirement for indexing.
- Any read/index failure for one file (OSError, UnicodeError, ValueError,
  RuntimeError, or an unexpected exception) is caught and logged so a
  single bad file never aborts a whole folder import.
"""
from __future__ import annotations

from typing import Iterable

from brisart_ai.io.readers import (
    iter_supported_files,
    read_file,
)
from brisart_ai.util import file_hash


def ingest_paths(
    paths: Iterable[str],
    index,
) -> int:
    """Ingest supported files from paths into the supplied index."""
    count = 0
    for path in iter_supported_files(paths):
        try:
            text = read_file(path)
            if not text or not text.strip():
                print(f"SKIPPED EMPTY: {path}")
                continue

            try:
                size_bytes = path.stat().st_size
            except OSError:
                size_bytes = 0

            try:
                content_hash = file_hash(path)
            except OSError as exc:
                print(f"WARN: could not hash {path}: {exc}")
                content_hash = ""

            indexed = index.add_source(
                source_type="file",
                location=str(path),
                title=path.name,
                text=text,
                content_hash=content_hash,
                size_bytes=size_bytes,
                extension=path.suffix.lower(),
            )
            if indexed:
                count += 1
                print(f"INGESTED: {path}")
            else:
                print(f"SKIPPED EMPTY: {path}")
        except (
            OSError,
            UnicodeError,
            ValueError,
            RuntimeError,
        ) as exc:
            print(f"WARN: could not ingest {path}: {exc}")
        except Exception as exc:
            print(
                f"WARN: unexpected ingestion failure "
                f"for {path}: {exc}"
            )
    return count


__all__ = ["ingest_paths"]
