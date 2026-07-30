from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import integrity  # noqa: E402
from fiction_compiler.promote import promote_candidate  # noqa: E402

PROSE = "Prose."
PROSE_SHA = hashlib.sha256(PROSE.encode("utf-8")).hexdigest()


def _critique(**fields) -> str:
    base = {"candidate": "c.md", "critic": "style-editor", "verdict": "pass",
            "findings": [], "confidence": 0.9}
    base.update(fields)
    return json.dumps(base)


def write_full_audit_set(scene: Path, candidate_name: str = "c.md", *, sha: str = PROSE_SHA) -> None:
    """A complete, clean triple audit (hard + literary + defaultness) that clears the candidate.

    Candidate-specific critiques carry the candidate's sha256; the hard audit is scene-level.
    """
    crit = scene / "critiques"
    (crit / "hard-audit.json").write_text(
        _critique(candidate="ch01-sc01", critic="hard-audit"), encoding="utf-8")
    (crit / "style-editor.json").write_text(
        _critique(candidate=candidate_name, critic="style-editor", candidate_sha256=sha), encoding="utf-8")
    (crit / "defaultness-lint.json").write_text(
        _critique(candidate=candidate_name, critic="defaultness-lint", candidate_sha256=sha), encoding="utf-8")


def build(root: Path, *, audits: bool = True) -> Path:
    project = root / "proj"
    scene = project / "scenes" / "ch01-sc01"
    (scene / "candidates").mkdir(parents=True)
    (scene / "critiques").mkdir(parents=True)
    (scene / "candidates" / "c.md").write_text(PROSE, encoding="utf-8")
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
                _critique(candidate="c.md", critic="defaultness-lint", candidate_sha256=PROSE_SHA,
                          verdict="pass",
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
                _critique(candidate="c.md", critic="style-editor", candidate_sha256=PROSE_SHA,
                          verdict="revise"), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("unresolved", str(ctx.exception))

    def test_critique_with_wrong_hash_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            # A critique that claims to judge c.md but carries a different candidate's hash.
            (project / "scenes" / "ch01-sc01" / "critiques" / "defaultness-lint.json").write_text(
                _critique(candidate="c.md", critic="defaultness-lint",
                          candidate_sha256=hashlib.sha256(b"different bytes").hexdigest()),
                encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("does not match", str(ctx.exception))

    def test_unhashed_literary_critique_does_not_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            # Same critique, but with the hash stripped: it can no longer be credited as evidence.
            (project / "scenes" / "ch01-sc01" / "critiques" / "style-editor.json").write_text(
                _critique(candidate="c.md", critic="style-editor"), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("literary", str(ctx.exception))

    def test_missing_defaultness_audit_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            (project / "scenes" / "ch01-sc01" / "critiques" / "defaultness-lint.json").unlink()
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("defaultness", str(ctx.exception))


class PromotionIntegrityTests(unittest.TestCase):
    """Slice 2 (ADR 0003): tamper-evidence, the acceptance manifest, locking, and atomicity."""

    def test_decision_records_acceptance_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            result = promote_candidate(project, "ch01-sc01", "c.md")
            decision = json.loads((project / "decisions" / "promote-ch01-sc01.json").read_text())
            self.assertEqual(decision["candidate_sha256"], PROSE_SHA)
            self.assertTrue(decision["state_delta_sha256"])
            self.assertEqual(decision["parent_canon_hash"], integrity.seed_hash(project))
            self.assertEqual(decision["resulting_canon_hash"], result["resulting_canon_hash"])
            self.assertTrue(all("sha256" in b for b in decision["binding_critiques"]))

    def test_verify_canon_clean_then_detects_delta_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            promote_candidate(project, "ch01-sc01", "c.md")
            self.assertEqual(integrity.verify_canon(project), [])
            # Silently rewrite the accepted delta; the recorded canon hash no longer matches.
            delta = project / "scenes" / "ch01-sc01" / "state-delta.json"
            tampered = json.loads(delta.read_text())
            tampered["facts_added"] = [{"id": "fact-x", "text": "smuggled in after acceptance"}]
            delta.write_text(json.dumps(tampered))
            errors = integrity.verify_canon(project)
            self.assertTrue(any("changed since promotion" in e for e in errors), errors)

    def test_lock_blocks_concurrent_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            (project / ".promote.lock").write_text("")  # a promotion already holds the lock
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("in progress", str(ctx.exception))

    def test_rollback_leaves_no_partial_state_on_commit_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            import os
            real_replace = os.replace
            calls = {"n": 0}

            def flaky(src, dst):  # fail on the third write (the decision manifest)
                calls["n"] += 1
                if calls["n"] == 3:
                    raise RuntimeError("simulated crash mid-commit")
                return real_replace(src, dst)

            with mock.patch("fiction_compiler.integrity.os.replace", side_effect=flaky):
                with self.assertRaises(RuntimeError):
                    promote_candidate(project, "ch01-sc01", "c.md")
            self.assertFalse((project / "manuscript" / "chapters" / "ch01-sc01.md").exists())
            index = json.loads((project / "canon" / "index.json").read_text())
            self.assertEqual(index["accepted_state_deltas"], [])
            self.assertFalse((project / ".promote.lock").exists(), "lock must be released")

    def test_candidate_outside_project_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))
            outside = Path(tmp) / "outside.md"
            outside.write_text(PROSE, encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", str(outside))
            self.assertIn("inside the project", str(ctx.exception))


class HumanGateTests(unittest.TestCase):
    """ADR 0012: a project can require a recorded human approver at promotion."""

    def _gated_project(self, root: Path) -> Path:
        project = with_delta(build(root))
        (project / "brief").mkdir(parents=True)
        (project / "brief" / "project.json").write_text(
            json.dumps({"id": "proj", "human_gates": ["promotion"]}), encoding="utf-8")
        return project

    def test_gated_promotion_refused_without_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._gated_project(Path(tmp))
            with self.assertRaises(ValueError) as ctx:
                promote_candidate(project, "ch01-sc01", "c.md")
            self.assertIn("human gate", str(ctx.exception))
            self.assertFalse((project / "manuscript").exists())

    def test_gated_promotion_records_approver_and_rubric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._gated_project(Path(tmp))
            promote_candidate(project, "ch01-sc01", "c.md",
                              approved_by="editor@example", rubric_version="literary-rubric@1")
            decision = json.loads((project / "decisions" / "promote-ch01-sc01.json").read_text())
            self.assertEqual(decision["human_gate"],
                             {"required": True, "approved": True, "approver": "editor@example"})
            self.assertEqual(decision["rubric_version"], "literary-rubric@1")

    def test_ungated_project_promotes_without_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = with_delta(build(Path(tmp)))  # no brief/project.json -> no promotion gate
            result = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertEqual(result["accepted_state_deltas"], ["ch01-sc01"])
            decision = json.loads((project / "decisions" / "promote-ch01-sc01.json").read_text())
            self.assertEqual(decision["human_gate"]["required"], False)


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
