from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import state  # noqa: E402


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_delta(project: Path, scene_id: str, delta: dict) -> None:
    write(project / "scenes" / scene_id / "state-delta.json", json.dumps(delta))


def build_project(root: Path) -> Path:
    project = root / "proj"
    canon = project / "canon"
    # Seed: one pre-existing fact, one seed relationship, opening time.
    write(canon / "facts.jsonl", json.dumps({"id": "fact-tide-table-exists", "text": "A tide table hangs in the office."}) + "\n")
    write(canon / "knowledge-state.jsonl", "")
    write(canon / "relationship-state.jsonl", json.dumps({"pair": ["char-mara", "char-jonas"], "state": "colleagues"}) + "\n")
    write(canon / "promises.jsonl", "")
    write(canon / "timeline.jsonl", json.dumps({"time": 0, "label": "story opens"}) + "\n")
    write(canon / "index.json", json.dumps({"accepted_state_deltas": ["ch01-sc01", "ch01-sc02"]}))

    write_delta(project, "ch01-sc01", {
        "scene_id": "ch01-sc01",
        "time": 1,
        "facts_added": [{"id": "fact-relay-cut", "text": "The relay was cut by hand."}],
        "facts_removed": [],
        "knowledge_changes": [{"character": "char-mara", "fact": "fact-relay-cut"}],
        "relationship_changes": [{"pair": ["char-mara", "char-jonas"], "state": "wary"}],
        "promises_opened": [{"id": "promise-who-cut-it", "text": "Who cut the relay?"}],
        "promises_closed": [],
    })
    write_delta(project, "ch01-sc02", {
        "scene_id": "ch01-sc02",
        "time": 2,
        "facts_added": [{"id": "fact-jonas-confesses", "text": "Jonas admits he cut it."}],
        "facts_removed": [],
        "knowledge_changes": [{"character": "char-mara", "fact": "fact-jonas-confesses"}],
        "relationship_changes": [],
        "promises_opened": [],
        "promises_closed": ["promise-who-cut-it"],
    })
    return project


class StateReconstructionTests(unittest.TestCase):
    def test_before_scene_two_has_scene_one_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            before = state.reconstruct_state_before(project, "ch01-sc02")
            # Scene one's effects are present:
            self.assertTrue(before.fact_exists("fact-relay-cut"))
            self.assertTrue(before.knows("char-mara", "fact-relay-cut"))
            self.assertEqual(before.relationship("char-mara", "char-jonas"), "wary")
            self.assertTrue(before.promise_is_open("promise-who-cut-it"))
            self.assertEqual(before.time, 1)

    def test_no_future_knowledge_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            before = state.reconstruct_state_before(project, "ch01-sc02")
            # Scene two's fact/knowledge must NOT leak backward:
            self.assertFalse(before.fact_exists("fact-jonas-confesses"))
            self.assertFalse(before.knows("char-mara", "fact-jonas-confesses"))
            self.assertTrue(before.promise_is_open("promise-who-cut-it"))  # not yet closed

    def test_full_history_closes_promise_and_advances_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            final = state.reconstruct(project)
            self.assertTrue(final.fact_exists("fact-jonas-confesses"))
            self.assertFalse(final.promise_is_open("promise-who-cut-it"))
            self.assertIn("promise-who-cut-it", final.closed_promises)
            self.assertEqual(final.time, 2)
            self.assertEqual(final.applied_scenes, ["ch01-sc01", "ch01-sc02"])

    def test_seed_only_before_first_scene(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build_project(Path(tmp))
            before = state.reconstruct_state_before(project, "ch01-sc01")
            self.assertTrue(before.fact_exists("fact-tide-table-exists"))
            self.assertFalse(before.fact_exists("fact-relay-cut"))
            self.assertEqual(before.relationship("char-mara", "char-jonas"), "colleagues")
            self.assertEqual(before.time, 0)


if __name__ == "__main__":
    unittest.main()
