"""
File: brisart_ai/knowledge/tests/test_entity_registry.py

Purpose
-------
Unit tests for brisart_ai.knowledge.entity_registry. Verifies the module's public
behavior and its documented edge cases so regressions are caught
before release. Contains 12 test cases across TestResolveEntityName, TestAreSameEntity, TestRegisterAlias, TestDedupeEntityNames.

Communication / relationships
------------------------------
- exercises brisart_ai.knowledge.entity_registry (are_same_entity, dedupe_entity_names, register_alias, resolve_entity_name)

Settings / parameters
---------------------
- Standard unittest.TestCase suite; run with pytest
  (--import-mode=importlib) or `python -m pytest`.
- Uses only in-memory / temp-dir fixtures where any state is
  needed; no network, no external services, no shared global state.
- No tunable parameters of its own; assertions pin the behavior
  and point values defined in the module under test.

Edge cases
----------
- asserts: empty input.

Known limitations
-----------------
- Covers the behaviors enumerated above; paths not listed here are
  not asserted by this file and may be covered elsewhere.
- Deterministic and offline by design; it does not exercise real
  network, GUI display, or concurrency behavior.

Examples
--------
    $ python -m pytest brisart_ai/knowledge/tests/test_entity_registry.py -v
    $ python -m pytest brisart_ai/knowledge/tests/test_entity_registry.py --import-mode=importlib
"""
import unittest

from brisart_ai.knowledge.entity_registry import (
    are_same_entity, dedupe_entity_names, register_alias, resolve_entity_name,
)


class TestResolveEntityName(unittest.TestCase):
    def test_canonical_name_unchanged(self):
        self.assertEqual(resolve_entity_name("Bill Gates"), "Bill Gates")

    def test_known_alias_resolved(self):
        self.assertEqual(resolve_entity_name("William Gates"), "Bill Gates")

    def test_title_stripped(self):
        self.assertEqual(resolve_entity_name("Dr. Bill Gates"), "Bill Gates")

    def test_suffix_stripped_and_aliased(self):
        self.assertEqual(resolve_entity_name("William H. Gates III"), "Bill Gates")

    def test_unregistered_name_returned_normalized(self):
        self.assertEqual(resolve_entity_name("Jane   Doe"), "Jane Doe")

    def test_empty_input(self):
        self.assertEqual(resolve_entity_name(""), "")
        self.assertEqual(resolve_entity_name("   "), "")

    def test_idempotent(self):
        once = resolve_entity_name("William Gates")
        twice = resolve_entity_name(once)
        self.assertEqual(once, twice)


class TestAreSameEntity(unittest.TestCase):
    def test_aliases_match(self):
        self.assertTrue(are_same_entity("Bill Gates", "William H. Gates III"))

    def test_different_people_do_not_match(self):
        self.assertFalse(are_same_entity("Bill Gates", "Paul Allen"))


class TestRegisterAlias(unittest.TestCase):
    def test_runtime_registration(self):
        register_alias("Test Canonical Person", "TCP Alias")
        self.assertEqual(resolve_entity_name("TCP Alias"), "Test Canonical Person")


class TestDedupeEntityNames(unittest.TestCase):
    def test_collapses_aliases(self):
        names = ["Bill Gates", "William Gates", "Paul Allen", "Paul G. Allen"]
        self.assertEqual(dedupe_entity_names(names), {"Bill Gates", "Paul Allen"})

    def test_empty_list(self):
        self.assertEqual(dedupe_entity_names([]), set())


if __name__ == "__main__":
    unittest.main()



