from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import dependencies  # noqa: E402


class DependencyStateTests(unittest.TestCase):
    def test_read_set_includes_epistemic_and_resource_state(self) -> None:
        bundle = {"state_before": {
            "facts": {"fact-current": "Current truth."},
            "participant_memory": {"char-a": ["fact-stale"]},
            "participant_beliefs": {"char-a": [
                {"fact": "fact-false", "value": True, "source": "testimony"}
            ]},
            "predicates": [{"predicate": "offline", "subject": "obj-relay", "object": None, "value": True}],
            "relationships": [{
                "subject": "char-a", "object": "char-b", "dimensions": {"trusts": "low"}
            }],
            "resources": [{"resource": "res-loaf", "holder": "char-a", "quantity": 1}],
            "open_promises": {},
        }}
        read_set = dependencies.read_set_from_context(bundle)
        self.assertEqual(read_set["facts"], ["fact-current", "fact-false", "fact-stale"])
        self.assertEqual(read_set["resources"], ["res-loaf"])
        self.assertEqual(read_set["predicates"], [
            {"predicate": "offline", "subject": "obj-relay", "object": None}
        ])
        self.assertEqual(read_set["relationships"], [
            {"subject": "char-a", "object": "char-b", "dimension": "trusts"}
        ])

    def test_changed_state_refs_include_beliefs_definitions_and_resources(self) -> None:
        before = {
            "belief_changes": [{
                "op": "set", "character": "char-a", "fact": "fact-door-open",
                "value": True, "source": "testimony",
            }],
            "resource_changes": [{
                "op": "transfer", "resource": "res-loaf", "from": "char-a", "to": "customer",
                "quantity": 1,
            }],
        }
        after = {
            "propositions_defined": [{"id": "fact-door-open", "text": "The door is open."}],
            "belief_changes": [{
                "op": "set", "character": "char-a", "fact": "fact-door-open",
                "value": False, "source": "correction",
            }],
            "resource_changes": [{
                "op": "transfer", "resource": "res-loaf", "from": "char-a", "to": "customer",
                "quantity": 2,
            }],
            "predicate_changes": [{"op": "add", "predicate": "offline", "subject": "obj-relay"}],
            "relationship_edges": [{
                "subject": "char-a", "object": "char-b", "dimension": "trusts", "value": "low"
            }],
        }
        changed = dependencies.changed_state_refs(before, after)
        self.assertEqual(changed["facts"], ["fact-door-open"])
        self.assertEqual(changed["resources"], ["res-loaf"])
        self.assertEqual(changed["predicates"], [
            {"predicate": "offline", "subject": "obj-relay", "object": None}
        ])
        self.assertEqual(changed["relationships"], [
            {"subject": "char-a", "object": "char-b", "dimension": "trusts"}
        ])
        self.assertTrue(dependencies.dependency_match(
            {"facts": [], "resources": ["res-loaf"], "predicates": [], "promises": []}, changed
        ))
        self.assertTrue(dependencies.dependency_match(
            {"facts": [], "resources": [], "promises": [],
             "predicates": [{"predicate": "offline", "subject": "obj-relay", "object": None}],
             "relationships": []}, changed
        ))
        self.assertTrue(dependencies.dependency_match(
            {"facts": [], "resources": [], "promises": [], "predicates": [],
             "relationships": [{"subject": "char-a", "object": "char-b", "dimension": "trusts"}]},
            changed,
        ))


if __name__ == "__main__":
    unittest.main()
