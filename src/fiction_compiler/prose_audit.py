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

from .state import reconstruct_state_before

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
    """Prove one candidate's extracted prose-claims against state-before + the scene spec."""
    spec = _load(project / "scenes" / scene_id / "spec.json", {})
    delta = _load(project / "scenes" / scene_id / "state-delta.json", {})
    discourse = _load(project / "planning" / "discourse-plan.json", {})
    before = reconstruct_state_before(project, scene_id)

    pov = spec.get("pov")
    participants = {p for p in [pov, *spec.get("participants", [])] if p}
    canon_chars = {p.stem for p in (project / "canon" / "characters").glob("*.json")}
    # Facts the pov legitimately gains this scene: what they learn, plus what the scene introduces.
    added_ids = {f["id"] for f in delta.get("facts_added", [])}
    pov_granted = {kc["fact"] for kc in delta.get("knowledge_changes", []) if kc.get("character") == pov} | added_ids
    closed_here = set(delta.get("promises_closed", []))

    findings: list[dict] = []

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

    critique = {
        "candidate": claims.get("candidate", scene_id),
        "critic": "prose-audit",
        "audit_class": "hard",
        "verdict": _verdict(findings),
        "confidence": 1.0,
        "findings": findings,
    }
    if claims.get("candidate_sha256"):  # keep the critique schema-valid when the hash is absent
        critique["candidate_sha256"] = claims["candidate_sha256"]
    return critique
