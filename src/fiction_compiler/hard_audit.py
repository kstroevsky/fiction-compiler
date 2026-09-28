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
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .ontology import check_atom, load_ontology
from .state import (accepted_scene_ids, reconstruct_state_before, resource_change_errors,
                    scene_sort_key, seed_state)

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


def _compare_time(a: Any, b: Any) -> int | None:
    """-1 if a<b, 0 if equal, 1 if a>b, None if not comparable."""
    na, nb = _as_number(a), _as_number(b)
    if na is not None and nb is not None:
        return (na > nb) - (na < nb)
    if isinstance(a, str) and isinstance(b, str):
        try:
            da = datetime.fromisoformat(a[:-1] + "+00:00" if a.endswith("Z") else a)
            db = datetime.fromisoformat(b[:-1] + "+00:00" if b.endswith("Z") else b)
            return (da > db) - (da < db)
        except (TypeError, ValueError):
            return None
    return None


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _load_delta(project: Path, scene_id: str) -> dict | None:
    return _load_json(project / "scenes" / scene_id / "state-delta.json", None)


def _narrative_mode(project: Path, scene_id: str) -> str:
    """Discourse/fabula relation of a scene: linear (default), analepsis (flashback), prolepsis."""
    mode = _load_json(project / "scenes" / scene_id / "spec.json", {}).get("narrative_mode", "linear")
    return mode if mode in ("linear", "analepsis", "prolepsis") else "linear"


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


def _event_graph_findings(project: Path) -> list[dict]:
    """Validate canonical event identity, directed references, and acyclicity."""
    graph = _load_json(project / "planning" / "event-graph.json", {})
    events = [e for e in graph.get("events", []) if isinstance(e, dict) and e.get("id")]
    ids = [str(e["id"]) for e in events]
    id_set = set(ids)
    findings: list[dict] = []
    for event_id in sorted({event_id for event_id in ids if ids.count(event_id) > 1}):
        findings.append(_finding(
            "causal", "material", f"duplicate event id {event_id!r}",
            "Canonical event identity must be unique.", "plot"))

    edges: set[tuple[str, str]] = set()
    for event in events:
        target = str(event["id"])
        for cause in event.get("causes", []):
            if isinstance(cause, str) and cause.startswith("evt-"):
                if cause in id_set:
                    edges.add((cause, target))
                else:
                    findings.append(_finding(
                        "causal", "material", f"{target} cause {cause!r}",
                        "Event cause does not resolve to a canonical event.", "plot"))
    for edge in graph.get("edges", []):
        if not isinstance(edge, dict):
            continue
        source, target = edge.get("from"), edge.get("to")
        if source in id_set and target in id_set:
            edges.add((str(source), str(target)))
        else:
            findings.append(_finding(
                "causal", "material", f"event edge {source!r} -> {target!r}",
                "Event-graph edge endpoint does not resolve to a canonical event.", "plot"))

    indegree = {event_id: 0 for event_id in id_set}
    successors = {event_id: set() for event_id in id_set}
    for source, target in edges:
        if target not in successors[source]:
            successors[source].add(target)
            indegree[target] += 1
    ready = sorted(event_id for event_id, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for target in sorted(successors[current]):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(id_set):
        cyclic = sorted(event_id for event_id, degree in indegree.items() if degree > 0)
        findings.append(_finding(
            "causal", "material", f"event cycle involves {cyclic}",
            "Event graph contains a directed causal cycle; no linear execution order can satisfy it.",
            "plot"))
    return findings


def _occurred_events_before(project: Path, scene_id: str) -> set[str]:
    """World events executed by earlier accepted scenes in discourse order."""
    target = scene_sort_key(scene_id)
    occurred: set[str] = set()
    for prior_scene in accepted_scene_ids(project):
        if scene_sort_key(prior_scene) >= target:
            continue
        prior_spec = _load_json(project / "scenes" / prior_scene / "spec.json", {})
        occurred.update(prior_spec.get("required_events", []))
    return occurred


# A precondition/effect string that already names a canon id is a reference we tolerate; a bare
# prose string is what earns the "migrate to a typed atom" advisory.
_REF_ID = re.compile(r"^(fact|char|obj|loc|evt|promise)-[a-z0-9-]+$")


def _atom_str(atom: dict) -> str:
    obj = atom.get("object")
    inside = f"{atom.get('subject', '?')}" + (f", {obj}" if obj else "")
    rendered = f"{atom.get('predicate', '?')}({inside})"
    if "value" in atom:
        rendered += f" == {atom['value']!r}"
    return rendered


def _effect_matches(required: dict, declared: dict) -> bool:
    """Compare an event effect with one state-delta predicate change semantically."""
    fields = ("op", "predicate", "subject", "object")
    if any(required.get(field) != declared.get(field) for field in fields):
        return False
    if required.get("op") == "remove":
        return True
    return required.get("value", True) == declared.get("value", True)


def _knowledge_effect_matches(required: dict, change: dict) -> bool:
    if required.get("predicate") != "knows":
        return False
    if required.get("subject") != change.get("character") or required.get("object") != change.get("fact"):
        return False
    op = required.get("op")
    if op != change.get("op", "add"):
        return False
    if op == "remove":
        return True
    return required.get("value", True) is True


def _belief_effect_matches(required: dict, change: dict) -> bool:
    if required.get("predicate") != "believes":
        return False
    if required.get("subject") != change.get("character") or required.get("object") != change.get("fact"):
        return False
    op = required.get("op")
    if op == "remove":
        return change.get("op") == "forget"
    if op != "add" or change.get("op") != "set":
        return False
    return required.get("value", True) == change.get("value")


def _apply_belief_shadow(state, change: dict, *, legacy: bool = False) -> None:
    """Apply an already-validated epistemic delta to an audit-only working state."""
    character, fact_id = change["character"], change["fact"]
    op = change.get("op", "add" if legacy else "set")
    if op in ("remove", "forget"):
        state.memory.setdefault(character, set()).discard(fact_id)
        state.beliefs.setdefault(character, {}).pop(fact_id, None)
        return
    state.memory.setdefault(character, set()).add(fact_id)
    state.beliefs.setdefault(character, {})[fact_id] = True if legacy else change.get("value", True)


def _match_and_apply_event_effect(state, effect: dict, scene_delta: dict) -> tuple[bool, str]:
    """Match one event effect to the aggregate scene delta, then apply only that beat's effect.

    This gives later required events a causally updated shadow state without applying unrelated
    end-of-scene changes early. The canonical state is never mutated here.
    """
    if effect.get("fact"):
        fact_id = effect["fact"]
        if effect.get("op") == "remove":
            matched = fact_id in scene_delta.get("facts_removed", [])
            if matched:
                state.facts.pop(fact_id, None)
            return matched, "Event fact removal is not recorded in state-delta facts_removed."
        record = next((item for item in scene_delta.get("facts_added", []) if item.get("id") == fact_id), None)
        if record is not None:
            previous = state.fact_definitions.get(fact_id)
            if previous is None or previous == record.get("text"):
                state.fact_definitions.setdefault(fact_id, record.get("text"))
                state.facts[fact_id] = record.get("text")
        return record is not None, "Event fact addition is not recorded in state-delta facts_added."

    predicate = effect.get("predicate")
    knowledge_changes = scene_delta.get("knowledge_changes", [])
    belief_changes = scene_delta.get("belief_changes", [])
    if predicate == "knows":
        for change in knowledge_changes:
            truth_ok = effect.get("op") == "remove" or state.fact_exists(effect.get("object"))
            if truth_ok and _knowledge_effect_matches(effect, change):
                _apply_belief_shadow(state, change, legacy=True)
                return True, ""
        fact_id = effect.get("object")
        if state.fact_exists(fact_id):
            for change in belief_changes:
                if change.get("character") != effect.get("subject") or change.get("fact") != fact_id:
                    continue
                if effect.get("op") == "add" and change.get("op") == "set" and change.get("value") is True:
                    _apply_belief_shadow(state, change)
                    return True, ""
                if effect.get("op") == "remove" and (
                    change.get("op") == "forget"
                    or (change.get("op") == "set" and change.get("value") is False)
                ):
                    _apply_belief_shadow(state, change)
                    return True, ""
        return False, "Event knowledge effect is not recorded by a factive knowledge/belief update."

    if predicate == "believes":
        for change in belief_changes:
            if _belief_effect_matches(effect, change):
                _apply_belief_shadow(state, change)
                return True, ""
        return False, "Event belief effect is not recorded in state-delta belief_changes."

    if predicate == "remembers":
        return False, "Memory changes must be expressed through knowledge_changes/belief_changes."

    declared = next(
        (change for change in scene_delta.get("predicate_changes", []) if _effect_matches(effect, change)),
        None,
    )
    if declared is None:
        return False, "Event effect is not recorded in this scene's state-delta predicate_changes."
    key = (declared["predicate"], declared["subject"], declared.get("object"))
    if declared.get("op") == "remove":
        state.predicates.pop(key, None)
    else:
        state.predicates[key] = declared.get("value", True)
    return True, ""


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
            if isinstance(eff, dict) and eff.get("predicate"):
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

    for requirement in spec.get("resource_requirements", []):
        resource = requirement.get("resource")
        holder = requirement.get("holder")
        expected = requirement.get("quantity")
        actual = before.resource_quantity(resource, holder)
        unit = requirement.get("unit")
        known_unit = before.resource_units.get(resource)
        if unit and known_unit and unit != known_unit:
            findings.append(_finding(
                "resource", "material", f"{scene_id}: {resource} unit {unit!r} != {known_unit!r}",
                "Scene resource requirement uses a different unit than the reconstructed resource ledger.",
                "scene"))
            continue
        comparison = requirement.get("comparison")
        satisfied = actual == expected if comparison == "exactly" else actual >= expected
        if not satisfied:
            findings.append(_finding(
                "resource", "material",
                f"{scene_id}: {resource} at {holder!r} is {actual}, requires {comparison} {expected}",
                "A load-bearing scene quantity is unavailable before the scene begins.", "plot"))

    event_map = _events(project)
    scene_delta = _load_delta(project, scene_id) or {}
    knowledge_changes = scene_delta.get("knowledge_changes", [])
    belief_changes = scene_delta.get("belief_changes", [])

    for change in scene_delta.get("predicate_changes", []):
        if change.get("predicate") in {"knows", "believes", "remembers"}:
            findings.append(_finding(
                "causal", "material", f"{scene_id} predicate_changes contains {change.get('predicate')}",
                "Epistemic state is stored in knowledge_changes/belief_changes; a generic predicate would not update it.",
                "scene"))

    declared_now: set[str] = set()
    for proposition in [*scene_delta.get("propositions_defined", []), *scene_delta.get("facts_added", [])]:
        fact_id = proposition.get("id")
        previous = before.fact_definitions.get(fact_id)
        if previous is not None and previous != proposition.get("text"):
            findings.append(_finding(
                "factual", "material", f"{scene_id} redefines {fact_id!r}",
                "A proposition id already denotes different text; create a new id for a changed proposition.",
                "world"))
        else:
            declared_now.add(fact_id)

    added_now = {fact.get("id") for fact in scene_delta.get("facts_added", [])}
    for change in knowledge_changes:
        fact_id = change.get("fact")
        if change.get("op", "add") != "remove" and not before.fact_exists(fact_id) and fact_id not in added_now:
            findings.append(_finding(
                "knowledge", "material", f"{scene_id}: {change.get('character')} learns {fact_id!r}",
                "Legacy knowledge_changes may only learn a proposition that is true at this point; use belief_changes for possibly false belief.",
                "scene"))

    defined = set(before.fact_definitions) | declared_now
    for change in belief_changes:
        fact_id = change.get("fact")
        if fact_id not in defined:
            findings.append(_finding(
                "knowledge", "material", f"{scene_id}: belief update references {fact_id!r}",
                "Belief updates must refer to a stable proposition definition, even when that proposition is false.",
                "scene"))
        event_ref = change.get("event")
        if event_ref and event_ref not in event_map:
            findings.append(_finding(
                "knowledge", "material", f"{scene_id}: belief source event {event_ref!r}",
                "Belief provenance event does not resolve to planning/event-graph.json.", "plot"))

    for error in resource_change_errors(before, scene_delta.get("resource_changes", [])):
        findings.append(_finding(
            "resource", "material", f"{scene_id}: {error}",
            "Ordered resource operations would consume or transfer unavailable quantity, use an invalid quantity, or change units.",
            "scene"))

    ordered_events = spec.get("narrative_mode", "linear") == "linear"
    event_state = deepcopy(before)
    # Non-linear scenes are still validated against one pre-scene snapshot until fabula-ordered
    # reconstruction lands. Preload end-of-scene facts only for effect/delta matching, never for
    # their preconditions.
    if not ordered_events:
        for fact in scene_delta.get("facts_added", []):
            previous = event_state.fact_definitions.get(fact.get("id"))
            if previous is None or previous == fact.get("text"):
                event_state.fact_definitions.setdefault(fact.get("id"), fact.get("text"))
                event_state.facts[fact.get("id")] = fact.get("text")
    occurred_before = _occurred_events_before(project, scene_id)
    executed_here: set[str] = set()
    event_references = set(spec.get("event_references", []))
    overlap = event_references & set(spec.get("required_events", []))
    for event_id in sorted(overlap):
        findings.append(_finding(
            "causal", "material", f"{scene_id}: {event_id!r} is both required and referenced",
            "One scene cannot both execute a canonical event and treat the same event as discourse-only; choose the intended identity role.",
            "scene"))
    for event_id in sorted(event_references):
        if event_id not in event_map:
            findings.append(_finding(
                "causal", "material", f"event_references includes {event_id!r}",
                "Discourse event reference does not resolve to planning/event-graph.json.", "plot"))

    for event_id in spec.get("required_events", []):
        if not EVENT_ID.match(event_id):
            continue
        if event_id not in event_map:
            findings.append(_finding("causal", "material", f"required_events includes {event_id!r}",
                                     "Required event is not present in planning/event-graph.json.", "plot"))
            continue
        if event_id in occurred_before:
            findings.append(_finding(
                "causal", "material", f"{scene_id} executes {event_id!r} again",
                "A canonical world event already executed in an earlier scene; use event_references for a discourse reappearance instead of applying its world effects twice.",
                "plot"))
        event = event_map[event_id]
        for cause in event.get("causes", []):
            if isinstance(cause, str) and cause.startswith("evt-"):
                if cause not in event_map:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} cause {cause!r}",
                        "Event cause does not resolve to an event in planning/event-graph.json.", "plot"))
                elif ordered_events and cause not in occurred_before | executed_here:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} cause {cause!r}",
                        "Causal predecessor has not executed before this event in the linear event order.", "plot"))
            elif isinstance(cause, str) and cause.startswith("fact-"):
                cause_state = event_state if ordered_events else before
                if not cause_state.fact_exists(cause):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} cause {cause!r}",
                        "Fact cause is not true when this event executes.", "plot"))
            elif isinstance(cause, str) and not _REF_ID.match(cause):
                findings.append(_finding(
                    "causal", "minor", f"{event_id} cause {cause!r}",
                    "Cause is unstructured prose; use a fact-* or evt-* reference to make it executable.", "plot"))
        for pre in event.get("preconditions", []):
            pre_state = event_state if ordered_events else before
            if isinstance(pre, dict):
                kwargs = {"value": pre["value"]} if "value" in pre else {}
                if not pre_state.holds(pre.get("predicate"), pre.get("subject"), pre.get("object"), **kwargs):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} precondition {_atom_str(pre)}",
                        "Event precondition does not hold immediately before this event executes.", "plot"))
            elif isinstance(pre, str):
                if pre.startswith("fact-") and not pre_state.fact_exists(pre):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} precondition {pre!r}",
                        "Fact precondition is not true immediately before this event executes.", "plot"))
                elif pre.startswith("evt-"):
                    if pre not in event_map:
                        findings.append(_finding(
                            "causal", "material", f"{event_id} precondition {pre!r}",
                            "Event precondition does not resolve to an event in planning/event-graph.json.", "plot"))
                    elif ordered_events and pre not in occurred_before | executed_here:
                        findings.append(_finding(
                            "causal", "material", f"{event_id} precondition {pre!r}",
                            "Event precondition has not executed before this beat.", "plot"))
                elif not _REF_ID.match(pre):
                    findings.append(_finding(
                        "causal", "minor", f"{event_id} precondition {pre!r}",
                        "Precondition is unstructured prose; encode it as a typed atom to make it verifiable.", "plot"))
        for eff in event.get("effects", []):
            if isinstance(eff, dict):
                matched, diagnosis = _match_and_apply_event_effect(event_state, eff, scene_delta)
                if not matched:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} effect {_atom_str(eff)}",
                        diagnosis, "scene"))
        if ordered_events:
            executed_here.add(event_id)

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
    findings: list[dict] = _event_graph_findings(project)
    before = seed_state(project)  # replay starts from the initial canon
    facts = dict(before.facts)
    fact_definitions = dict(before.fact_definitions)
    open_promises = dict(before.open_promises)
    promise_definitions = {pid: dict(value) for pid, value in before.promise_definitions.items()}
    event_map = _events(project)
    occurred_events: set[str] = set()
    prev_time: Any = before.time

    for scene_id in accepted_scene_ids(project):
        delta = _load_delta(project, scene_id)
        if delta is None:
            findings.append(_finding("factual", "material", f"accepted scene {scene_id}",
                                     "Accepted scene has no state-delta.json.", "process"))
            continue

        spec = _load_json(project / "scenes" / scene_id / "spec.json", {})
        scene_events = set(spec.get("required_events", []))

        valid_defined_ids: set[str] = set()
        for proposition in [*delta.get("propositions_defined", []), *delta.get("facts_added", [])]:
            fact_id, text = proposition["id"], proposition["text"]
            previous = fact_definitions.get(fact_id)
            if previous is not None and previous != text:
                findings.append(_finding(
                    "factual", "material", f"{scene_id} redefines {fact_id!r}",
                    "A proposition id already denotes different text; changing it would alias retained epistemic state.",
                    "world"))
            else:
                valid_defined_ids.add(fact_id)
        valid_added_ids = {fact["id"] for fact in delta.get("facts_added", []) if fact["id"] in valid_defined_ids}
        for fact_id in delta.get("facts_removed", []):
            if fact_id not in facts:
                findings.append(_finding("factual", "minor", f"{scene_id} removes {fact_id!r}",
                                         "Delta removes a fact that is not currently established.", "scene"))
        for change in delta.get("knowledge_changes", []):
            fact_id = change.get("fact")
            if change.get("op", "add") != "remove" and fact_id not in facts and fact_id not in valid_added_ids:
                findings.append(_finding(
                    "knowledge", "material",
                    f"{scene_id}: {change.get('character')} learns {fact_id!r}",
                    "Character learns a fact that does not exist at this point in the story.", "scene"))
        for change in delta.get("belief_changes", []):
            fact_id = change.get("fact")
            if fact_id not in fact_definitions and fact_id not in valid_defined_ids:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: belief update references {fact_id!r}",
                    "Belief update references a proposition that has never been defined.", "scene"))
        for promise_id in delta.get("promises_closed", []):
            if promise_id not in open_promises:
                findings.append(_finding("promise", "material", f"{scene_id} closes {promise_id!r}",
                                         "Delta pays off a promise that was never opened.", "plot"))
                continue
            definition = promise_definitions.get(promise_id, {})
            trigger_event = definition.get("trigger_event")
            payoff_event = definition.get("payoff_event")
            if trigger_event and trigger_event not in occurred_events | scene_events:
                findings.append(_finding(
                    "promise", "material", f"{scene_id} closes {promise_id!r} before {trigger_event!r}",
                    "Promise is closed before its declared trigger event occurs.", "plot"))
            if payoff_event and payoff_event not in scene_events:
                findings.append(_finding(
                    "promise", "material", f"{scene_id} closes {promise_id!r} without {payoff_event!r}",
                    "Promise closure does not occur in a scene that declares its payoff event.", "plot"))

        for promise in delta.get("promises_opened", []):
            promise_id = promise["id"]
            previous = promise_definitions.get(promise_id)
            if previous is not None and previous != promise:
                findings.append(_finding(
                    "promise", "material", f"{scene_id} redefines {promise_id!r}",
                    "A promise id already has a different definition; use a new id for a new obligation.", "plot"))
            for key in ("trigger_event", "payoff_event"):
                event_id = promise.get(key)
                if event_id and event_id not in event_map:
                    findings.append(_finding(
                        "promise", "material", f"{scene_id} {promise_id!r} {key}={event_id!r}",
                        f"Promise {key} does not resolve to planning/event-graph.json.", "plot"))

        # Chronology is checked along the LINEAR (discourse == fabula) thread only. A scene marked
        # analepsis/prolepsis is a deliberate divergence: it neither trips the backward-time rule nor
        # advances the linear clock (so a flashback between two present scenes is not a contradiction).
        current_time = delta.get("time")
        mode = _narrative_mode(project, scene_id)
        if mode == "linear":
            if current_time is not None and prev_time is not None:
                comparison = _compare_time(prev_time, current_time)
                if comparison is not None and comparison > 0:
                    findings.append(_finding(
                        "temporal", "material",
                        f"{scene_id}: time {current_time!r} precedes previous {prev_time!r}",
                        "Story time runs backward in linear narration; mark a deliberate flashback "
                        "with narrative_mode 'analepsis'.", "plot"))

        # Apply the delta to the running shadow state.
        for proposition in delta.get("propositions_defined", []):
            fact_id, text = proposition["id"], proposition["text"]
            if fact_id not in fact_definitions:
                fact_definitions[fact_id] = text
        for fact in delta.get("facts_added", []):
            fact_id, text = fact["id"], fact["text"]
            previous = fact_definitions.get(fact_id)
            if previous is None:
                fact_definitions[fact_id] = text
                facts[fact_id] = text
            elif previous == text:
                facts[fact_id] = text
        for fact_id in delta.get("facts_removed", []):
            facts.pop(fact_id, None)
        for promise in delta.get("promises_opened", []):
            open_promises[promise["id"]] = promise["text"]
            promise_definitions.setdefault(promise["id"], dict(promise))
        for promise_id in delta.get("promises_closed", []):
            open_promises.pop(promise_id, None)
        for promise_id in sorted(open_promises):
            payoff_event = promise_definitions.get(promise_id, {}).get("payoff_event")
            if payoff_event and payoff_event in scene_events:
                findings.append(_finding(
                    "promise", "material", f"{scene_id} reaches payoff event {payoff_event!r} for {promise_id!r}",
                    "Declared payoff event occurs but the promise remains open; record the closure or revise the promise definition.",
                    "scene"))
        occurred_events.update(scene_events)
        if current_time is not None and mode == "linear":
            prev_time = current_time

    for promise_id, text in sorted(open_promises.items()):
        trigger_event = promise_definitions.get(promise_id, {}).get("trigger_event")
        if trigger_event and trigger_event in occurred_events:
            findings.append(_finding(
                "promise", "material", f"{promise_id}: {text} (triggered by {trigger_event})",
                "Promise's declared trigger occurred, but the obligation remains open at manuscript end.", "plot"))
        else:
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
