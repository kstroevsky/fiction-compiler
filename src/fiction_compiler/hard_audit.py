"""Audit 1 — hard / symbolic checks, done in code.

The design brief is emphatic that these must NOT be delegated to an LLM ("Do not ask an
LLM whether a date comparison is correct when ordinary code can calculate it"). Every
finding here is a fact about the artifacts, computed from the event-sourced state:

  * knowledge cutoff  — a scene may not require knowledge no earlier scene established
  * causal reference  — a scene's required events must exist; their *typed* preconditions must
                        hold in the state reconstructed before the scene, and their *typed*
                        effects must be recorded in the scene's state delta (executable IR)
  * point of view     — pov / participants must resolve to defined characters
  * referential canon — a delta may not grant knowledge of a non-existent fact, or
                        close a promise never opened, or remove a fact that isn't there
  * chronology        — accepted scene times must not run backward
  * promise ledger    — promises opened and never paid off are reported

Output conforms to ``critique.schema.json`` so it flows through the same pipeline as the
literary and defaultness critics. Findings carry exact evidence and a repair layer.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .ontology import check_atom, load_ontology
from .state import accepted_scene_ids, reconstruct_state_before, seed_state

CHAR_ID = re.compile(r"^char-[a-z0-9-]+$")
EVENT_ID = re.compile(r"^evt-[a-z0-9-]+$")
_SEVERITY_RANK = {"minor": 0, "material": 1, "fatal": 2}


def _finding(dimension: str, severity: str, evidence: str, diagnosis: str, repair_layer: str) -> dict:
    return {
        "dimension": dimension,
        "severity": severity,
        "evidence": evidence,
        "diagnosis": diagnosis,
        "repair_layer": repair_layer,
    }


def _verdict(findings: list[dict]) -> str:
    worst = max((_SEVERITY_RANK[f["severity"]] for f in findings), default=-1)
    if worst == _SEVERITY_RANK["fatal"]:
        return "reject"
    if worst == _SEVERITY_RANK["material"]:
        return "revise"
    return "pass"


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?$")


def _compare_time(a: Any, b: Any) -> int | None:
    """-1 if a<b, 0 if equal, 1 if a>b, None if not comparable."""
    na, nb = _as_number(a), _as_number(b)
    if na is not None and nb is not None:
        return (na > nb) - (na < nb)
    if isinstance(a, str) and isinstance(b, str) and _ISO.match(a) and _ISO.match(b):
        return (a > b) - (a < b)
    return None


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _load_delta(project: Path, scene_id: str) -> dict | None:
    return _load_json(project / "scenes" / scene_id / "state-delta.json", None)


def _character_ids(project: Path) -> set[str]:
    ids: set[str] = set()
    for path in (project / "canon" / "characters").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("id"):
            ids.add(data["id"])
    return ids


def _event_ids(project: Path) -> set[str]:
    graph = _load_json(project / "planning" / "event-graph.json", {})
    return {e.get("id") for e in graph.get("events", []) if e.get("id")}


def _events(project: Path) -> dict[str, dict]:
    graph = _load_json(project / "planning" / "event-graph.json", {})
    return {e["id"]: e for e in graph.get("events", []) if e.get("id")}


# A precondition/effect string that already names a canon id is a reference we tolerate; a bare
# prose string is what earns the "migrate to a typed atom" advisory.
_REF_ID = re.compile(r"^(fact|char|obj|loc|evt|promise)-[a-z0-9-]+$")


def _atom_str(atom: dict) -> str:
    obj = atom.get("object")
    inside = f"{atom.get('subject', '?')}" + (f", {obj}" if obj else "")
    return f"{atom.get('predicate', '?')}({inside})"


def _ontology_findings(ontology: dict, spec: dict, event_map: dict, scene_delta: dict) -> list[dict]:
    """Every typed atom the scene touches must use a declared predicate at the right arity/type."""
    findings: list[dict] = []

    def check(context: str, predicate: str | None, subject: str | None, object: str | None) -> None:
        for message in check_atom(ontology, predicate, subject, object):
            findings.append(_finding("ontology", "material", f"{context}: {message}",
                                     "Typed atom violates the predicate ontology (canon/ontology.json).", "world"))

    for event_id in spec.get("required_events", []):
        event = event_map.get(event_id)
        if not event:
            continue
        for pre in event.get("preconditions", []):
            if isinstance(pre, dict):
                check(f"{event_id} precondition", pre.get("predicate"), pre.get("subject"), pre.get("object"))
        for eff in event.get("effects", []):
            if isinstance(eff, dict):
                check(f"{event_id} effect", eff.get("predicate"), eff.get("subject"), eff.get("object"))
    for change in scene_delta.get("predicate_changes", []):
        check("delta predicate_changes", change.get("predicate"), change.get("subject"), change.get("object"))
    for edge in scene_delta.get("relationship_edges", []):
        check("delta relationship_edges", edge.get("dimension"), edge.get("subject"), edge.get("object"))
    return findings


def audit_scene(project: Path, scene_id: str) -> dict:
    """Per-scene spec checks that depend on the state reconstructed before it."""
    spec = _load_json(project / "scenes" / scene_id / "spec.json", {})
    findings: list[dict] = []
    characters = _character_ids(project)
    before = reconstruct_state_before(project, scene_id)

    pov = spec.get("pov", "")
    if CHAR_ID.match(pov):
        if pov not in characters:
            findings.append(_finding("character", "material", f"pov={pov!r}",
                                     "Point-of-view character is not defined in canon.", "character"))
    elif pov:
        findings.append(_finding("character", "minor", f"pov={pov!r}",
                                 "Point of view is not linked to a char-* canon id.", "scene"))

    for participant in spec.get("participants", []):
        if CHAR_ID.match(participant) and participant not in characters:
            findings.append(_finding("character", "material", f"participant={participant!r}",
                                     "Participant is not defined in canon.", "character"))

    for requirement in spec.get("knowledge_required", []):
        character, fact = requirement.get("character"), requirement.get("fact")
        if not before.fact_exists(fact):
            findings.append(_finding(
                "knowledge", "fatal",
                f"scene {scene_id} requires {fact!r}",
                f"Scene relies on fact {fact!r} that no earlier accepted scene has established.",
                "plot"))
        elif not before.knows(character, fact):
            findings.append(_finding(
                "knowledge", "fatal",
                f"scene {scene_id}: {character} must know {fact!r}",
                f"{character} does not know {fact!r} at this point; knowledge would leak from the future.",
                "plot"))

    event_map = _events(project)
    scene_delta = _load_delta(project, scene_id) or {}
    declared_effects = {
        (p.get("op"), p.get("predicate"), p.get("subject"), p.get("object"))
        for p in scene_delta.get("predicate_changes", [])
    }
    for event_id in spec.get("required_events", []):
        if not EVENT_ID.match(event_id):
            continue
        if event_id not in event_map:
            findings.append(_finding("causal", "material", f"required_events includes {event_id!r}",
                                     "Required event is not present in planning/event-graph.json.", "plot"))
            continue
        event = event_map[event_id]
        for pre in event.get("preconditions", []):
            if isinstance(pre, dict):
                if not before.holds(pre.get("predicate"), pre.get("subject"), pre.get("object")):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} precondition {_atom_str(pre)}",
                        "Event precondition does not hold in the state reconstructed before this scene.", "plot"))
            elif isinstance(pre, str) and not _REF_ID.match(pre):
                findings.append(_finding(
                    "causal", "minor", f"{event_id} precondition {pre!r}",
                    "Precondition is unstructured prose; encode it as a typed atom to make it verifiable.", "plot"))
        for eff in event.get("effects", []):
            if isinstance(eff, dict):
                key = (eff.get("op"), eff.get("predicate"), eff.get("subject"), eff.get("object"))
                if key not in declared_effects:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} effect {_atom_str(eff)}",
                        "Event effect is declared but not recorded in this scene's state-delta predicate_changes.", "scene"))

    ontology = load_ontology(project)
    if ontology is not None:
        findings.extend(_ontology_findings(ontology, spec, event_map, scene_delta))

    return {
        "candidate": scene_id,
        "critic": "hard-audit",
        "verdict": _verdict(findings),
        "confidence": 1.0,
        "findings": findings,
    }


def audit_canon(project: Path) -> dict:
    """Cross-scene referential integrity, chronology, and the promise ledger."""
    findings: list[dict] = []
    before = seed_state(project)  # replay starts from the initial canon
    facts = dict(before.facts)
    knowledge = {c: set(v) for c, v in before.knowledge.items()}
    open_promises = dict(before.open_promises)
    prev_time: Any = before.time

    for scene_id in accepted_scene_ids(project):
        delta = _load_delta(project, scene_id)
        if delta is None:
            findings.append(_finding("factual", "material", f"accepted scene {scene_id}",
                                     "Accepted scene has no state-delta.json.", "process"))
            continue

        added_ids = {f["id"] for f in delta.get("facts_added", [])}
        for fact_id in delta.get("facts_removed", []):
            if fact_id not in facts:
                findings.append(_finding("factual", "minor", f"{scene_id} removes {fact_id!r}",
                                         "Delta removes a fact that is not currently established.", "scene"))
        for change in delta.get("knowledge_changes", []):
            fact_id = change.get("fact")
            if fact_id not in facts and fact_id not in added_ids:
                findings.append(_finding(
                    "knowledge", "material",
                    f"{scene_id}: {change.get('character')} learns {fact_id!r}",
                    "Character learns a fact that does not exist at this point in the story.", "scene"))
        for promise_id in delta.get("promises_closed", []):
            if promise_id not in open_promises:
                findings.append(_finding("promise", "material", f"{scene_id} closes {promise_id!r}",
                                         "Delta pays off a promise that was never opened.", "plot"))

        current_time = delta.get("time")
        if current_time is not None and prev_time is not None:
            comparison = _compare_time(prev_time, current_time)
            if comparison is not None and comparison > 0:
                findings.append(_finding(
                    "temporal", "material",
                    f"{scene_id}: time {current_time!r} precedes previous {prev_time!r}",
                    "Story time runs backward across accepted scenes (encode flashbacks explicitly).", "plot"))

        # Apply the delta to the running shadow state.
        for fact in delta.get("facts_added", []):
            facts[fact["id"]] = fact["text"]
        for fact_id in delta.get("facts_removed", []):
            facts.pop(fact_id, None)
        for change in delta.get("knowledge_changes", []):
            knowledge.setdefault(change["character"], set()).add(change["fact"])
        for promise in delta.get("promises_opened", []):
            open_promises[promise["id"]] = promise["text"]
        for promise_id in delta.get("promises_closed", []):
            open_promises.pop(promise_id, None)
        if current_time is not None:
            prev_time = current_time

    for promise_id, text in sorted(open_promises.items()):
        findings.append(_finding("promise", "minor", f"{promise_id}: {text}",
                                 "Promise remains open at the end of the accepted manuscript.", "plot"))

    return {
        "candidate": "canon",
        "critic": "hard-audit",
        "verdict": _verdict(findings),
        "confidence": 1.0,
        "findings": findings,
    }


def has_fatal(critique: dict) -> bool:
    return any(f["severity"] == "fatal" for f in critique.get("findings", []))
