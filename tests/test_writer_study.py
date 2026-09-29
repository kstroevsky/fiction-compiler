from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import run_manifest, selection_eval, tools, writer_study  # noqa: E402


SCENE = "ch01-sc01"


def _project(root: Path) -> Path:
    project = root / "writer-study"
    candidates = project / "scenes" / SCENE / "candidates"
    candidates.mkdir(parents=True)
    (candidates / "a.md").write_text("Candidate A.\n", encoding="utf-8")
    (candidates / "b.md").write_text("Candidate B.\n", encoding="utf-8")
    (candidates / "source.md").write_text("Source draft.\n", encoding="utf-8")
    return project


def _run(project: Path, candidate: str, provider: str, model: str,
         *, tokens: int | None = 100, cost: float | None = 0.10) -> str:
    run_id = run_manifest.start(project, SCENE, [{"step_id": "write", "phase": "generation"}])["run_id"]
    kwargs = {}
    if tokens is not None:
        kwargs = {"input_tokens": tokens // 2, "output_tokens": tokens - tokens // 2, "total_tokens": tokens}
    result = run_manifest.record_operation(
        project, SCENE, run_id, "write", "success", candidate=candidate,
        executor_kind="external_model", provider=provider, model=model, cost_usd=cost, **kwargs,
    )
    if "error" in result:
        raise AssertionError(result)
    return run_id


def _arms(run_a: str, run_b: str) -> list[dict]:
    return [
        {"candidate": "a.md", "run_id": run_a, "writer_family": "family-a",
         "strategy": "independent-draft", "provider": "vendor-a", "model": "writer-a"},
        {"candidate": "b.md", "run_id": run_b, "writer_family": "family-b",
         "strategy": "independent-draft", "provider": "vendor-b", "model": "writer-b"},
    ]


class WriterStudyTests(unittest.TestCase):
    def test_matched_family_study_freezes_before_reader_outcomes_and_reuses_blind_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a")
            run_b = _run(project, "b.md", "vendor-b", "writer-b")
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"], seed=3)
            frozen = writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens", max_relative_gap=0,
            )
            self.assertNotIn("error", frozen)
            report = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(report["study_status"], "ready_for_reader_evidence")
            self.assertTrue(report["cost_matching"]["within_tolerance"])
            self.assertEqual(report["writer_families"], ["family-a", "family-b"])

            label_to_name = {item["blind_label"]: item["candidate"] for item in pool["candidates"]}
            for index, pair in enumerate(pool["pairs"]):
                left = label_to_name[pair["left_label"]]
                choice = "left" if left == "a.md" else "right"
                result = selection_eval.record_preference(
                    project, SCENE, pool["experiment_id"], f"reader-{index}",
                    "target_reader", "human", pair["pair_id"], choice,
                )
                self.assertNotIn("error", result)
            report = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(report["study_status"], "descriptive_complete")
            self.assertEqual(report["reader_evidence"]["top_by_observed_score"], ["a.md"])

    def test_study_cannot_be_declared_after_reader_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a")
            run_b = _run(project, "b.md", "vendor-b", "writer-b")
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            pair = pool["pairs"][0]
            selection_eval.record_preference(
                project, SCENE, pool["experiment_id"], "reader", "target_reader", "human",
                pair["pair_id"], "left",
            )
            result = writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens",
            )
            self.assertIn("before reader preferences", result["error"])

    def test_missing_cost_stays_unknown_and_large_gap_is_not_called_matched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a", tokens=100)
            run_b = _run(project, "b.md", "vendor-b", "writer-b", tokens=None)
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            self.assertNotIn("error", writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens", max_relative_gap=0.1,
            ))
            report = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(report["study_status"], "incomplete_unknown_matching_cost")
            self.assertIsNone(report["cost_matching"]["within_tolerance"])

        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a", tokens=100)
            run_b = _run(project, "b.md", "vendor-b", "writer-b", tokens=200)
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            self.assertNotIn("error", writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens", max_relative_gap=0.1,
            ))
            report = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(report["study_status"], "cost_not_matched")
            self.assertAlmostEqual(report["cost_matching"]["observed_relative_gap"], 0.5)

    def test_edit_arm_requires_hash_bound_earlier_source_in_same_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            regen_run = _run(project, "a.md", "vendor-a", "writer-a", tokens=200)
            edit_run = run_manifest.start(project, SCENE, [
                {"step_id": "source", "phase": "generation"},
                {"step_id": "edit", "phase": "revision"},
            ])["run_id"]
            source = run_manifest.record_operation(
                project, SCENE, edit_run, "source", "success", candidate="source.md",
                executor_kind="external_model", provider="vendor-b", model="writer-b",
                input_tokens=50, output_tokens=50, total_tokens=100,
            )
            run_manifest.record_operation(
                project, SCENE, edit_run, "edit", "success", candidate="b.md",
                executor_kind="external_model", provider="vendor-b", model="writer-b",
                input_tokens=50, output_tokens=50, total_tokens=100,
            )
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            arms = [
                {"candidate": "a.md", "run_id": regen_run, "writer_family": "family-a",
                 "strategy": "regenerate", "provider": "vendor-a", "model": "writer-a"},
                {"candidate": "b.md", "run_id": edit_run, "writer_family": "family-b",
                 "strategy": "edit", "provider": "vendor-b", "model": "writer-b",
                 "source_candidate_sha256": source["candidate"]["sha256"]},
            ]
            frozen = writer_study.freeze(
                project, SCENE, pool["experiment_id"], arms, ["edit-vs-regeneration"],
                "total_tokens", max_relative_gap=0,
            )
            self.assertNotIn("error", frozen)
            self.assertEqual(writer_study.report(project, SCENE, pool["experiment_id"])["study_status"],
                             "ready_for_reader_evidence")

            bad_project = _project(Path(tmp) / "bad")
            bad_regen = _run(bad_project, "a.md", "vendor-a", "writer-a", tokens=100)
            bad_edit = _run(bad_project, "b.md", "vendor-b", "writer-b", tokens=100)
            bad_pool = selection_eval.freeze_pool(bad_project, SCENE, ["a.md", "b.md"])
            bad_arms = [
                {"candidate": "a.md", "run_id": bad_regen, "writer_family": "family-a",
                 "strategy": "regenerate", "provider": "vendor-a", "model": "writer-a"},
                {"candidate": "b.md", "run_id": bad_edit, "writer_family": "family-b",
                 "strategy": "edit", "provider": "vendor-b", "model": "writer-b"},
            ]
            result = writer_study.freeze(
                bad_project, SCENE, bad_pool["experiment_id"], bad_arms,
                ["edit-vs-regeneration"], "total_tokens",
            )
            self.assertIn("source_candidate_sha256", " ".join(result.get("details", [])))

    def test_provider_model_mismatch_is_rejected_and_tools_are_public(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a")
            run_b = _run(project, "b.md", "vendor-b", "writer-b")
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            arms = _arms(run_a, run_b)
            arms[1]["model"] = "wrong-model"
            result = writer_study.freeze(
                project, SCENE, pool["experiment_id"], arms, ["writer-family"], "total_tokens"
            )
            self.assertIn("provider/model", " ".join(result.get("details", [])))

            # Make the second run genuinely bind the same provider/model so this reaches family-label validation.
            project2 = _project(Path(tmp) / "relabel")
            same_a = _run(project2, "a.md", "vendor-a", "writer-a")
            same_b = _run(project2, "b.md", "vendor-a", "writer-a")
            pool2 = selection_eval.freeze_pool(project2, SCENE, ["a.md", "b.md"])
            relabeled = [
                {"candidate": "a.md", "run_id": same_a, "writer_family": "family-a",
                 "strategy": "independent-draft", "provider": "vendor-a", "model": "writer-a"},
                {"candidate": "b.md", "run_id": same_b, "writer_family": "family-b",
                 "strategy": "independent-draft", "provider": "vendor-a", "model": "writer-a"},
            ]
            result = writer_study.freeze(
                project2, SCENE, pool2["experiment_id"], relabeled, ["writer-family"], "total_tokens"
            )
            self.assertIn("cannot be relabeled", result["error"])

        names = {item["name"] for item in tools.list_tools()}
        self.assertTrue({"freeze_writer_study", "writer_study_report"}.issubset(names))

    def test_run_snapshot_tamper_and_post_freeze_writer_operations_invalidate_study(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a")
            run_b = _run(project, "b.md", "vendor-b", "writer-b")
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            frozen = writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens",
            )
            self.assertNotIn("error", frozen)

            extra = run_manifest.record_operation(
                project, SCENE, run_a, "write", "success", candidate="a.md",
                executor_kind="external_model", provider="vendor-a", model="writer-a",
                input_tokens=1, output_tokens=1, total_tokens=2,
            )
            self.assertNotIn("error", extra)
            changed = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(changed["status"], "invalid")
            self.assertIn("operation set changed", " ".join(changed["errors"]))

        with tempfile.TemporaryDirectory() as tmp:
            project = _project(Path(tmp))
            run_a = _run(project, "a.md", "vendor-a", "writer-a")
            run_b = _run(project, "b.md", "vendor-b", "writer-b")
            pool = selection_eval.freeze_pool(project, SCENE, ["a.md", "b.md"])
            self.assertNotIn("error", writer_study.freeze(
                project, SCENE, pool["experiment_id"], _arms(run_a, run_b), ["writer-family"],
                "total_tokens",
            ))
            snapshot = next((project / ".runs" / "scene-runs" / SCENE / run_a / "candidates").glob("*.md"))
            snapshot.write_text("tampered\n", encoding="utf-8")
            tampered = writer_study.report(project, SCENE, pool["experiment_id"])
            self.assertEqual(tampered["status"], "invalid")
            self.assertIn("snapshot is missing/corrupt", " ".join(tampered["errors"]))


if __name__ == "__main__":
    unittest.main()
