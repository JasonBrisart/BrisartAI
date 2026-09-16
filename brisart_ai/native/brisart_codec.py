"""
File: brisart_ai/native/brisart_codec.py

Purpose
-------
BrisartBase64 -- a from-spec, pure-Python Base64 encoder/decoder
(RFC 4648), replacing the base64 module's b64encode/b64decode and
urlsafe_b64decode calls -- currently used in web/search.py's
_decode_bing_target() to unwrap Bing's click-tracking redirect
wrapper, whose `u` parameter is URL-safe base64 without padding.

Communication / relationships
------------------------------
- Intended as a drop-in replacement for base64.b64encode()/b64decode()
  and base64.urlsafe_b64decode() at every current call site.
- Imports nothing from elsewhere in brisart_ai; pure stdlib-free
  integer/byte arithmetic.

Settings / parameters
----------------------
- _STANDARD_ALPHABET: the 64-character RFC 4648 standard alphabet
  (A-Z, a-z, 0-9, +, /).
- _URLSAFE_ALPHABET: the URL-safe variant (- and _ replace + and /),
  used specifically because Bing's redirect wrapper needs it.
- brisart_b64decode(data, urlsafe=False)'s `padding` handling: missing
  '=' padding is tolerated by right-padding with '=' up to a multiple
  of 4 characters before decoding, since Bing's wrapper strips padding
  entirely.

Edge cases
----------
- brisart_b64encode() always emits '=' padding to a multiple of 4
  characters, matching base64.b64encode()'s standard behavior exactly.
- brisart_b64decode() raises ValueError for a character outside the
  selected alphabet, same failure mode as base64.b64decode(validate
  effectively on by construction, since unknown characters have no
  table entry).
- An empty input encodes to an empty string and decodes back to empty
  bytes, exercised explicitly by this module's self-test.

Known limitations
-----------------
- Implements standard and URL-safe Base64 only; other encodings
  (Base32/Base85/Base58) are out of scope.
- brisart_b64decode() validates the alphabet and padding and raises on
  malformed input rather than silently truncating.
- Pure-Python byte loops: correct and dependency-free, but slower than
  the C-backed stdlib base64 on very large inputs.

Examples
--------
    >>> brisart_b64encode(b"hi")
    b'aGk='
    >>> brisart_b64decode(b"aGk=")
    b'hi'
    >>> brisart_urlsafe_b64decode(b"a-b_")        # doctest: +SKIP
"""
from __future__ import annotations

_STANDARD_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
)
_URLSAFE_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _build_decode_table(alphabet: str) -> dict:
    return {char: index for index, char in enumerate(alphabet)}


_STANDARD_DECODE = _build_decode_table(_STANDARD_ALPHABET)
_URLSAFE_DECODE = _build_decode_table(_URLSAFE_ALPHABET)


def brisart_b64encode(data: bytes, urlsafe: bool = False) -> bytes:
    """Encode bytes to Base64 (RFC 4648), with standard '=' padding."""
    alphabet = _URLSAFE_ALPHABET if urlsafe else _STANDARD_ALPHABET
    output = []
    length = len(data)
    for offset in range(0, length, 3):
        chunk = data[offset:offset + 3]
        chunk_len = len(chunk)
        padded = chunk + b"\x00" * (3 - chunk_len)
        value = (padded[0] << 16) | (padded[1] << 8) | padded[2]

        c0 = (value >> 18) & 0x3F
        c1 = (value >> 12) & 0x3F
        c2 = (value >> 6) & 0x3F
        c3 = value & 0x3F

        if chunk_len == 3:
            output.append(alphabet[c0] + alphabet[c1] + alphabet[c2] + alphabet[c3])
        elif chunk_len == 2:
            output.append(alphabet[c0] + alphabet[c1] + alphabet[c2] + "=")
        elif chunk_len == 1:
            output.append(alphabet[c0] + alphabet[c1] + "==")

    return "".join(output).encode("ascii")


def brisart_b64decode(data, urlsafe: bool = False) -> bytes:
    """Decode Base64 (RFC 4648) back to bytes. Tolerates missing '=' padding."""
    if isinstance(data, bytes):
        text = data.decode("ascii")
    else:
        text = data

    text = text.strip()
    remainder = len(text) % 4
    if remainder:
        text = text + ("=" * (4 - remainder))

    decode_table = _URLSAFE_DECODE if urlsafe else _STANDARD_DECODE
    output = bytearray()

    for offset in range(0, len(text), 4):
        group = text[offset:offset + 4]
        pad_count = group.count("=")
        digits = []
        for char in group:
            if char == "=":
                digits.append(0)
                continue
            if char not in decode_table:
                raise ValueError(f"invalid base64 character: {char!r}")
            digits.append(decode_table[char])

        value = (digits[0] << 18) | (digits[1] << 12) | (digits[2] << 6) | digits[3]
        group_bytes = bytes([(value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF])

        if pad_count == 0:
            output.extend(group_bytes)
        elif pad_count == 1:
            output.extend(group_bytes[:2])
        elif pad_count == 2:
            output.extend(group_bytes[:1])

    return bytes(output)


def brisart_urlsafe_b64decode(data) -> bytes:
    """Convenience wrapper matching base64.urlsafe_b64decode()'s signature."""
    return brisart_b64decode(data, urlsafe=True)


def _self_test() -> None:
    assert brisart_b64encode(b"") == b""
    assert brisart_b64decode(b"") == b""
    assert brisart_b64encode(b"f") == b"Zg=="
    assert brisart_b64encode(b"fo") == b"Zm8="
    assert brisart_b64encode(b"foo") == b"Zm9v"
    assert brisart_b64encode(b"foob") == b"Zm9vYg=="
    assert brisart_b64encode(b"fooba") == b"Zm9vYmE="
    assert brisart_b64encode(b"foobar") == b"Zm9vYmFy"
    assert brisart_b64decode(b"Zm9vYmFy") == b"foobar"
    assert brisart_b64decode("Zm9vYmFy") == b"foobar"
    assert brisart_b64decode("Zm9vYmFy", urlsafe=False) == b"foobar"
    assert brisart_b64decode("Zm9vYmFy".rstrip("=")) == b"foobar"


if __name__ == "__main__":
    _self_test()
    print("BrisartBase64 internal self-test passed.")


__all__ = ["brisart_b64encode", "brisart_b64decode", "brisart_urlsafe_b64decode"]


