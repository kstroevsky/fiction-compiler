from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import premise, schema  # noqa: E402


def candidate(identifier: str, logline: str, **extra) -> dict:
    value = {
        "id": identifier,
        "logline": logline,
        "pov_character": f"char-{identifier}",
        "theme_question": "What does the choice cost?",
    }
    value.update(extra)
    return value


class PremiseDiversityTests(unittest.TestCase):
    def test_relabeling_identical_premise_does_not_fake_diversity(self) -> None:
        same = "A courier must decide whether to deliver a letter that will expose a friend."
        candidates = [
            candidate("a", same, conflict_type="internal", obliqueness="direct"),
            candidate("b", same, conflict_type="interpersonal", obliqueness="oblique"),
            candidate("c", same, conflict_type="character-vs-society", obliqueness="direct"),
        ]
        report = premise.diversity_floor(candidates)
        self.assertFalse(report["ok"])
        self.assertEqual(report["distinct_loglines"], 1)
        self.assertTrue(any("logline" in issue for issue in report["issues"]))

    def test_genuinely_different_premise_texts_clear_search_floor(self) -> None:
        candidates = [
            candidate("a", "A courier hides a letter and must live with the recipient's false hope."),
            candidate("b", "Three siblings auction their father's workshop while each secretly bids through a proxy."),
            candidate("c", "A night guard discovers the museum closes one room only when she is on duty."),
        ]
        report = premise.diversity_floor(candidates)
        self.assertTrue(report["ok"], report["issues"])
        self.assertEqual(report["distinct_loglines"], 3)

    def test_schema_does_not_require_restrained_realism_taste_tags(self) -> None:
        value = candidate("ensemble", "A choir votes to keep performing while its hall floods.")
        self.assertEqual(schema.validate_named(value, "premise"), [])

    def test_resolution_and_conflict_taxonomies_are_open_ended(self) -> None:
        value = candidate(
            "comedy",
            "Two rivals accidentally become co-hosts of the same disastrous wedding.",
            conflict_type="farce-of-coordination",
            resolution_type="comic-reconciliation",
            transforming_character=None,
        )
        self.assertEqual(schema.validate_named(value, "premise"), [])

    def test_restrained_realism_probes_are_opt_in(self) -> None:
        core = premise.load_probes()
        restrained = premise.load_probes(profile="restrained-realism")
        core_ids = {item["id"] for item in core}
        restrained_ids = {item["id"] for item in restrained}
        self.assertNotIn("resolution-humility", core_ids)
        self.assertIn("resolution-humility", restrained_ids)


if __name__ == "__main__":
    unittest.main()
