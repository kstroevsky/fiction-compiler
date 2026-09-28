from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import reader, tools  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def build(root: Path) -> Path:
    project = root / "proj"
    write_json(project / "brief" / "project.json", {
        "id": "proj",
        "reader_contract": ["single focalizer", "ambiguity survives"],
    })
    (project / "canon").mkdir(parents=True)
    (project / "canon" / "facts.jsonl").write_text(
        json.dumps({"id": "fact-clue", "text": "The latch is scratched."}) + "\n", encoding="utf-8")
    for sid in ("ch01-sc01", "ch01-sc02"):
        scene = project / "scenes" / sid
        scene.mkdir(parents=True)
        write_json(scene / "state-delta.json", {
            "scene_id": sid,
            "facts_added": ([{"id": "fact-answer", "text": "The door was forced."}]
                            if sid == "ch01-sc02" else []),
        })
    return project


class ContractCoverageTests(unittest.TestCase):
    def test_missing_artifact_preserves_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = reader.contract_coverage(build(Path(tmp)))
            self.assertEqual(report["status"], "missing")
            self.assertEqual(report["untested"], 2)
            self.assertEqual(report["verification"], "not_assessed")

    def test_mapped_and_explicit_untested_are_distinct_from_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            write_json(project / "brief" / "contract-coverage.json", {
                "project_id": "proj",
                "clauses": [
                    {"text": "single focalizer", "coverage": [
                        {"kind": "deterministic-check", "ref": "prose_audit:pov"}]},
                    {"text": "ambiguity survives", "coverage": [],
                     "untested_reason": "Needs a reader interpretation probe."},
                ],
            })
            report = reader.contract_coverage(project)
            self.assertEqual(report["status"], "declared", report["errors"])
            self.assertEqual((report["mapped"], report["untested"]), (1, 1))
            self.assertEqual(report["verification"], "not_assessed")

    def test_missing_clause_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            write_json(project / "brief" / "contract-coverage.json", {
                "project_id": "proj",
                "clauses": [{"text": "single focalizer", "coverage": [],
                             "untested_reason": "Not bound yet."}],
            })
            report = reader.contract_coverage(project)
            self.assertEqual(report["status"], "invalid")
            self.assertTrue(any("no coverage declaration" in error for error in report["errors"]))


class ReaderDisclosureTests(unittest.TestCase):
    def test_valid_fair_play_and_curiosity_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            write_json(project / "planning" / "reader-disclosure.json", {
                "project_id": "proj",
                "disclosures": [
                    {"id": "disclosure-scratch", "fact": "fact-clue", "scene_id": "ch01-sc01", "mode": "implied"}
                ],
                "curiosity_gaps": [
                    {"id": "gap-door", "question": "Who forced the door?", "opened_in": "ch01-sc01", "closed_in": "ch01-sc02"}
                ],
                "surprises": [
                    {"id": "surprise-door", "reveal_scene": "ch01-sc02", "requires_setup": True,
                     "setup_disclosures": ["disclosure-scratch"]}
                ],
            })
            report = reader.disclosure_report(project)
            self.assertEqual(report["status"], "valid", report["errors"])
            self.assertEqual(report["verification"], "structural_only")

    def test_unplanted_or_withheld_surprise_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            write_json(project / "planning" / "reader-disclosure.json", {
                "project_id": "proj",
                "disclosures": [
                    {"id": "disclosure-hidden", "fact": "fact-clue", "scene_id": "ch01-sc01", "mode": "withheld"}
                ],
                "curiosity_gaps": [],
                "surprises": [
                    {"id": "surprise-door", "reveal_scene": "ch01-sc02", "requires_setup": True,
                     "setup_disclosures": ["disclosure-hidden"]},
                    {"id": "surprise-none", "reveal_scene": "ch01-sc02", "requires_setup": True,
                     "setup_disclosures": []},
                ],
            })
            report = reader.disclosure_report(project)
            self.assertEqual(report["status"], "invalid")
            self.assertTrue(any("withheld disclosure" in error for error in report["errors"]))
            self.assertTrue(any("names no setup" in error for error in report["errors"]))

    def test_tool_registry_exposes_reader_reports(self) -> None:
        names = {item["name"] for item in tools.list_tools()}
        self.assertIn("contract_coverage", names)
        self.assertIn("reader_disclosure", names)


if __name__ == "__main__":
    unittest.main()
