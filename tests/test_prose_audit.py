from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.prose_audit import audit_prose, prose_claim_bindings  # noqa: E402


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


def bind_candidate(project: Path, cl: dict, text: str, name: str = "candidate-a.md") -> dict:
    candidate = project / "scenes" / "ch01-sc01" / "candidates" / name
    candidate.parent.mkdir(exist_ok=True)
    candidate.write_text(text, encoding="utf-8")
    cl["candidate"] = name
    cl["word_count"] = len(text.split())
    cl.update(prose_claim_bindings(project, "ch01-sc01", name))
    for item in [*cl.get("claims", []), *cl.get("observed_events", [])]:
        evidence = item["evidence"]
        start = text.index(evidence)
        item["evidence_span"] = {"start": start, "end": start + len(evidence)}
    return cl


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
                "value": True, "source": "testimony", "at_event": "evt-rumor"
            }]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")
            (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
                "id": "evt-rumor", "preconditions": [], "effects": [{
                    "op": "add", "predicate": "believes", "subject": "char-x",
                    "object": "fact-door-open", "value": True,
                }],
            }]}), encoding="utf-8")
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-rumor"]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")

            text = "Mira said the door was open. She believed her."
            belief_claims = claims(c(
                "focalizer_believes", evidence="She believed her.",
                subject="char-x", object="fact-door-open", value=True,
            ))
            belief_claims["observed_events"] = [{
                "id": "observed-rumor", "description": "Mira says the door is open.",
                "evidence": "Mira said the door was open.", "consequential": True,
            }]
            belief_claims["event_alignment"] = [{
                "event_id": "evt-rumor", "status": "realized", "observed_id": "observed-rumor",
            }]
            bind_candidate(project, belief_claims, text)

            belief = audit_prose(project, "ch01-sc01", belief_claims)
            self.assertEqual(belief["verdict"], "pass", belief["findings"])

            knowledge_claims = claims(c(
                "focalizer_knows", evidence="She believed her.", subject="char-x", object="fact-door-open",
            ))
            knowledge_claims["observed_events"] = belief_claims["observed_events"]
            knowledge_claims["event_alignment"] = belief_claims["event_alignment"]
            bind_candidate(project, knowledge_claims, text)
            knowledge = audit_prose(project, "ch01-sc01", knowledge_claims)
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

    def test_variable_focalization_allows_other_declared_interiority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "planning" / "discourse-plan.json").write_text(json.dumps({
                "time": {"tense": "past"},
                "focalization": {"mode": "variable internal"},
            }), encoding="utf-8")
            critique = audit_prose(project, "ch01-sc01", claims(c("interiority_of", subject="char-y")))
            self.assertNotIn("pov", dims(critique))

    def test_tense_break_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(tense="present"))
            self.assertIn("tense", dims(critique))

    def test_spatial_contradiction_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            critique = self._audit(tmp, claims(c("located_at", subject="char-x", object="loc-b")))
            self.assertIn("continuity", dims(critique))

    def test_false_valued_location_is_not_treated_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "canon" / "world-state.jsonl").write_text(json.dumps({
                "predicate": "located_at", "subject": "char-x", "object": "loc-a", "value": False,
            }) + "\n", encoding="utf-8")
            critique = audit_prose(
                project, "ch01-sc01", claims(c("located_at", subject="char-x", object="loc-b")),
            )
            self.assertNotIn("continuity", dims(critique))

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
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-refusal"]
            spec_path.write_text(json.dumps(spec))
            text = "She turned the cup upside down and left it there."
            cl = claims()
            cl["observed_events"] = [{
                "id": "observed-cup", "description": "She refuses by inverting the cup.",
                "evidence": "She turned the cup upside down", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-refusal", "status": "realized", "observed_id": "observed-cup",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])
            self.assertEqual(critique["realization"]["required_events"][0]["status"], "realized")

    def test_candidate_bound_evidence_requires_exact_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            text = "Echo. Echo."
            cl = bind_candidate(project, claims(c("character_present", evidence="Echo.", subject="char-x")), text)
            cl["claims"][0]["evidence_span"] = {"start": 6, "end": 11}
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

            cl["claims"][0]["evidence_span"] = {"start": 1, "end": 6}
            result = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("evidence_span does not match", result["error"])

    def test_candidate_bound_claims_reject_stale_scene_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            cl = bind_candidate(
                project,
                claims(c("character_present", evidence="Nadia waited.", subject="char-x")),
                "Nadia waited.",
            )
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["max_words"] = 20
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            result = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("spec_sha256", result["error"])

    def test_candidate_bound_claims_reject_stale_event_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "planning" / "event-graph.json").write_text(
                json.dumps({"events": [{"id": "evt-one", "preconditions": [], "effects": []}]}),
                encoding="utf-8",
            )
            cl = bind_candidate(
                project,
                claims(c("character_present", evidence="Nadia waited.", subject="char-x")),
                "Nadia waited.",
            )
            (project / "planning" / "event-graph.json").write_text(
                json.dumps({"events": [{"id": "evt-one", "preconditions": [], "effects": [], "causes": ["fact-known"]}]}),
                encoding="utf-8",
            )
            result = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("audit_context_sha256", result["error"])

    def test_claim_before_aligned_learning_event_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_learning_event(project)
            text = "She knew the code. Mira told her the code."
            cl = claims(c(
                "focalizer_knows", evidence="She knew the code.", subject="char-x", object="fact-future",
            ))
            cl["observed_events"] = [{
                "id": "observed-learn", "description": "Mira tells her the code.",
                "evidence": "Mira told her the code.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-learn", "status": "realized", "observed_id": "observed-learn",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("knowledge", dims(critique))
            self.assertIn("before the aligned learning event", critique["findings"][0]["diagnosis"])

    def test_claim_after_aligned_learning_event_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_learning_event(project)
            text = "Mira told her the code. She knew the code."
            cl = claims(c(
                "focalizer_knows", evidence="She knew the code.", subject="char-x", object="fact-future",
            ))
            cl["observed_events"] = [{
                "id": "observed-learn", "description": "Mira tells her the code.",
                "evidence": "Mira told her the code.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-learn", "status": "realized", "observed_id": "observed-learn",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])
            self.assertEqual(critique["consistency"]["status"], "pass")
            self.assertEqual(critique["coverage"]["status"], "unverified")

    def test_fact_claim_before_aligned_establishing_event_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_fact_event(project)
            text = "The relay was broken. The relay snapped."
            cl = claims(c("states_fact", evidence="The relay was broken.", ref="fact-relay-broken"))
            cl["observed_events"] = [{
                "id": "observed-break", "description": "The relay breaks.",
                "evidence": "The relay snapped.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-break", "status": "realized", "observed_id": "observed-break",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("factual", dims(critique))
            self.assertIn("before the aligned event establishes", critique["findings"][0]["diagnosis"])

    def test_fact_claim_after_aligned_establishing_event_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_fact_event(project)
            text = "The relay snapped. The relay was broken."
            cl = claims(c("states_fact", evidence="The relay was broken.", ref="fact-relay-broken"))
            cl["observed_events"] = [{
                "id": "observed-break", "description": "The relay breaks.",
                "evidence": "The relay snapped.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-break", "status": "realized", "observed_id": "observed-break",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

    def test_fact_claim_with_unbound_in_scene_truth_change_is_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta = json.loads(delta_path.read_text())
            delta["facts_added"] = [{"id": "fact-relay-broken", "text": "The relay is broken."}]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")
            critique = audit_prose(
                project, "ch01-sc01", claims(c("states_fact", ref="fact-relay-broken")),
            )
            self.assertEqual(critique["verdict"], "uncertain")
            self.assertEqual(critique["consistency"]["status"], "pass")
            self.assertTrue(any(u["dimension"] == "factual" for u in critique["consistency"]["uncertainties"]))

    def test_location_claim_before_aligned_move_is_material(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_move_event(project)
            text = "She stood in the hall. She crossed into the hall."
            cl = claims(c("located_at", evidence="She stood in the hall.", subject="char-x", object="loc-b"))
            cl["observed_events"] = [{
                "id": "observed-move", "description": "She moves from loc-a to loc-b.",
                "evidence": "She crossed into the hall.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-move", "status": "realized", "observed_id": "observed-move",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("continuity", dims(critique))
            self.assertIn("before the aligned movement", critique["findings"][0]["diagnosis"])

    def test_location_claim_after_aligned_remove_add_move_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_move_event(project)
            text = "She crossed into the hall. She stood in the hall."
            cl = claims(c("located_at", evidence="She stood in the hall.", subject="char-x", object="loc-b"))
            cl["observed_events"] = [{
                "id": "observed-move", "description": "She moves from loc-a to loc-b.",
                "evidence": "She crossed into the hall.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-move", "status": "realized", "observed_id": "observed-move",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertEqual(critique["verdict"], "pass", critique["findings"])

    def test_prior_knowledge_is_invalidated_after_aligned_fact_removal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta = json.loads(delta_path.read_text())
            delta["facts_removed"] = ["fact-known"]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-expire"]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
                "id": "evt-expire", "preconditions": [],
                "effects": [{"op": "remove", "fact": "fact-known"}],
            }]}), encoding="utf-8")

            text = "The record expired. She knew it was still valid."
            cl = claims(c(
                "focalizer_knows", evidence="She knew it was still valid.",
                subject="char-x", object="fact-known",
            ))
            cl["observed_events"] = [{
                "id": "observed-expire", "description": "The record expires.",
                "evidence": "The record expired.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-expire", "status": "realized", "observed_id": "observed-expire",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("knowledge", dims(critique))

    def test_prior_belief_is_invalidated_after_aligned_correction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta = json.loads(delta_path.read_text())
            delta["belief_changes"] = [{
                "op": "set", "character": "char-x", "fact": "fact-known",
                "value": False, "source": "correction", "at_event": "evt-correct",
            }]
            delta_path.write_text(json.dumps(delta), encoding="utf-8")
            spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
            spec = json.loads(spec_path.read_text())
            spec["required_events"] = ["evt-correct"]
            spec_path.write_text(json.dumps(spec), encoding="utf-8")
            (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
                "id": "evt-correct", "preconditions": [], "effects": [{
                    "op": "add", "predicate": "believes", "subject": "char-x",
                    "object": "fact-known", "value": False,
                }],
            }]}), encoding="utf-8")

            text = "Mira corrected her. She still believed the old account."
            cl = claims(c(
                "focalizer_believes", evidence="She still believed the old account.",
                subject="char-x", object="fact-known", value=True,
            ))
            cl["observed_events"] = [{
                "id": "observed-correct", "description": "Mira corrects the belief.",
                "evidence": "Mira corrected her.", "consequential": True,
            }]
            cl["event_alignment"] = [{
                "event_id": "evt-correct", "status": "realized", "observed_id": "observed-correct",
            }]
            bind_candidate(project, cl, text)
            critique = audit_prose(project, "ch01-sc01", cl)
            self.assertIn("knowledge", dims(critique))

    def test_unordered_in_scene_learning_is_uncertain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            self._configure_learning_event(project)
            critique = audit_prose(
                project, "ch01-sc01",
                claims(c("focalizer_knows", subject="char-x", object="fact-future")),
            )
            self.assertEqual(critique["verdict"], "uncertain")
            self.assertEqual(critique["consistency"]["status"], "pass")
            self.assertTrue(critique["consistency"]["uncertainties"])

    @staticmethod
    def _configure_learning_event(project: Path) -> None:
        delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
        delta = json.loads(delta_path.read_text())
        delta["belief_changes"] = [{
            "op": "set", "character": "char-x", "fact": "fact-future",
            "value": True, "source": "testimony", "at_event": "evt-learn",
        }]
        delta_path.write_text(json.dumps(delta), encoding="utf-8")
        spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
        spec = json.loads(spec_path.read_text())
        spec["required_events"] = ["evt-learn"]
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
            "id": "evt-learn", "preconditions": [], "effects": [{
                "op": "add", "predicate": "knows", "subject": "char-x", "object": "fact-future",
            }],
        }]}), encoding="utf-8")

    @staticmethod
    def _configure_fact_event(project: Path) -> None:
        delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
        delta = json.loads(delta_path.read_text())
        delta["facts_added"] = [{"id": "fact-relay-broken", "text": "The relay is broken."}]
        delta_path.write_text(json.dumps(delta), encoding="utf-8")
        spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
        spec = json.loads(spec_path.read_text())
        spec["required_events"] = ["evt-break"]
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
            "id": "evt-break", "preconditions": [],
            "effects": [{"op": "add", "fact": "fact-relay-broken"}],
        }]}), encoding="utf-8")

    @staticmethod
    def _configure_move_event(project: Path) -> None:
        delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
        delta = json.loads(delta_path.read_text())
        delta["predicate_changes"] = [
            {"op": "remove", "predicate": "located_at", "subject": "char-x", "object": "loc-a",
             "at_event": "evt-move"},
            {"op": "add", "predicate": "located_at", "subject": "char-x", "object": "loc-b",
             "at_event": "evt-move"},
        ]
        delta_path.write_text(json.dumps(delta), encoding="utf-8")
        spec_path = project / "scenes" / "ch01-sc01" / "spec.json"
        spec = json.loads(spec_path.read_text())
        spec["required_events"] = ["evt-move"]
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        (project / "planning" / "event-graph.json").write_text(json.dumps({"events": [{
            "id": "evt-move", "preconditions": [], "effects": [
                {"op": "remove", "predicate": "located_at", "subject": "char-x", "object": "loc-a"},
                {"op": "add", "predicate": "located_at", "subject": "char-x", "object": "loc-b"},
            ],
        }]}), encoding="utf-8")

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
