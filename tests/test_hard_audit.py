from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import hard_audit  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj) -> None:
    write(path, json.dumps(obj))


def base_project(root: Path, accepted: list[str]) -> Path:
    project = root / "proj"
    write_json(project / "canon" / "characters" / "char-mara.json", {"id": "char-mara"})
    write_json(project / "canon" / "characters" / "char-jonas.json", {"id": "char-jonas"})
    write_json(project / "planning" / "event-graph.json", {"events": [{"id": "evt-relay-cut"}], "edges": []})
    write(project / "canon" / "facts.jsonl", "")
    write(project / "canon" / "knowledge-state.jsonl", "")
    write(project / "canon" / "relationship-state.jsonl", "")
    write(project / "canon" / "promises.jsonl", "")
    write(project / "canon" / "timeline.jsonl", json.dumps({"time": 0}) + "\n")
    write_json(project / "canon" / "index.json", {"accepted_state_deltas": accepted})
    return project


def clean_deltas(project: Path) -> None:
    write_json(project / "scenes" / "ch01-sc01" / "state-delta.json", {
        "scene_id": "ch01-sc01", "time": 1,
        "facts_added": [{"id": "fact-relay-cut", "text": "Relay cut by hand."}],
        "facts_removed": [], "knowledge_changes": [{"character": "char-mara", "fact": "fact-relay-cut"}],
        "relationship_changes": [], "promises_opened": [{"id": "promise-who", "text": "Who cut it?"}],
        "promises_closed": [],
    })
    write_json(project / "scenes" / "ch01-sc02" / "state-delta.json", {
        "scene_id": "ch01-sc02", "time": 2,
        "facts_added": [{"id": "fact-confession", "text": "Jonas confesses."}],
        "facts_removed": [], "knowledge_changes": [{"character": "char-mara", "fact": "fact-confession"}],
        "relationship_changes": [], "promises_opened": [], "promises_closed": ["promise-who"],
    })


class HardAuditSceneTests(unittest.TestCase):
    def test_clean_scene_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01", "ch01-sc02"])
            clean_deltas(project)
            write_json(project / "scenes" / "ch01-sc02" / "spec.json", {
                "id": "ch01-sc02", "pov": "char-mara", "participants": ["char-mara", "char-jonas"],
                "required_events": ["evt-relay-cut"],
                "knowledge_required": [{"character": "char-mara", "fact": "fact-relay-cut"}],
            })
            critique = hard_audit.audit_scene(project, "ch01-sc02")
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

    def test_knowledge_cutoff_detects_future_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01", "ch01-sc02"])
            clean_deltas(project)
            # Requires knowledge of a fact this same scene introduces -> leak from the future.
            write_json(project / "scenes" / "ch01-sc02" / "spec.json", {
                "id": "ch01-sc02", "pov": "char-mara", "participants": ["char-mara"],
                "required_events": [],
                "knowledge_required": [{"character": "char-mara", "fact": "fact-confession"}],
            })
            critique = hard_audit.audit_scene(project, "ch01-sc02")
            self.assertEqual(critique["verdict"], "reject")
            self.assertTrue(hard_audit.has_fatal(critique))
            self.assertTrue(any(f["dimension"] == "knowledge" for f in critique["findings"]))

    def test_undefined_pov_and_missing_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01"])
            clean_deltas(project)
            write_json(project / "scenes" / "ch01-sc01" / "spec.json", {
                "id": "ch01-sc01", "pov": "char-ghost", "participants": ["char-nobody"],
                "required_events": ["evt-does-not-exist"], "knowledge_required": [],
            })
            critique = hard_audit.audit_scene(project, "ch01-sc01")
            dims = {f["dimension"] for f in critique["findings"]}
            self.assertIn("character", dims)
            self.assertIn("causal", dims)


class HardAuditCanonTests(unittest.TestCase):
    def test_clean_canon_only_flags_nothing_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01", "ch01-sc02"])
            clean_deltas(project)
            critique = hard_audit.audit_canon(project)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

    def test_backward_time_and_unopened_promise_and_ghost_fact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01", "ch01-sc02"])
            write_json(project / "scenes" / "ch01-sc01" / "state-delta.json", {
                "scene_id": "ch01-sc01", "time": 5,
                "facts_added": [], "facts_removed": [],
                "knowledge_changes": [{"character": "char-mara", "fact": "fact-nonexistent"}],
                "relationship_changes": [], "promises_opened": [], "promises_closed": ["promise-never-opened"],
            })
            write_json(project / "scenes" / "ch01-sc02" / "state-delta.json", {
                "scene_id": "ch01-sc02", "time": 2,  # backward from 5
                "facts_added": [], "facts_removed": [], "knowledge_changes": [],
                "relationship_changes": [], "promises_opened": [], "promises_closed": [],
            })
            critique = hard_audit.audit_canon(project)
            dims = {f["dimension"] for f in critique["findings"]}
            self.assertIn("temporal", dims)   # time ran backward
            self.assertIn("promise", dims)     # closed a promise never opened
            self.assertIn("knowledge", dims)   # learned a fact that does not exist
            self.assertEqual(critique["verdict"], "revise")

    def test_open_promise_reported_as_minor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = base_project(Path(tmp), ["ch01-sc01"])
            write_json(project / "scenes" / "ch01-sc01" / "state-delta.json", {
                "scene_id": "ch01-sc01", "time": 1,
                "facts_added": [], "facts_removed": [], "knowledge_changes": [],
                "relationship_changes": [], "promises_opened": [{"id": "promise-dangling", "text": "unpaid"}],
                "promises_closed": [],
            })
            critique = hard_audit.audit_canon(project)
            self.assertTrue(any(f["dimension"] == "promise" and f["severity"] == "minor"
                                for f in critique["findings"]))


if __name__ == "__main__":
    unittest.main()
