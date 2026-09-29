"""Matched-cost writer-family and edit-vs-regeneration study bindings.

This module composes two existing evidence layers rather than inventing another evaluator: exact
candidate bytes and reader preferences come from ``selection_eval``; provider/model/cost provenance
comes from immutable ``run_manifest`` operations.  The study artifact freezes the arm labels before
reader outcomes exist and reports evidence completeness without ranking writer families.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, run_manifest, schema, selection_eval
from .workspace import validate_scene_id


_ALLOWED_HYPOTHESES = {"writer-family", "edit-vs-regeneration"}
_ALLOWED_PHASES = {"generation", "critique", "revision"}
_ALLOWED_STRATEGIES = {"independent-draft", "regenerate", "edit"}
_METERED_EXECUTORS = {"external_model", "role_runner", "unknown"}


def _study_path(project: Path, scene_id: str, experiment_id: str) -> Path:
    validate_scene_id(scene_id)
    return Path(project) / ".runs" / "selection-eval" / scene_id / experiment_id / "writer-study.json"


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _selection_manifest(project: Path, scene_id: str, experiment_id: str) -> tuple[dict | None, list[str]]:
    result = selection_eval.pool_manifest(project, scene_id, experiment_id)
    if result.get("status") == "valid":
        return result["manifest"], []
    details = result.get("errors") or result.get("details")
    if isinstance(details, list):
        return None, [str(item) for item in details]
    if details is not None:
        return None, [str(details)]
    return None, [str(result.get("error", "invalid selection pool"))]


def _operation_total_tokens(operation: dict) -> int | None:
    total = operation.get("total_tokens")
    if isinstance(total, int) and not isinstance(total, bool):
        return total
    input_tokens = operation.get("input_tokens")
    output_tokens = operation.get("output_tokens")
    if (isinstance(input_tokens, int) and not isinstance(input_tokens, bool) and
            isinstance(output_tokens, int) and not isinstance(output_tokens, bool)):
        return input_tokens + output_tokens
    return None


def _arm_evidence(project: Path, scene_id: str, arm: dict, included_phases: list[str]) -> dict:
    evidence = run_manifest.operation_evidence(project, scene_id, arm["run_id"])
    if evidence.get("status") != "valid":
        return {"status": "invalid", "errors": evidence.get("errors") or evidence.get("details") or [evidence.get("error", "invalid scene run")]}

    operations = [op for op in evidence["operations"] if op.get("phase") in included_phases]
    if not operations:
        return {"status": "invalid", "errors": ["no operations exist in the predeclared included phases"]}
    if "operation_ids" in arm or "operations_sha256" in arm:
        current_ids = [op["operation_id"] for op in operations]
        if current_ids != arm.get("operation_ids"):
            return {
                "status": "invalid",
                "errors": ["included scene-run operation set changed after writer-study freeze"],
            }
        current_sha = acceptance.sha256_bytes(acceptance.canonical_json_bytes(operations))
        if current_sha != arm.get("operations_sha256"):
            return {
                "status": "invalid",
                "errors": ["included scene-run operation evidence changed after writer-study freeze"],
            }
    matching = [
        op for op in operations
        if op.get("status") == "success"
        and isinstance(op.get("candidate"), dict)
        and op["candidate"].get("sha256") == arm["candidate_sha256"]
        and op.get("provider") == arm["provider"]
        and op.get("model") == arm["model"]
    ]
    expected_phase = "revision" if arm["strategy"] == "edit" else "generation"
    matching = [op for op in matching if op.get("phase") == expected_phase]
    errors: list[str] = []
    if not matching:
        errors.append(
            f"no successful {expected_phase} operation binds candidate {arm['candidate']!r} "
            f"to provider/model {arm['provider']!r}/{arm['model']!r}"
        )

    if arm["strategy"] == "edit":
        source_sha = arm.get("source_candidate_sha256")
        if not source_sha:
            errors.append("edit arm requires source_candidate_sha256")
        elif source_sha == arm["candidate_sha256"]:
            errors.append("edit arm source and output candidate hashes must differ")
        else:
            source_positions = [
                index for index, op in enumerate(operations)
                if op.get("status") == "success"
                and isinstance(op.get("candidate"), dict)
                and op["candidate"].get("sha256") == source_sha
            ]
            output_positions = [operations.index(op) for op in matching]
            if not source_positions or not output_positions or min(source_positions) >= min(output_positions):
                errors.append("edit arm source candidate is not bound by an earlier successful operation in the same run")
    elif arm.get("source_candidate_sha256") is not None:
        errors.append("source_candidate_sha256 is only valid for edit arms")

    return {"status": "valid" if not errors else "invalid", "errors": errors, "operations": operations}


def freeze(
    project: Path,
    scene_id: str,
    selection_experiment_id: str,
    arms: list[dict],
    hypotheses: list[str],
    matching_metric: str,
    max_relative_gap: float = 0.1,
    included_phases: list[str] | None = None,
) -> dict:
    """Freeze writer-study arms after generation and before any reader outcomes are recorded."""
    project = Path(project)
    validate_scene_id(scene_id)
    included_phases = list(included_phases or ["generation", "revision"])
    if not isinstance(hypotheses, list) or not hypotheses or set(hypotheses) - _ALLOWED_HYPOTHESES:
        return {"error": "hypotheses must contain writer-family and/or edit-vs-regeneration"}
    if len(set(hypotheses)) != len(hypotheses):
        return {"error": "hypotheses contains duplicates"}
    if matching_metric not in {"total_tokens", "cost_usd"}:
        return {"error": "matching_metric must be total_tokens or cost_usd"}
    if (not isinstance(max_relative_gap, (int, float)) or isinstance(max_relative_gap, bool) or
            not math.isfinite(float(max_relative_gap)) or not 0 <= float(max_relative_gap) <= 1):
        return {"error": "max_relative_gap must be a finite number between 0 and 1"}
    if not included_phases or len(set(included_phases)) != len(included_phases) or set(included_phases) - _ALLOWED_PHASES:
        return {"error": "included_phases must be unique generation/critique/revision phases"}

    pool, pool_errors = _selection_manifest(project, scene_id, selection_experiment_id)
    if pool is None:
        return {"error": "invalid selection experiment", "details": pool_errors}
    selection_report = selection_eval.report(project, scene_id, selection_experiment_id)
    if selection_report.get("status") != "valid":
        return {"error": "selection experiment report is invalid", "details": selection_report.get("errors", [])}
    if selection_report.get("artifacts", {}).get("preferences", 0):
        return {"error": "writer study must be frozen before reader preferences are recorded"}
    path = _study_path(project, scene_id, selection_experiment_id)
    if path.exists():
        return {"error": "writer study already exists for this selection experiment"}

    if not isinstance(arms, list) or len(arms) != len(pool["candidates"]):
        return {"error": "writer study must bind exactly one arm to every frozen selection candidate"}
    by_candidate = {item["candidate"]: item for item in pool["candidates"]}
    supplied_names = [arm.get("candidate") if isinstance(arm, dict) else None for arm in arms]
    if len(set(supplied_names)) != len(supplied_names) or set(supplied_names) != set(by_candidate):
        return {"error": "writer-study arm candidates must exactly match the frozen selection pool"}

    normalized_arms: list[dict[str, Any]] = []
    for index, arm in enumerate(arms, start=1):
        if not isinstance(arm, dict):
            return {"error": "every writer-study arm must be an object"}
        missing = [key for key in ("candidate", "run_id", "writer_family", "strategy", "provider", "model") if not arm.get(key)]
        if missing:
            return {"error": f"writer-study arm for {arm.get('candidate')!r} is missing {missing}"}
        if arm["strategy"] not in _ALLOWED_STRATEGIES:
            return {"error": f"invalid writer strategy {arm['strategy']!r}"}
        row = {
            "arm_id": f"arm-{index:02d}",
            "candidate": arm["candidate"],
            "candidate_sha256": by_candidate[arm["candidate"]]["sha256"],
            "run_id": arm["run_id"],
            "writer_family": arm["writer_family"],
            "strategy": arm["strategy"],
            "provider": arm["provider"],
            "model": arm["model"],
        }
        if arm.get("source_candidate_sha256") is not None:
            row["source_candidate_sha256"] = arm["source_candidate_sha256"]
        arm_check = _arm_evidence(project, scene_id, row, included_phases)
        if arm_check["status"] != "valid":
            return {"error": f"invalid provenance for {row['candidate']}", "details": arm_check["errors"]}
        row["operation_ids"] = [op["operation_id"] for op in arm_check["operations"]]
        row["operations_sha256"] = acceptance.sha256_bytes(
            acceptance.canonical_json_bytes(arm_check["operations"])
        )
        normalized_arms.append(row)

    families = {arm["writer_family"] for arm in normalized_arms}
    strategies = {arm["strategy"] for arm in normalized_arms}
    family_by_model: dict[tuple[str, str], str] = {}
    for arm in normalized_arms:
        model_key = (arm["provider"], arm["model"])
        prior_family = family_by_model.setdefault(model_key, arm["writer_family"])
        if prior_family != arm["writer_family"]:
            return {
                "error": (
                    f"provider/model {arm['provider']!r}/{arm['model']!r} cannot be relabeled "
                    "as multiple writer families in one study"
                )
            }
    if "writer-family" in hypotheses and len(families) < 2:
        return {"error": "writer-family hypothesis requires at least two declared writer families"}
    if "edit-vs-regeneration" in hypotheses and not (
        "edit" in strategies and strategies & {"independent-draft", "regenerate"}
    ):
        return {"error": "edit-vs-regeneration hypothesis requires an edit arm and a generation/regeneration arm"}

    record = {
        "schema_version": 1,
        "scene_id": scene_id,
        "selection_experiment_id": selection_experiment_id,
        "pool_fingerprint": pool["pool_fingerprint"],
        "hypotheses": hypotheses,
        "matching_metric": matching_metric,
        "max_relative_gap": float(max_relative_gap),
        "included_phases": included_phases,
        "arms": normalized_arms,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = schema.validate_named(record, "writer-study")
    if errors:
        return {"error": "invalid writer study: " + "; ".join(errors)}
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _load_study(project: Path, scene_id: str, selection_experiment_id: str) -> tuple[dict | None, list[str]]:
    path = _study_path(project, scene_id, selection_experiment_id)
    if not path.exists():
        return None, ["writer study does not exist"]
    try:
        record = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"writer study is unreadable: {exc}"]
    errors = schema.validate_named(record, "writer-study")
    if record.get("scene_id") != scene_id:
        errors.append("writer-study scene_id does not match request")
    if record.get("selection_experiment_id") != selection_experiment_id:
        errors.append("writer-study selection_experiment_id does not match request")
    pool, pool_errors = _selection_manifest(project, scene_id, selection_experiment_id)
    if pool is None:
        errors.extend(pool_errors)
    elif record.get("pool_fingerprint") != pool.get("pool_fingerprint"):
        errors.append("writer-study pool_fingerprint is stale")
    return record, errors


def _arm_metric(operations: list[dict], matching_metric: str) -> dict:
    known = 0.0
    unknown: list[str] = []
    for operation in operations:
        if matching_metric == "total_tokens":
            value = _operation_total_tokens(operation)
        else:
            raw = operation.get("cost_usd")
            value = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None
        if value is None:
            if operation.get("executor_kind") in _METERED_EXECUTORS or operation.get("provider") or operation.get("model"):
                unknown.append(operation["operation_id"])
        else:
            known += float(value)
    if matching_metric == "total_tokens":
        known_value: int | float = int(known)
    else:
        known_value = known
    return {"known": known_value, "unknown_operations": unknown, "complete": not unknown}


def report(project: Path, scene_id: str, selection_experiment_id: str) -> dict:
    """Report matched-cost/provenance readiness and bind it to existing blind reader evidence."""
    project = Path(project)
    study, errors = _load_study(project, scene_id, selection_experiment_id)
    if study is None:
        return {"error": "writer study not found", "details": errors}
    if errors:
        return {"status": "invalid", "errors": errors}
    selection_report = selection_eval.report(project, scene_id, selection_experiment_id)
    if selection_report.get("status") != "valid":
        return {"status": "invalid", "errors": selection_report.get("errors", ["selection experiment is invalid"])}

    arm_rows: list[dict] = []
    provenance_errors: list[str] = []
    metric_values: list[float] = []
    all_complete = True
    stats = selection_report["reader_evidence"]["candidate_stats"]
    for arm in study["arms"]:
        evidence = _arm_evidence(project, scene_id, arm, study["included_phases"])
        if evidence["status"] != "valid":
            provenance_errors.extend(f"{arm['candidate']}: {problem}" for problem in evidence["errors"])
            metric = {"known": 0, "unknown_operations": [], "complete": False}
            all_complete = False
        else:
            metric = _arm_metric(evidence["operations"], study["matching_metric"])
            all_complete = all_complete and metric["complete"]
            if metric["complete"]:
                metric_values.append(float(metric["known"]))
        arm_rows.append({
            **arm,
            "matching_metric": metric,
            "reader_preference": stats.get(arm["candidate"], {}),
        })

    if provenance_errors:
        return {"status": "invalid", "errors": provenance_errors}
    relative_gap: float | None = None
    within_tolerance: bool | None = None
    if all_complete and len(metric_values) == len(study["arms"]):
        high, low = max(metric_values), min(metric_values)
        relative_gap = 0.0 if high == 0 else (high - low) / high
        within_tolerance = relative_gap <= study["max_relative_gap"]

    if not all_complete:
        study_status = "incomplete_unknown_matching_cost"
    elif not within_tolerance:
        study_status = "cost_not_matched"
    elif selection_report["reader_evidence"]["status"] == "descriptive_complete":
        study_status = "descriptive_complete"
    else:
        study_status = "ready_for_reader_evidence"

    return {
        "status": "valid",
        "study_status": study_status,
        "scene_id": scene_id,
        "selection_experiment_id": selection_experiment_id,
        "pool_fingerprint": study["pool_fingerprint"],
        "hypotheses": study["hypotheses"],
        "writer_families": sorted({arm["writer_family"] for arm in study["arms"]}),
        "strategies": sorted({arm["strategy"] for arm in study["arms"]}),
        "cost_matching": {
            "metric": study["matching_metric"],
            "included_phases": study["included_phases"],
            "max_relative_gap": study["max_relative_gap"],
            "observed_relative_gap": relative_gap,
            "within_tolerance": within_tolerance,
            "complete": all_complete,
        },
        "arms": arm_rows,
        "reader_evidence": selection_report["reader_evidence"],
        "note": (
            "This binds a matched-cost study design to frozen writer provenance and blind reader evidence. "
            "It does not rank writer families, establish population-level superiority, or turn missing "
            "usage into zero."
        ),
    }


def validation_errors(project: Path) -> list[str]:
    """Validate persisted writer-study artifacts and their current immutable evidence bindings."""
    root = Path(project) / ".runs" / "selection-eval"
    if not root.exists():
        return []
    errors: list[str] = []
    for path in sorted(root.glob("*/selection-*/writer-study.json")):
        scene_id = path.parent.parent.name
        experiment_id = path.parent.name
        result = report(project, scene_id, experiment_id)
        if result.get("status") == "invalid" or "error" in result:
            details = result.get("errors") or result.get("details") or [result.get("error", "invalid writer study")]
            errors.extend(f"{path.relative_to(project)}: {problem}" for problem in details)
    return errors
