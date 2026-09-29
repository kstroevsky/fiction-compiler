from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import repertoire, tools  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_project(root: Path, project_id: str, complete: bool, ending: str) -> Path:
    project = root / project_id
    write_json(project / "brief" / "project.json", {"id": project_id})
    write_json(project / "planning" / "discourse-plan.json", {
        "chapter_map": [{"chapter": "1", "scenes": ["ch01-sc01", "ch01-sc02"]}]
    })
    chapters = project / "manuscript" / "chapters"
    chapters.mkdir(parents=True)
    (chapters / "ch01-sc01.md").write_text("one", encoding="utf-8")
    if complete:
        (chapters / "ch01-sc02.md").write_text("two", encoding="utf-8")
    write_json(project / "planning" / "story-repertoire.json", {
        "project_id": project_id,
        "evidence_basis": "complete-manuscript" if complete else "partial-manuscript",
        "complete_story": complete,
        "features": {
            "ending_form_tags": [ending] if complete else [],
            "turn_tags": ["choice"],
            "resolution_tags": ["open"] if complete else [],
            "object_motifs": ["door"],
            "focalization_tags": ["fixed-internal"],
        },
    })
    return project


class RepertoireTests(unittest.TestCase):
    def test_report_counts_complete_stories_and_excludes_partial_prefixes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projects = Path(tmp)
            make_project(projects, "alpha", True, "small-physical-act")
            make_project(projects, "beta", True, "small-physical-act")
            make_project(projects, "gamma", False, "unused")
            report = repertoire.report(projects)
            self.assertEqual(report["status"], "valid", report["errors"])
            self.assertEqual(report["complete_projects_included"], ["alpha", "beta"])
            self.assertEqual(report["partial_projects_excluded"], ["gamma"])
            repeated = {(item["dimension"], item["tag"]): item for item in report["repeated_features"]}
            self.assertEqual(repeated[("ending_form_tags", "small-physical-act")]["count"], 2)
            self.assertEqual(repeated[("ending_form_tags", "small-physical-act")]["prevalence"], 1.0)

    def test_false_completeness_claim_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp), "alpha", False, "unused")
            data = json.loads((project / "planning" / "story-repertoire.json").read_text())
            data["complete_story"] = True
            data["evidence_basis"] = "complete-manuscript"
            data["features"]["ending_form_tags"] = ["small-physical-act"]
            data["features"]["resolution_tags"] = ["open"]
            write_json(project / "planning" / "story-repertoire.json", data)
            result = repertoire.annotation(project)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(any("does not match manuscript chapter coverage" in error for error in result["errors"]))

    def test_repository_report_preserves_partial_project_and_observed_repetition(self) -> None:
        report = repertoire.report(ROOT / "projects")
        self.assertEqual(report["status"], "valid", report["errors"])
        self.assertEqual(set(report["complete_projects_included"]), {
            "forecourt", "slack-water", "the-overnight", "verbatim", "visiting-order",
        })
        self.assertEqual(report["partial_projects_excluded"], ["salt-in-the-wire"])
        repeated = {(item["dimension"], item["tag"]): item for item in report["repeated_features"]}
        self.assertEqual(repeated[("ending_form_tags", "small-physical-act")]["count"], 5)
        self.assertEqual(repeated[("focalization_tags", "fixed-internal")]["count"], 5)

    def test_tool_registry_exposes_repertoire_report(self) -> None:
        names = {item["name"] for item in tools.list_tools()}
        self.assertIn("repertoire_report", names)


if __name__ == "__main__":
    unittest.main()
