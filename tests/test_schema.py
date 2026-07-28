from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import schema  # noqa: E402


def valid_project() -> dict:
    return {
        "id": "a-b",
        "title": "T",
        "form": "short-story",
        "audience": "readers",
        "reader_contract": [],
        "theme_question": "q",
        "constraints": [],
    }


class SchemaValidatorTests(unittest.TestCase):
    def test_all_repo_schemas_load(self) -> None:
        for name in ["project", "character", "scene", "event", "state-delta", "critique"]:
            self.assertIsInstance(schema.load_schema(name), dict)

    def test_valid_project_passes(self) -> None:
        self.assertEqual(schema.validate_named(valid_project(), "project"), [])

    def test_missing_required_reported(self) -> None:
        instance = valid_project()
        del instance["audience"]
        errors = schema.validate_named(instance, "project")
        self.assertTrue(any("audience" in e for e in errors))

    def test_pattern_and_minlength_and_enum(self) -> None:
        instance = valid_project()
        instance["id"] = "Bad_ID"
        instance["title"] = ""
        instance["form"] = "epic"
        errors = schema.validate_named(instance, "project")
        self.assertTrue(any("pattern" in e for e in errors))
        self.assertTrue(any("minLength" in e for e in errors))
        self.assertTrue(any("not one of" in e for e in errors))

    def test_union_type_string_or_number(self) -> None:
        event = {
            "id": "evt-x",
            "time": "day-1",
            "actors": [],
            "preconditions": [],
            "action": "a",
            "effects": [],
            "causes": [],
        }
        self.assertEqual(schema.validate_named(event, "event"), [])
        event["time"] = 3
        self.assertEqual(schema.validate_named(event, "event"), [])
        event["time"] = True  # bool is not a valid number here
        self.assertTrue(schema.validate_named(event, "event"))

    def test_nested_findings_and_numeric_range(self) -> None:
        critique = {
            "candidate": "c",
            "critic": "x",
            "verdict": "maybe",
            "confidence": 1.5,
            "findings": [
                {
                    "dimension": "d",
                    "severity": "huge",
                    "evidence": "e",
                    "diagnosis": "g",
                    "repair_layer": "nowhere",
                }
            ],
        }
        errors = schema.validate_named(critique, "critique")
        self.assertTrue(any("verdict" in e for e in errors))
        self.assertTrue(any("maximum" in e for e in errors))
        self.assertTrue(any("severity" in e for e in errors))
        self.assertTrue(any("repair_layer" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
