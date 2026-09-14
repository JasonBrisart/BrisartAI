"""
File: brisart_ai/native/brisart_hash.py

Purpose
-------
BrisartHash256 -- a from-spec, pure-Python SHA-256 implementation,
replacing hashlib.sha256() everywhere BrisartAI fingerprints content
(stable source keys in knowledge/index.py, file de-duplication in
util.file_hash(), content-hash de-duplication in web/crawler.py).

This is NOT a new cryptographic design -- SHA-256 is a public, fully
specified algorithm (FIPS 180-4), and BrisartAI's use of it is entirely
non-adversarial (content fingerprinting and de-duplication, never
password/secret handling). Reimplementing a published, standardized
public algorithm in pure Python is a straightforward correctness
exercise, verifiable byte-for-byte against any other conforming
implementation -- it carries none of the risk of designing a NEW
cryptographic primitive from scratch (that risk profile belongs to
BSR2 in the Identity Tools project, a genuinely different situation).

Communication / relationships
------------------------------
- Intended as a drop-in replacement for hashlib.sha256(...).hexdigest()
  at every current call site (util.stable_hash(), util.file_hash(),
  web/crawler.py's content_exists() hashing).
- Imports nothing from elsewhere in brisart_ai; only stdlib struct-free
  pure-integer arithmetic (no external hash/crypto library at all).

Settings / parameters
----------------------
- _INITIAL_HASH: the eight 32-bit initial hash values (fractional parts
  of the square roots of the first 8 primes), fixed by the SHA-256
  specification -- not tunable, not a design choice.
- _ROUND_CONSTANTS: the 64 round constants (fractional parts of the
  cube roots of the first 64 primes), likewise fixed by spec.
- BrisartHash256.digest_size == 32, block_size == 64, matching
  hashlib's own attributes so any code introspecting a hash object's
  size keeps working unchanged.

Edge cases
----------
- Padding follows the spec exactly: a single 0x80 bit, then zero bits,
  then the original message length in bits as a 64-bit big-endian
  integer, padded so the total is a multiple of 512 bits (64 bytes).
  An empty message is a fully valid input (produces the well-known
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
  digest) and is exercised explicitly by this module's self-test.
- update() may be called multiple times before digest()/hexdigest();
  internal state (a running bytearray buffer plus the 8 running hash
  words) is carried across calls exactly like hashlib's streaming API.
- All 32-bit arithmetic is masked with `& 0xFFFFFFFF` after every
  addition, exactly matching modulo-2^32 addition -- Python integers
  are arbitrary precision, so this mask is REQUIRED, not optional
  defensive code.
"""
from __future__ import annotations

from typing import List

_INITIAL_HASH: List[int] = [
    0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A,
    0x510E527F, 0x9B05688C, 0x1F83D9AB, 0x5BE0CD19,
]

_ROUND_CONSTANTS: List[int] = [
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
    0xE49B69C1, 0xEFBE4786, 0x0FC19DC6, 0x240CA1CC,
    0x2DE92C6F, 0x4A7484AA, 0x5CB0A9DC, 0x76F988DA,
    0x983E5152, 0xA831C66D, 0xB00327C8, 0xBF597FC7,
    0xC6E00BF3, 0xD5A79147, 0x06CA6351, 0x14292967,
    0x27B70A85, 0x2E1B2138, 0x4D2C6DFC, 0x53380D13,
    0x650A7354, 0x766A0ABB, 0x81C2C92E, 0x92722C85,
    0xA2BFE8A1, 0xA81A664B, 0xC24B8B70, 0xC76C51A3,
    0xD192E819, 0xD6990624, 0xF40E3585, 0x106AA070,
    0x19A4C116, 0x1E376C08, 0x2748774C, 0x34B0BCB5,
    0x391C0CB3, 0x4ED8AA4A, 0x5B9CCA4F, 0x682E6FF3,
    0x748F82EE, 0x78A5636F, 0x84C87814, 0x8CC70208,
    0x90BEFFFA, 0xA4506CEB, 0xBEF9A3F7, 0xC67178F2,
]

_MASK32 = 0xFFFFFFFF


def _rotr(value: int, bits: int) -> int:
    """32-bit right rotate."""
    return ((value >> bits) | (value << (32 - bits))) & _MASK32


def _compress_chunk(state: List[int], chunk: bytes) -> None:
    """Process exactly one 64-byte (512-bit) chunk, updating `state` in place."""
    w = [0] * 64
    for i in range(16):
        w[i] = int.from_bytes(chunk[i * 4:i * 4 + 4], "big")
    for i in range(16, 64):
        s0 = _rotr(w[i - 15], 7) ^ _rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
        s1 = _rotr(w[i - 2], 17) ^ _rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) & _MASK32

    a, b, c, d, e, f, g, h = state
    for i in range(64):
        big_s1 = _rotr(e, 6) ^ _rotr(e, 11) ^ _rotr(e, 25)
        ch = (e & f) ^ ((~e) & g & _MASK32)
        temp1 = (h + big_s1 + ch + _ROUND_CONSTANTS[i] + w[i]) & _MASK32
        big_s0 = _rotr(a, 2) ^ _rotr(a, 13) ^ _rotr(a, 22)
        maj = (a & b) ^ (a & c) ^ (b & c)
        temp2 = (big_s0 + maj) & _MASK32

        h = g
        g = f
        f = e
        e = (d + temp1) & _MASK32
        d = c
        c = b
        b = a
        a = (temp1 + temp2) & _MASK32

    state[0] = (state[0] + a) & _MASK32
    state[1] = (state[1] + b) & _MASK32
    state[2] = (state[2] + c) & _MASK32
    state[3] = (state[3] + d) & _MASK32
    state[4] = (state[4] + e) & _MASK32
    state[5] = (state[5] + f) & _MASK32
    state[6] = (state[6] + g) & _MASK32
    state[7] = (state[7] + h) & _MASK32


class BrisartHash256:
    """From-spec pure-Python SHA-256, streaming-compatible with hashlib.sha256()."""

    digest_size = 32
    block_size = 64
    name = "brisart_sha256"

    def __init__(self, initial_data: bytes = b""):
        self._state: List[int] = list(_INITIAL_HASH)
        self._buffer = bytearray()
        self._total_length = 0
        if initial_data:
            self.update(initial_data)

    def update(self, data: bytes) -> "BrisartHash256":
        if isinstance(data, str):
            raise TypeError("update() requires bytes, not str")
        self._total_length += len(data)
        self._buffer.extend(data)
        while len(self._buffer) >= 64:
            _compress_chunk(self._state, bytes(self._buffer[:64]))
            del self._buffer[:64]
        return self

    def _padded_final_state(self) -> List[int]:
        """Return the finished 8-word state after applying spec padding, without mutating self."""
        state = list(self._state)
        buffer = bytearray(self._buffer)
        bit_length = self._total_length * 8

        buffer.append(0x80)
        while (len(buffer) % 64) != 56:
            buffer.append(0x00)
        buffer.extend(bit_length.to_bytes(8, "big"))

        for offset in range(0, len(buffer), 64):
            _compress_chunk(state, bytes(buffer[offset:offset + 64]))
        return state

    def digest(self) -> bytes:
        state = self._padded_final_state()
        return b"".join(word.to_bytes(4, "big") for word in state)

    def hexdigest(self) -> str:
        return self.digest().hex()

    def copy(self) -> "BrisartHash256":
        clone = BrisartHash256()
        clone._state = list(self._state)
        clone._buffer = bytearray(self._buffer)
        clone._total_length = self._total_length
        return clone


def brisart_sha256(data: bytes) -> BrisartHash256:
    """Convenience constructor mirroring hashlib.sha256(data)."""
    return BrisartHash256(data)


def brisart_stable_hash(value: str) -> str:
    """Drop-in replacement for util.stable_hash(): hex digest of a string."""
    return brisart_sha256(value.encode("utf-8", "replace")).hexdigest()


def _self_test() -> None:
    """Verify against the standard published SHA-256 test vectors (FIPS 180-4 examples)."""
    assert brisart_sha256(b"").hexdigest() == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert brisart_sha256(b"abc").hexdigest() == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert brisart_sha256(
        b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    ).hexdigest() == (
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
    )


if __name__ == "__main__":
    _self_test()
    print("BrisartHash256 internal self-test passed.")


__all__ = ["BrisartHash256", "brisart_sha256", "brisart_stable_hash"]
