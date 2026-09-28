from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import realization_calibration  # noqa: E402


class RealizationCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        started = realization_calibration.start_study(self.project, "D pilot")
        self.assertNotIn("error", started)
        self.study = started["study_id"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def extract(self, case: str, evidence: str | None, trial: int = 1) -> dict:
        observed = [] if evidence is None else [{
            "id": "observed-refusal", "description": "Mara refuses the shipment.",
            "evidence": evidence, "consequential": True,
        }]
        result = realization_calibration.record_extraction(
            self.project, self.study, case, "extractor-family", "extractor-1", trial, observed
        )
        self.assertNotIn("error", result)
        return result

    def align(self, extraction: dict, status: str, observed_id: str | None = None) -> dict:
        item = {"event_id": "evt-refusal", "status": status}
        if observed_id:
            item["observed_id"] = observed_id
        result = realization_calibration.record_alignment(
            self.project, self.study, extraction["extraction_id"], "aligner-family", "aligner-1", [item]
        )
        self.assertNotIn("error", result)
        return result

    def test_packets_keep_stage_blinding(self) -> None:
        packet = realization_calibration.extractor_packet(self.project, self.study, "required-event-oblique")
        self.assertIn("prose", packet)
        self.assertNotIn("required_events", packet)
        extraction = self.extract("required-event-oblique", "folded the unsigned manifest into quarters")
        align = realization_calibration.aligner_packet(self.project, self.study, extraction["extraction_id"])
        self.assertEqual(align["required_events"][0]["event_id"], "evt-refusal")
        self.assertIn("prose", align)
        self.assertNotIn("expected_status", align["required_events"][0])
        self.assertNotIn("evidence_anchors", align["required_events"][0])

    def test_oblique_realization_is_measured_as_success(self) -> None:
        extraction = self.extract("required-event-oblique", "folded the unsigned manifest into quarters")
        self.align(extraction, "realized", "observed-refusal")
        report = realization_calibration.report(self.project, self.study)
        row = next(row for row in report["rows"] if row["case_id"] == "required-event-oblique")
        self.assertEqual(row["extractor_status"], "recognized_fixture_evidence")
        self.assertEqual(row["pipeline_status"], "correct_realization")

    def test_planted_omission_can_be_explicitly_recognized(self) -> None:
        extraction = self.extract("required-event-omitted", None)
        self.align(extraction, "omitted")
        report = realization_calibration.report(self.project, self.study)
        row = next(row for row in report["rows"] if row["case_id"] == "required-event-omitted")
        self.assertEqual(row["pipeline_status"], "correct_omission")

    def test_extractor_miss_never_becomes_proved_omission(self) -> None:
        extraction = self.extract("required-event-oblique", None)
        self.align(extraction, "omitted")
        report = realization_calibration.report(self.project, self.study)
        row = next(row for row in report["rows"] if row["case_id"] == "required-event-oblique")
        self.assertEqual(row["pipeline_status"], "unverified_extractor_miss")
        self.assertIn("omission cannot be inferred", row["reason"])

    def test_alignment_miss_is_separate_from_extractor_miss(self) -> None:
        extraction = self.extract("required-event-literal", "No. Send the shipment back.")
        self.align(extraction, "omitted")
        report = realization_calibration.report(self.project, self.study)
        row = next(row for row in report["rows"] if row["case_id"] == "required-event-literal")
        self.assertEqual(row["extractor_status"], "recognized_fixture_evidence")
        self.assertEqual(row["pipeline_status"], "alignment_false_omission")

    def test_report_keeps_turn_and_affect_unverified_and_no_gate_authority(self) -> None:
        report = realization_calibration.report(self.project, self.study)
        self.assertEqual(report["authority"], "not_a_prose_audit_gate")
        self.assertIn("free_text_turn_and_affect", report["open_evidence"])

    def test_tampered_extraction_invalidates_report(self) -> None:
        extraction = self.extract("required-event-literal", "No. Send the shipment back.")
        path = self.project / extraction["path"]
        data = json.loads(path.read_text())
        data["prose_sha256"] = "0" * 64
        path.write_text(json.dumps(data))
        report = realization_calibration.report(self.project, self.study)
        self.assertEqual(report["evidence_status"], "invalid")


if __name__ == "__main__":
    unittest.main()
