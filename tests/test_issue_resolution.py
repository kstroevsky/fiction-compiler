from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import acceptance, critique, issue_resolution, revision  # noqa: E402
from fiction_compiler.promote import promote_candidate  # noqa: E402
from tests.test_promote import build  # noqa: E402


FINDING = {
    "dimension": "agency",
    "severity": "material",
    "evidence": "she simply agreed",
    "diagnosis": "the choice is passive",
    "repair_layer": "scene",
}


def _source_review(project: Path, candidate: str) -> tuple[str, str]:
    result = critique.record_critique(
        project, "ch01-sc01", candidate, "adversarial-reader", "revise", findings=[FINDING]
    )
    assert "error" not in result, result
    return Path(result["written"]).name, issue_resolution.finding_id(FINDING)


class IssueResolutionTests(unittest.TestCase):
    def test_predecessor_finding_requires_bound_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            scene = project / "scenes" / "ch01-sc01"
            (scene / "candidates" / "old.md").write_text("She simply agreed.", encoding="utf-8")
            source_file, fid = _source_review(project, "old.md")
            revision.log_revision(scene, {
                "before": "old.md", "after": "c.md", "target_dimension": "agency",
                "decision": "accept", "reason": "fixture lineage",
            })

            with self.assertRaisesRegex(ValueError, "predecessor finding"):
                promote_candidate(project, "ch01-sc01", "c.md")

            recorded = issue_resolution.record_resolution(
                project, "ch01-sc01", "c.md", source_file, fid,
                "predecessor", "applies", "resolved", "choice rewritten on-page", "editor@test",
            )
            self.assertNotIn("error", recorded)
            result = promote_candidate(project, "ch01-sc01", "c.md")
            snapshot = acceptance.load_object(project, result["acceptance_object"])
            self.assertEqual(len(snapshot["issue_resolutions"]), 1)
            pair = snapshot["issue_resolutions"][0]
            self.assertIn("issue-resolution@1", pair["resolution"]["text"])
            self.assertIn(source_file, pair["source_critique"]["path"])

    def test_sibling_finding_requires_explicit_applicability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            scene = project / "scenes" / "ch01-sc01"
            (scene / "candidates" / "sibling.md").write_text("She simply agreed.", encoding="utf-8")
            source_file, fid = _source_review(project, "sibling.md")

            with self.assertRaisesRegex(ValueError, "sibling finding"):
                promote_candidate(project, "ch01-sc01", "c.md")

            recorded = issue_resolution.record_resolution(
                project, "ch01-sc01", "c.md", source_file, fid,
                "sibling", "does_not_apply", "adjudicated",
                "target uses a different decision structure", "editor@test",
            )
            self.assertNotIn("error", recorded)
            self.assertFalse(recorded.get("error"))
            promote_candidate(project, "ch01-sc01", "c.md")

    def test_resolution_is_invalidated_when_source_critique_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            scene = project / "scenes" / "ch01-sc01"
            (scene / "candidates" / "sibling.md").write_text("She simply agreed.", encoding="utf-8")
            source_file, fid = _source_review(project, "sibling.md")
            issue_resolution.record_resolution(
                project, "ch01-sc01", "c.md", source_file, fid,
                "sibling", "does_not_apply", "adjudicated", "different branch", "editor@test",
            )
            path = scene / "critiques" / source_file
            data = json.loads(path.read_text())
            data["confidence"] = 0.5
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "lacks an exact"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_predecessor_cannot_be_declared_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            scene = project / "scenes" / "ch01-sc01"
            (scene / "candidates" / "old.md").write_text("She simply agreed.", encoding="utf-8")
            source_file, fid = _source_review(project, "old.md")
            revision.log_revision(scene, {"before": "old.md", "after": "c.md"})
            result = issue_resolution.record_resolution(
                project, "ch01-sc01", "c.md", source_file, fid,
                "predecessor", "does_not_apply", "adjudicated", "attempt", "editor@test",
            )
            self.assertIn("must be marked", result["error"])


if __name__ == "__main__":
    unittest.main()
