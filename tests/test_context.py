from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.context import compile_bundle  # noqa: E402


def build(root: Path) -> Path:
    project = root / "proj"
    canon = project / "canon"
    (canon / "characters").mkdir(parents=True)
    (canon / "characters" / "char-x.json").write_text(json.dumps({"id": "char-x"}), encoding="utf-8")
    (canon / "facts.jsonl").write_text(
        json.dumps({"id": "fact-known", "text": "needed"}) + "\n"
        + json.dumps({"id": "fact-bg", "text": "background"}) + "\n", encoding="utf-8")
    (canon / "knowledge-state.jsonl").write_text(
        json.dumps({"character": "char-x", "fact": "fact-known"}) + "\n", encoding="utf-8")
    (canon / "index.json").write_text(json.dumps({"accepted_state_deltas": [], "world_rules": ["a world rule"]}), encoding="utf-8")
    scene = project / "scenes" / "ch01-sc01"
    scene.mkdir(parents=True)
    scene.joinpath("spec.json").write_text(json.dumps({
        "id": "ch01-sc01", "pov": "char-x", "participants": ["char-x"],
        "knowledge_required": [{"character": "char-x", "fact": "fact-known"}]}), encoding="utf-8")
    return project


class ContextManifestTests(unittest.TestCase):
    def test_manifest_marks_reason_priority_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = compile_bundle(build(Path(tmp)), "ch01-sc01")
            manifest = {(m["kind"], m["ref"]): m for m in bundle["context_manifest"]}
            self.assertEqual(manifest[("character", "char-x")]["priority"], "required")
            self.assertEqual(manifest[("fact", "fact-known")]["priority"], "required")
            self.assertEqual(manifest[("fact", "fact-bg")]["priority"], "background")
            self.assertEqual(manifest[("world_rule", "a world rule")]["priority"], "reference")
            # every entry carries a reason + a source
            self.assertTrue(all(m.get("reason") and m.get("source") for m in bundle["context_manifest"]))


if __name__ == "__main__":
    unittest.main()
