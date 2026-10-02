from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import framework_change, tools  # noqa: E402


def _root(tmp: str) -> tuple[Path, Path]:
    root = Path(tmp)
    project = root / "projects" / "demo"
    project.mkdir(parents=True)
    (root / "config").mkdir(parents=True)
    (root / "config" / "policy.json").write_text('{"mode":"before"}\n', encoding="utf-8")
    (root / "src" / "fiction_compiler").mkdir(parents=True)
    (root / "src" / "fiction_compiler" / "placeholder.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "regression").mkdir(parents=True)
    (root / "regression" / "fixtures.json").write_text(json.dumps({
        "fixtures": [{
            "name": "clean baseline",
            "check": "defaultness_verdict",
            "input": {"text": "The relay lay open."},
            "expect": "pass",
        }]
    }), encoding="utf-8")
    return root, project


def _start(root: Path, project: Path, **overrides) -> dict:
    kwargs = dict(
        title="Test process change",
        failure_observed="The same process defect recurred in several scenes.",
        evidence=["scene-a finding", "scene-b finding"],
        root_layer="process",
        minimal_change="Change the test policy fixture.",
        regression_case="The clean baseline regression remains green.",
        blind_comparison_plan="Compare one before/after output without revealing which is which.",
        tradeoffs=["May overfit the local cases."],
        changed_paths=["config/policy.json"],
        proposed_by="agent-1",
        proposer_kind="agent",
        minimum_observations=1,
        minimum_after_wins=1,
        maximum_before_wins=0,
        root=root,
    )
    kwargs.update(overrides)
    return framework_change.start(project, **kwargs)


def _after_label(project: Path, change_id: str, comparison_id: str) -> str:
    path = project / ".runs" / "framework-changes" / change_id / "comparisons" / f"{comparison_id}.json"
    private = json.loads(path.read_text(encoding="utf-8"))
    return next(label for label, meaning in private["label_map"].items() if meaning == "after")


class FrameworkChangeTests(unittest.TestCase):
    def test_full_transaction_requires_blind_evidence_and_human_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            started = _start(root, project)
            self.assertNotIn("error", started)
            change_id = started["change_id"]

            (root / "config" / "policy.json").write_text('{"mode":"after"}\n', encoding="utf-8")
            evaluated = framework_change.evaluate(project, change_id, root=root)
            self.assertTrue(evaluated["mechanically_ready"])
            self.assertEqual(evaluated["unexpected_framework_paths"], [])

            packet = framework_change.prepare_comparison(
                project, change_id, objective="Which output better satisfies the reader contract?",
                before_output="Before output", after_output="After output", prepared_by="agent-1", root=root)
            self.assertNotIn("label_map", packet)
            self.assertEqual(set(packet["outputs"]), {"A", "B"})
            preferred = _after_label(project, change_id, packet["comparison_id"])
            evidence = framework_change.record_comparison(
                project, change_id, packet["comparison_id"], evaluator_kind="model",
                evaluator_id="independent-judge", preferred=preferred, rationale="After is clearer.")
            self.assertEqual(evidence["outcome"], "after")

            status = framework_change.status(project, change_id, root=root)
            self.assertTrue(status["ready_for_human_decision"])
            rejected_agent = framework_change.decide(
                project, change_id, decision="approve", decided_by="agent-2", decider_kind="agent",
                reason="self approval", root=root)
            self.assertIn("error", rejected_agent)
            decision = framework_change.decide(
                project, change_id, decision="approve", decided_by="human-owner", decider_kind="human",
                reason="Blind evidence and regression floor support adoption.", root=root)
            self.assertEqual(decision["decision"], "approve")

    def test_undeclared_framework_change_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            extra = root / ".agents" / "skills" / "x" / "SKILL.md"
            extra.parent.mkdir(parents=True)
            extra.write_text("before\n", encoding="utf-8")
            started = _start(root, project)
            (root / "config" / "policy.json").write_text('{"mode":"after"}\n', encoding="utf-8")
            extra.write_text("after\n", encoding="utf-8")
            evaluated = framework_change.evaluate(project, started["change_id"], root=root)
            self.assertFalse(evaluated["mechanically_ready"])
            self.assertEqual(evaluated["unexpected_framework_paths"], [".agents/skills/x/SKILL.md"])

    def test_agent_self_comparison_does_not_satisfy_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            started = _start(root, project)
            change_id = started["change_id"]
            (root / "config" / "policy.json").write_text('{"mode":"after"}\n', encoding="utf-8")
            framework_change.evaluate(project, change_id, root=root)
            packet = framework_change.prepare_comparison(
                project, change_id, objective="blind quality", before_output="before",
                after_output="after", prepared_by="agent-1", root=root)
            preferred = _after_label(project, change_id, packet["comparison_id"])
            result = framework_change.record_comparison(
                project, change_id, packet["comparison_id"], evaluator_kind="model",
                evaluator_id="agent-1", preferred=preferred, rationale="I prefer my revision.")
            self.assertFalse(result["independent_of_agent_proposer"])
            status = framework_change.status(project, change_id, root=root)
            self.assertEqual(status["comparison"]["observations"], 0)
            self.assertFalse(status["ready_for_human_decision"])

    def test_rollback_restores_exact_bytes_and_deletes_new_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            before = (root / "config" / "policy.json").read_bytes()
            started = _start(
                root, project, changed_paths=["config/policy.json", "config/new-policy.json"])
            change_id = started["change_id"]
            (root / "config" / "policy.json").write_text('{"mode":"after"}\n', encoding="utf-8")
            (root / "config" / "new-policy.json").write_text('{"new":true}\n', encoding="utf-8")
            evaluated = framework_change.evaluate(project, change_id, root=root)
            self.assertTrue(evaluated["mechanically_ready"])
            rolled = framework_change.rollback(
                project, change_id, decided_by="human-owner", decider_kind="human",
                reason="Experiment rejected",
                confirm=True, root=root)
            self.assertTrue(rolled["baseline_restored"])
            self.assertTrue(rolled["regression_ok"])
            self.assertEqual((root / "config" / "policy.json").read_bytes(), before)
            self.assertFalse((root / "config" / "new-policy.json").exists())

    def test_rollback_refuses_to_clobber_post_evaluation_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            started = _start(root, project)
            change_id = started["change_id"]
            target = root / "config" / "policy.json"
            target.write_text('{"mode":"after"}\n', encoding="utf-8")
            framework_change.evaluate(project, change_id, root=root)
            target.write_text('{"mode":"later-edit"}\n', encoding="utf-8")
            result = framework_change.rollback(
                project, change_id, decided_by="human-owner", decider_kind="human",
                reason="reject", confirm=True, root=root)
            self.assertIn("error", result)
            self.assertIn("changed after", result["error"])
            self.assertIn("later-edit", target.read_text(encoding="utf-8"))

    def test_rollback_requires_human_decider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            started = _start(root, project)
            change_id = started["change_id"]
            (root / "config" / "policy.json").write_text('{"mode":"after"}\n', encoding="utf-8")
            framework_change.evaluate(project, change_id, root=root)
            result = framework_change.rollback(
                project, change_id, decided_by="agent-2", decider_kind="agent",
                reason="self rollback", confirm=True, root=root)
            self.assertIn("human decider", result["error"])

    def test_start_requires_clean_baseline_and_at_least_one_blind_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            bad_policy = _start(root, project, minimum_observations=0, minimum_after_wins=0)
            self.assertIn("error", bad_policy)
            fixtures = root / "regression" / "fixtures.json"
            data = json.loads(fixtures.read_text())
            data["fixtures"][0]["expect"] = "revise"
            fixtures.write_text(json.dumps(data), encoding="utf-8")
            bad_baseline = _start(root, project)
            self.assertIn("baseline regression is not clean", bad_baseline["error"])

    def test_start_rejects_non_framework_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, project = _root(tmp)
            result = _start(root, project, changed_paths=["docs/notes.md"])
            self.assertIn("behavior-relevant framework files", result["error"])

    def test_tool_registry_exposes_framework_transaction_workflow(self) -> None:
        names = {item["name"] for item in tools.list_tools()}
        self.assertTrue({
            "start_framework_change", "evaluate_framework_change", "prepare_framework_comparison",
            "framework_comparison_packet", "record_framework_comparison", "framework_change_status",
            "decide_framework_change", "rollback_framework_change",
        } <= names)


if __name__ == "__main__":
    unittest.main()
