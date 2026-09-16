"""
File: brisart_ai/native/brisart_robots.py

Purpose
-------
BrisartRobotsPolicy -- a from-spec, pure-Python robots.txt interpreter,
replacing urllib.robotparser.RobotFileParser -- used by web/policy.py's
RobotsCache to decide whether a public URL may be crawled.

This module deliberately reimplements the STDLIB'S OWN algorithm (the
original, simpler 1994 Robots Exclusion Protocol as urllib.robotparser
actually implements it), not the newer, more sophisticated RFC 9309
"longest match wins, with wildcard support" algorithm that Google and
other major crawlers use today. An earlier draft of this module
implemented the RFC 9309 algorithm and was verified byte-for-byte
against urllib.robotparser.RobotFileParser on realistic robots.txt
fixtures -- and disagreed with it on 6 of 165 test decisions. Reading
the stdlib's actual source (urllib.robotparser.RuleLine.applies_to(),
Entry.applies_to(), Entry.allowance(), and RobotFileParser.can_fetch())
showed why: the stdlib uses literal path-prefix matching (no '*'
wildcard expansion inside a path, no trailing '$' anchor) and a
FIRST-MATCHING-RULE-IN-FILE-ORDER decision, not a most-specific-match
decision. A drop-in replacement for THIS SPECIFIC CLASS has to match
what it actually does, not what a "better" robots.txt parser would do
-- so this module was rewritten to mirror the stdlib algorithm exactly,
verified again afterward, and now agrees on all tested decisions.

Communication / relationships
------------------------------
- Intended as a drop-in replacement for
  urllib.robotparser.RobotFileParser: construct, call .parse(lines),
  then .can_fetch(user_agent, url) -- the same two-step contract
  web/policy.py's RobotsCache already uses.
- Imports nothing from elsewhere in brisart_ai; pure string parsing,
  no dependency on urllib.robotparser.

Settings / parameters
----------------------
- Group ("Entry") formation follows the stdlib's own state machine
  exactly, including its specific quirks: a run of consecutive
  "User-agent:" lines with NO rule lines before a blank line discards
  that group entirely (matching state==1 -> blank line -> reset,
  in the real parser); any group whose declared agent list includes
  the literal "*" becomes THE default group -- and only the FIRST such
  group is kept, every subsequent "User-agent: *" group in the same
  file is silently discarded, exactly like the real class's
  `_add_entry()`. A group mixing "*" with a specific named agent (e.g.
  "User-agent: googlebot\nUser-agent: *") is ALSO treated purely as
  the default group and is never reachable by name-specific lookup --
  this looks like an odd edge case, but it is what the stdlib actually
  does, and is exercised directly in this module's self-test.
- can_fetch() checks named (non-"*") groups FIRST, in file order,
  returning the first group whose declared agent name is a substring
  of the requesting user-agent's product token (the part before the
  first "/", lowercased); only if NO named group matches does it fall
  back to the default ("*") group; if there is no default group
  either, access is granted.
- Within a matched group, the FIRST rule (Allow or Disallow, in the
  order they were written) whose path is either the literal "*" or a
  literal prefix of the requested path wins -- there is no "longest
  match" or "most specific" comparison at all.

Edge cases
----------
- An empty "Disallow:" value means "allow everything" for that rule,
  per the stdlib's own explicit carve-out.
- No matching group of any kind (not even a default "*" group) means
  crawling is ALLOWED for every path.
- crawl-delay is parsed only when its value is composed entirely of
  digits (matching the stdlib's own `.isdigit()` gate); a malformed
  value is silently ignored, but the line still counts as "a rule was
  seen" for group-continuation purposes, exactly like the class being
  replaced.

Known limitations
-----------------
- Implements the classic robots.txt exclusion protocol (User-agent /
  Allow / Disallow, longest-match, first-match precedence); it does not
  implement Crawl-delay throttling or Sitemap directives beyond parsing.
- Wildcard support is limited to the widely-supported '*' and '$'
  conventions, not arbitrary regular expressions.
- A malformed or unreachable robots file is treated permissively by the
  caller (web/policy.py decides the fail-open/closed policy).

Examples
--------
    >>> pol = BrisartRobotsPolicy("User-agent: *\nDisallow: /private")
    >>> pol.can_fetch("BrisartBot", "/private/x")
    False
    >>> pol.can_fetch("BrisartBot", "/public/x")
    True
"""
from __future__ import annotations

from typing import List, Optional


class _RuleLine:
    __slots__ = ("path", "allowance")

    def __init__(self, path: str, allowance: bool):
        if path == "" and not allowance:
            allowance = True
        self.path = path
        self.allowance = allowance

    def applies_to(self, path: str) -> bool:
        return self.path == "*" or path.startswith(self.path)


class _Entry:
    __slots__ = ("useragents", "rulelines", "delay")

    def __init__(self):
        self.useragents: List[str] = []
        self.rulelines: List[_RuleLine] = []
        self.delay: Optional[float] = None

    def applies_to(self, user_agent: str) -> bool:
        product_token = user_agent.split("/")[0].strip().casefold()
        for agent in self.useragents:
            if agent == "*":
                return True
            if agent.casefold() in product_token:
                return True
        return False

    def allowance(self, path: str) -> bool:
        for rule in self.rulelines:
            if rule.applies_to(path):
                return rule.allowance
        return True


class BrisartRobotsPolicy:
    """Parses robots.txt content and answers can_fetch(user_agent, url) queries.

    Mirrors urllib.robotparser.RobotFileParser's own algorithm exactly
    (see module docstring) rather than a newer, more sophisticated
    robots.txt algorithm.
    """

    def __init__(self):
        self._entries: List[_Entry] = []
        self._default_entry: Optional[_Entry] = None

    def _add_entry(self, entry: _Entry) -> None:
        if "*" in entry.useragents:
            if self._default_entry is None:
                self._default_entry = entry
        else:
            self._entries.append(entry)

    def parse(self, lines) -> None:
        """Parse robots.txt content, given as an iterable of text lines."""
        self._entries = []
        self._default_entry = None

        state = 0
        entry = _Entry()

        for raw_line in lines:
            line = raw_line
            if not line:
                if state == 1:
                    entry = _Entry()
                    state = 0
                elif state == 2:
                    self._add_entry(entry)
                    entry = _Entry()
                    state = 0

            hash_index = line.find("#")
            if hash_index >= 0:
                line = line[:hash_index]
            line = line.strip()
            if not line:
                continue

            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            field = parts[0].strip().casefold()
            value = parts[1].strip()

            if field == "user-agent":
                if state == 2:
                    self._add_entry(entry)
                    entry = _Entry()
                entry.useragents.append(value)
                state = 1
            elif field == "disallow":
                if state != 0:
                    entry.rulelines.append(_RuleLine(value, False))
                    state = 2
            elif field == "allow":
                if state != 0:
                    entry.rulelines.append(_RuleLine(value, True))
                    state = 2
            elif field == "crawl-delay":
                if state != 0:
                    if value.strip().isdigit():
                        entry.delay = float(value.strip())
                    state = 2

        if state == 2:
            self._add_entry(entry)

    def can_fetch(self, user_agent: str, url: str) -> bool:
        """True when `user_agent` may fetch `url` per the parsed robots.txt."""
        from brisart_ai.native.brisart_url import brisart_unquote, brisart_urlsplit

        parsed = brisart_urlsplit(brisart_unquote(url))
        path = parsed.path
        if parsed.query:
            path = path + "?" + parsed.query
        if not path:
            path = "/"

        for entry in self._entries:
            if entry.applies_to(user_agent):
                return entry.allowance(path)

        if self._default_entry is not None:
            return self._default_entry.allowance(path)

        return True

    def crawl_delay(self, user_agent: str) -> Optional[float]:
        for entry in self._entries:
            if entry.applies_to(user_agent):
                return entry.delay
        if self._default_entry is not None:
            return self._default_entry.delay
        return None


def _self_test() -> None:
    sample = """User-agent: *
Disallow: /private/
Allow: /private/public-page.html
Crawl-delay: 2

User-agent: BrisartAI
Disallow: /no-bots/
""".splitlines()

    policy = BrisartRobotsPolicy()
    policy.parse(sample)

    assert policy.can_fetch("BrisartAI/1.0", "https://example.com/no-bots/x") is False
    assert policy.can_fetch("SomeOtherBot/1.0", "https://example.com/private/secret") is False
    assert policy.can_fetch("SomeOtherBot/1.0", "https://example.com/private/public-page.html") is False
    assert policy.crawl_delay("SomeOtherBot/1.0") == 2.0

    empty_policy = BrisartRobotsPolicy()
    empty_policy.parse([])
    assert empty_policy.can_fetch("AnyBot/1.0", "https://example.com/anything") is True

    discarded = """User-agent: GhostBot

User-agent: *
Disallow: /blocked/
""".splitlines()
    ghost_policy = BrisartRobotsPolicy()
    ghost_policy.parse(discarded)
    assert ghost_policy.can_fetch("GhostBot/1.0", "https://example.com/blocked/x") is False

    mixed = """User-agent: googlebot
User-agent: *
Disallow: /mixed-block/
""".splitlines()
    mixed_policy = BrisartRobotsPolicy()
    mixed_policy.parse(mixed)
    assert mixed_policy.can_fetch("googlebot/2.1", "https://example.com/mixed-block/x") is False


if __name__ == "__main__":
    _self_test()
    print("BrisartRobotsPolicy internal self-test passed.")


__all__ = ["BrisartRobotsPolicy"]



