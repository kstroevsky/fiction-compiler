from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.prose_audit import audit_prose  # noqa: E402


def build(root: Path) -> Path:
    project = root / "proj"
    canon = project / "canon"
    (canon / "characters").mkdir(parents=True)
    for cid in ("char-x", "char-y"):
        (canon / "characters" / f"{cid}.json").write_text(json.dumps({"id": cid}), encoding="utf-8")
    (canon / "facts.jsonl").write_text(json.dumps({"id": "fact-known", "text": "k"}) + "\n"
                                       + json.dumps({"id": "fact-future", "text": "f"}) + "\n", encoding="utf-8")
    (canon / "knowledge-state.jsonl").write_text(json.dumps({"character": "char-x", "fact": "fact-known"}) + "\n", encoding="utf-8")
    (canon / "world-state.jsonl").write_text(json.dumps({"predicate": "located_at", "subject": "char-x", "object": "loc-a"}) + "\n", encoding="utf-8")
    (canon / "index.json").write_text(json.dumps({"accepted_state_deltas": []}), encoding="utf-8")
    (project / "planning").mkdir()
    (project / "planning" / "discourse-plan.json").write_text(json.dumps({"time": {"tense": "past"}}), encoding="utf-8")
    scene = project / "scenes" / "ch01-sc01"
    scene.mkdir(parents=True)
    scene.joinpath("spec.json").write_text(json.dumps({"id": "ch01-sc01", "pov": "char-x", "participants": ["char-x"]}), encoding="utf-8")
    scene.joinpath("state-delta.json").write_text(json.dumps({
        "scene_id": "ch01-sc01", "facts_added": [], "facts_removed": [], "knowledge_changes": [],
        "relationship_changes": [], "promises_opened": [], "promises_closed": []}), encoding="utf-8")
    return project


def claims(*items, pov="char-x", tense="past", wc=100) -> dict:
    return {"scene_id": "ch01-sc01", "pov": pov, "tense": tense, "word_count": wc, "claims": list(items)}


def c(ctype, evidence="prose evidence", **kw) -> dict:
    return {"type": ctype, "evidence": evidence, **kw}


def dims(critique) -> set:
    return {f["dimension"] for f in critique["findings"] if f["severity"] in ("material", "fatal")}


class ProseAuditTests(unittest.TestCase):
    def _audit(self, tmp, cl):
        return audit_prose(build(Path(tmp)), "ch01-sc01", cl)

    def test_consistent_prose_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cl = claims(
                c("character_present", subject="char-x"),
                c("focalizer_knows", subject="char-x", object="fact-known"),
                c("located_at", subject="char-x", object="loc-a"))
            critique = self._audit(tmp, cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

    def test_knowledge_leak_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("focalizer_knows", subject="char-x", object="fact-future")))
            self.assertIn("knowledge", dims(critique))

    def test_unplanned_character_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("character_present", subject="char-z")))  # not in canon
            self.assertIn("continuity", dims(critique))

    def test_declared_canon_char_but_not_participant_is_minor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("character_present", subject="char-y")))  # in canon, not a participant
            self.assertEqual(critique["verdict"], "pass")  # only a minor
            self.assertTrue(any(f["severity"] == "minor" for f in critique["findings"]))

    def test_head_hopping_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("interiority_of", subject="char-y")))
            self.assertIn("pov", dims(critique))

    def test_tense_break_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(tense="present"))
            self.assertIn("tense", dims(critique))

    def test_spatial_contradiction_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("located_at", subject="char-x", object="loc-b")))
            self.assertIn("continuity", dims(critique))

    def test_unrecorded_promise_closure_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("closes_promise", ref="promise-p")))
            self.assertIn("promise", dims(critique))


if __name__ == "__main__":
    unittest.main()
