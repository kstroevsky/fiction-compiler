from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import acceptance, role_runner, run_manifest, schema, tools  # noqa: E402
from fiction_compiler.role_runner import Assignment  # noqa: E402


def _project(tmp: str) -> Path:
    root = Path(tmp)
    scene = root / "scenes" / "ch01-sc01"
    (scene / "candidates").mkdir(parents=True)
    (scene / "spec.json").write_text(json.dumps({
        "id": "ch01-sc01", "pov": "Jo", "purpose": "a decision",
        "desire": "avoid notice", "conflict": "duty vs. safety", "turn": "Jo stays",
    }), encoding="utf-8")
    (scene / "state-delta.json").write_text(json.dumps({
        "scene_id": "ch01-sc01", "facts_added": [], "facts_removed": [],
        "knowledge_changes": [], "relationship_changes": [],
        "promises_opened": [], "promises_closed": [],
    }), encoding="utf-8")
    (scene / "candidates" / "a.md").write_text("Original candidate bytes.\n", encoding="utf-8")
    return root


STEPS = [
    {"step_id": "generate-a", "phase": "generation"},
    {"step_id": "review-a", "phase": "critique"},
]


class SceneRunManifestTests(unittest.TestCase):
    def test_start_with_explicit_id_is_idempotent_and_conflicts_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = "run-20260928T120000000000Z-aaaaaaaaaaaa"
            first = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 4}, run_id)
            second = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 4}, run_id)
            self.assertFalse(first["resumed"])
            self.assertTrue(second["resumed"])
            self.assertEqual(second["run_id"], run_id)
            conflict = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 5}, run_id)
            self.assertIn("different steps or budgets", conflict["error"])

    def test_failed_attempt_survives_retry_and_idempotent_retry_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run = run_manifest.start(project, "ch01-sc01", STEPS)
            run_id = run["run_id"]
            failed = run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "failure",
                executor_kind="external_model", provider="vendor", model="writer",
                failure_reason="transport timeout", idempotency_key="generate-a:attempt-1",
            )
            self.assertEqual(failed["status"], "failure")
            retry = run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md",
                executor_kind="external_model", provider="vendor", model="writer",
                input_tokens=10, output_tokens=5, cost_usd=0.01,
                idempotency_key="generate-a:attempt-2",
            )
            replay = run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md",
                executor_kind="external_model", provider="vendor", model="writer",
                input_tokens=10, output_tokens=5, cost_usd=0.01,
                idempotency_key="generate-a:attempt-2",
            )
            self.assertTrue(replay["resumed"])
            self.assertEqual(replay["operation_id"], retry["operation_id"])
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(status["operation_count"], 2)
            self.assertIn("generate-a", status["completed_steps"])
            self.assertIn("review-a", status["pending_steps"])
            operation_files = list((project / status["path"] / "operations").glob("*.json"))
            self.assertEqual(len(operation_files), 2)

    def test_candidate_bytes_are_frozen_and_later_mutation_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            op = run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md",
                executor_kind="human", idempotency_key="manual-a",
            )
            frozen = project / ".runs" / "scene-runs" / "ch01-sc01" / run_id / op["candidate"]["snapshot"]
            self.assertEqual(frozen.read_text(encoding="utf-8"), "Original candidate bytes.\n")
            (project / "scenes" / "ch01-sc01" / "candidates" / "a.md").write_text(
                "Mutated later.\n", encoding="utf-8"
            )
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(len(status["stale_candidate_bindings"]), 1)
            self.assertEqual(status["stale_candidate_bindings"][0]["recorded_sha256"], op["candidate"]["sha256"])
            self.assertEqual(frozen.read_text(encoding="utf-8"), "Original candidate bytes.\n")

    def test_unknown_model_usage_is_not_treated_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(
                project, "ch01-sc01", STEPS,
                {"max_total_tokens": 1000, "max_cost_usd": 1.0},
            )["run_id"]
            op = run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md",
                executor_kind="external_model", provider="vendor", model="writer",
            )
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(status["accounting"]["total_tokens"]["known"], 0)
            self.assertEqual(status["accounting"]["total_tokens"]["unknown_operations"], [op["operation_id"]])
            self.assertEqual(status["accounting"]["cost_usd"]["unknown_operations"], [op["operation_id"]])
            self.assertEqual(status["budget"]["gate"], "unknown")

    def test_budget_preflight_blocks_next_operation_at_call_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 1})["run_id"]
            before = run_manifest.check_budget(project, "ch01-sc01", run_id)
            self.assertEqual(before["decision"], "allow")
            run_manifest.record_operation(
                project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md",
                executor_kind="human",
            )
            after = run_manifest.check_budget(project, "ch01-sc01", run_id)
            self.assertEqual(after["decision"], "block")
            self.assertEqual(after["metrics"]["operations"]["projected"], 2)

    def test_budget_preflight_allows_reaching_exact_usage_limit_then_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS, {"max_total_tokens": 10, "max_cost_usd": 1.0})["run_id"]
            before = run_manifest.check_budget(project, "ch01-sc01", run_id, estimated_total_tokens=10, estimated_cost_usd=1.0)
            self.assertEqual(before["decision"], "allow")
            self.assertEqual(before["metrics"]["total_tokens"]["projected_state"], "exhausted")
            run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md", executor_kind="external_model", input_tokens=6, output_tokens=4, total_tokens=10, cost_usd=1.0)
            after = run_manifest.check_budget(project, "ch01-sc01", run_id, estimated_total_tokens=0, estimated_cost_usd=0.0)
            self.assertEqual(after["current_gate"], "block")
            self.assertEqual(after["decision"], "block")

    def test_zero_operation_budget_blocks_and_invalid_estimates_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 0})["run_id"]
            self.assertEqual(run_manifest.check_budget(project, "ch01-sc01", run_id)["decision"], "block")
            self.assertIn("non-negative integer", run_manifest.check_budget(project, "ch01-sc01", run_id, estimated_total_tokens=-1)["error"])
            self.assertIn("finite non-negative number", run_manifest.check_budget(project, "ch01-sc01", run_id, estimated_cost_usd=float("nan"))["error"])

    def test_invalid_usage_and_inconsistent_totals_are_rejected_before_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            run_dir = project / ".runs" / "scene-runs" / "ch01-sc01" / run_id
            bad = run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md", input_tokens=-1)
            self.assertIn("non-negative integer", bad["error"])
            self.assertFalse((run_dir / "candidates").exists())
            self.assertIn("must equal", run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", input_tokens=2, output_tokens=3, total_tokens=6)["error"])
            self.assertIn("finite non-negative number", run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", cost_usd=float("inf"))["error"])

    def test_duplicate_successes_are_preserved_and_counted_as_real_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS, {"max_operations": 3})["run_id"]
            first = run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md", executor_kind="human")
            second = run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md", executor_kind="human")
            self.assertNotEqual(first["operation_id"], second["operation_id"])
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(status["operation_count"], 2)
            self.assertEqual(status["steps"][0]["attempts"], 2)

    def test_unknown_executor_usage_is_unknown_but_human_work_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            unknown = run_manifest.record_operation(project, "ch01-sc01", run_id, "generate-a", "success", candidate="a.md", executor_kind="unknown")
            run_manifest.record_operation(project, "ch01-sc01", run_id, "review-a", "success", executor_kind="human")
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(status["accounting"]["total_tokens"]["unknown_operations"], [unknown["operation_id"]])
            self.assertEqual(status["accounting"]["cost_usd"]["unknown_operations"], [unknown["operation_id"]])

    def test_malformed_role_runner_candidate_hash_is_refused_before_path_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            review_run_id = "b" * 32
            attempt_dir = project / ".runs" / "reviews" / "ch01-sc01"
            attempt_dir.mkdir(parents=True)
            (attempt_dir / f"{review_run_id}.json").write_text(json.dumps({"packet": {"run_id": review_run_id, "scene_id": "ch01-sc01", "candidate": {"sha256": "../../escape"}}, "provider_response": {}, "validation": {"status": "valid"}}), encoding="utf-8")
            linked = run_manifest.link_review_attempt(project, "ch01-sc01", run_id, "review-a", review_run_id, candidate="a.md")
            self.assertIn("valid candidate sha256", linked["error"])

    def test_source_artifact_schema_rejects_project_escape(self) -> None:
        operation = {"schema_version": 1, "run_id": "run-20260928T120000000000Z-aaaaaaaaaaaa", "scene_id": "ch01-sc01", "operation_id": "op-" + "a" * 32, "step_id": "review-a", "phase": "critique", "status": "success", "executor_kind": "role_runner", "source_artifact": {"path": "../escape.json", "sha256": "a" * 64}, "recorded_at": "2026-09-28T12:00:00+00:00"}
        errors = schema.validate_named(operation, "scene-run-operation")
        self.assertTrue(any("source_artifact.path" in error and "pattern" in error for error in errors))

    def test_scene_run_tool_schemas_mirror_scene_id_validation(self) -> None:
        names = {"start_scene_run", "scene_run_status", "scene_run_budget", "record_scene_run_operation", "link_scene_run_review"}
        descriptors = {item["name"]: item for item in tools.list_tools() if item["name"] in names}
        self.assertEqual(set(descriptors), names)
        for descriptor in descriptors.values():
            self.assertEqual(descriptor["inputSchema"]["properties"]["scene_id"].get("pattern"), "^ch[0-9]{2}-sc[0-9]{2}$")

    def test_invalid_manifest_reports_invalid_status_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            manifest = project / ".runs" / "scene-runs" / "ch01-sc01" / run_id / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertEqual(status["status"], "invalid")
            self.assertTrue(status["integrity_errors"])

    def test_role_runner_attempt_is_linked_without_repeating_call_or_losing_usage(self) -> None:
        class MeteredTransport:
            def complete(self, system: str, user: str, model: str, **params: object):
                return role_runner.CompletionResult(
                    text='{"verdict":"pass","confidence":0.9,"findings":[]}',
                    input_tokens=120, output_tokens=30, total_tokens=150,
                    provider_request_id="req-1", response_model="writer-v2", finish_reason="stop",
                )

        roster = {
            "adversarial-reader": Assignment(
                "adversarial-reader", "anthropic", "claude-test",
                persona="You are a blind adversarial reader.",
            )
        }
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            run_id = run_manifest.start(project, "ch01-sc01", STEPS)["run_id"]
            review = role_runner.run_role(
                str(project), "ch01-sc01", "a.md", "adversarial-reader",
                roster=roster, transport=MeteredTransport(), record=False,
            )
            review_run_id = review["provenance"]["run_id"]
            linked = run_manifest.link_review_attempt(
                project, "ch01-sc01", run_id, "review-a", review_run_id, cost_usd=0.04,
            )
            self.assertEqual(linked["executor_kind"], "role_runner")
            self.assertEqual(linked["total_tokens"], 150)
            self.assertEqual(linked["provider_request_id"], "req-1")
            self.assertEqual(linked["cost_usd"], 0.04)
            source = project / linked["source_artifact"]["path"]
            self.assertEqual(acceptance.sha256_bytes(source.read_bytes()), linked["source_artifact"]["sha256"])
            replay = run_manifest.link_review_attempt(
                project, "ch01-sc01", run_id, "review-a", review_run_id, cost_usd=0.04,
            )
            self.assertTrue(replay["resumed"])
            status = run_manifest.status(project, "ch01-sc01", run_id)
            self.assertIn("review-a", status["completed_steps"])
            self.assertEqual(status["accounting"]["total_tokens"]["known"], 150)

    def test_scene_run_cli_can_resume_from_persisted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = _project(tmp)
            script = ROOT / "scripts" / "scene_run.py"
            started = subprocess.run(
                [sys.executable, str(script), "start", "--project", str(project),
                 "--scene", "ch01-sc01", "--step", "generate-a:generation",
                 "--step", "review-a:critique", "--max-operations", "3"],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(started.returncode, 0, started.stderr)
            run_id = json.loads(started.stdout)["run_id"]
            recorded = subprocess.run(
                [sys.executable, str(script), "record", "--project", str(project),
                 "--scene", "ch01-sc01", "--run", run_id, "--step", "generate-a",
                 "--status", "success", "--candidate", "a.md", "--executor-kind", "human",
                 "--idempotency-key", "manual-generation"],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(recorded.returncode, 0, recorded.stderr)
            resumed = subprocess.run(
                [sys.executable, str(script), "status", "--project", str(project),
                 "--scene", "ch01-sc01", "--run", run_id],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            report = json.loads(resumed.stdout)
            self.assertEqual(report["completed_steps"], ["generate-a"])
            self.assertEqual(report["pending_steps"], ["review-a"])


if __name__ == "__main__":
    unittest.main()
