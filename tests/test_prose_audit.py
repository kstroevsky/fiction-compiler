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

    def test_world_fact_added_this_scene_is_not_automatic_pov_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta = json.loads(delta_path.read_text())
            delta["facts_added"] = [{"id": "fact-new", "text": "The relay is broken."}]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")
            critique = audit_prose(
                project, "ch01-sc01",
                claims(c("focalizer_knows", subject="char-x", object="fact-new")),
            )
            self.assertIn("knowledge", dims(critique))

    def test_false_belief_can_be_represented_without_becoming_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta = json.loads(delta_path.read_text())
            delta["propositions_defined"] = [{"id": "fact-door-open", "text": "The door is open."}]
            delta["belief_changes"] = [{
                "op": "set", "character": "char-x", "fact": "fact-door-open",
                "value": True, "source": "testimony"
            }]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")

            belief = audit_prose(
                project, "ch01-sc01",
                claims(c("focalizer_believes", subject="char-x", object="fact-door-open", value=True)),
            )
            self.assertEqual(belief["verdict"], "pass", belief["findings"])

            knowledge = audit_prose(
                project, "ch01-sc01",
                claims(c("focalizer_knows", subject="char-x", object="fact-door-open")),
            )
            self.assertIn("knowledge", dims(knowledge))

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

    def test_missing_event_alignment_is_uncertain_not_omission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-turn"]
            spec_path.write_text(json.dumps(spec))
            critique = audit_prose(project, "ch01-sc01", claims())
            self.assertEqual(critique["verdict"], "uncertain")
            self.assertEqual(critique["realization"]["required_events"], [
                {"event_id": "evt-turn", "status": "unverified"}
            ])
            self.assertNotIn("realization", dims(critique))

    def test_explicit_omission_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-turn"]
            spec_path.write_text(json.dumps(spec))
            cl = claims()
            cl["event_alignment"] = [{"event_id": "evt-turn", "status": "omitted",
                                      "note": "No corresponding action in extraction."}]
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "revise")
            self.assertIn("realization", dims(critique))

    def test_discourse_event_reference_has_separate_realization_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["event_references"] = ["evt-memory"]
            spec_path.write_text(json.dumps(spec))
            cl = claims()
            cl["observed_events"] = [{
                "id": "observed-memory", "description": "A prior event is recalled.",
                "evidence": "prose evidence", "consequential": False,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-memory", "status": "realized", "observed_id": "observed-memory",
            }]
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])
            self.assertEqual(critique["realization"]["event_references"], [
                {"event_id": "evt-memory", "status": "realized", "observed_id": "observed-memory"}
            ])

    def test_oblique_realization_passes_when_alignment_is_evidence_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            candidate = project / "scenes" / "ch01-sc01" / "candidates" / "candidate-a.md"
            candidate.parent.mkdir()
            candidate.write_text("She turned the cup upside down and left it there.", encoding="utf-8")
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-refusal"]
            spec_path.write_text(json.dumps(spec))
            text = candidate.read_text(encoding="utf-8")
            import hashlib
            cl = claims(wc=len(text.split()))
            cl["candidate"] = "candidate-a.md"
            cl["candidate_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            cl["observed_events"] = [{
                "id": "observed-cup", "description": "She refuses by inverting the cup.",
                "evidence": "She turned the cup upside down", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-refusal", "status": "realized", "observed_id": "observed-cup",
            }]
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])
            self.assertEqual(critique["realization"]["required_events"][0]["status"], "realized")

    def test_unaligned_consequential_event_is_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cl = claims()
            cl["observed_events"] = [{
                "id": "observed-breaks-door", "description": "A door is broken.",
                "evidence": "prose evidence", "consequential": True,
            }]
            critique = self._audit(tmp, cl)
            self.assertEqual(critique["verdict"], "pass")
            self.assertIn("observed-breaks-door", critique["realization"]["unplanned_consequential"])
            self.assertTrue(any(f["dimension"] == "realization" and f["severity"] == "minor"
                                for f in critique["findings"]))

    def test_realized_alignment_must_resolve_to_observed_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cl = claims()
            cl["event_alignment"] = [{
                "event_id": "evt-turn", "status": "realized", "observed_id": "observed-missing",
            }]
            result = self._audit(tmp, cl)
            self.assertIn("unknown observed event", result["error"])


if __name__ == "__main__":
    unittest.main()
