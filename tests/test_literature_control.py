from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import literature_control, tools  # noqa: E402


CONTROL_ID = "joyce-araby-1914"


class LiteratureControlTests(unittest.TestCase):
    def test_araby_control_is_hash_bound_rights_cleared_and_nonempty(self) -> None:
        errors = literature_control.validation_errors(CONTROL_ID)
        self.assertEqual(errors, [])
        report = literature_control.report(CONTROL_ID)
        self.assertEqual(report["status"], "valid", report)
        self.assertEqual(report["full_story_sha256"],
                         "1c1179769c641f4480d537f8fd5a9a8f75a71aa93cde3080b9c3df616248cae9")
        self.assertEqual(len(report["scenes"]), 4)
        self.assertTrue(all(scene["word_count"] > 0 for scene in report["scenes"]))
        self.assertTrue(all(scene["format_probe"]["schema_status"] == "valid"
                            for scene in report["scenes"]))

    def test_current_linter_flags_classic_prose_but_does_not_block_it(self) -> None:
        report = literature_control.report(CONTROL_ID)
        counts = [scene["defaultness"]["finding_count"] for scene in report["scenes"]]
        self.assertEqual(counts, [4, 3, 5, 5])
        self.assertEqual(report["deterministic_lint"]["total_findings"], 17)
        self.assertEqual(report["deterministic_lint"]["blocking_scene_ids"], [])
        self.assertTrue(all(scene["defaultness"]["verdict"] == "pass" for scene in report["scenes"]))
        self.assertTrue(all(
            set(scene["defaultness"]["by_severity"]) <= {"minor"}
            for scene in report["scenes"]
        ))

    def test_story_format_limits_are_manual_and_do_not_claim_unrepresentability(self) -> None:
        report = literature_control.report(CONTROL_ID)
        self.assertEqual(report["segmentation"]["kind"], "editorial-analysis")
        for scene in report["scenes"]:
            assessment = scene["story_format"]
            self.assertEqual(assessment["evidence_kind"], "manual_annotation")
            self.assertEqual(assessment["assessment_kind"], "manual-annotation")
            self.assertEqual(assessment["typed_fit"], "partial")
            self.assertTrue(assessment["not_first_class"])
            self.assertNotIn("cannot represent", assessment["note"].lower())

    def test_critic_evidence_stays_explicitly_unrun(self) -> None:
        report = literature_control.report(CONTROL_ID)
        self.assertEqual(report["evidence_status"], "deterministic_only_critics_unrun")
        self.assertEqual(report["critic_evidence"]["status"], "unrun")
        self.assertIn("No live critic", report["critic_evidence"]["reason"])

    def test_tampered_scene_invalidates_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(literature_control.CONTROL_ROOT / CONTROL_ID, root / CONTROL_ID)
            (root / CONTROL_ID / "scene-02.txt").write_text("tampered", encoding="utf-8")
            result = literature_control.report(CONTROL_ID, controls_root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(any("content hash changed" in error for error in result["errors"]))

    def test_tampered_story_format_probe_invalidates_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(literature_control.CONTROL_ROOT / CONTROL_ID, root / CONTROL_ID)
            spec_path = root / CONTROL_ID / "scene-04.spec.json"
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            spec["turn"] = "A different retrospective claim."
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            result = literature_control.report(CONTROL_ID, controls_root=root)
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(any("spec probe content hash changed" in error for error in result["errors"]))

    def test_generic_gutenberg_corpus_cannot_authorize_full_text_control(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(literature_control.CONTROL_ROOT / CONTROL_ID, root / CONTROL_ID)
            manifest_path = root / CONTROL_ID / "control.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_id"] = "gutenberg"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = literature_control.validation_errors(CONTROL_ID, controls_root=root)
            self.assertTrue(any("not cleared for EU/DE" in error for error in errors))
            self.assertTrue(any("does not allow full-text" in error for error in errors))

    def test_tool_registry_exposes_read_only_control_report(self) -> None:
        descriptors = {item["name"]: item for item in tools.list_tools()}
        self.assertIn("literature_control_report", descriptors)
        schema = descriptors["literature_control_report"]["inputSchema"]
        self.assertEqual(schema["required"], ["control_id"])


if __name__ == "__main__":
    unittest.main()
