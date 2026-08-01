from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import critique, integrity  # noqa: E402


def _scene(tmp: str):
    """A minimal on-disk scene: a spec, a schema-valid matching delta, and one candidate."""
    root = Path(tmp)
    scene = root / "scenes" / "ch01-sc01"
    (scene / "candidates").mkdir(parents=True)
    (scene / "spec.json").write_text(json.dumps({"id": "ch01-sc01"}), encoding="utf-8")
    (scene / "state-delta.json").write_text(json.dumps({
        "scene_id": "ch01-sc01", "facts_added": [], "facts_removed": [], "knowledge_changes": [],
        "relationship_changes": [], "promises_opened": [], "promises_closed": []}), encoding="utf-8")
    (scene / "candidates" / "candidate-a.md").write_text("Clean prose.", encoding="utf-8")
    return root, scene


_MATERIAL = {"dimension": "cliche", "severity": "material", "evidence": "heart pounded",
             "diagnosis": "stock", "repair_layer": "prose"}


class RecordCritiqueTests(unittest.TestCase):
    def test_stamps_real_sha_and_derives_audit_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, scene = _scene(tmp)
            r = critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "adversarial-reader", "pass")
            self.assertEqual(r["audit_class"], "literary")
            self.assertEqual(r["candidate_sha256"], integrity.sha256_file(scene / "candidates" / "candidate-a.md"))
            data = json.loads((proj / r["written"]).read_text(encoding="utf-8"))
            self.assertEqual(data["candidate"], "candidate-a.md")
            self.assertEqual(data["candidate_sha256"], r["candidate_sha256"])
            self.assertEqual(data["audit_class"], "literary")

    def test_scene_level_hard_audit_has_no_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, _ = _scene(tmp)
            r = critique.record_critique(proj, "ch01-sc01", "ch01-sc01", "hard-audit", "pass")
            self.assertEqual(r["audit_class"], "hard")
            self.assertIsNone(r["candidate_sha256"])

    def test_refuses_pass_carrying_material_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, scene = _scene(tmp)
            r = critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "style-editor", "pass",
                                         findings=[_MATERIAL])
            self.assertIn("error", r)
            self.assertFalse((scene / "critiques").exists())

    def test_invalid_finding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, _ = _scene(tmp)
            r = critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "style-editor", "revise",
                                         findings=[{"dimension": "x", "severity": "material"}])
            self.assertIn("error", r)


class ConsistencyTests(unittest.TestCase):
    def test_pass_with_material_flagged(self) -> None:
        self.assertIsNotNone(critique.consistency_problem("pass", [{"severity": "material"}]))

    def test_clean_pass_ok(self) -> None:
        self.assertIsNone(critique.consistency_problem("pass", []))

    def test_revise_may_carry_material(self) -> None:
        self.assertIsNone(critique.consistency_problem("revise", [{"severity": "material"}]))


class SceneStatusTests(unittest.TestCase):
    def test_reports_gate_reasons_when_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, _ = _scene(tmp)
            st = critique.scene_status(proj, "ch01-sc01", "candidate-a.md")
            self.assertFalse(st["audit_gate"]["ready"])
            joined = " ".join(st["audit_gate"]["reasons"])
            self.assertIn("hard", joined)
            self.assertIn("literary", joined)
            self.assertIn("defaultness", joined)
            self.assertFalse(st["promoted"])

    def test_ready_when_triple_audit_clean_and_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj, _ = _scene(tmp)
            critique.record_critique(proj, "ch01-sc01", "ch01-sc01", "hard-audit", "pass")
            critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "defaultness-lint", "pass")
            critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "adversarial-reader", "pass")
            st = critique.scene_status(proj, "ch01-sc01", "candidate-a.md")
            self.assertTrue(st["audit_gate"]["ready"], st["audit_gate"]["reasons"])
            self.assertEqual(len(st["binding_critiques"]), 3)

    def test_stale_sha_is_not_credited(self) -> None:
        """A critique recorded, then the candidate edited: the gate must stop crediting it."""
        with tempfile.TemporaryDirectory() as tmp:
            proj, scene = _scene(tmp)
            critique.record_critique(proj, "ch01-sc01", "ch01-sc01", "hard-audit", "pass")
            critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "defaultness-lint", "pass")
            critique.record_critique(proj, "ch01-sc01", "candidate-a.md", "adversarial-reader", "pass")
            (scene / "candidates" / "candidate-a.md").write_text("Edited prose after judging.", encoding="utf-8")
            st = critique.scene_status(proj, "ch01-sc01", "candidate-a.md")
            self.assertFalse(st["audit_gate"]["ready"])  # sha no longer matches the judged bytes


if __name__ == "__main__":
    unittest.main()
