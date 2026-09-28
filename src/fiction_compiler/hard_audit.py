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
from pathlib import Path
from typing import Any

from .ontology import (check_atom, exclusive_predicate_errors, load_entity_registry,
                       load_ontology, typed_equal)
from .state import (accepted_scene_ids, accepted_scene_ids_before, compare_fabula_time,
                    fabula_order, normalize_fabula_time, reconstruct_state_before,
                    resource_change_errors, scene_fabula_time, scene_sort_key, seed_state)

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


def _compare_time(a: Any, b: Any) -> int | None:
    """-1 if a<b, 0 if equal, 1 if a>b, None if not comparable."""
    return compare_fabula_time(a, b)


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
    """World events executed before this scene in fabula order when time is reconstructible."""
    occurred: set[str] = set()
    prior_scenes, _ = accepted_scene_ids_before(project, scene_id)
    for prior_scene in prior_scenes:
        prior_spec = _load_json(project / "scenes" / prior_scene / "spec.json", {})
        occurred.update(prior_spec.get("required_events", []))
    return occurred


def _executed_events_elsewhere(project: Path, scene_id: str) -> set[str]:
    """Canonical event identities executed by any other accepted scene, regardless of discourse/fabula order."""
    occurred: set[str] = set()
    for other_scene in accepted_scene_ids(project):
        if other_scene == scene_id:
            continue
        other_spec = _load_json(project / "scenes" / other_scene / "spec.json", {})
        occurred.update(other_spec.get("required_events", []))
    return occurred


# A precondition/effect string that already names a canon id is a reference we tolerate; a bare
# prose string is what earns the "migrate to a typed atom" advisory.
_REF_ID = re.compile(r"^(fact|char|obj|loc|evt|promise)-[a-z0-9-]+$")


def _atom_str(atom: dict) -> str:
    obj = atom.get("object")
    inside = f"{atom.get('subject', '?')}" + (f", {obj}" if obj else "")
    rendered = f"{atom.get('predicate', '?')}({inside})"
    if "value" in atom:
        operator = {
            "eq": "==", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">=",
        }.get(atom.get("comparison", "eq"), atom.get("comparison", "?"))
        rendered += f" {operator} {atom['value']!r}"
    return rendered


def _effect_matches(required: dict, declared: dict) -> bool:
    """Compare an event effect with one state-delta predicate change semantically."""
    fields = ("op", "predicate", "subject", "object")
    if any(required.get(field) != declared.get(field) for field in fields):
        return False
    if required.get("op") == "remove":
        return True
    return typed_equal(required.get("value", True), declared.get("value", True))


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


def _belief_change_supported_by_event(event: dict, change: dict) -> bool:
    """Whether an event carries the effect that makes one belief change effective."""
    for effect in event.get("effects", []):
        if not isinstance(effect, dict):
            continue
        if _belief_effect_matches(effect, change):
            return True
        if (effect.get("predicate") == "knows"
                and effect.get("subject") == change.get("character")
                and effect.get("object") == change.get("fact")):
            if effect.get("op") == "add" and change.get("op") == "set" and change.get("value") is True:
                return True
            if effect.get("op") == "remove" and change.get("op") in {"forget", "set"}:
                return True
    return False


def _change_can_apply_at_event(change: dict, event_id: str | None) -> bool:
    """Unbound legacy changes remain compatible; explicit at_event may satisfy only that beat."""
    bound = change.get("at_event")
    return bound is None or bound == event_id


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


def _match_and_apply_event_effect(state, effect: dict, scene_delta: dict,
                                  event_id: str | None = None) -> tuple[bool, str]:
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
            if truth_ok and _change_can_apply_at_event(change, event_id) and _knowledge_effect_matches(effect, change):
                _apply_belief_shadow(state, change, legacy=True)
                return True, ""
        fact_id = effect.get("object")
        if state.fact_exists(fact_id):
            for change in belief_changes:
                if not _change_can_apply_at_event(change, event_id):
                    continue
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
            if _change_can_apply_at_event(change, event_id) and _belief_effect_matches(effect, change):
                _apply_belief_shadow(state, change)
                return True, ""
        return False, "Event belief effect is not recorded in state-delta belief_changes."

    if predicate == "remembers":
        return False, "Memory changes must be expressed through knowledge_changes/belief_changes."

    declared = next(
        (
            change for change in scene_delta.get("predicate_changes", [])
            if _change_can_apply_at_event(change, event_id) and _effect_matches(effect, change)
        ),
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


def _ontology_findings(ontology: dict, registry: dict | None, before, spec: dict,
                       event_map: dict, scene_delta: dict) -> list[dict]:
    """Check declared predicate, entity, value-domain and exclusivity constraints."""
    findings: list[dict] = []

    def check(context: str, atom: dict, *, op: str | None = None) -> None:
        kwargs: dict[str, Any] = {"registry": registry, "op": op or atom.get("op")}
        if "value" in atom:
            kwargs["value"] = atom["value"]
        if "comparison" in atom:
            kwargs["comparison"] = atom["comparison"]
        for message in check_atom(
            ontology, atom.get("predicate"), atom.get("subject"), atom.get("object"), **kwargs
        ):
            findings.append(_finding("ontology", "material", f"{context}: {message}",
                                     "Typed atom violates the predicate ontology (canon/ontology.json).", "world"))

    for event_id in spec.get("required_events", []):
        event = event_map.get(event_id)
        if not event:
            continue
        for pre in event.get("preconditions", []):
            if isinstance(pre, dict):
                check(f"{event_id} precondition", pre)
        for eff in event.get("effects", []):
            if isinstance(eff, dict) and eff.get("predicate"):
                check(f"{event_id} effect", eff)
    for change in scene_delta.get("predicate_changes", []):
        check("delta predicate_changes", change)
    for edge in scene_delta.get("relationship_edges", []):
        atom = {
            "predicate": edge.get("dimension"), "subject": edge.get("subject"),
            "object": edge.get("object"),
        }
        if "value" in edge:
            atom["value"] = edge["value"]
        check("delta relationship_edges", atom, op="add")

    pre_errors = set(exclusive_predicate_errors(ontology, before.predicates))
    for message in sorted(pre_errors):
        findings.append(_finding(
            "ontology", "material", f"pre-scene state: {message}",
            "Canonical state violates a declared predicate exclusivity rule.", "world"))
    if scene_delta.get("predicate_changes"):
        after_predicates = deepcopy(before.predicates)
        for change in scene_delta.get("predicate_changes", []):
            key = (change.get("predicate"), change.get("subject"), change.get("object"))
            if change.get("op") == "remove":
                after_predicates.pop(key, None)
            else:
                after_predicates[key] = change.get("value", True)
        for message in sorted(set(exclusive_predicate_errors(ontology, after_predicates)) - pre_errors):
            findings.append(_finding(
                "ontology", "material", f"post-scene state: {message}",
                "Scene consequences violate a declared predicate exclusivity rule.", "scene"))
    return findings


def audit_scene(project: Path, scene_id: str) -> dict:
    """Per-scene spec checks that depend on the state reconstructed before it."""
    spec = _load_json(project / "scenes" / scene_id / "spec.json", {})
    findings: list[dict] = []
    characters = _character_ids(project)
    before = reconstruct_state_before(project, scene_id)

    for issue in before.reconstruction_issues:
        findings.append(_finding(
            "temporal", "material", f"{scene_id}: {issue}",
            "Historical state could not be reconstructed unambiguously; use comparable fabula timestamps before relying on this scene's preconditions.",
            "plot"))

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
    mode = spec.get("narrative_mode", "linear")
    spec_time = spec.get("fabula_time")
    delta_time = scene_delta.get("time")
    if mode in {"analepsis", "prolepsis"}:
        if spec_time is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: nonlinear scene has no fabula_time",
                "Analepsis/prolepsis needs an explicit planning-time timestamp so historical state can be reconstructed.",
                "discourse"))
        if delta_time is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: nonlinear delta has no time",
                "A nonlinear accepted scene needs canonical delta.time matching its planned fabula_time.",
                "scene"))
    if spec_time is not None and delta_time is not None:
        comparison = compare_fabula_time(spec_time, delta_time)
        if comparison is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: fabula_time {spec_time!r} vs delta.time {delta_time!r}",
                "Scene planning time and canonical delta time use incomparable timestamp domains.", "scene"))
        elif comparison != 0:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: fabula_time {spec_time!r} != delta.time {delta_time!r}",
                "The accepted delta must take effect at the same fabula timestamp the scene was planned against.",
                "scene"))
    knowledge_changes = scene_delta.get("knowledge_changes", [])
    belief_changes = scene_delta.get("belief_changes", [])
    required_event_ids = set(spec.get("required_events", []))

    for change in scene_delta.get("predicate_changes", []):
        if change.get("predicate") in {"knows", "believes", "remembers"}:
            findings.append(_finding(
                "causal", "material", f"{scene_id} predicate_changes contains {change.get('predicate')}",
                "Epistemic state is stored in knowledge_changes/belief_changes; a generic predicate would not update it.",
                "scene"))
        at_event = change.get("at_event")
        if at_event:
            event = event_map.get(at_event)
            if event is None:
                findings.append(_finding(
                    "causal", "material", f"{scene_id}: predicate at_event {at_event!r}",
                    "Predicate execution event does not resolve to planning/event-graph.json.", "plot"))
            elif at_event not in required_event_ids:
                findings.append(_finding(
                    "causal", "material", f"{scene_id}: predicate at_event {at_event!r}",
                    "Predicate change is bound to an event this scene does not execute.", "scene"))
            elif not any(
                isinstance(effect, dict) and _effect_matches(effect, change)
                for effect in event.get("effects", [])
            ):
                findings.append(_finding(
                    "causal", "material", f"{scene_id}: predicate at_event {at_event!r}",
                    "Predicate execution event does not carry the matching typed effect.", "plot"))

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
        event_ref = change.get("event")
        if event_ref:
            if event_ref not in event_map:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: knowledge source event {event_ref!r}",
                    "Knowledge provenance event does not resolve to planning/event-graph.json.", "plot"))
        at_event = change.get("at_event")
        if at_event:
            event = event_map.get(at_event)
            if event is None:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: knowledge at_event {at_event!r}",
                    "Knowledge execution event does not resolve to planning/event-graph.json.", "plot"))
            elif at_event not in required_event_ids:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: knowledge at_event {at_event!r}",
                    "Knowledge change is bound to an event this scene does not execute.", "scene"))
            elif not any(
                isinstance(effect, dict) and _knowledge_effect_matches(effect, change)
                for effect in event.get("effects", [])
            ):
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: knowledge at_event {at_event!r}",
                    "Knowledge execution event does not carry the matching factive knowledge effect.", "plot"))

    defined = set(before.fact_definitions) | declared_now
    for change in belief_changes:
        fact_id = change.get("fact")
        if fact_id not in defined:
            findings.append(_finding(
                "knowledge", "material", f"{scene_id}: belief update references {fact_id!r}",
                "Belief updates must refer to a stable proposition definition, even when that proposition is false.",
                "scene"))
        event_ref = change.get("event")
        if event_ref:
            if event_ref not in event_map:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: belief source event {event_ref!r}",
                    "Belief provenance event does not resolve to planning/event-graph.json.", "plot"))
        at_event = change.get("at_event")
        if at_event:
            event = event_map.get(at_event)
            if event is None:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: belief at_event {at_event!r}",
                    "Belief execution event does not resolve to planning/event-graph.json.", "plot"))
            elif at_event not in required_event_ids:
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: belief at_event {at_event!r}",
                    "Belief change is bound to an event this scene does not execute.", "scene"))
            elif not _belief_change_supported_by_event(event, change):
                findings.append(_finding(
                    "knowledge", "material", f"{scene_id}: belief at_event {at_event!r}",
                    "Belief execution event does not carry a matching belief/knowledge effect.", "plot"))

    for error in resource_change_errors(before, scene_delta.get("resource_changes", [])):
        findings.append(_finding(
            "resource", "material", f"{scene_id}: {error}",
            "Ordered resource operations would consume or transfer unavailable quantity, use an invalid quantity, or change units.",
            "scene"))

    # Once the pre-scene snapshot is reconstructed at the scene's fabula time, nonlinear scenes can
    # use the same beat executor as linear scenes. Repeated narration still belongs in event_references.
    event_state = deepcopy(before)
    occurred_before = _occurred_events_before(project, scene_id)
    executed_elsewhere = _executed_events_elsewhere(project, scene_id)
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
        if event_id in executed_elsewhere:
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
                elif cause not in occurred_before | executed_here:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} cause {cause!r}",
                        "Causal predecessor has not executed before this event in the linear event order.", "plot"))
            elif isinstance(cause, str) and cause.startswith("fact-"):
                cause_state = event_state
                if not cause_state.fact_exists(cause):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} cause {cause!r}",
                        "Fact cause is not true when this event executes.", "plot"))
            elif isinstance(cause, str) and not _REF_ID.match(cause):
                findings.append(_finding(
                    "causal", "minor", f"{event_id} cause {cause!r}",
                    "Cause is unstructured prose; use a fact-* or evt-* reference to make it executable.", "plot"))
        for pre in event.get("preconditions", []):
            pre_state = event_state
            if isinstance(pre, dict):
                kwargs = {"value": pre["value"]} if "value" in pre else {}
                if "comparison" in pre:
                    kwargs["comparison"] = pre["comparison"]
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
                    elif pre not in occurred_before | executed_here:
                        findings.append(_finding(
                            "causal", "material", f"{event_id} precondition {pre!r}",
                            "Event precondition has not executed before this beat.", "plot"))
                elif not _REF_ID.match(pre):
                    findings.append(_finding(
                        "causal", "minor", f"{event_id} precondition {pre!r}",
                        "Precondition is unstructured prose; encode it as a typed atom to make it verifiable.", "plot"))
        for eff in event.get("effects", []):
            if isinstance(eff, dict):
                matched, diagnosis = _match_and_apply_event_effect(event_state, eff, scene_delta, event_id)
                if not matched:
                    findings.append(_finding(
                        "causal", "material", f"{event_id} effect {_atom_str(eff)}",
                        diagnosis, "scene"))
        executed_here.add(event_id)

    ontology = load_ontology(project)
    if ontology is not None:
        registry = load_entity_registry(project)
        findings.extend(_ontology_findings(ontology, registry, before, spec, event_map, scene_delta))

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
    seed_time: Any = before.time
    prev_time: Any = before.time

    discourse_ids = accepted_scene_ids(project)
    for scene_id in discourse_ids:
        delta = _load_delta(project, scene_id)
        if delta is None:
            continue
        spec = _load_json(project / "scenes" / scene_id / "spec.json", {})
        mode = _narrative_mode(project, scene_id)
        current_time = delta.get("time")
        spec_time = spec.get("fabula_time")
        if mode in {"analepsis", "prolepsis"} and spec_time is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: nonlinear scene has no fabula_time",
                "Nonlinear scenes need an explicit planning timestamp for historical reconstruction.",
                "discourse"))
        if mode in {"analepsis", "prolepsis"} and current_time is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: nonlinear delta has no time",
                "Nonlinear accepted scenes need canonical delta.time.", "scene"))
        if current_time is not None and normalize_fabula_time(current_time) is None:
            findings.append(_finding(
                "temporal", "material", f"{scene_id}: unorderable time {current_time!r}",
                "Accepted fabula time must be numeric or an ISO datetime before canonical history can be replayed.",
                "plot"))
        elif current_time is not None and seed_time is not None:
            seed_comparison = compare_fabula_time(current_time, seed_time)
            if seed_comparison is None:
                findings.append(_finding(
                    "temporal", "material",
                    f"{scene_id}: fabula time {current_time!r} is incomparable with seed {seed_time!r}",
                    "Accepted history and seed canon must use a comparable fabula-time domain.",
                    "plot"))
            elif seed_comparison < 0:
                findings.append(_finding(
                    "temporal", "material",
                    f"{scene_id}: fabula time {current_time!r} precedes seed {seed_time!r}",
                    "The current seed canon cannot reconstruct history earlier than its opening state.",
                    "plot"))
        if spec_time is not None and current_time is not None:
            comparison = compare_fabula_time(spec_time, current_time)
            if comparison is None or comparison != 0:
                findings.append(_finding(
                    "temporal", "material",
                    f"{scene_id}: fabula_time {spec_time!r} vs delta.time {current_time!r}",
                    "Planning-time and canonical fabula timestamps must be comparable and equal.", "scene"))
        # Chronology diagnostics remain a discourse-order check over the linear thread. Nonlinear
        # scenes deliberately diverge and do not advance that thread's clock.
        if mode == "linear":
            if current_time is not None and prev_time is not None:
                comparison = _compare_time(prev_time, current_time)
                if comparison is not None and comparison > 0:
                    findings.append(_finding(
                        "temporal", "material",
                        f"{scene_id}: time {current_time!r} precedes previous {prev_time!r}",
                        "Story time runs backward in linear narration; mark a deliberate flashback "
                        "with narrative_mode 'analepsis'.", "plot"))
            if current_time is not None:
                prev_time = current_time

    replay_ids, replay_issues = fabula_order(project, discourse_ids)
    for issue in replay_issues:
        findings.append(_finding(
            "temporal", "material", f"canon replay: {issue}",
            "Canonical cross-scene checks fell back to discourse order because fabula order is not fully specified.",
            "plot"))

    for scene_id in replay_ids:
        delta = _load_delta(project, scene_id)
        if delta is None:
            findings.append(_finding("factual", "material", f"accepted scene {scene_id}",
                                     "Accepted scene has no state-delta.json.", "process"))
            continue

        spec = _load_json(project / "scenes" / scene_id / "spec.json", {})
        scene_events = set(spec.get("required_events", []))
        for duplicate in sorted(scene_events & occurred_events):
            findings.append(_finding(
                "causal", "material", f"{scene_id} executes {duplicate!r} more than once in canon",
                "Canonical world events execute once; later discourse appearances belong in event_references.",
                "plot"))

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
