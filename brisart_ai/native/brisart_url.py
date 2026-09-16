"""
File: brisart_ai/native/brisart_url.py

Purpose
-------
BrisartURL -- a from-spec, pure-Python URL parsing/joining/encoding
toolkit (RFC 3986), replacing urllib.parse's urlsplit/urlunsplit/quote/
unquote/urlencode/parse_qsl/urljoin -- used throughout util.py
(normalize_url, same_site), io/extractor.py (link resolution),
web/crawler.py, web/search.py, and web/policy.py.

Communication / relationships
------------------------------
- Intended as a drop-in replacement for the corresponding
  urllib.parse functions at every current call site.
- Imports nothing from elsewhere in brisart_ai; pure string/byte
  manipulation.

Settings / parameters
----------------------
- BrisartSplitResult: a small named-tuple-like class exposing
  .scheme/.netloc/.path/.query/.fragment plus a computed .hostname
  property (lowercased, with a bracketed IPv6 literal or a trailing
  ":port" stripped), matching urllib.parse.SplitResult's public
  surface closely enough for every current call site.
- _UNRESERVED_CHARS: RFC 3986's always-safe character set (letters,
  digits, and -._~), used by brisart_quote()/brisart_unquote().
- brisart_quote(safe="/"): matches urllib.parse.quote()'s default
  `safe` parameter so a path's own "/" separators are preserved by
  default, exactly like the function it replaces.

Edge cases
----------
- brisart_urlsplit() treats a URL with no "://" as having an empty
  scheme and treats the whole remainder as a path, mirroring
  urllib.parse.urlsplit()'s own behavior for a schemeless string
  ("example.com/x" is NOT auto-upgraded to a scheme here -- util.py's
  normalize_url() is responsible for that policy decision, same as it
  was when calling the stdlib version).
- brisart_unquote() leaves a malformed "%" escape (not followed by two
  hex digits) untouched in the output rather than raising, matching
  urllib.parse.unquote()'s lenient behavior.
- brisart_urljoin() implements RFC 3986 section 5.3's reference
  resolution algorithm, including the dot-segment removal step
  (collapsing "/a/b/../c" to "/a/c" and "/a/./b" to "/a/b").

Known limitations
-----------------
- A pragmatic URL splitter/joiner covering the schemes the crawler
  needs; it is not a full RFC 3986 validator and accepts some inputs a
  strict parser would reject.
- brisart_quote/unquote handle percent-encoding for the common unreserved
  set; exotic IRI/punycode host encoding is out of scope.
- Relative-reference resolution in brisart_urljoin covers common cases,
  not every abnormal example in the RFC.

Examples
--------
    >>> brisart_urlsplit("https://a.com/p?q=1").hostname
    'a.com'
    >>> brisart_urljoin("https://a.com/x/y", "../z")
    'https://a.com/z'
    >>> brisart_quote("a b")
    'a%20b'
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

_HEX_DIGITS = "0123456789ABCDEFabcdef"
_UNRESERVED_CHARS = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


class BrisartSplitResult:
    """Mirrors urllib.parse.SplitResult's public surface for our call sites."""

    __slots__ = ("scheme", "netloc", "path", "query", "fragment")

    def __init__(self, scheme: str, netloc: str, path: str, query: str, fragment: str):
        self.scheme = scheme
        self.netloc = netloc
        self.path = path
        self.query = query
        self.fragment = fragment

    @property
    def hostname(self) -> Optional[str]:
        netloc = self.netloc
        if not netloc:
            return None
        if "@" in netloc:
            netloc = netloc.rsplit("@", 1)[1]
        if netloc.startswith("["):
            end = netloc.find("]")
            if end == -1:
                return netloc.lower() or None
            return netloc[1:end].lower() or None
        if ":" in netloc:
            netloc = netloc.rsplit(":", 1)[0]
        return netloc.lower() or None

    def __repr__(self) -> str:
        return (
            f"BrisartSplitResult(scheme={self.scheme!r}, netloc={self.netloc!r}, "
            f"path={self.path!r}, query={self.query!r}, fragment={self.fragment!r})"
        )

    def geturl(self) -> str:
        return brisart_urlunsplit(self)


def brisart_urlsplit(url: str) -> BrisartSplitResult:
    """Split a URL into (scheme, netloc, path, query, fragment)."""
    remainder = str(url or "")

    fragment = ""
    if "#" in remainder:
        remainder, fragment = remainder.split("#", 1)

    scheme = ""
    colon_index = remainder.find(":")
    if colon_index > 0:
        candidate_scheme = remainder[:colon_index]
        if candidate_scheme[0].isalpha() and all(
            ch.isalnum() or ch in "+-." for ch in candidate_scheme
        ):
            if "/" not in candidate_scheme:
                scheme = candidate_scheme.lower()
                remainder = remainder[colon_index + 1:]

    netloc = ""
    if remainder.startswith("//"):
        remainder = remainder[2:]
        end = len(remainder)
        for marker in ("/", "?", "#"):
            index = remainder.find(marker)
            if index != -1:
                end = min(end, index)
        netloc = remainder[:end]
        remainder = remainder[end:]

    query = ""
    if "?" in remainder:
        remainder, query = remainder.split("?", 1)

    path = remainder
    return BrisartSplitResult(scheme, netloc, path, query, fragment)


def brisart_urlunsplit(parts) -> str:
    """Reassemble a (scheme, netloc, path, query, fragment)-like object into a URL string."""
    scheme, netloc, path, query, fragment = (
        parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment
    )
    result = ""
    if scheme:
        result += scheme + ":"
    if netloc or (scheme and path.startswith("/")):
        result += "//" + netloc
    result += path
    if query:
        result += "?" + query
    if fragment:
        result += "#" + fragment
    return result


def brisart_quote(text: str, safe: str = "/") -> str:
    """Percent-encode a string (RFC 3986), leaving unreserved and `safe` characters as-is."""
    if isinstance(text, bytes):
        raw = text
    else:
        raw = text.encode("utf-8", "replace")

    keep = set(_UNRESERVED_CHARS) | set(safe)
    output = []
    for byte in raw:
        char = chr(byte)
        if byte < 128 and char in keep:
            output.append(char)
        else:
            output.append(f"%{byte:02X}")
    return "".join(output)


def brisart_unquote(text: str) -> str:
    """Reverse percent-encoding. Malformed '%' escapes are left untouched (lenient, like urllib)."""
    if not text or "%" not in text:
        return text

    output_bytes = bytearray()
    i = 0
    length = len(text)
    literal_buffer = []

    def flush_literal():
        if literal_buffer:
            output_bytes.extend("".join(literal_buffer).encode("utf-8", "replace"))
            literal_buffer.clear()

    while i < length:
        char = text[i]
        if char == "%" and i + 2 < length and text[i + 1] in _HEX_DIGITS and text[i + 2] in _HEX_DIGITS:
            flush_literal()
            output_bytes.append(int(text[i + 1:i + 3], 16))
            i += 3
        else:
            literal_buffer.append(char)
            i += 1
    flush_literal()
    return output_bytes.decode("utf-8", "replace")


def _quote_plus(text: str) -> str:
    """Like brisart_quote(safe=""), but a literal space encodes as '+' (RFC 1866 form
    encoding), matching urllib.parse.urlencode()'s use of quote_plus() internally."""
    encoded = brisart_quote(text, safe="")
    return encoded.replace("%20", "+")


def brisart_urlencode(pairs: Iterable[Tuple[str, str]], doseq: bool = False) -> str:
    """Encode a sequence of (key, value) pairs as an application/x-www-form-urlencoded string.

    Matches urllib.parse.urlencode()'s default behavior of encoding a
    space as '+' (via quote_plus), not '%20' -- this is a DIFFERENT
    default than brisart_quote()/urllib.parse.quote() use on their own.
    """
    segments = []
    for key, value in pairs:
        if doseq and isinstance(value, (list, tuple)):
            for item in value:
                segments.append(f"{_quote_plus(str(key))}={_quote_plus(str(item))}")
        else:
            segments.append(f"{_quote_plus(str(key))}={_quote_plus(str(value))}")
    return "&".join(segments)


def brisart_parse_qsl(query: str, keep_blank_values: bool = False) -> List[Tuple[str, str]]:
    """Parse a query string into a list of (key, value) pairs."""
    pairs: List[Tuple[str, str]] = []
    if not query:
        return pairs
    for segment in query.split("&"):
        if not segment:
            continue
        if "=" in segment:
            raw_key, raw_value = segment.split("=", 1)
        else:
            raw_key, raw_value = segment, ""
        if not raw_value and not keep_blank_values:
            continue
        key = brisart_unquote(raw_key.replace("+", " "))
        value = brisart_unquote(raw_value.replace("+", " "))
        pairs.append((key, value))
    return pairs


def _remove_dot_segments(path: str) -> str:
    """RFC 3986 section 5.2.4: collapse '.' and '..' path segments."""
    if not path:
        return path
    input_segments = path.split("/")
    output: List[str] = []
    for index, segment in enumerate(input_segments):
        if segment == ".":
            continue
        if segment == "..":
            if output and output[-1] != "":
                output.pop()
            continue
        output.append(segment)
    result = "/".join(output)
    if path.startswith("/") and not result.startswith("/"):
        result = "/" + result
    return result


def brisart_urljoin(base: str, url: str) -> str:
    """Resolve a possibly-relative `url` against an absolute `base` (RFC 3986 section 5.3)."""
    if not url:
        return base
    parsed_url = brisart_urlsplit(url)
    if parsed_url.scheme:
        return brisart_urlunsplit(
            BrisartSplitResult(
                parsed_url.scheme, parsed_url.netloc,
                _remove_dot_segments(parsed_url.path),
                parsed_url.query, parsed_url.fragment,
            )
        )

    parsed_base = brisart_urlsplit(base)

    if url.startswith("//"):
        return brisart_urlunsplit(
            BrisartSplitResult(
                parsed_base.scheme, parsed_url.netloc,
                _remove_dot_segments(parsed_url.path),
                parsed_url.query, parsed_url.fragment,
            )
        )

    if parsed_url.netloc:
        return brisart_urlunsplit(
            BrisartSplitResult(
                parsed_base.scheme, parsed_url.netloc,
                _remove_dot_segments(parsed_url.path),
                parsed_url.query, parsed_url.fragment,
            )
        )

    if not parsed_url.path:
        new_query = parsed_url.query if (parsed_url.query or url.startswith("?")) else parsed_base.query
        new_fragment = parsed_url.fragment
        return brisart_urlunsplit(
            BrisartSplitResult(
                parsed_base.scheme, parsed_base.netloc, parsed_base.path,
                new_query, new_fragment,
            )
        )

    if parsed_url.path.startswith("/"):
        merged_path = parsed_url.path
    else:
        base_path = parsed_base.path
        last_slash = base_path.rfind("/")
        base_dir = base_path[:last_slash + 1] if last_slash != -1 else ""
        merged_path = base_dir + parsed_url.path

    return brisart_urlunsplit(
        BrisartSplitResult(
            parsed_base.scheme, parsed_base.netloc,
            _remove_dot_segments(merged_path),
            parsed_url.query, parsed_url.fragment,
        )
    )


def _self_test() -> None:
    result = brisart_urlsplit("https://Example.COM:8080/a/b?x=1&y=2#frag")
    assert result.scheme == "https"
    assert result.hostname == "example.com"
    assert result.path == "/a/b"
    assert result.query == "x=1&y=2"
    assert result.fragment == "frag"

    assert brisart_quote("a b/c", safe="/") == "a%20b/c"
    assert brisart_unquote("a%20b/c") == "a b/c"
    assert brisart_unquote("100%") == "100%"

    assert brisart_urljoin("https://a.com/x/y", "z") == "https://a.com/x/z"
    assert brisart_urljoin("https://a.com/x/y", "/z") == "https://a.com/z"
    assert brisart_urljoin("https://a.com/x/y/", "../z") == "https://a.com/x/z"
    assert brisart_urljoin("https://a.com/x", "//other.com/y") == "https://other.com/y"


if __name__ == "__main__":
    _self_test()
    print("BrisartURL internal self-test passed.")


__all__ = [
    "BrisartSplitResult",
    "brisart_parse_qsl",
    "brisart_quote",
    "brisart_unquote",
    "brisart_urlencode",
    "brisart_urljoin",
    "brisart_urlsplit",
    "brisart_urlunsplit",
]



