"""
File: brisart_ai/native/brisart_json.py

Purpose
-------
BrisartJSON -- a from-spec, pure-Python JSON parser and serializer
(RFC 8259), replacing the json module -- used in core/settings.py
(research_settings.json persistence), io/readers.py (pretty-printing
.json/.jsonl files for ingestion), and web/search.py (parsing the
Wikipedia API's JSON search response).

Communication / relationships
------------------------------
- Intended as a drop-in replacement for json.loads()/json.dumps() at
  every current call site.
- Imports nothing from elsewhere in brisart_ai; a hand-written
  recursive-descent parser and serializer, no dependency on the json
  module itself.

Settings / parameters
----------------------
- brisart_dumps(value, indent=None, sort_keys=False): matches the
  json module's own keyword names and defaults closely enough that
  call sites (core/settings.py's json.dumps(self.values, indent=2,
  sort_keys=True)) can switch by changing only the import.
- _ESCAPE_MAP: the required-escape output table (", \\, and control
  characters below 0x20) used by the serializer; every other character
  is passed straight through and re-encoded as UTF-8 at the end, so
  BrisartAI's own non-ASCII content (a source title copied verbatim
  from a web page, for instance) round-trips correctly without forcing
  an ensure_ascii-style \\uXXXX escape.

Edge cases
----------
- brisart_loads() raises BrisartJSONDecodeError (a thin ValueError
  subclass) with a human-readable "at position N" marker on malformed
  input, mirroring json.JSONDecodeError's role as a catchable, specific
  exception type rather than a bare ValueError or a silent None return.
- Duplicate object keys follow "last one wins", matching the json
  module's own documented behavior for duplicate keys in an object.
- A bare NaN/Infinity/-Infinity token is accepted on parse (Python's
  json module accepts these by default, and Wikipedia's or any other
  real-world API response could in principle include one) but is
  never emitted by brisart_dumps() for an ordinary float, since valid
  JSON text has no literal representation for them.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

JSONValue = Union[None, bool, int, float, str, List[Any], Dict[str, Any]]


class BrisartJSONDecodeError(ValueError):
    """Raised for malformed JSON input, mirroring json.JSONDecodeError's role."""

    def __init__(self, message: str, text: str, position: int):
        line = text.count("\n", 0, position) + 1
        column = position - text.rfind("\n", 0, position)
        super().__init__(f"{message}: line {line} column {column} (char {position})")
        self.position = position


_WHITESPACE = " \t\n\r"
_ESCAPE_DECODE = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b",
    "f": "\f", "n": "\n", "r": "\r", "t": "\t",
}
_ESCAPE_ENCODE = {
    '"': '\\"', "\\": "\\\\", "\b": "\\b",
    "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t",
}


class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.pos = 0

    def _skip_whitespace(self) -> None:
        while self.pos < self.length and self.text[self.pos] in _WHITESPACE:
            self.pos += 1

    def _error(self, message: str) -> BrisartJSONDecodeError:
        return BrisartJSONDecodeError(message, self.text, self.pos)

    def parse(self) -> JSONValue:
        self._skip_whitespace()
        value = self._parse_value()
        self._skip_whitespace()
        if self.pos != self.length:
            raise self._error("Extra data after valid JSON value")
        return value

    def _parse_value(self) -> JSONValue:
        self._skip_whitespace()
        if self.pos >= self.length:
            raise self._error("Expecting value")
        char = self.text[self.pos]
        if char == '"':
            return self._parse_string()
        if char == "{":
            return self._parse_object()
        if char == "[":
            return self._parse_array()
        if char == "t" and self.text[self.pos:self.pos + 4] == "true":
            self.pos += 4
            return True
        if char == "f" and self.text[self.pos:self.pos + 5] == "false":
            self.pos += 5
            return False
        if char == "n" and self.text[self.pos:self.pos + 4] == "null":
            self.pos += 4
            return None
        if char == "N" and self.text[self.pos:self.pos + 3] == "NaN":
            self.pos += 3
            return float("nan")
        if char == "I" and self.text[self.pos:self.pos + 8] == "Infinity":
            self.pos += 8
            return float("inf")
        if char == "-" and self.text[self.pos:self.pos + 9] == "-Infinity":
            self.pos += 9
            return float("-inf")
        if char == "-" or char.isdigit():
            return self._parse_number()
        raise self._error(f"Expecting value, found {char!r}")

    def _parse_string(self) -> str:
        assert self.text[self.pos] == '"'
        self.pos += 1
        start = self.pos
        pieces: List[str] = []
        while True:
            if self.pos >= self.length:
                raise self._error("Unterminated string")
            char = self.text[self.pos]
            if char == '"':
                pieces.append(self.text[start:self.pos])
                self.pos += 1
                return "".join(pieces)
            if char == "\\":
                pieces.append(self.text[start:self.pos])
                self.pos += 1
                if self.pos >= self.length:
                    raise self._error("Unterminated escape sequence")
                escape_char = self.text[self.pos]
                if escape_char == "u":
                    hex_digits = self.text[self.pos + 1:self.pos + 5]
                    if len(hex_digits) != 4:
                        raise self._error("Invalid \\u escape")
                    code_point = int(hex_digits, 16)
                    self.pos += 5
                    if 0xD800 <= code_point <= 0xDBFF and self.text[self.pos:self.pos + 2] == "\\u":
                        low_hex = self.text[self.pos + 2:self.pos + 6]
                        if len(low_hex) == 4:
                            low = int(low_hex, 16)
                            if 0xDC00 <= low <= 0xDFFF:
                                combined = 0x10000 + (code_point - 0xD800) * 0x400 + (low - 0xDC00)
                                pieces.append(chr(combined))
                                self.pos += 6
                                start = self.pos
                                continue
                    pieces.append(chr(code_point))
                    start = self.pos
                    continue
                if escape_char in _ESCAPE_DECODE:
                    pieces.append(_ESCAPE_DECODE[escape_char])
                    self.pos += 1
                    start = self.pos
                    continue
                raise self._error(f"Invalid escape character: \\{escape_char}")
            if ord(char) < 0x20:
                raise self._error("Invalid control character in string")
            self.pos += 1

    def _parse_number(self) -> Union[int, float]:
        start = self.pos
        if self.text[self.pos] == "-":
            self.pos += 1
        while self.pos < self.length and self.text[self.pos].isdigit():
            self.pos += 1
        is_float = False
        if self.pos < self.length and self.text[self.pos] == ".":
            is_float = True
            self.pos += 1
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
        if self.pos < self.length and self.text[self.pos] in "eE":
            is_float = True
            self.pos += 1
            if self.pos < self.length and self.text[self.pos] in "+-":
                self.pos += 1
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
        raw = self.text[start:self.pos]
        if not raw or raw == "-":
            raise self._error("Invalid number")
        return float(raw) if is_float else int(raw)

    def _parse_object(self) -> Dict[str, JSONValue]:
        assert self.text[self.pos] == "{"
        self.pos += 1
        result: Dict[str, JSONValue] = {}
        self._skip_whitespace()
        if self.pos < self.length and self.text[self.pos] == "}":
            self.pos += 1
            return result
        while True:
            self._skip_whitespace()
            if self.pos >= self.length or self.text[self.pos] != '"':
                raise self._error("Expecting property name enclosed in double quotes")
            key = self._parse_string()
            self._skip_whitespace()
            if self.pos >= self.length or self.text[self.pos] != ":":
                raise self._error("Expecting ':' delimiter")
            self.pos += 1
            value = self._parse_value()
            result[key] = value
            self._skip_whitespace()
            if self.pos >= self.length:
                raise self._error("Unterminated object")
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.text[self.pos] == "}":
                self.pos += 1
                return result
            raise self._error("Expecting ',' or '}'")

    def _parse_array(self) -> List[JSONValue]:
        assert self.text[self.pos] == "["
        self.pos += 1
        result: List[JSONValue] = []
        self._skip_whitespace()
        if self.pos < self.length and self.text[self.pos] == "]":
            self.pos += 1
            return result
        while True:
            value = self._parse_value()
            result.append(value)
            self._skip_whitespace()
            if self.pos >= self.length:
                raise self._error("Unterminated array")
            if self.text[self.pos] == ",":
                self.pos += 1
                continue
            if self.text[self.pos] == "]":
                self.pos += 1
                return result
            raise self._error("Expecting ',' or ']'")


def brisart_loads(text: str) -> JSONValue:
    """Parse a JSON document into Python values."""
    return _Parser(text).parse()


def _encode_string(value: str) -> str:
    pieces = ['"']
    for char in value:
        if char in _ESCAPE_ENCODE:
            pieces.append(_ESCAPE_ENCODE[char])
        elif ord(char) < 0x20:
            pieces.append(f"\\u{ord(char):04x}")
        else:
            pieces.append(char)
    pieces.append('"')
    return "".join(pieces)


def _encode_value(value: JSONValue, indent, sort_keys: bool, level: int) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _encode_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "NaN"
        if value == float("inf"):
            return "Infinity"
        if value == float("-inf"):
            return "-Infinity"
        return repr(value)
    if isinstance(value, (list, tuple)):
        return _encode_array(value, indent, sort_keys, level)
    if isinstance(value, dict):
        return _encode_object(value, indent, sort_keys, level)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _encode_array(items, indent, sort_keys: bool, level: int) -> str:
    if not items:
        return "[]"
    if indent is None:
        return "[" + ", ".join(_encode_value(item, indent, sort_keys, level) for item in items) + "]"
    pad = " " * (indent * (level + 1))
    closing_pad = " " * (indent * level)
    body = (",\n" + pad).join(_encode_value(item, indent, sort_keys, level + 1) for item in items)
    return "[\n" + pad + body + "\n" + closing_pad + "]"


def _encode_object(obj: Dict[str, Any], indent, sort_keys: bool, level: int) -> str:
    if not obj:
        return "{}"
    keys = sorted(obj.keys()) if sort_keys else list(obj.keys())
    if indent is None:
        body = ", ".join(
            f"{_encode_string(str(key))}: {_encode_value(obj[key], indent, sort_keys, level)}"
            for key in keys
        )
        return "{" + body + "}"
    pad = " " * (indent * (level + 1))
    closing_pad = " " * (indent * level)
    body = (",\n" + pad).join(
        f"{_encode_string(str(key))}: {_encode_value(obj[key], indent, sort_keys, level + 1)}"
        for key in keys
    )
    return "{\n" + pad + body + "\n" + closing_pad + "}"


def brisart_dumps(value: JSONValue, indent=None, sort_keys: bool = False) -> str:
    """Serialize a Python value to a JSON string."""
    return _encode_value(value, indent, sort_keys, 0)


def _self_test() -> None:
    assert brisart_loads("null") is None
    assert brisart_loads("true") is True
    assert brisart_loads("false") is False
    assert brisart_loads("42") == 42
    assert brisart_loads("3.14") == 3.14
    assert brisart_loads('"hello\\nworld"') == "hello\nworld"
    assert brisart_loads("[1, 2, 3]") == [1, 2, 3]
    assert brisart_loads('{"a": 1, "b": [2, 3]}') == {"a": 1, "b": [2, 3]}
    assert brisart_loads('"\\u00e9"') == "\u00e9"

    assert brisart_dumps(None) == "null"
    assert brisart_dumps({"b": 1, "a": 2}, sort_keys=True) == '{"a": 2, "b": 1}'
    round_tripped = brisart_loads(brisart_dumps({"x": [1, 2, {"y": "z"}]}))
    assert round_tripped == {"x": [1, 2, {"y": "z"}]}


if __name__ == "__main__":
    _self_test()
    print("BrisartJSON internal self-test passed.")


__all__ = ["BrisartJSONDecodeError", "brisart_dumps", "brisart_loads"]
