"""
File: brisart_ai/native/brisart_inflate.py

Purpose
-------
BrisartInflate -- a from-spec, pure-Python DEFLATE decompressor
(RFC 1951) plus a zlib-stream wrapper (RFC 1950), replacing
zlib.decompress() -- currently used in io/binary_readers.py's
read_pdf_best_effort() to decompress a PDF's `stream...endstream`
content blocks, which are essentially always zlib/DEFLATE-compressed.

This is the single most involved module in the Brisart native stack:
DEFLATE combines a sliding-window LZ77 back-reference scheme with
canonical Huffman coding, and getting the bit-order conventions wrong
in either direction is the single easiest way to silently produce
garbage output instead of a clean failure. RFC 1951 section 3.1.1 is
followed exactly on this point: ordinary multi-bit fields (LEN/NLEN,
extra length/distance bits, the HLIT/HDIST/HCLEN counts) are packed
LEAST-significant-bit first, but a Huffman CODE itself is packed
MOST-significant-bit first -- meaning code bits are read one at a time
from the same LSB-first bit source and accumulated as
`code = (code << 1) | bit`, the opposite direction from every other
field in the format. BrisartBitReader below is the single place this
distinction is implemented, so every other function in this module can
just call read_bits() or read_huffman_symbol() without re-deriving it.

Communication / relationships
------------------------------
- Intended as a drop-in replacement for zlib.decompress(data) at
  io/binary_readers.py's PDF stream-decompression call site.
- Imports nothing from elsewhere in brisart_ai; pure integer/byte
  arithmetic, no dependency on zlib, gzip, or any compression library.

Settings / parameters
----------------------
- _FIXED_LITERAL_LENGTHS / _FIXED_DISTANCE_LENGTHS: the fixed Huffman
  code-length tables defined directly by RFC 1951 section 3.2.6 (used
  for DEFLATE block type 1, "fixed Huffman codes") -- not tunable.
- _LENGTH_BASE / _LENGTH_EXTRA_BITS and _DISTANCE_BASE /
  _DISTANCE_EXTRA_BITS: the standard length/distance code tables from
  RFC 1951 section 3.2.5, fixed by the format specification.
- _CODE_LENGTH_ORDER: the specific, non-obvious transmission order for
  the 19-entry code-length alphabet used to decode a dynamic Huffman
  block's own Huffman tables (RFC 1951 section 3.2.7) -- getting this
  order wrong silently corrupts every dynamic block.
- brisart_zlib_decompress(data, verify_checksum=True): wraps
  brisart_inflate() with the 2-byte zlib header (RFC 1950) and,
  optionally, verifies the trailing 4-byte big-endian Adler-32
  checksum via brisart_adler32() below.

Edge cases
----------
- Overlapping LZ77 back-references (distance < length, e.g. "copy 20
  bytes starting 3 bytes back") are copied ONE BYTE AT A TIME rather
  than via a bulk slice, because Python's bytearray slicing of
  `out[-distance:]` would not correctly reproduce the run-length
  self-overlapping pattern DEFLATE relies on for compressing repeated
  short sequences.
- A canonical Huffman decode that exhausts all lengths up to 15 bits
  without finding a matching code raises ValueError rather than
  looping forever or silently returning a wrong symbol.
- brisart_zlib_decompress() checks the zlib header's FDICT flag and
  raises NotImplementedError if a preset dictionary is signaled, since
  BrisartAI's own PDF-decompression use case never produces one and
  silently ignoring it would risk a wrong (rather than a failing)
  decompression.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


class BrisartBitReader:
    """Reads a DEFLATE bitstream: LSB-first for ordinary fields, MSB-first
    accumulation for Huffman codes (see module docstring)."""

    def __init__(self, data: bytes):
        self._data = data
        self._byte_pos = 0
        self._bit_pos = 0

    def read_bit(self) -> int:
        if self._byte_pos >= len(self._data):
            raise ValueError("unexpected end of DEFLATE stream")
        byte = self._data[self._byte_pos]
        bit = (byte >> self._bit_pos) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bit_pos = 0
            self._byte_pos += 1
        return bit

    def read_bits(self, count: int) -> int:
        """Ordinary multi-bit field: LSB-first (first bit read = value's bit 0)."""
        value = 0
        for i in range(count):
            value |= self.read_bit() << i
        return value

    def align_to_byte(self) -> None:
        if self._bit_pos != 0:
            self._bit_pos = 0
            self._byte_pos += 1

    def read_raw_bytes(self, count: int) -> bytes:
        """Only valid immediately after align_to_byte()."""
        chunk = self._data[self._byte_pos:self._byte_pos + count]
        self._byte_pos += count
        return chunk

    def read_huffman_symbol(self, table: Dict[Tuple[int, int], int]) -> int:
        """MSB-first code accumulation, per RFC 1951 section 3.1.1."""
        code = 0
        for length in range(1, 16):
            code = (code << 1) | self.read_bit()
            symbol = table.get((length, code))
            if symbol is not None:
                return symbol
        raise ValueError("no matching Huffman code found (corrupt stream)")


def _build_huffman_table(code_lengths: List[int]) -> Dict[Tuple[int, int], int]:
    """Build a {(bit_length, code): symbol} table from per-symbol code lengths."""
    if not code_lengths:
        return {}
    max_length = max(code_lengths) if code_lengths else 0
    bit_length_count = [0] * (max_length + 1)
    for length in code_lengths:
        if length > 0:
            bit_length_count[length] += 1

    next_code = [0] * (max_length + 2)
    code = 0
    bit_length_count[0] = 0
    for bits in range(1, max_length + 1):
        code = (code + bit_length_count[bits - 1]) << 1
        next_code[bits] = code

    table: Dict[Tuple[int, int], int] = {}
    for symbol, length in enumerate(code_lengths):
        if length == 0:
            continue
        table[(length, next_code[length])] = symbol
        next_code[length] += 1
    return table


def _fixed_literal_length_table() -> Dict[Tuple[int, int], int]:
    lengths = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
    assert len(lengths) == 288
    return _build_huffman_table(lengths)


def _fixed_distance_table() -> Dict[Tuple[int, int], int]:
    lengths = [5] * 32
    return _build_huffman_table(lengths)


_FIXED_LITERAL_TABLE = _fixed_literal_length_table()
_FIXED_DISTANCE_TABLE = _fixed_distance_table()

_LENGTH_BASE = [
    3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
    35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258,
]
_LENGTH_EXTRA_BITS = [
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
    3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0,
]
_DISTANCE_BASE = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
    257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
    8193, 12289, 16385, 24577,
]
_DISTANCE_EXTRA_BITS = [
    0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
    7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13,
]

_CODE_LENGTH_ORDER = [
    16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15,
]


def _read_dynamic_tables(reader: BrisartBitReader):
    """Read a dynamic Huffman block's header and build its two symbol tables."""
    literal_count = reader.read_bits(5) + 257
    distance_count = reader.read_bits(5) + 1
    code_length_count = reader.read_bits(4) + 4

    code_length_lengths = [0] * 19
    for i in range(code_length_count):
        code_length_lengths[_CODE_LENGTH_ORDER[i]] = reader.read_bits(3)
    code_length_table = _build_huffman_table(code_length_lengths)

    all_lengths: List[int] = []
    while len(all_lengths) < literal_count + distance_count:
        symbol = reader.read_huffman_symbol(code_length_table)
        if symbol <= 15:
            all_lengths.append(symbol)
        elif symbol == 16:
            repeat_count = reader.read_bits(2) + 3
            previous = all_lengths[-1] if all_lengths else 0
            all_lengths.extend([previous] * repeat_count)
        elif symbol == 17:
            repeat_count = reader.read_bits(3) + 3
            all_lengths.extend([0] * repeat_count)
        elif symbol == 18:
            repeat_count = reader.read_bits(7) + 11
            all_lengths.extend([0] * repeat_count)
        else:
            raise ValueError(f"invalid code-length symbol: {symbol}")

    literal_lengths = all_lengths[:literal_count]
    distance_lengths = all_lengths[literal_count:literal_count + distance_count]
    return _build_huffman_table(literal_lengths), _build_huffman_table(distance_lengths)


def _inflate_block(
    reader: BrisartBitReader,
    output: bytearray,
    literal_table: Dict[Tuple[int, int], int],
    distance_table: Dict[Tuple[int, int], int],
) -> None:
    """Decode one Huffman-coded block's symbols until the end-of-block marker (256)."""
    while True:
        symbol = reader.read_huffman_symbol(literal_table)
        if symbol < 256:
            output.append(symbol)
        elif symbol == 256:
            return
        else:
            length_index = symbol - 257
            if length_index >= len(_LENGTH_BASE):
                raise ValueError(f"invalid length symbol: {symbol}")
            extra_bits = _LENGTH_EXTRA_BITS[length_index]
            length = _LENGTH_BASE[length_index] + (
                reader.read_bits(extra_bits) if extra_bits else 0
            )

            distance_symbol = reader.read_huffman_symbol(distance_table)
            if distance_symbol >= len(_DISTANCE_BASE):
                raise ValueError(f"invalid distance symbol: {distance_symbol}")
            extra_bits = _DISTANCE_EXTRA_BITS[distance_symbol]
            distance = _DISTANCE_BASE[distance_symbol] + (
                reader.read_bits(extra_bits) if extra_bits else 0
            )

            if distance > len(output):
                raise ValueError("back-reference distance exceeds output so far")

            start = len(output) - distance
            for i in range(length):
                output.append(output[start + i])


def brisart_inflate(data: bytes) -> bytes:
    """Decompress a raw DEFLATE stream (RFC 1951; no zlib/gzip framing)."""
    reader = BrisartBitReader(data)
    output = bytearray()

    while True:
        is_final = reader.read_bits(1)
        block_type = reader.read_bits(2)

        if block_type == 0:
            reader.align_to_byte()
            length = int.from_bytes(reader.read_raw_bytes(2), "little")
            _one_complement_length = int.from_bytes(reader.read_raw_bytes(2), "little")
            output.extend(reader.read_raw_bytes(length))
        elif block_type == 1:
            _inflate_block(reader, output, _FIXED_LITERAL_TABLE, _FIXED_DISTANCE_TABLE)
        elif block_type == 2:
            literal_table, distance_table = _read_dynamic_tables(reader)
            _inflate_block(reader, output, literal_table, distance_table)
        else:
            raise ValueError("invalid DEFLATE block type (3, reserved)")

        if is_final:
            break

    return bytes(output)


_ADLER32_MODULO = 65521


def brisart_adler32(data: bytes, seed: int = 1) -> int:
    a = seed & 0xFFFF
    b = (seed >> 16) & 0xFFFF
    chunk_size = 5552
    for offset in range(0, len(data), chunk_size):
        for byte in data[offset:offset + chunk_size]:
            a += byte
            b += a
        a %= _ADLER32_MODULO
        b %= _ADLER32_MODULO
    return (b << 16) | a


def brisart_zlib_decompress(data: bytes, verify_checksum: bool = True) -> bytes:
    """Decompress a full zlib stream (RFC 1950: 2-byte header + DEFLATE + Adler-32)."""
    if len(data) < 6:
        raise ValueError("input too short to be a valid zlib stream")

    compression_method_and_flags = data[0]
    flags_byte = data[1]

    compression_method = compression_method_and_flags & 0x0F
    if compression_method != 8:
        raise ValueError(f"unsupported zlib compression method: {compression_method}")

    header_check = (compression_method_and_flags * 256 + flags_byte) % 31
    if header_check != 0:
        raise ValueError("invalid zlib header checksum")

    has_preset_dictionary = bool(flags_byte & 0x20)
    if has_preset_dictionary:
        raise NotImplementedError(
            "zlib stream signals a preset dictionary (FDICT); "
            "not needed for BrisartAI's PDF-decompression use case"
        )

    deflate_payload = data[2:-4]
    trailing_checksum = int.from_bytes(data[-4:], "big")

    decompressed = brisart_inflate(deflate_payload)

    if verify_checksum:
        computed = brisart_adler32(decompressed)
        if computed != trailing_checksum:
            raise ValueError(
                f"Adler-32 checksum mismatch: expected {trailing_checksum:#010x}, "
                f"computed {computed:#010x}"
            )

    return decompressed


def _self_test() -> None:
    """Minimal smoke test using a hand-built stored (uncompressed) DEFLATE block."""
    payload = b"Brisart"
    header_byte = 0b00000001
    length = len(payload)
    nlen = (~length) & 0xFFFF
    stream = bytes([header_byte]) + length.to_bytes(2, "little") + nlen.to_bytes(2, "little") + payload
    assert brisart_inflate(stream) == payload


if __name__ == "__main__":
    _self_test()
    print("BrisartInflate internal self-test passed.")


__all__ = [
    "BrisartBitReader",
    "brisart_adler32",
    "brisart_inflate",
    "brisart_zlib_decompress",
]
