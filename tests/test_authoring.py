from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import authoring  # noqa: E402


def project_data(slug: str) -> dict:
    return {
        "id": slug,
        "title": "MCP Smoke Story",
        "form": "short-story",
        "audience": "adult general reader",
        "reader_contract": ["A consequential choice under uncertainty."],
        "theme_question": "What does care require when certainty is unavailable?",
        "desired_affect": ["tension"],
        "constraints": ["single viewpoint"],
        "human_gates": [],
    }


def character() -> dict:
    return {
        "id": "char-jo",
        "name": "Jo",
        "desire": "Get through the shift without making the wrong irreversible choice.",
        "values": ["care", "caution"],
        "beliefs": ["Uncertainty does not remove responsibility."],
        "constraints": ["She cannot safely leave the kiosk."],
        "voice": {"lexicon": ["concrete"], "syntax": ["plain"], "avoid": ["aphorisms"]},
    }


def scene_spec() -> dict:
    return {
        "id": "ch01-sc01",
        "chapter": "1",
        "pov": "char-jo",
        "participants": ["char-jo"],
        "purpose": ["Force Jo to choose under incomplete information."],
        "entry_state": ["Jo is alone on shift."],
        "desire": "Keep herself safe while deciding whether to help.",
        "conflict": "Helping requires accepting a risk she cannot measure.",
        "turn": "A detail makes inaction carry its own cost.",
        "exit_state": ["Jo commits to an action."],
        "required_events": [],
        "forbidden_moves": ["No omniscient confirmation of danger."],
    }


def state_delta() -> dict:
    return {
        "scene_id": "ch01-sc01",
        "facts_added": [],
        "facts_removed": [],
        "knowledge_changes": [],
        "relationship_changes": [],
        "promises_opened": [],
        "promises_closed": [],
        "time": 1,
    }


class AuthoringTests(unittest.TestCase):
    def make_project(self, root: Path, slug: str = "mcp-smoke") -> Path:
        authoring.create_project(
            slug,
            project_data=project_data(slug),
            creative_brief="# Creative brief\n\nKeep the moral uncertainty live.",
            projects_root=root,
        )
        return root / slug

    def test_create_project_rebinds_all_template_project_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            self.assertEqual(json.loads((project / "brief" / "project.json").read_text())["id"], "mcp-smoke")
            for rel in (
                "brief/contract-coverage.json",
                "planning/reader-disclosure.json",
                "planning/reader-probes.json",
                "planning/story-repertoire.json",
            ):
                self.assertEqual(json.loads((project / rel).read_text())["project_id"], "mcp-smoke", rel)
            overview = authoring.project_overview(project)
            self.assertEqual(overview["project"]["title"], "MCP Smoke Story")
            self.assertIn("moral uncertainty", overview["creative_brief"])

    def test_character_scene_delta_and_candidate_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            authoring.write_character(project, character())
            index = json.loads((project / "canon" / "index.json").read_text())
            self.assertIn("char-jo", index["characters"])

            authoring.write_scene_spec(project, "ch01-sc01", scene_spec())
            authoring.write_state_delta(project, "ch01-sc01", state_delta())
            saved = authoring.write_candidate(
                project, "ch01-sc01", "candidate-a.md",
                "Jo kept one hand below the counter and slid the first-aid packet through the drawer.",
            )
            self.assertEqual(len(saved["sha256"]), 64)
            loaded = authoring.get_candidate(project, "ch01-sc01", "candidate-a.md")
            self.assertIn("first-aid packet", loaded["text"])
            self.assertEqual(loaded["sha256"], saved["sha256"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                authoring.write_candidate(project, "ch01-sc01", "candidate-a.md", "replacement")

    def test_seed_canon_freezes_after_first_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            result = authoring.write_seed_ledger(
                project, "facts", [{"id": "fact-alone", "text": "Jo is alone on shift."}],
            )
            self.assertEqual(result["records"], 1)
            index_path = project / "canon" / "index.json"
            index = json.loads(index_path.read_text())
            index["accepted_state_deltas"] = ["ch01-sc01"]
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable"):
                authoring.write_seed_ledger(project, "facts", [])

    def test_project_artifact_guards_identity_and_acceptance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            with self.assertRaisesRegex(ValueError, "project id"):
                authoring.write_project_artifact(project, "project", project_data("wrong-id"))
            with self.assertRaisesRegex(ValueError, "protected fields"):
                authoring.write_project_artifact(
                    project, "canon_index", {"accepted_state_deltas": ["ch01-sc01"]},
                )
            result = authoring.write_project_artifact(
                project, "canon_index", {"world_rules": ["The kiosk stays locked overnight."]},
            )
            self.assertEqual(result["value"]["world_rules"], ["The kiosk stays locked overnight."])

    def test_accepted_scene_inputs_are_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            authoring.write_scene_spec(project, "ch01-sc01", scene_spec())
            authoring.write_state_delta(project, "ch01-sc01", state_delta())
            index_path = project / "canon" / "index.json"
            index = json.loads(index_path.read_text())
            index["accepted_state_deltas"] = ["ch01-sc01"]
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "immutable"):
                authoring.write_scene_spec(project, "ch01-sc01", scene_spec(), overwrite=True)
            with self.assertRaisesRegex(ValueError, "immutable"):
                authoring.write_state_delta(project, "ch01-sc01", state_delta(), overwrite=True)


if __name__ == "__main__":
    unittest.main()
