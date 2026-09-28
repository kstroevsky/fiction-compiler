"""Prose audit — the hard audit's missing half (review §4).

The hard audit (``hard_audit.py``) proves the scene *spec*, delta, and event graph. It never reads
the candidate prose, so it cannot catch the prose revealing something the focalizer does not know,
introducing an unplanned character, head-hopping, breaking tense, contradicting object location, or
resolving a promise it never records. Those are prose-level facts.

The division of labour mirrors the tournament: an **extraction agent** turns one candidate's prose
into structured ``prose-claims`` (an LLM reading the text), and this module **proves** those claims
deterministically against the state reconstructed *before* the scene and the scene spec. The LLM
extracts; the code judges. Output conforms to ``critique.schema`` so it flows through the same gate
and tournament as every other critique.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import integrity, schema
from .state import reconstruct_state_before
from .workspace import resolve_scene_candidate, validate_scene_id

_SEVERITY_RANK = {"minor": 0, "material": 1, "fatal": 2}


def _finding(dimension: str, severity: str, evidence: str, diagnosis: str, repair_layer: str) -> dict:
    return {"dimension": dimension, "severity": severity, "evidence": evidence,
            "diagnosis": diagnosis, "repair_layer": repair_layer}


def _verdict(findings: list[dict]) -> str:
    worst = max((_SEVERITY_RANK[f["severity"]] for f in findings), default=-1)
    if worst == _SEVERITY_RANK["fatal"]:
        return "reject"
    if worst == _SEVERITY_RANK["material"]:
        return "revise"
    return "pass"


def _load(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def is_knowledge_leak(pov_knows_before: bool, granted_this_scene: bool) -> bool:
    """The pure epistemic rule: the focalizer may only 'know' a fact it knew coming in, or that this
    scene establishes/grants. Anything else is a leak from the future or another mind."""
    return not (pov_knows_before or granted_this_scene)


def audit_prose(project: Path, scene_id: str, claims: dict) -> dict:
    """Prove extracted claims and report plan-to-prose realization with explicit unknown states.

    ``observed_events`` must be extracted without the plan.  ``event_alignment`` is a separate,
    plan-aware pass that maps those observations to canonical event ids.  Missing alignment is
    uncertainty, not evidence of omission; an explicit ``omitted`` assessment is a material defect.
    Free-text turn and exit-state realization remain literary questions and are reported unverified.
    """
    project = Path(project).resolve()
    validate_scene_id(scene_id)
    errors = schema.validate_named(claims, "prose-claims")
    if errors:
        return {"error": "invalid prose-claims: " + "; ".join(errors)}
    if claims.get("scene_id") != scene_id:
        return {"error": f"claims scene_id {claims.get('scene_id')!r} != {scene_id!r}"}

    candidate_text: str | None = None
    if claims.get("candidate"):
        try:
            candidate_path = resolve_scene_candidate(project, scene_id, str(claims["candidate"]))
        except ValueError as exc:
            return {"error": str(exc)}
        if not candidate_path.exists():
            return {"error": f"candidate not found: {claims['candidate']}"}
        raw = candidate_path.read_bytes()
        actual_sha = integrity.sha256_bytes(raw)
        if claims.get("candidate_sha256") != actual_sha:
            return {"error": "prose-claims candidate_sha256 does not match the candidate bytes"}
        candidate_text = raw.decode("utf-8")
        actual_words = len(candidate_text.split())
        if claims.get("word_count") != actual_words:
            return {
                "error": (
                    f"prose-claims word_count {claims.get('word_count')} does not match "
                    f"candidate word count {actual_words}"
                )
            }
        evidence_items = [*claims.get("claims", []), *claims.get("observed_events", [])]
        for claim in evidence_items:
            evidence = claim.get("evidence", "")
            if evidence and evidence not in candidate_text:
                return {"error": f"prose-claims evidence is not present in candidate: {evidence!r}"}
    spec = _load(project / "scenes" / scene_id / "spec.json", {})
    delta = _load(project / "scenes" / scene_id / "state-delta.json", {})
    discourse = _load(project / "planning" / "discourse-plan.json", {})
    before = reconstruct_state_before(project, scene_id)

    pov = spec.get("pov")
    participants = {p for p in [pov, *spec.get("participants", [])] if p}
    canon_chars = {
        data.get("id")
        for path in (project / "canon" / "characters").glob("*.json")
        for data in [_load(path, {})]
        if isinstance(data, dict) and data.get("id")
    }
    # Epistemic grants must be explicit. A world fact becoming true does not by itself tell the POV.
    added_ids = {f["id"] for f in delta.get("facts_added", [])}
    legacy_grants = {
        kc["fact"] for kc in delta.get("knowledge_changes", [])
        if kc.get("character") == pov and kc.get("op", "add") != "remove"
    }
    belief_grants = {
        bc["fact"]: bc.get("value")
        for bc in delta.get("belief_changes", [])
        if bc.get("character") == pov and bc.get("op") == "set"
    }
    true_during_scene = lambda fact_id: before.fact_exists(fact_id) or fact_id in added_ids
    pov_granted = {fact_id for fact_id in legacy_grants if true_during_scene(fact_id)} | {
        fact_id for fact_id, value in belief_grants.items()
        if value is True and true_during_scene(fact_id)
    }
    closed_here = set(delta.get("promises_closed", []))

    findings: list[dict] = []

    observed = claims.get("observed_events", [])
    observed_by_id: dict[str, dict] = {}
    for item in observed:
        observed_id = item["id"]
        if observed_id in observed_by_id:
            return {"error": f"duplicate observed event id: {observed_id}"}
        observed_by_id[observed_id] = item

    alignments = claims.get("event_alignment", [])
    alignment_by_event: dict[str, dict] = {}
    for alignment in alignments:
        event_id = alignment["event_id"]
        if event_id in alignment_by_event:
            return {"error": f"duplicate event alignment: {event_id}"}
        status = alignment["status"]
        observed_id = alignment.get("observed_id")
        if status == "realized":
            if not observed_id:
                return {"error": f"realized event alignment {event_id!r} requires observed_id"}
            if observed_id not in observed_by_id:
                return {"error": f"event alignment {event_id!r} references unknown observed event {observed_id!r}"}
        elif observed_id:
            return {"error": f"{status} event alignment {event_id!r} must not claim observed_id"}
        alignment_by_event[event_id] = alignment

    required_events = list(spec.get("required_events", []))
    realization_events: list[dict] = []
    used_observations: set[str] = set()
    realization_uncertain = False
    for event_id in required_events:
        alignment = alignment_by_event.get(event_id)
        if alignment is None:
            realization_events.append({"event_id": event_id, "status": "unverified"})
            realization_uncertain = True
            continue
        status = alignment["status"]
        item = {"event_id": event_id, "status": status}
        if alignment.get("observed_id"):
            item["observed_id"] = alignment["observed_id"]
            used_observations.add(alignment["observed_id"])
        realization_events.append(item)
        if status == "omitted":
            findings.append(_finding(
                "realization", "material", f"required event {event_id} assessed omitted",
                "Plan-to-prose alignment explicitly found that a required event is absent from the candidate.",
                "prose"))
        elif status == "unverified":
            realization_uncertain = True

    # Alignments to non-required events are allowed for diagnosis, but they cannot satisfy a required
    # event. Consequential extracted events with no realized alignment are routed back to plan/delta.
    for alignment in alignments:
        if alignment.get("status") == "realized" and alignment.get("observed_id"):
            used_observations.add(alignment["observed_id"])
    unplanned_consequential = [
        item["id"] for item in observed
        if item.get("consequential") and item["id"] not in used_observations
    ]
    for observed_id in unplanned_consequential:
        findings.append(_finding(
            "realization", "minor", observed_by_id[observed_id]["evidence"],
            "A consequential prose event has no canonical event alignment; route it to the scene plan/state delta or mark it non-consequential.",
            "scene"))

    # POV / tense / length are whole-candidate properties.
    if claims.get("pov") and pov and claims["pov"] != pov:
        findings.append(_finding("pov", "material", f"prose pov={claims['pov']!r}",
                                 f"Prose is focalized on {claims['pov']}, but the spec pov is {pov}.", "prose"))
    expected_tense = (discourse.get("time") or {}).get("tense")
    if expected_tense and claims.get("tense") and claims["tense"] not in (expected_tense, "mixed"):
        findings.append(_finding("tense", "material", f"prose tense={claims['tense']!r}",
                                 f"Discourse plan calls for {expected_tense} tense.", "prose"))
    max_words = spec.get("max_words")
    if isinstance(max_words, int) and isinstance(claims.get("word_count"), int) and claims["word_count"] > max_words:
        findings.append(_finding("length", "material", f"word_count={claims['word_count']} > max {max_words}",
                                 "Candidate exceeds the scene's length restriction.", "prose"))

    for claim in claims.get("claims", []):
        ctype, subject, obj, ref = claim.get("type"), claim.get("subject"), claim.get("object"), claim.get("ref")
        ev = claim.get("evidence", "")
        if ctype == "character_present":
            if subject and subject not in participants:
                if subject in canon_chars:
                    findings.append(_finding("continuity", "minor", ev,
                        f"{subject} acts in the scene but is not a declared participant.", "scene"))
                else:
                    findings.append(_finding("continuity", "material", ev,
                        f"Unplanned character {subject!r} appears in the prose but is not in canon or the spec.", "scene"))
        elif ctype == "focalizer_knows":
            if subject == pov and obj and is_knowledge_leak(before.knows(pov, obj), obj in pov_granted):
                findings.append(_finding("knowledge", "material", ev,
                    f"The focalizer knows/reveals {obj!r}, which they have not learned by this scene "
                    "(nor does it record learning it) — knowledge leaks from the future or another mind.", "plot"))
        elif ctype == "focalizer_believes":
            expected = claim.get("value", True)
            granted = belief_grants.get(obj) is expected or (expected is True and obj in legacy_grants)
            if subject == pov and obj and not (before.believes(pov, obj, expected) or granted):
                findings.append(_finding("knowledge", "material", ev,
                    f"The focalizer is represented as believing {obj!r}={expected}, but that stance is not in their prior or in-scene belief state.",
                    "plot"))
        elif ctype == "interiority_of":
            if subject and pov and subject != pov:
                findings.append(_finding("pov", "material", ev,
                    f"Head-hopping: the prose enters {subject}'s interiority, but the focalizer is {pov}.", "prose"))
        elif ctype == "located_at":
            for (predicate, psubj, pobj), _ in before.predicates.items():
                if predicate == "located_at" and psubj == subject and obj and pobj != obj:
                    findings.append(_finding("continuity", "material", ev,
                        f"Spatial contradiction: prose places {subject} at {obj}, but state has {pobj}.", "prose"))
        elif ctype == "closes_promise":
            if ref and ref not in closed_here:
                findings.append(_finding("promise", "material", ev,
                    f"Prose resolves promise {ref!r} but the scene's state delta does not record closing it.", "scene"))
        elif ctype == "states_fact":
            if ref and not before.fact_exists(ref) and ref not in added_ids:
                findings.append(_finding("factual", "material", ev,
                    f"Prose states fact {ref!r}, which is not established in canon and not added by this scene.", "scene"))

    verdict = _verdict(findings)
    if verdict == "pass" and realization_uncertain:
        verdict = "uncertain"
    critique = {
        "candidate": claims.get("candidate", scene_id),
        "critic": "prose-audit",
        "audit_class": "hard",
        "verdict": verdict,
        "confidence": 1.0,
        "findings": findings,
        "realization": {
            "required_events": realization_events,
            "unplanned_consequential": unplanned_consequential,
            "turn": "unverified",
            "exit_state": "unverified",
        },
    }
    if claims.get("candidate_sha256"):  # keep the critique schema-valid when the hash is absent
        critique["candidate_sha256"] = claims["candidate_sha256"]
    return critique
