from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import plan_search, tools  # noqa: E402
from fiction_compiler.context import compile_bundle  # noqa: E402


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value), encoding="utf-8")


def build_project(root: Path) -> Path:
    project = root / "plan-search"
    _write(project / "brief" / "project.json", {
        "id": "plan-search", "title": "Plan Search", "form": "short-story",
        "audience": "adult", "reader_contract": ["Causal pressure"],
    })
    _write(project / "canon" / "index.json", {"accepted_state_deltas": []})
    _write(project / "canon" / "facts.jsonl", "")
    _write(project / "canon" / "knowledge-state.jsonl", "")
    _write(project / "canon" / "relationship-state.jsonl", "")
    _write(project / "canon" / "world-state.jsonl", "")
    _write(project / "canon" / "promises.jsonl", "")
    _write(project / "canon" / "timeline.jsonl", "")
    _write(project / "planning" / "event-graph.json", {
        "events": [
            {"id": "evt-a", "preconditions": [], "effects": []},
            {"id": "evt-b", "preconditions": [], "effects": []},
            {"id": "evt-c", "preconditions": [], "effects": []},
        ]
    })
    _write(project / "scenes" / "ch01-sc01" / "spec.json", {
        "id": "ch01-sc01", "chapter": "One", "pov": "char-a", "participants": ["char-a"],
        "purpose": ["force a choice"], "entry_state": ["waiting"], "desire": "leave",
        "conflict": "the door is watched", "turn": "the watcher leaves", "exit_state": ["committed"],
        "required_events": [], "forbidden_moves": ["miracle escape"], "knowledge_required": [],
    })
    _write(project / "canon" / "characters" / "char-a.json", {
        "id": "char-a", "name": "A", "role": "protagonist", "wants": ["leave"],
        "needs": ["choose"], "fears": ["capture"], "misbeliefs": [], "voice_markers": [],
        "knowledge": [], "relationships": []
    })
    return project


def plan(plan_id: str, *, tactic: str, turn: str, cost: str, learns: str,
         event: str = "evt-a") -> dict:
    return {
        "plan_id": plan_id,
        "title": plan_id.replace("plan-", "").title(),
        "tactic": tactic,
        "turn": turn,
        "cost": cost,
        "reader_learns": [learns],
        "required_events": [event],
        "knowledge_required": [],
        "forbidden_moves": ["miracle escape"],
        "easy_solution_checks": [{
            "solution": "walk out openly",
            "available_information": "A sees the watcher",
            "capability": "A can walk but cannot outrun security",
            "cost": "capture would end the attempt",
            "motive": "A wants to leave without exposing the ally",
        }],
    }


def record_three(project: Path) -> list[str]:
    values = [
        plan("plan-decoy", tactic="stage a decoy", turn="the watcher follows it",
             cost="lose the ally's trust", learns="the watcher is personally invested", event="evt-a"),
        plan("plan-bargain", tactic="offer a bargain", turn="the watcher names a price",
             cost="owe the watcher a favor", learns="the watcher wants leverage", event="evt-b"),
        plan("plan-wait", tactic="wait for shift change", turn="the replacement knows A",
             cost="miss the safe train", learns="the net is wider than expected", event="evt-c"),
    ]
    for value in values:
        result = plan_search.record_plan(project, "ch01-sc01", value)
        if "error" in result:
            raise AssertionError(result["error"])
    return [value["plan_id"] for value in values]


def pass_review(project: Path, plan_id: str) -> dict:
    return plan_search.record_review(
        project, "ch01-sc01", plan_id, "narrative-architect", "pass",
        easy_solution_assessments=[{
            "solution": "walk out openly", "verdict": "supported_conflict",
            "reason": "capture risk and ally exposure make the obvious route costly",
        }],
    )


class PlanSearchTests(unittest.TestCase):
    def test_three_distinct_hard_feasible_plans_clear_search_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            record_three(project)
            status = plan_search.search_status(project, "ch01-sc01")
            self.assertTrue(status["diversity_floor"]["ok"])
            self.assertEqual(len(status["hard_feasible_plan_ids"]), 3)
            self.assertFalse(status["review_complete"])
            self.assertFalse(status["ready_for_selection"])

    def test_relabelled_plan_batch_does_not_fake_search_width(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            base = plan("plan-one", tactic="wait", turn="door opens", cost="time",
                        learns="the guard is late")
            for plan_id in ("plan-one", "plan-two", "plan-three"):
                value = dict(base)
                value["plan_id"] = plan_id
                self.assertNotIn("error", plan_search.record_plan(project, "ch01-sc01", value))
            status = plan_search.search_status(project, "ch01-sc01")
            self.assertFalse(status["diversity_floor"]["ok"])
            self.assertIn("relabeling", " ".join(status["diversity_floor"]["issues"]))

    def test_missing_event_is_a_hard_plan_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            result = plan_search.record_plan(
                project, "ch01-sc01",
                plan("plan-bad", tactic="trigger alarm", turn="help arrives", cost="exposure",
                     learns="the alarm is monitored", event="evt-missing"),
            )
            self.assertNotIn("error", result)
            status = plan_search.search_status(project, "ch01-sc01")
            audit = status["plans"][0]["hard_audit"]
            self.assertEqual(audit["verdict"], "revise")
            self.assertTrue(any("absent" in f["diagnosis"] for f in audit["findings"]))

    def test_plan_review_packet_is_plan_aware_and_contains_no_prose_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            record_three(project)
            packet = tools.plan_review_packet(str(project), "ch01-sc01", "plan-decoy")
            self.assertEqual(packet["plan_id"], "plan-decoy")
            self.assertIn("why don't they just", " ".join(packet["review_questions"]).lower())
            self.assertIn("no candidate prose", packet["boundary"].lower())
            self.assertNotIn("selected_scene_plans", packet["context"])
            self.assertNotIn("accepted_prefix", packet)

    def test_selection_requires_reviewed_batch_and_binds_selected_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            plan_ids = record_three(project)
            early = plan_search.select_plans(project, "ch01-sc01", [plan_ids[0]], "owner", "best fit")
            self.assertIn("error", early)

            for plan_id in plan_ids:
                review = pass_review(project, plan_id)
                self.assertNotIn("error", review)

            status = plan_search.search_status(project, "ch01-sc01")
            self.assertTrue(status["ready_for_selection"])
            selected = plan_search.select_plans(
                project, "ch01-sc01", ["plan-decoy", "plan-bargain"],
                "owner", "keep two materially different realizations",
            )
            self.assertNotIn("error", selected)
            self.assertEqual(len(selected["selected_plans"]), 2)
            current = plan_search.search_status(project, "ch01-sc01")["latest_selection"]
            self.assertEqual(current["status"], "current")
            bundle = compile_bundle(project, "ch01-sc01")
            self.assertEqual(
                {item["plan_id"] for item in bundle["selected_scene_plans"]},
                {"plan-decoy", "plan-bargain"},
            )

    def test_stale_plan_review_and_selection_are_exposed_not_silently_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            plan_ids = record_three(project)
            for plan_id in plan_ids:
                self.assertNotIn("error", pass_review(project, plan_id))
            selected = plan_search.select_plans(
                project, "ch01-sc01", ["plan-decoy"], "owner", "chosen before spec change"
            )
            self.assertNotIn("error", selected)

            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["desire"] = "leave before dawn"
            _write(spec_path, spec)

            status = plan_search.search_status(project, "ch01-sc01")
            self.assertEqual(status["hard_feasible_plan_ids"], [])
            self.assertEqual(status["latest_selection"]["status"], "stale_or_invalid")
            self.assertEqual(compile_bundle(project, "ch01-sc01")["selected_scene_plans"], [])

    def test_plan_review_must_cover_easy_solutions_and_cannot_pass_unsupported_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            record_three(project)
            missing = plan_search.record_review(
                project, "ch01-sc01", "plan-decoy", "narrative-architect", "pass"
            )
            self.assertIn("assess every easy-solution", missing["error"])
            unsupported = plan_search.record_review(
                project, "ch01-sc01", "plan-decoy", "narrative-architect", "pass",
                easy_solution_assessments=[{
                    "solution": "walk out openly", "verdict": "unsupported_conflict",
                    "reason": "the plan gives no reason A cannot simply leave",
                }],
            )
            self.assertIn("cannot pass", unsupported["error"])

    def test_tool_registry_exposes_plan_search_workflow(self) -> None:
        names = {item["name"] for item in tools.list_tools()}
        self.assertTrue({
            "record_scene_plan", "scene_plan_search", "plan_review_packet",
            "record_plan_review", "select_scene_plans",
        }.issubset(names))


if __name__ == "__main__":
    unittest.main()
