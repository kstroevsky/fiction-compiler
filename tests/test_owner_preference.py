from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import owner_preference, schema, tools  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_project(root: Path, project_id: str = "proj") -> Path:
    project = root / project_id
    write_json(project / "brief" / "project.json", {"id": project_id})
    return project


def alternatives() -> list[dict]:
    return [
        {"id": "quiet-ending", "label": "Quiet", "text": "She closes the gate."},
        {"id": "open-ending", "label": "Open", "text": "She leaves the gate open."},
    ]


class OwnerPreferenceTests(unittest.TestCase):
    def test_record_choice_freezes_exact_alternatives_and_packet_hides_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            result = owner_preference.record_choice(
                project, "ending", alternatives(), "quiet-ending", "The smaller action lands harder.",
                "2026-09-29",
            )
            self.assertEqual(result["status"], "recorded", result)
            record_path = project / result["path"]
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["chosen_id"], "quiet-ending")
            self.assertEqual(record["reason"], "The smaller action lands harder.")
            for item in record["alternatives"]:
                snapshot = project / item["snapshot"]
                self.assertTrue(snapshot.is_file())
                self.assertEqual(owner_preference.acceptance.sha256_bytes(snapshot.read_bytes()), item["sha256"])

            packet = owner_preference.packet(project, result["preference_id"])
            self.assertNotIn("chosen_id", packet)
            self.assertNotIn("reason", packet)
            self.assertEqual([item["id"] for item in packet["alternatives"]],
                             ["quiet-ending", "open-ending"])
            self.assertEqual(packet["alternatives"][0]["text"], "She closes the gate.")

    def test_record_choice_rejects_escape_duplicate_ids_and_unknown_choice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = make_project(root)
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")

            escaped = owner_preference.record_choice(
                project, "candidate",
                [{"id": "one", "path": str(outside)}, {"id": "two", "text": "two"}],
                "two", "reason", "2026-09-29",
            )
            self.assertIn("escapes project", escaped["error"])

            duplicate = owner_preference.record_choice(
                project, "candidate",
                [{"id": "same", "text": "one"}, {"id": "same", "text": "two"}],
                "same", "reason", "2026-09-29",
            )
            self.assertIn("ids must be unique", duplicate["error"])

            unknown = owner_preference.record_choice(
                project, "candidate", alternatives(), "missing", "reason", "2026-09-29",
            )
            self.assertIn("chosen_id", unknown["error"])

    def test_prediction_requires_current_packet_and_is_one_per_critic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            choice = owner_preference.record_choice(
                project, "ending", alternatives(), "quiet-ending", "reason", "2026-09-29",
            )
            packet = owner_preference.packet(project, choice["preference_id"])

            stale = owner_preference.record_prediction(
                project, choice["preference_id"], "critic-a", "0" * 64, "quiet-ending"
            )
            self.assertIn("stale", stale["error"])

            prediction = owner_preference.record_prediction(
                project, choice["preference_id"], "critic-a", packet["packet_sha256"], "quiet-ending"
            )
            self.assertEqual(prediction["status"], "recorded", prediction)

            duplicate = owner_preference.record_prediction(
                project, choice["preference_id"], "critic-a", packet["packet_sha256"], None
            )
            self.assertIn("already predicted", duplicate["error"])

            abstain = owner_preference.record_prediction(
                project, choice["preference_id"], "critic-b", packet["packet_sha256"], None
            )
            self.assertEqual(abstain["status"], "recorded", abstain)

    def test_report_is_descriptive_owner_only_and_counts_abstention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            choice = owner_preference.record_choice(
                project, "ending", alternatives(), "quiet-ending", "reason", "2026-09-29",
            )
            packet = owner_preference.packet(project, choice["preference_id"])
            owner_preference.record_prediction(
                project, choice["preference_id"], "critic-a", packet["packet_sha256"], "quiet-ending"
            )
            owner_preference.record_prediction(
                project, choice["preference_id"], "critic-b", packet["packet_sha256"], None
            )

            report = owner_preference.report(project)
            self.assertEqual(report["status"], "valid", report["errors"])
            self.assertEqual(report["evidence_status"], "descriptive_agreement_available")
            self.assertEqual(report["critics"]["critic-a"]["agreement_among_picks"], 1.0)
            self.assertEqual(report["critics"]["critic-b"]["abstentions"], 1)
            self.assertIsNone(report["critics"]["critic-b"]["agreement_among_picks"])
            self.assertIn("this owner's recorded choices only", report["note"])
            self.assertIn("not target-reader preference", report["note"])

    def test_tampered_snapshot_invalidates_report_and_persistent_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            choice = owner_preference.record_choice(
                project, "ending", alternatives(), "quiet-ending", "reason", "2026-09-29",
            )
            record = json.loads((project / choice["path"]).read_text(encoding="utf-8"))
            (project / record["alternatives"][0]["snapshot"]).write_text("tampered", encoding="utf-8")

            report = owner_preference.report(project)
            self.assertEqual(report["status"], "invalid")
            self.assertTrue(any("snapshot hash changed" in error for error in report["errors"]))
            validation = owner_preference.persistent_validation_errors(project)
            self.assertTrue(any("snapshot hash changed" in error for error in validation))

    def test_empty_project_and_repository_projects_do_not_backfill_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            report = owner_preference.report(project)
            self.assertEqual(report["evidence_status"], "no_owner_preferences_recorded")
            self.assertEqual(report["preference_records"], 0)

        repository_report = owner_preference.report(ROOT / "projects" / "forecourt")
        self.assertEqual(repository_report["status"], "valid", repository_report["errors"])
        self.assertEqual(repository_report["evidence_status"], "no_owner_preferences_recorded")
        self.assertEqual(repository_report["preference_records"], 0)

    def test_prediction_schema_and_tool_registry_enforce_blind_calibration_contract(self) -> None:
        base = {
            "schema_version": 1,
            "prediction_id": "prediction-" + "a" * 32,
            "preference_id": "pref-" + "b" * 32,
            "preference_sha256": "c" * 64,
            "packet_sha256": "d" * 64,
            "project_id": "proj",
            "critic": "critic-a",
            "recorded_at": "2026-09-29T00:00:00+00:00",
        }
        missing_pick = {**base, "prediction": {"kind": "pick"}}
        self.assertTrue(schema.validate_named(missing_pick, "owner-preference-prediction"))
        invalid_abstain = {**base, "prediction": {"kind": "abstain", "alternative_id": "one"}}
        self.assertTrue(schema.validate_named(invalid_abstain, "owner-preference-prediction"))

        descriptors = {item["name"]: item for item in tools.list_tools()}
        for name in (
            "record_owner_preference", "owner_preference_packet",
            "record_owner_preference_prediction", "owner_preference_report",
        ):
            self.assertIn(name, descriptors)
        alternatives_schema = descriptors["record_owner_preference"]["inputSchema"]["properties"]["alternatives"]
        self.assertEqual(alternatives_schema["minItems"], 2)


if __name__ == "__main__":
    unittest.main()
