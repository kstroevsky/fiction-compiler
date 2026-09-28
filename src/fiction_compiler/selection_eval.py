"""Frozen candidate-pool experiments for measuring selection value.

The production tournament answers a workflow question: which currently eligible candidate should the
operator consider?  This module answers a different empirical question from the 2026-09-28 audit:
does a selector beat first/random choices on the *same already-generated pool* for independently
recorded readers, at what observed cost, and with what missing evidence?

The mechanics here are deliberately modest.  Code freezes exact bytes and generation order, blinds
identity, counterbalances every pair, records immutable reader/selector/operation evidence, and
computes descriptive summaries.  It does not turn a small sample into a significance claim or treat
missing token/cost metadata as zero.
"""
from __future__ import annotations

import json
import random
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, schema, tournament
from .workspace import resolve_scene_candidate, validate_scene_id


_EXPERIMENT_ID_RE = re.compile(r"^selection-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")
_PAIR_ID_RE = re.compile(r"^pair-[0-9]{3}-(?:forward|reverse)$")
_AUDIENCE_COHORTS = {"target_reader", "expert_reader"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _experiment_id(now: datetime | None = None) -> str:
    now = now or _now()
    return f"selection-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"


def _validate_experiment_id(experiment_id: str) -> str:
    if not isinstance(experiment_id, str) or _EXPERIMENT_ID_RE.fullmatch(experiment_id) is None:
        raise ValueError(f"invalid experiment_id {experiment_id!r}")
    return experiment_id


def _root(project: Path, scene_id: str) -> Path:
    validate_scene_id(scene_id)
    return Path(project) / ".runs" / "selection-eval" / scene_id


def _dir(project: Path, scene_id: str, experiment_id: str) -> Path:
    return _root(project, scene_id) / _validate_experiment_id(experiment_id)


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def _manifest_path(project: Path, scene_id: str, experiment_id: str) -> Path:
    return _dir(project, scene_id, experiment_id) / "pool.json"


def _pool_fingerprint(candidates: list[dict]) -> str:
    identity = [
        {
            "candidate": item["candidate"],
            "sha256": item["sha256"],
            "generation_index": item["generation_index"],
            "blind_label": item["blind_label"],
        }
        for item in candidates
    ]
    return acceptance.sha256_bytes(acceptance.canonical_json_bytes(identity))


def _pair_schedule(labels: list[str]) -> list[dict]:
    pairs: list[dict] = []
    number = 1
    for left_index, left in enumerate(labels):
        for right in labels[left_index + 1:]:
            base = f"pair-{number:03d}"
            pairs.append({"pair_id": f"{base}-forward", "left_label": left, "right_label": right})
            pairs.append({"pair_id": f"{base}-reverse", "left_label": right, "right_label": left})
            number += 1
    return pairs


def freeze_pool(project: Path, scene_id: str, candidates: list[str], seed: int = 0) -> dict:
    """Freeze one ordered generation pool before selector or reader evidence is collected."""
    project = Path(project)
    validate_scene_id(scene_id)
    if not isinstance(candidates, list) or len(candidates) < 2:
        return {"error": "selection experiment needs at least two generated candidates"}
    if len(candidates) > 26:
        return {"error": "selection experiment supports at most 26 blinded candidates"}
    if len(set(candidates)) != len(candidates):
        return {"error": "candidate pool contains duplicate entries"}

    resolved: list[tuple[str, Path, bytes, str]] = []
    try:
        for candidate in candidates:
            path = resolve_scene_candidate(project, scene_id, candidate)
            if not path.exists() or not path.is_file():
                return {"error": f"candidate does not exist: {candidate!r}"}
            raw = path.read_bytes()
            resolved.append((path.name, path, raw, acceptance.sha256_bytes(raw)))
    except ValueError as exc:
        return {"error": str(exc)}

    names = [name for name, _, _, _ in resolved]
    if len(set(names)) != len(names):
        return {"error": "candidate pool resolves multiple inputs to the same candidate filename"}
    label_by_name, _ = tournament.anonymize(names, seed=seed)
    records = [
        {
            "candidate": name,
            "sha256": digest,
            "generation_index": index,
            "blind_label": label_by_name[name],
        }
        for index, (name, _, _, digest) in enumerate(resolved)
    ]
    fingerprint = _pool_fingerprint(records)
    created = _now()
    experiment_id = _experiment_id(created)
    run_dir = _dir(project, scene_id, experiment_id)
    if run_dir.exists():
        return {"error": f"selection experiment collision at {experiment_id}"}

    manifest = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "seed": seed,
        "pool_fingerprint": fingerprint,
        "candidates": records,
        "pairs": _pair_schedule(sorted(label_by_name.values())),
        "created_at": created.isoformat(),
    }
    errors = schema.validate_named(manifest, "selection-pool")
    if errors:
        return {"error": "invalid selection pool: " + "; ".join(errors)}

    # A unique run directory makes this a create-only evidence transaction.  Write frozen prose
    # first, then the manifest last: existence of pool.json means the complete pool is available.
    for name, _, raw, _ in resolved:
        label = label_by_name[name]
        acceptance.atomic_write(run_dir / "blind" / f"{label}.md", raw)
    acceptance.atomic_write(run_dir / "pool.json", acceptance.canonical_json_bytes(manifest))
    return {
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": fingerprint,
        "candidates": records,
        "pairs": manifest["pairs"],
        "path": str(run_dir.relative_to(project)),
    }


def _load_pool(project: Path, scene_id: str, experiment_id: str) -> tuple[dict | None, list[str]]:
    path = _manifest_path(project, scene_id, experiment_id)
    if not path.exists():
        return None, [f"selection experiment {experiment_id!r} does not exist"]
    try:
        manifest = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [str(exc)]
    errors = schema.validate_named(manifest, "selection-pool")
    if manifest.get("scene_id") != scene_id:
        errors.append("selection pool scene_id does not match request")
    candidates = manifest.get("candidates", []) if isinstance(manifest.get("candidates"), list) else []
    if candidates and manifest.get("pool_fingerprint") != _pool_fingerprint(candidates):
        errors.append("selection pool fingerprint does not match candidate identity/order")
    for item in candidates:
        if not isinstance(item, dict):
            continue
        label = item.get("blind_label")
        frozen_path = _dir(project, scene_id, experiment_id) / "blind" / f"{label}.md"
        if not frozen_path.exists():
            errors.append(f"frozen blind candidate {label!r} is missing")
        elif acceptance.sha256_bytes(frozen_path.read_bytes()) != item.get("sha256"):
            errors.append(f"frozen blind candidate {label!r} has a content-hash mismatch")
    return manifest, errors


def reader_packet(project: Path, scene_id: str, experiment_id: str) -> dict:
    """Return only blinded frozen prose and counterbalanced pair assignments for readers."""
    project = Path(project)
    try:
        manifest, errors = _load_pool(project, scene_id, experiment_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid selection experiment", "details": errors}
    run_dir = _dir(project, scene_id, experiment_id)
    prose = {
        item["blind_label"]: (run_dir / "blind" / f"{item['blind_label']}.md").read_text(encoding="utf-8")
        for item in manifest["candidates"]
    }
    return {
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": manifest["pool_fingerprint"],
        "candidates": prose,
        "pairs": manifest["pairs"],
        "instructions": (
            "Judge only the blinded texts. Record the scheduled left/right order actually shown. "
            "Tie and abstain are valid outcomes; do not infer candidate identity or generation order."
        ),
    }


def _preference_dir(project: Path, scene_id: str, experiment_id: str) -> Path:
    return _dir(project, scene_id, experiment_id) / "preferences"


def _selector_dir(project: Path, scene_id: str, experiment_id: str) -> Path:
    return _dir(project, scene_id, experiment_id) / "selectors"


def _operation_dir(project: Path, scene_id: str, experiment_id: str) -> Path:
    return _dir(project, scene_id, experiment_id) / "operations"


def record_preference(project: Path, scene_id: str, experiment_id: str, rater_id: str,
                      cohort_kind: str, rater_kind: str, pair_id: str, choice: str,
                      confidence: float | None = None, reason: str | None = None) -> dict:
    """Persist one immutable pairwise reader judgment bound to the exact frozen pool."""
    project = Path(project)
    try:
        manifest, errors = _load_pool(project, scene_id, experiment_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid selection experiment", "details": errors}
    pair = next((item for item in manifest["pairs"] if item.get("pair_id") == pair_id), None)
    if pair is None or _PAIR_ID_RE.fullmatch(pair_id) is None:
        return {"error": f"unknown scheduled pair {pair_id!r}"}
    pair_base = pair_id.rsplit("-", 1)[0]
    for existing_path in sorted(_preference_dir(project, scene_id, experiment_id).glob("*.json")):
        try:
            existing = _load_json(existing_path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return {"error": f"existing preference evidence is unreadable: {existing_path.name}: {exc}"}
        if existing.get("rater_id") == rater_id and str(existing.get("pair_id", "")).rsplit("-", 1)[0] == pair_base:
            return {"error": "one rater may judge at most one orientation of the same candidate pair"}

    record = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": manifest["pool_fingerprint"],
        "rater_id": rater_id,
        "cohort_kind": cohort_kind,
        "rater_kind": rater_kind,
        "pair_id": pair_id,
        "left_label": pair["left_label"],
        "right_label": pair["right_label"],
        "choice": choice,
        "recorded_at": _now().isoformat(),
    }
    if confidence is not None:
        record["confidence"] = confidence
    if reason is not None:
        record["reason"] = reason
    validation = schema.validate_named(record, "pairwise-preference")
    if validation:
        return {"error": "invalid pairwise preference: " + "; ".join(validation)}

    stamp = _now().strftime("%Y%m%dT%H%M%S.%fZ")
    path = _preference_dir(project, scene_id, experiment_id) / f"{stamp}-{uuid.uuid4().hex[:12]}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def record_selector(project: Path, scene_id: str, experiment_id: str, selector: str,
                    candidate: str, provenance: dict | None = None) -> dict:
    """Record a selector's choice before reader outcomes are available."""
    project = Path(project)
    try:
        manifest, errors = _load_pool(project, scene_id, experiment_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid selection experiment", "details": errors}
    if any(_preference_dir(project, scene_id, experiment_id).glob("*.json")):
        return {"error": "selector choices must be frozen before reader preferences are recorded"}
    by_name = {item["candidate"]: item for item in manifest["candidates"]}
    candidate_name = Path(candidate).name
    if candidate_name != candidate:
        return {"error": "selector candidate must be the frozen candidate filename, not a path alias"}
    if candidate_name not in by_name:
        return {"error": f"selector chose candidate outside frozen pool: {candidate!r}"}
    if selector in {"first", "random"}:
        return {"error": "first and random are compiler-owned baselines; do not record them manually"}
    for existing_path in sorted(_selector_dir(project, scene_id, experiment_id).glob("*.json")):
        try:
            existing = _load_json(existing_path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return {"error": f"existing selector evidence is unreadable: {existing_path.name}: {exc}"}
        if existing.get("selector") == selector:
            return {"error": f"selector {selector!r} already has a frozen choice for this experiment"}

    record = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": manifest["pool_fingerprint"],
        "selector": selector,
        "candidate": candidate_name,
        "candidate_sha256": by_name[candidate_name]["sha256"],
        "provenance": dict(provenance or {}),
        "selected_at": _now().isoformat(),
    }
    validation = schema.validate_named(record, "selector-choice")
    if validation:
        return {"error": "invalid selector choice: " + "; ".join(validation)}
    stamp = _now().strftime("%Y%m%dT%H%M%S.%fZ")
    path = _selector_dir(project, scene_id, experiment_id) / f"{selector}--{stamp}-{uuid.uuid4().hex[:8]}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def record_operation(project: Path, scene_id: str, experiment_id: str, phase: str, status: str,
                     candidate: str | None = None, provider: str | None = None,
                     model: str | None = None, input_tokens: int | None = None,
                     output_tokens: int | None = None, cost_usd: float | None = None,
                     failure_reason: str | None = None) -> dict:
    """Record cost/failure evidence without converting unknown usage into zero."""
    project = Path(project)
    try:
        manifest, errors = _load_pool(project, scene_id, experiment_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid selection experiment", "details": errors}
    by_name = {item["candidate"]: item for item in manifest["candidates"]}
    candidate_name = Path(candidate).name if candidate else None
    if candidate is not None and candidate_name != candidate:
        return {"error": "operation candidate must be the frozen candidate filename, not a path alias"}
    if candidate_name is not None and candidate_name not in by_name:
        return {"error": f"operation candidate is outside frozen pool: {candidate!r}"}
    if status == "failure" and not failure_reason:
        return {"error": "failed operation needs a failure_reason"}

    record: dict[str, Any] = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": manifest["pool_fingerprint"],
        "operation_id": f"op-{uuid.uuid4().hex}",
        "phase": phase,
        "status": status,
        "recorded_at": _now().isoformat(),
    }
    optional = {
        "candidate": candidate_name,
        "provider": provider,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "failure_reason": failure_reason,
    }
    record.update({key: value for key, value in optional.items() if value is not None})
    validation = schema.validate_named(record, "selection-operation")
    if validation:
        return {"error": "invalid selection operation: " + "; ".join(validation)}
    path = _operation_dir(project, scene_id, experiment_id) / f"{record['operation_id']}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _validated_records(path: Path, schema_name: str, manifest: dict) -> tuple[list[dict], list[str]]:
    valid: list[dict] = []
    errors: list[str] = []
    for record_path in sorted(path.glob("*.json")):
        try:
            record = _load_json(record_path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{record_path.name}: unreadable evidence ({exc})")
            continue
        problems = schema.validate_named(record, schema_name)
        if record.get("experiment_id") != manifest["experiment_id"]:
            problems.append("experiment_id does not match pool")
        if record.get("scene_id") != manifest["scene_id"]:
            problems.append("scene_id does not match pool")
        if record.get("pool_fingerprint") != manifest["pool_fingerprint"]:
            problems.append("pool_fingerprint is stale")
        if problems:
            errors.append(f"{record_path.name}: {'; '.join(problems)}")
        else:
            valid.append(record)
    return valid, errors


def _audience_preferences(preferences: list[dict]) -> list[dict]:
    return [
        record for record in preferences
        if record.get("rater_kind") == "human" and record.get("cohort_kind") in _AUDIENCE_COHORTS
    ]


def _candidate_stats(manifest: dict, preferences: list[dict]) -> dict[str, dict]:
    name_by_label = {item["blind_label"]: item["candidate"] for item in manifest["candidates"]}
    stats = {
        item["candidate"]: {"wins": 0, "losses": 0, "ties": 0, "abstentions": 0,
                            "non_abstain_comparisons": 0, "observed_preference_score": None}
        for item in manifest["candidates"]
    }
    for pref in preferences:
        left = name_by_label[pref["left_label"]]
        right = name_by_label[pref["right_label"]]
        choice = pref["choice"]
        if choice == "abstain":
            stats[left]["abstentions"] += 1
            stats[right]["abstentions"] += 1
            continue
        stats[left]["non_abstain_comparisons"] += 1
        stats[right]["non_abstain_comparisons"] += 1
        if choice == "tie":
            stats[left]["ties"] += 1
            stats[right]["ties"] += 1
        elif choice == "left":
            stats[left]["wins"] += 1
            stats[right]["losses"] += 1
        elif choice == "right":
            stats[right]["wins"] += 1
            stats[left]["losses"] += 1
    for item in stats.values():
        denominator = item["non_abstain_comparisons"]
        if denominator:
            item["observed_preference_score"] = (item["wins"] + 0.5 * item["ties"]) / denominator
    return stats


def _coverage(manifest: dict, preferences: list[dict]) -> dict:
    name_by_label = {item["blind_label"]: item["candidate"] for item in manifest["candidates"]}
    required: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for pair in manifest["pairs"]:
        a, b = name_by_label[pair["left_label"]], name_by_label[pair["right_label"]]
        key = tuple(sorted((a, b)))
        required[key].add((a, b))
    observed: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for pref in preferences:
        if pref.get("choice") == "abstain":
            continue
        a, b = name_by_label[pref["left_label"]], name_by_label[pref["right_label"]]
        observed[tuple(sorted((a, b)))].add((a, b))
    missing_pairs = [list(key) for key in sorted(required) if not observed.get(key)]
    missing_orientations = [
        {"pair": list(key), "missing": [list(order) for order in sorted(required[key] - observed.get(key, set()))]}
        for key in sorted(required)
        if required[key] - observed.get(key, set())
    ]
    complete = not missing_pairs and not missing_orientations
    return {
        "complete_counterbalanced_pair_coverage": complete,
        "missing_pairs": missing_pairs,
        "missing_orientations": missing_orientations,
    }


def _cost_summary(operations: list[dict]) -> dict:
    phases: dict[str, dict[str, int]] = {}
    for operation in operations:
        bucket = phases.setdefault(operation["phase"], {"operations": 0, "failures": 0})
        bucket["operations"] += 1
        bucket["failures"] += 1 if operation["status"] == "failure" else 0
    input_known = [op["input_tokens"] for op in operations if "input_tokens" in op]
    output_known = [op["output_tokens"] for op in operations if "output_tokens" in op]
    cost_known = [op["cost_usd"] for op in operations if "cost_usd" in op]
    return {
        "operations": len(operations),
        "failures": sum(1 for op in operations if op["status"] == "failure"),
        "by_phase": phases,
        "input_tokens": {"known_records": len(input_known), "missing_records": len(operations) - len(input_known),
                         "known_total": sum(input_known)},
        "output_tokens": {"known_records": len(output_known), "missing_records": len(operations) - len(output_known),
                          "known_total": sum(output_known)},
        "cost_usd": {"known_records": len(cost_known), "missing_records": len(operations) - len(cost_known),
                     "known_total": sum(cost_known)},
        "note": "Missing token/cost metadata is unknown and is not counted as zero.",
    }


def report(project: Path, scene_id: str, experiment_id: str) -> dict:
    """Describe selector performance against independent pairwise reader evidence."""
    project = Path(project)
    try:
        manifest, pool_errors = _load_pool(project, scene_id, experiment_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None:
        return {"error": "selection experiment not found", "details": pool_errors}
    if pool_errors:
        return {"status": "invalid", "experiment_id": experiment_id, "errors": pool_errors}

    run_dir = _dir(project, scene_id, experiment_id)
    preferences, preference_errors = _validated_records(
        _preference_dir(project, scene_id, experiment_id), "pairwise-preference", manifest
    )
    selectors, selector_errors = _validated_records(
        _selector_dir(project, scene_id, experiment_id), "selector-choice", manifest
    )
    operations, operation_errors = _validated_records(
        _operation_dir(project, scene_id, experiment_id), "selection-operation", manifest
    )
    record_errors = preference_errors + selector_errors + operation_errors
    if record_errors:
        return {"status": "invalid", "experiment_id": experiment_id, "errors": record_errors}

    audience = _audience_preferences(preferences)
    stats = _candidate_stats(manifest, audience)
    coverage = _coverage(manifest, audience)
    if not audience:
        evidence_status = "insufficient_no_independent_human_audience_judgments"
    elif not coverage["complete_counterbalanced_pair_coverage"]:
        evidence_status = "insufficient_pair_or_order_coverage"
    else:
        evidence_status = "descriptive_complete"

    scored = {
        candidate: values["observed_preference_score"]
        for candidate, values in stats.items()
        if values["observed_preference_score"] is not None
    }
    top_observed: list[str] = []
    best_score: float | None = None
    if scored:
        best_score = max(scored.values())
        top_observed = sorted(candidate for candidate, value in scored.items() if value == best_score)

    ordered = sorted(manifest["candidates"], key=lambda item: item["generation_index"])
    first = ordered[0]["candidate"]
    random_choice = random.Random(f"{manifest['seed']}:selector-random").choice(
        [item["candidate"] for item in ordered]
    )
    choices = [
        {"selector": "first", "candidate": first, "source": "compiler_baseline"},
        {"selector": "random", "candidate": random_choice, "source": "compiler_baseline"},
    ]
    choices.extend({
        "selector": record["selector"],
        "candidate": record["candidate"],
        "source": "recorded_selector",
        "provenance": record.get("provenance", {}),
    } for record in selectors)
    selector_results: list[dict] = []
    for choice in choices:
        candidate_score = stats.get(choice["candidate"], {}).get("observed_preference_score")
        result = dict(choice)
        result["observed_preference_score"] = candidate_score
        if evidence_status == "descriptive_complete" and candidate_score is not None and best_score is not None:
            result["empirical_regret"] = best_score - candidate_score
        else:
            result["empirical_regret"] = None
        selector_results.append(result)

    cohorts: dict[str, int] = defaultdict(int)
    rater_kinds: dict[str, int] = defaultdict(int)
    for pref in preferences:
        cohorts[pref["cohort_kind"]] += 1
        rater_kinds[pref["rater_kind"]] += 1

    return {
        "status": "valid",
        "experiment_id": experiment_id,
        "scene_id": scene_id,
        "pool_fingerprint": manifest["pool_fingerprint"],
        "generation_order": [item["candidate"] for item in ordered],
        "reader_evidence": {
            "status": evidence_status,
            "records": len(preferences),
            "audience_records_used": len(audience),
            "by_cohort": dict(sorted(cohorts.items())),
            "by_rater_kind": dict(sorted(rater_kinds.items())),
            "coverage": coverage,
            "candidate_stats": stats,
            "top_by_observed_score": top_observed,
            "note": (
                "Scores and regret are descriptive for this frozen pool. They are not a powered "
                "population estimate, significance test, or evidence of general literary superiority."
            ),
        },
        "selectors": selector_results,
        "cost_and_failures": _cost_summary(operations),
        "artifacts": {
            "run_dir": str(run_dir.relative_to(project)),
            "preferences": len(preferences),
            "selectors": len(selectors),
            "operations": len(operations),
        },
    }
