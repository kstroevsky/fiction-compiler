from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.promote import promote_candidate  # noqa: E402


def build(root: Path) -> Path:
    project = root / "proj"
    scene = project / "scenes" / "ch01-sc01"
    (scene / "candidates").mkdir(parents=True)
    (scene / "critiques").mkdir(parents=True)
    (scene / "candidates" / "c.md").write_text("Prose.", encoding="utf-8")
    (scene / "spec.json").write_text(json.dumps({"id": "ch01-sc01"}), encoding="utf-8")
    (scene / "critiques" / "hard.json").write_text(json.dumps({"critic": "hard-audit"}), encoding="utf-8")
    (project / "canon").mkdir(parents=True)
    (project / "canon" / "index.json").write_text(json.dumps({"accepted_state_deltas": []}), encoding="utf-8")
    return project


def valid_delta() -> dict:
    return {
        "scene_id": "ch01-sc01", "facts_added": [], "facts_removed": [],
        "knowledge_changes": [], "relationship_changes": [], "promises_opened": [], "promises_closed": [],
    }


class PromoteTests(unittest.TestCase):
    def test_happy_path_updates_manuscript_and_canon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "scenes" / "ch01-sc01" / "state-delta.json").write_text(json.dumps(valid_delta()))
            result = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertTrue((project / "manuscript" / "chapters" / "ch01-sc01.md").exists())
            self.assertEqual(result["accepted_state_deltas"], ["ch01-sc01"])
            index = json.loads((project / "canon" / "index.json").read_text())
            self.assertIn("ch01-sc01", index["accepted_state_deltas"])
            self.assertTrue((project / "decisions" / "promote-ch01-sc01.json").exists())

    def test_missing_state_delta_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            with self.assertRaises(ValueError):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_missing_critique_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            for f in (project / "scenes" / "ch01-sc01" / "critiques").glob("*.json"):
                f.unlink()
            (project / "scenes" / "ch01-sc01" / "state-delta.json").write_text(json.dumps(valid_delta()))
            with self.assertRaises(ValueError):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_invalid_delta_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            bad = valid_delta()
            del bad["promises_closed"]  # violates schema
            (project / "scenes" / "ch01-sc01" / "state-delta.json").write_text(json.dumps(bad))
            with self.assertRaises(ValueError):
                promote_candidate(project, "ch01-sc01", "c.md")


if __name__ == "__main__":
    unittest.main()
