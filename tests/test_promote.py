from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.promote import promote_candidate  # noqa: E402


def _critique(**fields) -> str:
    base = {"candidate": "c.md", "critic": "style-editor", "verdict": "pass",
            "findings": [], "confidence": 0.9}
    base.update(fields)
    return json.dumps(base)


def write_full_audit_set(scene: Path, candidate_name: str = "c.md") -> None:
    """A complete, clean triple audit (hard + literary + defaultness) that clears the candidate."""
    crit = scene / "critiques"
    # Hard audit is candidate-independent: its `candidate` is the scene id.
    (crit / "hard-audit.json").write_text(
        _critique(candidate="ch01-sc01", critic="hard-audit"), encoding="utf-8")
    (crit / "style-editor.json").write_text(
        _critique(candidate=candidate_name, critic="style-editor"), encoding="utf-8")
    (crit / "defaultness-lint.json").write_text(
        _critique(candidate=candidate_name, critic="defaultness-lint"), encoding="utf-8")


def build(root: Path, *, audits: bool = True) -> Path:
    project = root / "proj"
    scene = project / "scenes" / "ch01-sc01"
    (scene / "candidates").mkdir(parents=True)
    (scene / "critiques").mkdir(parents=True)
    (scene / "candidates" / "c.md").write_text("Prose.", encoding="utf-8")
    (scene / "spec.json").write_text(json.dumps({"id": "ch01-sc01"}), encoding="utf-8")
    if audits:
        write_full_audit_set(scene)
    else:
        # A lone empty critique — the shape the *old* gate accepted.
        (scene / "critiques" / "hard.json").write_text(json.dumps({"critic": "hard-audit"}), encoding="utf-8")
    (project / "canon").mkdir(parents=True)
    (project / "canon" / "index.json").write_text(json.dumps({"accepted_state_deltas": []}), encoding="utf-8")
    return project


def valid_delta() -> dict:
    return {
        "scene_id": "ch01-sc01", "facts_added": [], "facts_removed": [],
        "knowledge_changes": [], "relationship_changes": [], "promises_opened": [], "promises_closed": [],
    }


def with_delta(project: Path) -> Path:
    (project / "scenes" / "ch01-sc01" / "state-delta.json").write_text(json.dumps(valid_delta()))
    return project


class PromoteTests(unittest.TestCase):
    def test_happy_path_updates_manuscript_and_canon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            result = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertTrue((project / "manuscript" / "chapters" / "ch01-sc01.md").exists())
            self.assertEqual(result["accepted_state_deltas"], ["ch01-sc01"])
            index = json.loads((project / "canon" / "index.json").read_text())
            self.assertIn("ch01-sc01", index["accepted_state_deltas"])
            decision = json.loads((project / "decisions" / "promote-ch01-sc01.json").read_text())
            classes = {b["audit_class"] for b in decision["binding_critiques"]}
            self.assertEqual(classes, {"hard", "literary", "defaultness"})

    def test_missing_state_delta_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            with self.assertRaises(ValueError):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_missing_critique_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            for f in (project / "scenes" / "ch01-sc01" / "critiques").glob("*.json"):
                f.unlink()
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

    # --- audit-gate enforcement ------------------------------------------------------------------

    def test_lone_empty_critique_no_longer_promotes(self) -> None:
        """The exact shape the old gate accepted (one bare critique) must now be refused."""
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp), audits=False))
            with self.assertRaises(ValueError):
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertFalse((project / "manuscript").exists(), "a rejected promotion must not write")

    def test_critiques_for_other_candidate_are_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            crit = project / "scenes" / "ch01-sc01" / "critiques"
            # Literary + defaultness now judge a *different* candidate; only the scene-level hard binds.
            crit.joinpath("style-editor.json").write_text(
                _critique(candidate="other.md", critic="style-editor"), encoding="utf-8")
            crit.joinpath("defaultness-lint.json").write_text(
                _critique(candidate="other.md", critic="defaultness-lint"), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("literary", str(ctx.exception))
            self.assertIn("defaultness", str(ctx.exception))

    def test_pass_verdict_with_material_finding_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            (project / "scenes" / "ch01-sc01" / "critiques" / "defaultness-lint.json").write_text(
                _critique(candidate="c.md", critic="defaultness-lint", verdict="pass",
                          findings=[{"dimension": "cliche", "severity": "material",
                                     "evidence": "heart pounded", "diagnosis": "default phrasing",
                                     "repair_layer": "prose"}]),
                encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("contradicts", str(ctx.exception))

    def test_revise_verdict_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            (project / "scenes" / "ch01-sc01" / "critiques" / "style-editor.json").write_text(
                _critique(candidate="c.md", critic="style-editor", verdict="revise"), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("unresolved", str(ctx.exception))

    def test_missing_defaultness_audit_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            (project / "scenes" / "ch01-sc01" / "critiques" / "defaultness-lint.json").unlink()
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("defaultness", str(ctx.exception))


class CommittedExampleRegressionTests(unittest.TestCase):
    """The committed examples violate the triple-audit protocol; the gate must now catch them.

    These run against a *copy* of the real project so the committed evidence stays untouched and
    is exercised exactly as it sits on disk. If someone later retrofits the examples to pass the
    gate honestly, these tests should be updated alongside that change.
    """

    def _copy_project(self, tmp: str, slug: str) -> Path:
        dest = Path(tmp) / slug
        shutil.copytree(ROOT / "projects" / slug, dest)
        return dest

    def test_salt_sc02_rejected_wrong_candidate_and_missing_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_project(tmp, "salt-in-the-wire")
            # candidate-b was "promoted", but 3 of its 4 critiques judge candidate-a and there is
            # no hard or defaultness audit for the scene at all.
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc02", "candidate-b.md")
            msg = str(ctx.exception)
            self.assertIn("hard", msg)
            self.assertIn("defaultness", msg)

    def test_verbatim_sc01_rejected_missing_literary_and_defaultness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._copy_project(tmp, "verbatim")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "candidate-a.md")
            msg = str(ctx.exception)
            self.assertIn("literary", msg)
            self.assertIn("defaultness", msg)


if __name__ == "__main__":
    unittest.main()
