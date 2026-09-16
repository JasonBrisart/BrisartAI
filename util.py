"""
File: brisart_ai/util.py

Purpose
-------
The one shared, dependency-free toolbox every other layer imports from:
tokenization, SHA-256 fingerprints, URL normalization/host comparison,
sentence splitting, timestamps, and best-effort multi-encoding reads.

Communication / relationships
------------------------------
- Imported from anywhere above native/. Uses the Brisart Native Stack
  (brisart_hash, brisart_url) with a stdlib fallback so the module still
  works if the native package is not importable in a given environment.
- Consumed by knowledge/index.py (tokenize, stable_hash, file_hash),
  knowledge/synthesizer.py (split_sentences, tokenize), knowledge/ingest.py
  and io/readers.py (safe_read_text, file_hash), web/crawler.py
  (normalize_url, same_site), and most other modules for tokenize().

Settings / parameters
---------------------
- STOPWORDS / WORD_RE: the small English stopword set and word-boundary
  pattern tokenize() uses; single-character words are always dropped.
- file_hash(chunk_size = 1_048_576): files are hashed in 1 MB chunks.
- split_sentences(min_len = 30, max_len = 700): sentences outside this
  character band are discarded as noise (fragments / run-ons).
- normalize_url(): prepends https:// to a schemeless string, lowercases
  scheme+host, percent-normalizes the path, strips the fragment.

Edge cases
----------
- tokenize(None) / tokenize("") return [] rather than raising.
- split_sentences("") returns []; normalize_url("") returns "".
- safe_read_text() tries utf-8 -> utf-16 -> latin-1 and always succeeds
  via a final errors="replace", returning "" only on an OS-level read
  failure.
- Every native-stack import is guarded with a stdlib fallback, so a
  missing brisart_ai.native package degrades gracefully.

Known limitations
-----------------
- tokenize() is a plain word-boundary splitter with a fixed stopword
  set; it does no stemming, lemmatization, or language detection, and is
  tuned for English only.
- split_sentences() is regex-based; it mis-splits on abbreviations
  ("Dr. Smith"), in-prose decimals, and non-Latin scripts, and cannot
  recover a sentence outside the 30-700 char band.
- normalize_url() applies a fixed normalization policy (https upgrade,
  fragment strip); callers needing different behavior must post-process.
- file_hash() reads the whole file; there is no partial fingerprinting
  beyond the streaming chunk size.

Examples
--------
    >>> tokenize("Hello, World! Co-founder")
    ['hello', 'world', 'co-founder']
    >>> len(stable_hash("x"))
    64
    >>> normalize_url("Example.COM/A").startswith("https://example.com")
    True
    >>> same_site("http://a.com/x", "https://a.com/y")
    True
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import List

try:  # Native stack preferred (matches the real repo), stdlib fallback.
    from brisart_ai.native.brisart_hash import brisart_sha256 as _sha256_factory

    def _sha256_hex(data: bytes) -> str:
        return _sha256_factory(data).hexdigest()
except Exception:  # pragma: no cover - fallback path
    import hashlib

    def _sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

try:
    from brisart_ai.native.brisart_url import brisart_urlsplit as _urlsplit
    from brisart_ai.native.brisart_url import brisart_urlunsplit as _urlunsplit
    from brisart_ai.native.brisart_url import brisart_quote as _quote
    _NATIVE_URL = True
except Exception:  # pragma: no cover - fallback path
    from urllib.parse import urlsplit as _urlsplit
    from urllib.parse import urlunsplit as _urlunsplit
    from urllib.parse import quote as _quote
    _NATIVE_URL = False


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "has", "have", "he", "her", "his", "i", "in", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "she", "that", "the",
    "their", "them", "they", "this", "to", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with",
    "you", "your", "how", "about", "into", "over", "under", "can",
    "could", "should", "would", "not", "no", "yes", "do", "does",
    "did", "than", "then", "there", "here", "if", "so", "like",
    "file", "files", "data", "using", "use", "used", "also", "may",
    "one", "two",
}
WORD_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-]{1,}")


def tokenize(text: str) -> List[str]:
    """Lowercase, split on word boundaries, drop single-char words and a
    small English stopword set. Returns [] for None/'' rather than raising."""
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    return [w for w in words if len(w) > 1 and w not in STOPWORDS]


def now_ts() -> int:
    """Whole-second Unix timestamp."""
    return int(time.time())


def stable_hash(value: str) -> str:
    """SHA-256 hex digest of a string (stable source keys, de-duplication)."""
    return _sha256_hex(str(value).encode("utf-8", "replace"))


def file_hash(path, chunk_size: int = 1_048_576) -> str:
    """Streaming SHA-256 hex digest of a file, read in 1 MB chunks."""
    try:
        from brisart_ai.native.brisart_hash import BrisartHash256 as _H
        hasher = _H()
    except Exception:  # pragma: no cover
        import hashlib
        hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


def split_sentences(text: str, min_len: int = 30, max_len: int = 700) -> List[str]:
    """Split text into sentences, dropping any outside the [min_len, max_len]
    character band (very short fragments and giant run-ons are noise)."""
    if not text:
        return []
    raw = re.sub(r"\s+", " ", str(text)).strip()
    if not raw:
        return []
    pieces = _SENTENCE_SPLIT_RE.split(raw)
    out: List[str] = []
    for piece in pieces:
        cleaned = piece.strip()
        if min_len <= len(cleaned) <= max_len:
            out.append(cleaned)
    return out


def normalize_url(url: str) -> str:
    """Normalize a URL: prepend https:// to a schemeless string, lowercase
    scheme+host, percent-normalize the path, and strip the fragment.
    Returns '' for empty input."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    if "://" not in raw and not raw.startswith("//"):
        raw = "https://" + raw
    try:
        parts = _urlsplit(raw)
    except Exception:
        return ""
    scheme = (parts.scheme or "https").lower()
    host = (parts.hostname or "").lower()
    netloc = host
    port = getattr(parts, "port", None)
    if port:
        netloc = f"{host}:{port}"
    path = parts.path or ""
    try:
        path = _quote(_unquote_safe(path), safe="/%:@&=+$,;~()!*'")
    except Exception:
        pass
    query = parts.query or ""
    rebuilt_parts = (scheme, netloc, path, query, "")
    try:
        if _NATIVE_URL:
            from brisart_ai.native.brisart_url import BrisartSplitResult
            return _urlunsplit(BrisartSplitResult(scheme, netloc, path, query, ""))
        return _urlunsplit(rebuilt_parts)
    except Exception:
        return f"{scheme}://{netloc}{path}" + (f"?{query}" if query else "")


def _unquote_safe(text: str) -> str:
    try:
        from brisart_ai.native.brisart_url import brisart_unquote
        return brisart_unquote(text)
    except Exception:
        from urllib.parse import unquote
        return unquote(text)


def same_site(url_a: str, url_b: str) -> bool:
    """True when two URLs share the same host (case-insensitive), scheme-agnostic."""
    try:
        host_a = (_urlsplit(normalize_url(url_a)).hostname or "").lower()
        host_b = (_urlsplit(normalize_url(url_b)).hostname or "").lower()
    except Exception:
        return False
    return bool(host_a) and host_a == host_b


def safe_read_text(path) -> str:
    """Best-effort multi-encoding read (utf-8 -> utf-16 -> latin-1), always
    succeeding via a final errors='replace'."""
    p = Path(path)
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return p.read_text(encoding=encoding)
        except (UnicodeError, UnicodeDecodeError):
            continue
        except OSError:
            return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


__all__ = [
    "STOPWORDS", "WORD_RE", "tokenize", "now_ts", "stable_hash", "file_hash",
    "split_sentences", "normalize_url", "same_site", "safe_read_text",
]



