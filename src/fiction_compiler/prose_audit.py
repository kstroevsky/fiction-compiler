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


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return integrity.sha256_bytes(raw)


def _state_binding_payload(state) -> dict:
    """Stable serialization of every reconstructed StoryState field prose checks may depend on."""
    return {
        "time": state.time,
        "facts": state.facts,
        "fact_definitions": state.fact_definitions,
        "memory": {character: sorted(facts) for character, facts in sorted(state.memory.items())},
        "beliefs": state.beliefs,
        "belief_sources": state.belief_sources,
        "relationships": [
            {"subject": subject, "object": obj, "dimensions": dimensions}
            for (subject, obj), dimensions in sorted(state.relationships.items())
        ],
        "predicates": [
            {"predicate": predicate, "subject": subject, "object": obj, "value": value}
            for (predicate, subject, obj), value in sorted(
                state.predicates.items(), key=lambda item: tuple("" if part is None else part for part in item[0])
            )
        ],
        "resources": [
            {"resource": resource, "holder": holder, "quantity": quantity}
            for (resource, holder), quantity in sorted(state.resources.items())
        ],
        "resource_units": state.resource_units,
        "open_promises": state.open_promises,
        "promise_definitions": state.promise_definitions,
        "closed_promises": sorted(state.closed_promises),
        "applied_scenes": state.applied_scenes,
    }


def prose_claim_bindings(project: Path, scene_id: str, candidate: str) -> dict:
    """Return the deterministic inputs a candidate-bound prose extraction must attest to."""
    project = Path(project).resolve()
    validate_scene_id(scene_id)
    candidate_path = resolve_scene_candidate(project, scene_id, candidate)
    if not candidate_path.exists():
        raise ValueError(f"candidate not found: {candidate}")
    spec_path = project / "scenes" / scene_id / "spec.json"
    delta_path = project / "scenes" / scene_id / "state-delta.json"
    before = reconstruct_state_before(project, scene_id)
    spec = _load(spec_path, {})
    delta = _load(delta_path, {})
    discourse = _load(project / "planning" / "discourse-plan.json", {})
    event_graph = _load(project / "planning" / "event-graph.json", {})
    character_ids = sorted(
        data.get("id")
        for path in (project / "canon" / "characters").glob("*.json")
        for data in [_load(path, {})]
        if isinstance(data, dict) and data.get("id")
    )
    state_payload = _state_binding_payload(before)
    return {
        "candidate_sha256": integrity.sha256_file(candidate_path),
        "spec_sha256": integrity.sha256_file(spec_path),
        "state_before_sha256": _canonical_sha256(state_payload),
        "state_delta_sha256": integrity.sha256_file(delta_path),
        "audit_context_sha256": _canonical_sha256({
            "scene_spec": spec,
            "state_before": state_payload,
            "state_delta": delta,
            "discourse_plan": discourse,
            "event_graph": event_graph,
            "canon_character_ids": character_ids,
        }),
    }


def _evidence_position(item: dict) -> tuple[int, int] | None:
    span = item.get("evidence_span")
    if not isinstance(span, dict):
        return None
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
        return None
    return start, end


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
    before = reconstruct_state_before(project, scene_id)
    spec = _load(project / "scenes" / scene_id / "spec.json", {})
    delta = _load(project / "scenes" / scene_id / "state-delta.json", {})
    discourse = _load(project / "planning" / "discourse-plan.json", {})
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
        expected_bindings = prose_claim_bindings(project, scene_id, str(claims["candidate"]))
        for binding in ("spec_sha256", "state_before_sha256", "state_delta_sha256", "audit_context_sha256"):
            if claims.get(binding) != expected_bindings[binding]:
                return {"error": f"prose-claims {binding} does not match the audited scene context"}
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
            span = _evidence_position(claim)
            if span is None:
                return {"error": f"candidate-bound prose evidence requires evidence_span: {evidence!r}"}
            start, end = span
            if start < 0 or end <= start or end > len(candidate_text):
                return {"error": f"invalid prose evidence_span {start}:{end} for candidate length {len(candidate_text)}"}
            if candidate_text[start:end] != evidence:
                return {"error": f"prose evidence_span does not match candidate bytes decoded as UTF-8: {evidence!r}"}

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
    removed_ids = set(delta.get("facts_removed", []))
    closed_here = set(delta.get("promises_closed", []))
    required_events = list(spec.get("required_events", []))

    findings: list[dict] = []
    uncertainties: list[dict] = []

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

    event_graph = _load(project / "planning" / "event-graph.json", {})
    event_map = {event.get("id"): event for event in event_graph.get("events", []) if event.get("id")}
    aligned_event_positions: dict[str, tuple[int, int]] = {}
    for event_id, alignment in alignment_by_event.items():
        if alignment.get("status") != "realized" or not alignment.get("observed_id"):
            continue
        position = _evidence_position(observed_by_id[alignment["observed_id"]])
        if position is not None:
            aligned_event_positions[event_id] = position

    def _supports_epistemic_change(event_id: str, change: dict, *, legacy: bool) -> bool:
        event = event_map.get(event_id) or {}
        for effect in event.get("effects", []):
            if not isinstance(effect, dict):
                continue
            if effect.get("subject") != change.get("character") or effect.get("object") != change.get("fact"):
                continue
            if legacy:
                if (effect.get("predicate") == "knows"
                        and effect.get("op") == change.get("op", "add")):
                    return True
                continue
            if effect.get("predicate") == "believes":
                if effect.get("op") == "remove":
                    if change.get("op") == "forget":
                        return True
                    continue
                if (effect.get("op") == "add" and change.get("op") == "set"
                        and effect.get("value", True) == change.get("value")):
                    return True
                continue
            if effect.get("predicate") == "knows":
                if effect.get("op") == "add":
                    return change.get("op") == "set" and change.get("value") is True
                if effect.get("op") == "remove":
                    return change.get("op") in {"forget", "set"}
        return False

    def _fact_source_events(fact_id: str, op: str) -> list[str]:
        """Infer timing only from canonical events this scene actually executes."""
        matches: list[str] = []
        for event_id in required_events:
            event = event_map.get(event_id) or {}
            if any(
                isinstance(effect, dict)
                and effect.get("fact") == fact_id
                and (effect.get("op") == "remove") == (op == "remove")
                for effect in event.get("effects", [])
            ):
                matches.append(event_id)
        return matches

    def _ordered_event_positions(source_events: set[str], claim: dict) -> tuple[str, list[tuple[int, int, str]]]:
        """Resolve canonical events to non-overlapping prose spans around one claim."""
        claim_position = _evidence_position(claim)
        if claim_position is None:
            return "unknown", []
        positioned: list[tuple[int, int, str]] = []
        for event_id in source_events:
            position = aligned_event_positions.get(event_id)
            if position is None:
                return "unknown", []
            positioned.append((position[0], position[1], event_id))
        positioned.sort()
        for left, right in zip(positioned, positioned[1:]):
            if left[1] > right[0]:
                return "unknown", []
        if any(start < claim_position[1] and end > claim_position[0] for start, end, _ in positioned):
            return "unknown", []
        return "resolved", positioned

    def _ordered_fact_status(fact_id: str, claim: dict) -> str:
        """Whether a world fact is true at this exact prose claim, later, or never."""
        if not before.fact_exists(fact_id) and fact_id not in added_ids:
            return "absent"

        source_events: set[str] = set()
        unresolved = False
        if fact_id in added_ids:
            sources = _fact_source_events(fact_id, "add")
            if not sources:
                unresolved = True
            source_events.update(sources)
        if fact_id in removed_ids:
            sources = _fact_source_events(fact_id, "remove")
            if not sources:
                unresolved = True
            source_events.update(sources)

        claim_position = _evidence_position(claim)
        if claim_position is None:
            if source_events or unresolved:
                return "unknown"
            return "before" if before.fact_exists(fact_id) else "absent"
        if unresolved:
            return "unknown"
        position_status, positioned = _ordered_event_positions(source_events, claim)
        if position_status == "unknown":
            return "unknown"

        truth = before.fact_exists(fact_id)
        before_events = [row for row in positioned if row[1] <= claim_position[0]]
        after_events = [row for row in positioned if row[0] >= claim_position[1]]
        for _, _, event_id in before_events:
            event = event_map.get(event_id) or {}
            for effect in event.get("effects", []):
                if not isinstance(effect, dict) or effect.get("fact") != fact_id:
                    continue
                if effect.get("op") == "remove" and fact_id in removed_ids:
                    truth = False
                elif effect.get("op") != "remove" and fact_id in added_ids:
                    truth = True
        if truth:
            return "before"
        for _, _, event_id in after_events:
            event = event_map.get(event_id) or {}
            for effect in event.get("effects", []):
                if not isinstance(effect, dict) or effect.get("fact") != fact_id:
                    continue
                if effect.get("op") == "remove" and fact_id in removed_ids:
                    truth = False
                elif effect.get("op") != "remove" and fact_id in added_ids:
                    truth = True
        return "after" if truth else "absent"

    def _predicate_change_supported(event_id: str, change: dict) -> bool:
        event = event_map.get(event_id) or {}
        for effect in event.get("effects", []):
            if not isinstance(effect, dict):
                continue
            if any(effect.get(field) != change.get(field) for field in ("op", "predicate", "subject", "object")):
                continue
            if change.get("op") == "remove" or effect.get("value", True) == change.get("value", True):
                return True
        return False

    def _ordered_location_status(subject: str, obj: str, claim: dict) -> tuple[str, set[str]]:
        """Replay event-bound located_at changes and return claim-time active locations."""
        locations = {
            pobj for (predicate, psubj, pobj), value in before.predicates.items()
            if predicate == "located_at" and psubj == subject and pobj is not None and bool(value)
        }
        changes = [
            change for change in delta.get("predicate_changes", [])
            if change.get("predicate") == "located_at" and change.get("subject") == subject
        ]
        if not changes:
            return ("matches" if obj in locations else "contradicts" if locations else "absent"), locations

        source_events: set[str] = set()
        unresolved = False
        for change in changes:
            event_id = change.get("at_event")
            if (not event_id or event_id not in required_events
                    or not _predicate_change_supported(event_id, change)):
                unresolved = True
                continue
            source_events.add(event_id)
        claim_position = _evidence_position(claim)
        if claim_position is None or unresolved:
            return "unknown", locations
        position_status, positioned = _ordered_event_positions(source_events, claim)
        if position_status == "unknown":
            return "unknown", locations

        def apply_event(active: set[str], event_id: str) -> None:
            for change in changes:
                if change.get("at_event") != event_id:
                    continue
                location = change.get("object")
                if not location:
                    continue
                if change.get("op") == "remove" or not bool(change.get("value", True)):
                    active.discard(location)
                else:
                    active.add(location)

        before_events = [row for row in positioned if row[1] <= claim_position[0]]
        after_events = [row for row in positioned if row[0] >= claim_position[1]]
        for _, _, event_id in before_events:
            apply_event(locations, event_id)
        if obj in locations:
            return "matches", locations

        later_locations = set(locations)
        for _, _, event_id in after_events:
            apply_event(later_locations, event_id)
        if obj in later_locations:
            return "after", locations
        return ("contradicts" if locations else "absent"), locations

    def _apply_temporal_event(event_id: str, fact_id: str,
                              truth: bool, belief: bool | None) -> tuple[bool, bool | None]:
        event = event_map.get(event_id) or {}
        for effect in event.get("effects", []):
            if not isinstance(effect, dict) or effect.get("fact") != fact_id:
                continue
            if effect.get("op") == "remove" and fact_id in removed_ids:
                truth = False
            elif effect.get("op") != "remove" and fact_id in added_ids:
                truth = True
        for change in delta.get("knowledge_changes", []):
            if (change.get("character") == pov and change.get("fact") == fact_id
                    and change.get("at_event") == event_id):
                belief = None if change.get("op", "add") == "remove" else True
        for change in delta.get("belief_changes", []):
            if (change.get("character") == pov and change.get("fact") == fact_id
                    and change.get("at_event") == event_id):
                belief = None if change.get("op") == "forget" else change.get("value")
        return truth, belief

    def _ordered_epistemic_status(fact_id: str, expected: bool, claim: dict, *, factive: bool) -> str:
        """Replay event-bound truth/belief changes up to the claim's exact prose position."""
        legacy_changes = [
            change for change in delta.get("knowledge_changes", [])
            if change.get("character") == pov and change.get("fact") == fact_id
        ]
        belief_changes = [
            change for change in delta.get("belief_changes", [])
            if change.get("character") == pov and change.get("fact") == fact_id
        ]

        stance_can_match = before.believes(pov, fact_id, expected) or any(
            (change.get("op") == "set" and change.get("value") is expected)
            for change in belief_changes
        ) or (expected is True and any(change.get("op", "add") != "remove" for change in legacy_changes))
        if not stance_can_match:
            return "absent"
        if factive and not (before.fact_exists(fact_id) or fact_id in added_ids):
            return "absent"

        source_events: set[str] = set()
        unresolved = False
        for change, legacy in [*((change, True) for change in legacy_changes),
                               *((change, False) for change in belief_changes)]:
            event_id = change.get("at_event")
            if (not event_id or event_id not in required_events
                    or not _supports_epistemic_change(event_id, change, legacy=legacy)):
                unresolved = True
                continue
            source_events.add(event_id)
        if factive and fact_id in added_ids:
            sources = _fact_source_events(fact_id, "add")
            if not sources:
                unresolved = True
            source_events.update(sources)
        if factive and fact_id in removed_ids:
            sources = _fact_source_events(fact_id, "remove")
            if not sources:
                unresolved = True
            source_events.update(sources)

        claim_position = _evidence_position(claim)
        if claim_position is None and (source_events or unresolved):
            return "unknown"
        if claim_position is None:
            truth, belief = before.fact_exists(fact_id), before.belief(pov, fact_id)
            holds = belief is expected and (truth if factive else True)
            return "before" if holds else "absent"

        positioned: list[tuple[int, int, str]] = []
        for event_id in source_events:
            position = aligned_event_positions.get(event_id)
            if position is None:
                unresolved = True
                continue
            positioned.append((position[0], position[1], event_id))
        positioned.sort()
        for left, right in zip(positioned, positioned[1:]):
            if left[1] > right[0]:
                unresolved = True
        if any(start < claim_position[1] and end > claim_position[0] for start, end, _ in positioned):
            unresolved = True
        if unresolved:
            return "unknown"

        truth, belief = before.fact_exists(fact_id), before.belief(pov, fact_id)
        before_events = [row for row in positioned if row[1] <= claim_position[0]]
        after_events = [row for row in positioned if row[0] >= claim_position[1]]
        for _, _, event_id in before_events:
            truth, belief = _apply_temporal_event(event_id, fact_id, truth, belief)
        holds_at_claim = belief is expected and (truth if factive else True)
        if holds_at_claim:
            return "before"

        for _, _, event_id in after_events:
            truth, belief = _apply_temporal_event(event_id, fact_id, truth, belief)
        holds_later = belief is expected and (truth if factive else True)
        return "after" if holds_later else "absent"

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

    reference_events = list(spec.get("event_references", []))
    realization_references: list[dict] = []
    for event_id in reference_events:
        alignment = alignment_by_event.get(event_id)
        if alignment is None:
            realization_references.append({"event_id": event_id, "status": "unverified"})
            realization_uncertain = True
            continue
        status = alignment["status"]
        item = {"event_id": event_id, "status": status}
        if alignment.get("observed_id"):
            item["observed_id"] = alignment["observed_id"]
            used_observations.add(alignment["observed_id"])
        realization_references.append(item)
        if status == "omitted":
            findings.append(_finding(
                "realization", "material", f"event reference {event_id} assessed omitted",
                "Plan-to-prose alignment explicitly found that a required discourse event reference is absent from the candidate.",
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
    focalization = discourse.get("focalization") if isinstance(discourse.get("focalization"), dict) else {}
    focalization_mode = str(focalization.get("mode", "")).strip().lower()
    fixed_internal = not focalization_mode or ("fixed" in focalization_mode and "internal" in focalization_mode)
    declared_focalizer = focalization.get("focalizer") or pov
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
            if subject == pov and obj:
                temporal = _ordered_epistemic_status(obj, True, claim, factive=True)
                if temporal in {"absent", "after"}:
                    diagnosis = (
                        f"The focalizer knows/reveals {obj!r} before the aligned learning event occurs."
                        if temporal == "after" else
                        f"The focalizer knows/reveals {obj!r}, which is absent from prior and in-scene factive knowledge."
                    )
                    findings.append(_finding("knowledge", "material", ev, diagnosis, "plot"))
                elif temporal == "unknown":
                    uncertainties.append({
                        "dimension": "knowledge", "evidence": ev,
                        "reason": f"Timing of the in-scene learning for {obj!r} is not evidence-bound to an aligned event."
                    })
        elif ctype == "focalizer_believes":
            expected = claim.get("value", True)
            if subject == pov and obj:
                temporal = _ordered_epistemic_status(obj, expected, claim, factive=False)
                if temporal in {"absent", "after"}:
                    diagnosis = (
                        f"The focalizer is represented as believing {obj!r}={expected} before the aligned belief-changing event occurs."
                        if temporal == "after" else
                        f"The focalizer is represented as believing {obj!r}={expected}, but that stance is absent from prior and in-scene belief state."
                    )
                    findings.append(_finding("knowledge", "material", ev, diagnosis, "plot"))
                elif temporal == "unknown":
                    uncertainties.append({
                        "dimension": "knowledge", "evidence": ev,
                        "reason": f"Timing of the in-scene belief update for {obj!r}={expected} is not evidence-bound to an aligned event."
                    })
        elif ctype == "interiority_of":
            if subject and fixed_internal and declared_focalizer and subject != declared_focalizer:
                findings.append(_finding("pov", "material", ev,
                    f"Head-hopping: the prose enters {subject}'s interiority, but fixed internal focalization is {declared_focalizer}.", "prose"))
        elif ctype == "located_at":
            if subject and obj:
                temporal, active_locations = _ordered_location_status(subject, obj, claim)
                if temporal in {"contradicts", "after"}:
                    diagnosis = (
                        f"Spatial contradiction: prose places {subject} at {obj} before the aligned movement establishes that location."
                        if temporal == "after" else
                        f"Spatial contradiction: prose places {subject} at {obj}, but active state has {sorted(active_locations)}."
                    )
                    findings.append(_finding("continuity", "material", ev, diagnosis, "prose"))
                elif temporal == "unknown":
                    uncertainties.append({
                        "dimension": "continuity", "evidence": ev,
                        "reason": f"Timing of located_at changes for {subject!r} is not evidence-bound to aligned events."
                    })
        elif ctype == "closes_promise":
            if ref and ref not in closed_here:
                findings.append(_finding("promise", "material", ev,
                    f"Prose resolves promise {ref!r} but the scene's state delta does not record closing it.", "scene"))
        elif ctype == "states_fact":
            if ref:
                temporal = _ordered_fact_status(ref, claim)
                if temporal in {"absent", "after"}:
                    diagnosis = (
                        f"Prose states fact {ref!r} before the aligned event establishes it."
                        if temporal == "after" else
                        f"Prose states fact {ref!r}, which is not true at this point in the scene."
                    )
                    findings.append(_finding("factual", "material", ev, diagnosis, "scene"))
                elif temporal == "unknown":
                    uncertainties.append({
                        "dimension": "factual", "evidence": ev,
                        "reason": f"Timing of the in-scene truth change for {ref!r} is not evidence-bound to an aligned event."
                    })

    consistency_status = _verdict(findings)
    verdict = consistency_status
    if verdict == "pass" and (realization_uncertain or uncertainties):
        verdict = "uncertain"
    critique = {
        "candidate": claims.get("candidate", scene_id),
        "critic": "prose-audit",
        "audit_class": "hard",
        "verdict": verdict,
        "confidence": 1.0,
        "findings": findings,
        "consistency": {
            "status": consistency_status,
            "checked_claims": len(claims.get("claims", [])),
            "uncertainties": uncertainties,
        },
        "coverage": {
            "status": "unverified",
            "claimed_items": len(claims.get("claims", [])),
            "observed_events": len(observed),
            "reason": "Deterministic claim checking cannot establish that the extractor found every relevant prose fact or event.",
        },
        "realization": {
            "required_events": realization_events,
            "event_references": realization_references,
            "unplanned_consequential": unplanned_consequential,
            "turn": "unverified",
            "exit_state": "unverified",
        },
    }
    if claims.get("candidate_sha256"):  # keep the critique schema-valid when the hash is absent
        critique["candidate_sha256"] = claims["candidate_sha256"]
    return critique
