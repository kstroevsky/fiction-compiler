from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import selection_eval, tools  # noqa: E402


SCENE = "ch01-sc01"


def build_project(root: Path) -> Path:
    project = root / "selection-eval"
    candidates = project / "scenes" / SCENE / "candidates"
    candidates.mkdir(parents=True)
    (candidates / "candidate-a.md").write_text("A: spare, exact prose.\n", encoding="utf-8")
    (candidates / "candidate-b.md").write_text("B: competent prose.\n", encoding="utf-8")
    (candidates / "candidate-c.md").write_text("C: weaker prose.\n", encoding="utf-8")
    return project


def complete_human_preferences(project: Path, frozen: dict,
                               ranking: list[str]) -> None:
    """Record both scheduled orientations for every pair, respecting the desired true-name ranking."""
    rank = {candidate: index for index, candidate in enumerate(ranking)}
    label_to_name = {item["blind_label"]: item["candidate"] for item in frozen["candidates"]}
    for index, pair in enumerate(frozen["pairs"]):
        left = label_to_name[pair["left_label"]]
        right = label_to_name[pair["right_label"]]
        choice = "left" if rank[left] < rank[right] else "right"
        result = selection_eval.record_preference(
            project, SCENE, frozen["experiment_id"], f"reader-{index}", "target_reader", "human",
            pair["pair_id"], choice,
        )
        if "error" in result:
            raise AssertionError(result["error"])


class FrozenPoolTests(unittest.TestCase):
    def test_freeze_preserves_generation_order_and_bytes_while_reader_packet_stays_blind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(
                project, SCENE, ["candidate-b.md", "candidate-a.md", "candidate-c.md"], seed=7
            )
            self.assertNotIn("error", frozen)
            self.assertEqual(
                [item["candidate"] for item in frozen["candidates"]],
                ["candidate-b.md", "candidate-a.md", "candidate-c.md"],
            )
            self.assertEqual([item["generation_index"] for item in frozen["candidates"]], [0, 1, 2])
            self.assertEqual(len(frozen["pairs"]), 6)  # every unordered pair in both orientations

            # Later source edits cannot alter the experiment bytes.
            source = project / "scenes" / SCENE / "candidates" / "candidate-a.md"
            source.write_text("CHANGED AFTER FREEZE\n", encoding="utf-8")
            packet = selection_eval.reader_packet(project, SCENE, frozen["experiment_id"])
            self.assertNotIn("error", packet)
            joined = json.dumps(packet)
            self.assertNotIn("candidate-a.md", joined)
            self.assertNotIn("candidate-b.md", joined)
            self.assertNotIn("generation_index", joined)
            self.assertNotIn("CHANGED AFTER FREEZE", joined)
            self.assertIn("A: spare, exact prose.", joined)

    def test_frozen_candidate_tamper_invalidates_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            run_dir = project / frozen["path"]
            label = frozen["candidates"][0]["blind_label"]
            (run_dir / "blind" / f"{label}.md").write_text("tampered", encoding="utf-8")
            report = selection_eval.report(project, SCENE, frozen["experiment_id"])
            self.assertEqual(report["status"], "invalid")
            self.assertIn("content-hash mismatch", " ".join(report["errors"]))


class MeasurementTests(unittest.TestCase):
    def test_first_random_and_recorded_selector_share_pool_and_get_descriptive_regret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(
                project, SCENE, ["candidate-b.md", "candidate-a.md", "candidate-c.md"], seed=13
            )
            chosen = selection_eval.record_selector(
                project, SCENE, frozen["experiment_id"], "critic", "candidate-a.md",
                provenance={"judge": "held-out-critic", "packet": "frozen"},
            )
            self.assertNotIn("error", chosen)
            complete_human_preferences(
                project, frozen, ["candidate-a.md", "candidate-b.md", "candidate-c.md"]
            )

            report = selection_eval.report(project, SCENE, frozen["experiment_id"])
            self.assertEqual(report["reader_evidence"]["status"], "descriptive_complete")
            self.assertEqual(report["reader_evidence"]["top_by_observed_score"], ["candidate-a.md"])
            selectors = {row["selector"]: row for row in report["selectors"]}
            self.assertEqual(selectors["first"]["candidate"], "candidate-b.md")
            self.assertEqual(selectors["critic"]["candidate"], "candidate-a.md")
            self.assertEqual(selectors["critic"]["empirical_regret"], 0.0)
            self.assertGreater(selectors["first"]["empirical_regret"], 0.0)
            self.assertIn("random", selectors)

    def test_incomplete_reader_matrix_is_explicitly_insufficient_and_owner_is_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(
                project, SCENE, ["candidate-a.md", "candidate-b.md", "candidate-c.md"]
            )
            first_pair = frozen["pairs"][0]["pair_id"]
            self.assertNotIn("error", selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "reader", "target_reader", "human",
                first_pair, "tie",
            ))
            self.assertNotIn("error", selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "owner", "owner", "human",
                first_pair, "left",
            ))
            self.assertNotIn("error", selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "probe", "target_reader", "model_probe",
                first_pair, "left",
            ))
            report = selection_eval.report(project, SCENE, frozen["experiment_id"])
            evidence = report["reader_evidence"]
            self.assertEqual(evidence["audience_records_used"], 1)
            self.assertEqual(evidence["status"], "insufficient_pair_or_order_coverage")
            self.assertEqual(evidence["by_cohort"]["owner"], 1)
            self.assertEqual(evidence["by_rater_kind"]["model_probe"], 1)
            self.assertTrue(all(row["empirical_regret"] is None for row in report["selectors"]))

    def test_selector_choice_is_frozen_before_reader_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            pair = frozen["pairs"][0]["pair_id"]
            selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "reader", "target_reader", "human", pair, "left"
            )
            late = selection_eval.record_selector(
                project, SCENE, frozen["experiment_id"], "critic", "candidate-a.md"
            )
            self.assertIn("before reader preferences", late["error"])

    def test_one_rater_cannot_weight_both_orders_of_the_same_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            forward, reverse = frozen["pairs"]
            self.assertNotIn("error", selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "same-reader", "target_reader", "human",
                forward["pair_id"], "left",
            ))
            duplicate = selection_eval.record_preference(
                project, SCENE, frozen["experiment_id"], "same-reader", "target_reader", "human",
                reverse["pair_id"], "right",
            )
            self.assertIn("at most one orientation", duplicate["error"])

    def test_corrupt_evidence_invalidates_report_instead_of_disappearing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            run_dir = project / frozen["path"]
            bad = run_dir / "preferences" / "corrupt.json"
            bad.parent.mkdir(parents=True)
            bad.write_text("{not json", encoding="utf-8")
            report = selection_eval.report(project, SCENE, frozen["experiment_id"])
            self.assertEqual(report["status"], "invalid")
            self.assertIn("unreadable evidence", " ".join(report["errors"]))

    def test_selector_name_can_only_be_frozen_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            exp = frozen["experiment_id"]
            self.assertNotIn("error", selection_eval.record_selector(
                project, SCENE, exp, "critic", "candidate-a.md"
            ))
            duplicate = selection_eval.record_selector(project, SCENE, exp, "critic", "candidate-b.md")
            self.assertIn("already has a frozen choice", duplicate["error"])

    def test_cost_report_preserves_unknown_usage_and_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            frozen = selection_eval.freeze_pool(project, SCENE, ["candidate-a.md", "candidate-b.md"])
            exp = frozen["experiment_id"]
            known = selection_eval.record_operation(
                project, SCENE, exp, "generation", "success", candidate="candidate-a.md",
                provider="vendor-x", model="writer-1", input_tokens=100, output_tokens=50, cost_usd=0.12,
            )
            failed = selection_eval.record_operation(
                project, SCENE, exp, "generation", "failure", candidate="candidate-b.md",
                provider="vendor-y", model="writer-2", failure_reason="timeout",
            )
            self.assertNotIn("error", known)
            self.assertNotIn("error", failed)
            cost = selection_eval.report(project, SCENE, exp)["cost_and_failures"]
            self.assertEqual(cost["operations"], 2)
            self.assertEqual(cost["failures"], 1)
            self.assertEqual(cost["input_tokens"]["known_total"], 100)
            self.assertEqual(cost["input_tokens"]["missing_records"], 1)
            self.assertEqual(cost["cost_usd"]["known_total"], 0.12)
            self.assertEqual(cost["cost_usd"]["missing_records"], 1)

    def test_tool_registry_exposes_selection_measurement_workflow(self) -> None:
        names = {item["name"] for item in tools.list_tools()}
        self.assertTrue({
            "freeze_selection_pool", "selection_reader_packet", "record_pairwise_preference",
            "record_selector_choice", "record_selection_operation", "selection_experiment_report",
        }.issubset(names))


if __name__ == "__main__":
    unittest.main()
