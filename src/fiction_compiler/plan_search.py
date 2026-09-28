"""Versioned scene-plan search and evidence-bound plan review.

This module owns mechanics the compiler can defend: immutable plan artifacts, schema/spec binding,
typed feasibility checks, search-width diagnostics, hash-bound reviewer evidence, and explicit
selection provenance.  It deliberately does not rank plans or claim that a deterministic metric can
identify the most literary option.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, schema
from .state import reconstruct_state_before


MIN_PLANS = 3
MAX_PLANS = 4
BLOCKING_SEVERITIES = {"material", "fatal"}


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _spec_path(project: Path, scene_id: str) -> Path:
    return Path(project) / "scenes" / scene_id / "spec.json"


def _candidate_dir(project: Path, scene_id: str) -> Path:
    return Path(project) / "scenes" / scene_id / "plans" / "candidates"


def _review_dir(project: Path, scene_id: str) -> Path:
    return Path(project) / "scenes" / scene_id / "plans" / "reviews"


def _selection_dir(project: Path, scene_id: str) -> Path:
    return Path(project) / "scenes" / scene_id / "plans" / "selections"


def _plan_path(project: Path, scene_id: str, plan_id: str) -> Path:
    return _candidate_dir(project, scene_id) / f"{plan_id}.json"


def _sha(path: Path) -> str:
    return acceptance.sha256_bytes(path.read_bytes())


def _finding(dimension: str, severity: str, evidence: str, diagnosis: str,
             repair_layer: str = "scene") -> dict:
    return {
        "dimension": dimension,
        "severity": severity,
        "evidence": evidence,
        "diagnosis": diagnosis,
        "repair_layer": repair_layer,
    }


def _verdict(findings: list[dict]) -> str:
    return "revise" if any(f.get("severity") in BLOCKING_SEVERITIES for f in findings) else "pass"


def record_plan(project: Path, scene_id: str, plan: dict) -> dict:
    """Create one immutable, spec-bound scene-plan candidate."""
    project = Path(project)
    spec_path = _spec_path(project, scene_id)
    if not spec_path.exists():
        return {"error": f"scene spec is missing: {spec_path.relative_to(project)}"}
    if not isinstance(plan, dict):
        return {"error": "plan must be an object"}
    payload = dict(plan)
    payload["schema_version"] = 1
    payload["scene_id"] = scene_id
    payload["source_spec_sha256"] = _sha(spec_path)
    errors = schema.validate_named(payload, "scene-plan")
    if errors:
        return {"error": "invalid scene plan: " + "; ".join(errors)}
    path = _plan_path(project, scene_id, payload["plan_id"])
    raw = acceptance.canonical_json_bytes(payload)
    if path.exists():
        if path.read_bytes() == raw:
            return {
                "plan_id": payload["plan_id"],
                "path": str(path.relative_to(project)),
                "sha256": acceptance.sha256_bytes(raw),
                "idempotent": True,
            }
        return {"error": f"plan {payload['plan_id']} already exists; create a new version/id"}
    acceptance.atomic_write(path, raw)
    return {
        "plan_id": payload["plan_id"],
        "path": str(path.relative_to(project)),
        "sha256": acceptance.sha256_bytes(raw),
        "idempotent": False,
    }


def load_plans(project: Path, scene_id: str) -> list[tuple[Path, dict]]:
    plans: list[tuple[Path, dict]] = []
    for path in sorted(_candidate_dir(project, scene_id).glob("*.json")):
        value = _load_json(path, None)
        if isinstance(value, dict):
            plans.append((path, value))
    return plans


def _event_map(project: Path) -> dict[str, dict]:
    graph = _load_json(Path(project) / "planning" / "event-graph.json", {})
    events = graph.get("events", []) if isinstance(graph, dict) else []
    return {
        event["id"]: event
        for event in events
        if isinstance(event, dict) and isinstance(event.get("id"), str)
    }


def audit_plan(project: Path, scene_id: str, plan: dict) -> dict:
    """Check structural and typed-state feasibility without making a literary judgment."""
    project = Path(project)
    findings: list[dict] = []
    errors = schema.validate_named(plan, "scene-plan")
    for message in errors:
        findings.append(_finding("schema", "material", message, "Plan artifact is schema-invalid."))
    plan_id = str(plan.get("plan_id", "unknown"))
    if errors:
        return {
            "candidate": plan_id, "critic": "plan-hard-audit", "verdict": "revise",
            "confidence": 1.0, "findings": findings,
        }
    if plan.get("scene_id") != scene_id:
        findings.append(_finding(
            "identity", "material", f"scene_id={plan.get('scene_id')!r}",
            f"Plan belongs to {plan.get('scene_id')!r}, not {scene_id!r}."
        ))
    spec_path = _spec_path(project, scene_id)
    if not spec_path.exists():
        findings.append(_finding("identity", "fatal", "spec.json missing", "Scene spec is missing."))
    elif plan.get("source_spec_sha256") != _sha(spec_path):
        findings.append(_finding(
            "freshness", "material", f"source_spec_sha256={plan.get('source_spec_sha256')}",
            "Plan was generated against different scene-spec bytes; regenerate/review it."
        ))

    before = reconstruct_state_before(project, scene_id)
    events = _event_map(project)
    for requirement in plan.get("knowledge_required", []):
        character, fact = requirement.get("character"), requirement.get("fact")
        if not before.fact_exists(fact):
            findings.append(_finding(
                "knowledge", "fatal", f"{character} requires absent {fact}",
                "Plan depends on a fact not established before this scene.", "plot"
            ))
        elif not before.knows(character, fact):
            findings.append(_finding(
                "knowledge", "fatal", f"{character} requires unknown {fact}",
                "Plan gives a character information they do not have before the scene.", "plot"
            ))

    for event_id in plan.get("required_events", []):
        event = events.get(event_id)
        if event is None:
            findings.append(_finding(
                "causal", "material", f"required event {event_id}",
                "Plan references an event absent from planning/event-graph.json.", "plot"
            ))
            continue
        for precondition in event.get("preconditions", []):
            if isinstance(precondition, dict):
                kwargs = {"value": precondition["value"]} if "value" in precondition else {}
                if not before.holds(
                    precondition.get("predicate"), precondition.get("subject"),
                    precondition.get("object"), **kwargs,
                ):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} precondition {precondition}",
                        "Typed event precondition does not hold before the scene.", "plot"
                    ))
            elif isinstance(precondition, str) and precondition.startswith("fact-"):
                if not before.fact_exists(precondition):
                    findings.append(_finding(
                        "causal", "material", f"{event_id} precondition {precondition}",
                        "Fact precondition is not established before the scene.", "plot"
                    ))

    return {
        "candidate": plan_id,
        "critic": "plan-hard-audit",
        "verdict": _verdict(findings),
        "confidence": 1.0,
        "findings": findings,
    }


def _normalized(value: Any) -> str:
    return " ".join(str(value).lower().split())


def architecture_signature(plan: dict) -> tuple:
    return (
        _normalized(plan.get("tactic", "")),
        _normalized(plan.get("turn", "")),
        _normalized(plan.get("cost", "")),
        tuple(sorted(_normalized(item) for item in plan.get("reader_learns", []))),
    )


def diversity_floor(plans: list[dict]) -> dict:
    issues: list[str] = []
    count = len(plans)
    if count < MIN_PLANS:
        issues.append(f"need at least {MIN_PLANS} hard-feasible scene plans; got {count}")
    if count > MAX_PLANS:
        issues.append(f"keep the comparison set to at most {MAX_PLANS} scene plans; got {count}")
    signatures = {architecture_signature(plan) for plan in plans}
    if count >= MIN_PLANS and len(signatures) < MIN_PLANS:
        issues.append(
            f"scene-plan batch contains only {len(signatures)} distinct tactic/turn/cost/disclosure "
            f"signatures across {count} plans; relabeling one plan does not widen search"
        )
    dimensions = {
        "tactic": len({_normalized(plan.get("tactic", "")) for plan in plans}),
        "turn": len({_normalized(plan.get("turn", "")) for plan in plans}),
        "cost": len({_normalized(plan.get("cost", "")) for plan in plans}),
        "reader_learns": len({
            tuple(sorted(_normalized(item) for item in plan.get("reader_learns", [])))
            for plan in plans
        }),
    }
    if count >= MIN_PLANS:
        for dimension, distinct in dimensions.items():
            if distinct < 2:
                issues.append(f"scene-plan search does not vary {dimension}; found {distinct} distinct value(s)")
    return {
        "ok": not issues,
        "issues": issues,
        "plans": count,
        "distinct_signatures": len(signatures),
        "dimension_diversity": dimensions,
    }


def _reviews(project: Path, scene_id: str) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in sorted(_review_dir(project, scene_id).glob("*.json")):
        value = _load_json(path, None)
        if isinstance(value, dict):
            records.append((path, value))
    return records


def _review_summary(project: Path, scene_id: str, plan_id: str, plan_sha256: str) -> dict:
    current: list[dict] = []
    stale: list[dict] = []
    invalid: list[dict] = []
    for path, review in _reviews(project, scene_id):
        if review.get("plan_id") != plan_id:
            continue
        errors = schema.validate_named(review, "plan-review")
        item = {"path": str(path.relative_to(project)), "review": review}
        if errors:
            item["errors"] = errors
            invalid.append(item)
        elif review.get("plan_sha256") != plan_sha256:
            stale.append(item)
        else:
            current.append(item)
    return {
        "current": current,
        "stale": stale,
        "invalid": invalid,
        "has_current_review": bool(current),
        "has_current_pass": any(
            item["review"].get("verdict") == "pass"
            and not any(
                finding.get("severity") in BLOCKING_SEVERITIES
                for finding in item["review"].get("findings", [])
            )
            for item in current
        ),
    }


def _batch_fingerprint(plans: list[dict]) -> str:
    entries = sorted(
        ({"plan_id": plan["plan_id"], "sha256": plan["sha256"]} for plan in plans),
        key=lambda item: item["plan_id"],
    )
    return acceptance.sha256_bytes(acceptance.canonical_json_bytes(entries))


def search_status(project: Path, scene_id: str) -> dict:
    project = Path(project)
    records: list[dict] = []
    hard_feasible: list[dict] = []
    for path, plan in load_plans(project, scene_id):
        digest = _sha(path)
        hard = audit_plan(project, scene_id, plan)
        reviews = _review_summary(project, scene_id, str(plan.get("plan_id", path.stem)), digest)
        record = {
            "plan_id": plan.get("plan_id", path.stem),
            "path": str(path.relative_to(project)),
            "sha256": digest,
            "plan": plan,
            "hard_audit": hard,
            "reviews": reviews,
        }
        records.append(record)
        if hard.get("verdict") == "pass":
            hard_feasible.append(record)
    floor = diversity_floor([record["plan"] for record in hard_feasible])
    review_complete = bool(hard_feasible) and all(
        record["reviews"]["has_current_review"] for record in hard_feasible
    )
    batch_fingerprint = _batch_fingerprint(hard_feasible) if hard_feasible else None
    selection = latest_selection(project, scene_id, records=records, batch_fingerprint=batch_fingerprint)
    return {
        "scene_id": scene_id,
        "plans": records,
        "hard_feasible_plan_ids": [record["plan_id"] for record in hard_feasible],
        "diversity_floor": floor,
        "review_complete": review_complete,
        "ready_for_selection": floor["ok"] and review_complete,
        "batch_fingerprint": batch_fingerprint,
        "latest_selection": selection,
        "selection_policy": (
            "No automatic best-plan score exists. Selection must explicitly bind one or two hard-"
            "feasible plans with current reviewer evidence and record who chose them and why."
        ),
    }


def review_packet(project: Path, scene_id: str, plan_id: str, context_bundle: dict) -> dict:
    project = Path(project)
    path = _plan_path(project, scene_id, plan_id)
    if not path.exists():
        return {"error": f"unknown scene plan {plan_id!r}"}
    plan = _load_json(path, {})
    return {
        "scene_id": scene_id,
        "plan_id": plan_id,
        "plan_sha256": _sha(path),
        "plan": plan,
        "context": context_bundle,
        "review_questions": [
            "Is the tactic feasible from the characters' actual knowledge, capability, resources, and motives?",
            "Does the turn arise from character/world pressure rather than authorial convenience?",
            "Is the stated cost concrete and causally attached to the tactic/turn?",
            "Does the disclosure plan control what the reader learns without requiring prose-level mind reading?",
            "Run the 'why don't they just...?' test for each easy solution: check available information, capability, cost, and motive. Flag unsupported conflict, not merely non-optimal behavior.",
        ],
        "boundary": (
            "This packet is plan-aware and contains no candidate prose. Prefix-reader judgment is "
            "reserved for realized prose; this review addresses feasibility and intentionality."
        ),
    }


def record_review(project: Path, scene_id: str, plan_id: str, reviewer: str, verdict: str,
                  findings: list | None = None, confidence: float = 1.0,
                  easy_solution_assessments: list | None = None) -> dict:
    project = Path(project)
    plan_path = _plan_path(project, scene_id, plan_id)
    if not plan_path.exists():
        return {"error": f"unknown scene plan {plan_id!r}"}
    findings = list(findings or [])
    assessments = list(easy_solution_assessments or [])
    plan = _load_json(plan_path, {})
    expected_solutions = {
        _normalized(item.get("solution", ""))
        for item in plan.get("easy_solution_checks", [])
        if isinstance(item, dict) and _normalized(item.get("solution", ""))
    }
    assessed_solutions = {
        _normalized(item.get("solution", ""))
        for item in assessments
        if isinstance(item, dict) and _normalized(item.get("solution", ""))
    }
    if assessed_solutions != expected_solutions:
        missing = sorted(expected_solutions - assessed_solutions)
        extra = sorted(assessed_solutions - expected_solutions)
        return {
            "error": "plan review must assess every easy-solution check exactly once",
            "missing_solutions": missing,
            "unknown_solutions": extra,
        }
    if verdict == "pass" and any(f.get("severity") in BLOCKING_SEVERITIES for f in findings):
        return {"error": "plan review cannot pass while carrying a material/fatal finding"}
    if verdict == "pass" and any(
        item.get("verdict") != "supported_conflict" for item in assessments if isinstance(item, dict)
    ):
        return {
            "error": "plan review cannot pass while an easy-solution assessment is unsupported or uncertain"
        }
    record = {
        "schema_version": 1,
        "scene_id": scene_id,
        "plan_id": plan_id,
        "plan_sha256": _sha(plan_path),
        "reviewer": reviewer,
        "verdict": verdict,
        "confidence": confidence,
        "findings": findings,
        "easy_solution_assessments": assessments,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = schema.validate_named(record, "plan-review")
    if errors:
        return {"error": "invalid plan review: " + "; ".join(errors)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = _review_dir(project, scene_id) / f"{plan_id}--{reviewer}--{stamp}-{uuid.uuid4().hex[:8]}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _selection_files(project: Path, scene_id: str) -> list[Path]:
    return sorted(_selection_dir(project, scene_id).glob("selection-*.json"))


def selection_errors(project: Path, scene_id: str, selection: dict,
                     records: list[dict] | None = None,
                     batch_fingerprint: str | None = None) -> list[str]:
    errors = schema.validate_named(selection, "plan-selection")
    if errors:
        return errors
    if selection.get("scene_id") != scene_id:
        errors.append(f"selection belongs to {selection.get('scene_id')!r}, not {scene_id!r}")
        return errors
    if records is None:
        status = search_status(project, scene_id)
        records = status["plans"]
        batch_fingerprint = status.get("batch_fingerprint")
    by_id = {record["plan_id"]: record for record in records}
    if selection.get("batch_fingerprint") != batch_fingerprint:
        errors.append("selection batch fingerprint is stale")
    for selected in selection.get("selected_plans", []):
        record = by_id.get(selected.get("plan_id"))
        if record is None:
            errors.append(f"selected plan {selected.get('plan_id')!r} no longer exists")
            continue
        if selected.get("sha256") != record.get("sha256"):
            errors.append(f"selected plan {selected.get('plan_id')!r} hash is stale")
        if record.get("hard_audit", {}).get("verdict") != "pass":
            errors.append(f"selected plan {selected.get('plan_id')!r} does not pass hard feasibility")
        if not record.get("reviews", {}).get("has_current_pass"):
            errors.append(f"selected plan {selected.get('plan_id')!r} has no current passing plan review")
    return errors


def latest_selection(project: Path, scene_id: str, *, records: list[dict] | None = None,
                     batch_fingerprint: str | None = None) -> dict | None:
    files = _selection_files(project, scene_id)
    if not files:
        return None
    path = files[-1]
    selection = _load_json(path, {})
    errors = selection_errors(
        project, scene_id, selection, records=records, batch_fingerprint=batch_fingerprint
    )
    return {
        "path": str(path.relative_to(project)),
        "selection": selection,
        "status": "current" if not errors else "stale_or_invalid",
        "errors": errors,
    }


def select_plans(project: Path, scene_id: str, plan_ids: list[str], decided_by: str,
                 reason: str) -> dict:
    project = Path(project)
    if not 1 <= len(plan_ids) <= 2 or len(set(plan_ids)) != len(plan_ids):
        return {"error": "select one or two distinct plan ids"}
    status = search_status(project, scene_id)
    if not status["ready_for_selection"]:
        reasons = list(status["diversity_floor"]["issues"])
        if not status["review_complete"]:
            reasons.append("every hard-feasible plan needs a current plan-aware review")
        return {"error": "plan search is not ready for selection: " + "; ".join(reasons)}
    by_id = {record["plan_id"]: record for record in status["plans"]}
    selected: list[dict] = []
    for plan_id in plan_ids:
        record = by_id.get(plan_id)
        if record is None:
            return {"error": f"unknown scene plan {plan_id!r}"}
        if record["hard_audit"].get("verdict") != "pass":
            return {"error": f"plan {plan_id!r} does not pass hard feasibility"}
        if not record["reviews"]["has_current_pass"]:
            return {"error": f"plan {plan_id!r} has no current passing plan-aware review"}
        selected.append({"plan_id": plan_id, "sha256": record["sha256"]})
    now = datetime.now(timezone.utc)
    selection_id = f"selection-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"
    record = {
        "schema_version": 1,
        "scene_id": scene_id,
        "selection_id": selection_id,
        "batch_fingerprint": status["batch_fingerprint"],
        "selected_plans": selected,
        "decided_by": decided_by,
        "reason": reason,
        "selected_at": now.isoformat(),
    }
    errors = schema.validate_named(record, "plan-selection")
    if errors:
        return {"error": "invalid plan selection: " + "; ".join(errors)}
    path = _selection_dir(project, scene_id) / f"{selection_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def selected_plans(project: Path, scene_id: str) -> list[dict]:
    status = search_status(project, scene_id)
    latest = status.get("latest_selection")
    if not latest or latest.get("status") != "current":
        return []
    by_id = {record["plan_id"]: record for record in status["plans"]}
    return [
        by_id[item["plan_id"]]["plan"]
        for item in latest["selection"].get("selected_plans", [])
        if item.get("plan_id") in by_id
    ]
