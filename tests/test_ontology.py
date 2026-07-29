from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.ontology import check_atom  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
