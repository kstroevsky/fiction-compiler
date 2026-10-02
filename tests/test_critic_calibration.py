from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import critic_calibration


def finding(signal: str, severity: str = "material") -> dict:
    return {
        "dimension": signal,
        "severity": severity,
        "evidence": "exact calibration evidence",
        "diagnosis": f"targeted {signal} defect",
        "repair_layer": "prose",
    }


class CriticCalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        started = critic_calibration.start_study(
            self.project,
            "B2 pilot",
            case_ids=["llm-told-emotion", "llm-physical-control"],
            criteria={"purpose": "pilot"},
        )
        self.assertNotIn("error", started)
        self.study = started["study_id"]

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def observe(self, case_id: str, *, judge_family: str = "family-a", judge_id: str = "a-judge",
                writer_family: str = "writer-a", trial: int = 1, variant: str = "base",
                transform: str = "identity", expectation: str = "baseline", group: str | None = None,
                caught: bool = True) -> dict:
        findings = [finding("emotion")] if caught and case_id == "llm-told-emotion" else []
        if caught and case_id == "llm-physical-control":
            findings = [finding("emotion")]
        return critic_calibration.record_observation(
            self.project, self.study, case_id, judge_family, judge_id, writer_family, trial,
            variant, transform, expectation, "revise" if findings else "pass", findings,
            invariance_group=group,
        )

    def test_repeatability_reports_disagreement_without_calling_it_correctness(self) -> None:
        self.observe("llm-told-emotion", trial=1, caught=True)
        self.observe("llm-told-emotion", trial=2, caught=False)
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["repeatability"]["status"], "measured")
        row = report["repeatability"]["groups"][0]
        self.assertEqual(row["caught_values"], [True, False])
        self.assertEqual(row["pairwise_agreement"], 0.0)
        self.assertIn("does not establish correctness", report["repeatability"]["note"])

    def test_invariance_uses_matched_trials_and_preserves_failures(self) -> None:
        self.observe("llm-told-emotion", trial=1, variant="plain", group="g1", caught=True)
        self.observe(
            "llm-told-emotion", trial=1, variant="formatted", transform="formatting",
            expectation="invariant", group="g1", caught=False,
        )
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["invariance"]["status"], "measured")
        self.assertEqual(report["invariance"]["satisfaction_rate"], 0.0)
        self.assertFalse(report["invariance"]["matched_pairs"][0]["expectation_satisfied"])

    def test_crossed_family_matrix_requires_both_axes(self) -> None:
        self.observe("llm-told-emotion", judge_family="j1", judge_id="j1", writer_family="w1")
        self.observe("llm-told-emotion", judge_family="j2", judge_id="j2", writer_family="w1")
        self.observe("llm-physical-control", judge_family="j1", judge_id="j1", writer_family="w2", caught=False)
        self.observe("llm-physical-control", judge_family="j2", judge_id="j2", writer_family="w2", caught=False)
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["crossed_families"]["status"], "crossed")
        self.assertEqual(set(report["crossed_families"]["writer_families"]), {"w1", "w2"})
        self.assertEqual(set(report["crossed_families"]["judge_families"]), {"j1", "j2"})
        self.assertEqual(len(report["crossed_families"]["cells"]), 4)

    def test_missing_human_labels_is_explicit(self) -> None:
        self.observe("llm-told-emotion")
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["human_agreement"]["status"], "insufficient_human_labels")
        self.assertEqual(report["authority"], "not_a_promotion_gate")
        self.assertIn("repair_benefit", report["open_evidence"])

    def test_human_disagreement_is_preserved_and_excluded_from_agreement(self) -> None:
        for annotator, label in (("expert-1", "defect"), ("expert-2", "control")):
            recorded = critic_calibration.record_human_label(
                self.project, self.study, "llm-told-emotion", annotator, "expert", label
            )
            self.assertNotIn("error", recorded)
        self.observe("llm-told-emotion")
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["human_labels"]["llm-told-emotion"]["status"], "disputed")
        self.assertEqual(report["human_agreement"]["status"], "insufficient_human_labels")

    def test_agreed_human_labels_enable_separate_agreement_measure(self) -> None:
        for annotator in ("expert-1", "expert-2"):
            critic_calibration.record_human_label(
                self.project, self.study, "llm-told-emotion", annotator, "expert", "defect",
                severity="material", signals=["emotion"],
            )
        self.observe("llm-told-emotion", caught=True)
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["human_agreement"]["status"], "measured")
        self.assertEqual(report["human_agreement"]["by_judge_family"]["family-a"]["agreement_rate"], 1.0)

    def test_judge_packet_hides_expected_label_and_signals(self) -> None:
        packet = critic_calibration.judge_packet(self.project, self.study, "llm-told-emotion")
        self.assertNotIn("error", packet)
        self.assertNotIn("expect_caught", packet)
        self.assertNotIn("signals", packet)
        self.assertNotIn("case_id", packet)

    def test_corrupt_evidence_invalidates_report(self) -> None:
        observed = self.observe("llm-told-emotion")
        path = self.project / observed["path"]
        path.write_text("{}", encoding="utf-8")
        report = critic_calibration.report(self.project, self.study)
        self.assertEqual(report["evidence_status"], "invalid")
        self.assertTrue(report["integrity_errors"])


if __name__ == "__main__":
    unittest.main()
