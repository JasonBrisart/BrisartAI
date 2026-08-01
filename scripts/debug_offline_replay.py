#!/usr/bin/env python3
"""Offline retrieval replay: rank imported-document chunks with no network.

Why this exists
---------------
``debug_search_replay.py`` covers public web search, which means every run
depends on whatever DuckDuckGo and Bing feel like returning that minute.
That made a real bug hard to see: providers under rate-limiting return
well-formed HTML for an unrelated query, so "who invented the transistor"
came back as airline booking pages. Ranking work cannot be evaluated on a
moving target.

This script removes the network entirely. It builds a temporary SQLite
index from in-file text fixtures, runs the real
:func:`brisart_ai.knowledge.ranker.search`, and prints the intent, score
and reason for every candidate. The fixtures are throwaway: the database
goes in a temp directory and is deleted on exit. No production data is
touched and nothing is written to the repository.

Usage::

    python3 scripts/debug_offline_replay.py            # all fixtures
    python3 scripts/debug_offline_replay.py microsoft  # one fixture
    python3 scripts/debug_offline_replay.py --list

Exit status is non-zero when a fixture's expected top chunk does not win,
so this doubles as a regression check for the intent ranking.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from typing import Dict, List, Sequence, Tuple

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from brisart_ai.intent import describe_intent, detect_intent  # noqa: E402
from brisart_ai.knowledge.index import Index  # noqa: E402
from brisart_ai.knowledge.ranker import search  # noqa: E402

# Each fixture is (name, query, expected_top_title, chunks) where chunks
# are (title, text). Text is deliberately plain prose: these stand in for
# imported .txt/.md/.pdf content, so nothing here should depend on markup.
Fixture = Tuple[str, str, str, List[Tuple[str, str]]]

FIXTURES: List[Fixture] = [
    (
        "microsoft",
        "who invented microsoft?",
        "History of Microsoft",
        [
            (
                "Microsoft PowerPoint",
                "Microsoft PowerPoint is a presentation program. Slides "
                "can include text, images and charts. PowerPoint is part "
                "of the Microsoft Office suite and is available for "
                "Windows and macOS. Use the ribbon to change slide "
                "layout, apply a theme, or start a slideshow.",
            ),
            (
                "Outlook.com and your Microsoft account",
                "Sign in to Outlook.com with your Microsoft account. If "
                "you forgot your password, use the account recovery page "
                "to reset it. You can manage your subscription, update "
                "billing details, and change your login preferences from "
                "the account dashboard.",
            ),
            (
                "History of Microsoft",
                "Microsoft was founded by Bill Gates and Paul Allen on "
                "April 4, 1975, in Albuquerque, New Mexico. The two "
                "co-founders had previously written a BASIC interpreter "
                "for the Altair 8800. The company moved to Bellevue, "
                "Washington in 1979 and later became a corporation.",
            ),
        ],
    ),
    (
        "transistor",
        "who invented the transistor and when was it invented?",
        "History of the transistor",
        [
            (
                "Field-effect transistor",
                "A field-effect transistor uses an electric field to "
                "control the flow of current through a semiconductor. "
                "Variants include the MOSFET and the JFET. The device "
                "has a gate, a drain and a source terminal, and is used "
                "widely in analog and digital circuits.",
            ),
            (
                "Invention",
                "An invention is a unique or novel device, method, "
                "composition or process. An invention that is patentable "
                "must be novel and non-obvious. Inventions can be "
                "improvements upon a machine or product, or a new "
                "process for creating an object or a result.",
            ),
            (
                "History of the transistor",
                "John Bardeen and Walter Brattain invented the "
                "point-contact transistor at Bell Labs in 1947. William "
                "Shockley developed the bipolar junction transistor in "
                "1948. The three shared the Nobel Prize in Physics in "
                "1956 for their research on semiconductors.",
            ),
        ],
    ),
    (
        "cats",
        "how many cats are in america?",
        "Pet cat population statistics",
        [
            (
                "Cat breeds",
                "There are many recognised cat breeds. The Siamese, the "
                "Maine Coon, the Persian and the Bengal are among the "
                "most popular. Breed standards describe coat length, "
                "colour, body shape and temperament for each recognised "
                "pedigree.",
            ),
            (
                "Cat behavior",
                "Cats communicate through vocalisation and body "
                "language. A cat may knead with its paws, rub against "
                "furniture, or sleep for long stretches during the day. "
                "Many cats are most active at dawn and dusk.",
            ),
            (
                "Pet cat population statistics",
                "An estimated 73.8 million pet cats live in the United "
                "States. Survey data from the American Pet Products "
                "Association puts the number of cat-owning households at "
                "roughly 46.5 million, about 29 percent of all "
                "households. Census-style demographics suggest the "
                "population has grown steadily.",
            ),
        ],
    ),
    (
        "purr",
        "why do cats purr?",
        "Why cats purr",
        [
            (
                "Cats",
                "The cat is a small domesticated carnivorous mammal. It "
                "is the only domesticated species in the family Felidae. "
                "Cats are valued as companion animals and were "
                "domesticated in the Near East around 7500 BC.",
            ),
            (
                "Why cats purr",
                "Cats purr because of rapid twitching in the muscles of "
                "the larynx, which causes the vocal cords to vibrate as "
                "the cat breathes. The mechanism explains how the sound "
                "continues on both the inhale and the exhale. Research "
                "suggests the reason is not only contentment: purring "
                "may also serve to self-soothe when a cat is injured, "
                "because the low-frequency vibration appears to promote "
                "healing.",
            ),
        ],
    ),
]


def run_fixture(fixture: Fixture, limit: int = 5) -> bool:
    """Index one fixture into a temp DB and print the ranking. True if OK."""
    name, query, expected_top, chunks = fixture
    tmpdir = tempfile.mkdtemp(prefix="brisart-offline-replay-")
    try:
        index = Index(os.path.join(tmpdir, "fixture.sqlite"))
        try:
            for title, text in chunks:
                index.add_source(
                    source_type="file",
                    location=f"/fixtures/{name}/{title}.txt",
                    title=title,
                    text=text,
                    extension="txt",
                    size_bytes=len(text),
                )

            intent = detect_intent(query)
            print("=" * 74)
            print(f"fixture: {name}")
            print(f"query:   {query!r}")
            print(f"intent:  {describe_intent(intent, query)}")
            print(f"chunks:  {len(chunks)}")
            print("-" * 74)

            results = search(index, query, limit=limit)
            if not results:
                print("  (no results)")
                return False

            for position, doc in enumerate(results, 1):
                boosts = doc.get("intent_boosts") or []
                penalties = doc.get("intent_penalties") or []
                reason = []
                if boosts:
                    reason.append("boost=" + ",".join(boosts))
                if penalties:
                    reason.append("penalty=" + ",".join(penalties))
                if not reason:
                    reason.append("term overlap only")
                print(
                    f"  {position}. {doc['score']:7.3f}  {doc['title']}"
                )
                print(f"        source: {doc['location']}")
                print(f"        reason: {'; '.join(reason)}")

            top = str(results[0]["title"])
            ok = top == expected_top
            print("-" * 74)
            print(f"  expected top: {expected_top}")
            print(f"  actual top:   {top}")
            print(f"  result: {'PASS' if ok else 'FAIL'}")
            return ok
        finally:
            index.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main(argv: Sequence[str]) -> int:
    args = [arg for arg in argv if not arg.startswith("-")]
    if "--list" in argv:
        for name, query, _expected, _chunks in FIXTURES:
            print(f"{name:12} {query}")
        return 0

    selected = [f for f in FIXTURES if not args or f[0] in args]
    if not selected:
        print(f"no fixture matching {args}; use --list", file=sys.stderr)
        return 2

    results: Dict[str, bool] = {}
    for fixture in selected:
        results[fixture[0]] = run_fixture(fixture)
        print()

    passed = sum(1 for ok in results.values() if ok)
    print("=" * 74)
    print(f"offline fixtures: {passed}/{len(results)} passed")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
