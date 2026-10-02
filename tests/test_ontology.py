from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.ontology import (check_atom, entity_registry_errors,
                                       ontology_definition_errors)  # noqa: E402

ONTOLOGY = {
    "located_at": {"name": "located_at", "arity": "binary", "subject_types": ["char", "obj"], "object_types": ["loc"]},
    "offline": {"name": "offline", "arity": "unary", "subject_types": ["obj"]},
}


class OntologyCheckTests(unittest.TestCase):
    def test_valid_atom_has_no_errors(self) -> None:
        self.assertEqual(check_atom(ONTOLOGY, "located_at", "char-jonas", "loc-station"), [])

    def test_typo_predicate_is_undeclared(self) -> None:
        errors = check_atom(ONTOLOGY, "located_att", "char-jonas", "loc-station")
        self.assertTrue(any("not declared" in e for e in errors))

    def test_binary_used_without_object(self) -> None:
        self.assertTrue(any("binary" in e for e in check_atom(ONTOLOGY, "located_at", "char-jonas", None)))

    def test_unary_used_with_object(self) -> None:
        self.assertTrue(any("unary" in e for e in check_atom(ONTOLOGY, "offline", "obj-relay", "loc-station")))

    def test_subject_type_mismatch(self) -> None:
        self.assertTrue(any("subject" in e for e in check_atom(ONTOLOGY, "located_at", "fact-x", "loc-station")))

    def test_object_type_mismatch(self) -> None:
        self.assertTrue(any("object" in e for e in check_atom(ONTOLOGY, "located_at", "char-jonas", "char-mara")))

    def test_declared_value_domain_requires_and_validates_values(self) -> None:
        ontology = {"temperature": {
            "name": "temperature", "arity": "unary", "subject_types": ["obj"],
            "value_type": "number", "minimum": -20, "maximum": 50,
        }}
        self.assertTrue(any("explicit typed value" in e
                            for e in check_atom(ontology, "temperature", "obj-relay", None)))
        self.assertEqual(check_atom(ontology, "temperature", "obj-relay", None,
                                    value=-2, comparison="lt"), [])
        self.assertTrue(any("not number" in e
                            for e in check_atom(ontology, "temperature", "obj-relay", None, value=False)))
        self.assertTrue(any("above maximum" in e
                            for e in check_atom(ontology, "temperature", "obj-relay", None, value=60)))

    def test_allowed_values_use_typed_equality(self) -> None:
        ontology = {"enabled": {
            "name": "enabled", "arity": "unary", "subject_types": ["obj"],
            "value_type": "boolean", "allowed_values": [False],
        }}
        self.assertEqual(check_atom(ontology, "enabled", "obj-relay", None, value=False), [])
        errors = check_atom(ontology, "enabled", "obj-relay", None, value=0)
        self.assertTrue(any("not boolean" in e for e in errors))
        self.assertTrue(any("outside allowed_values" in e for e in errors))

    def test_closed_entity_type_rejects_unregistered_id(self) -> None:
        registry = {
            "closed_types": ["loc"],
            "entities": [{"id": "place-platform", "type": "loc"}],
        }
        self.assertEqual(
            check_atom(ONTOLOGY, "located_at", "char-jonas", "place-platform", registry=registry), []
        )
        errors = check_atom(ONTOLOGY, "located_at", "char-jonas", "loc-ghost", registry=registry)
        self.assertTrue(any("closed entity registry" in e for e in errors))

    def test_semantic_definition_checks_duplicate_and_incompatible_domains(self) -> None:
        errors = ontology_definition_errors({"predicates": [
            {"name": "stance", "arity": "binary", "value_type": "string",
             "allowed_values": ["high", 0], "exclusive_object_per_subject": True},
            {"name": "stance", "arity": "binary"},
        ]})
        self.assertTrue(any("duplicate predicate" in e for e in errors))
        self.assertTrue(any("allowed value" in e for e in errors))
        self.assertTrue(any("exclusivity requires boolean" in e for e in errors))

    def test_registry_duplicate_ids_are_rejected(self) -> None:
        errors = entity_registry_errors({
            "closed_types": ["loc"],
            "entities": [{"id": "loc-a", "type": "loc"}, {"id": "loc-a", "type": "loc"}],
        })
        self.assertTrue(any("duplicate entity id" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
