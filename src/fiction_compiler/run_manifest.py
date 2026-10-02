"""Resumable, budget-aware provenance for one scene's operational loop.

The compiler does not author prose.  This module records what external/manual/compiler operations
actually happened, freezes candidate bytes touched by those operations, and derives resumable status
without overwriting prior evidence.  Unknown provider usage remains unknown rather than becoming 0.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, schema
from .workspace import resolve_scene_candidate, validate_scene_id


RUN_ID_RE = re.compile(r"^run-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")
STEP_ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ROLE_RUN_ID_RE = re.compile(r"^[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PHASES = {"generation", "critique", "revision", "selection", "reader", "promotion", "other"}
EXECUTOR_KINDS = {"compiler", "human", "external_model", "role_runner", "unknown"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_run_id() -> str:
    stamp = _now().strftime("%Y%m%dT%H%M%S%fZ")
    return f"run-{stamp}-{uuid.uuid4().hex[:12]}"


def _run_dir(project: Path, scene_id: str, run_id: str) -> Path:
    validate_scene_id(scene_id)
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError(f"invalid run_id {run_id!r}")
    return Path(project) / ".runs" / "scene-runs" / scene_id / run_id


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _normalize_steps(steps: list[dict]) -> list[dict]:
    if not isinstance(steps, list) or not steps:
        raise ValueError("scene run needs at least one declared step")
    normalized: list[dict] = []
    seen: set[str] = set()
    for raw in steps:
        if not isinstance(raw, dict):
            raise ValueError("each scene-run step must be an object")
        step_id = raw.get("step_id")
        phase = raw.get("phase")
        if not isinstance(step_id, str) or STEP_ID_RE.fullmatch(step_id) is None:
            raise ValueError(f"invalid step_id {step_id!r}; use lowercase letters/digits/hyphens")
        if step_id in seen:
            raise ValueError(f"duplicate scene-run step_id {step_id!r}")
        if phase not in PHASES:
            raise ValueError(f"invalid scene-run phase {phase!r}")
        item = {"step_id": step_id, "phase": phase}
        description = raw.get("description")
        if description is not None:
            if not isinstance(description, str) or not description.strip():
                raise ValueError(f"step {step_id!r} description must be non-empty")
            item["description"] = description.strip()
        normalized.append(item)
        seen.add(step_id)
    return normalized


def _normalize_budgets(budgets: dict | None) -> dict:
    if budgets is not None and not isinstance(budgets, dict):
        raise ValueError("scene-run budgets must be an object")
    value = dict(budgets or {})
    allowed = {"max_operations", "max_total_tokens", "max_cost_usd"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValueError(f"unknown scene-run budget fields: {extra}")
    for key in ("max_operations", "max_total_tokens"):
        if key in value and (not isinstance(value[key], int) or isinstance(value[key], bool) or value[key] < 0):
            raise ValueError(f"{key} must be a non-negative integer")
    if "max_cost_usd" in value:
        cost = value["max_cost_usd"]
        if (not isinstance(cost, (int, float)) or isinstance(cost, bool) or
                not math.isfinite(float(cost)) or cost < 0):
            raise ValueError("max_cost_usd must be a finite non-negative number")
        value["max_cost_usd"] = float(cost)
    return value


def _non_negative_int(name: str, value: int | None) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _non_negative_number(name: str, value: float | None) -> float | None:
    if value is None:
        return None
    if (not isinstance(value, (int, float)) or isinstance(value, bool) or
            not math.isfinite(float(value)) or value < 0):
        raise ValueError(f"{name} must be a finite non-negative number")
    return float(value)


def _manifest(project: Path, scene_id: str, run_id: str) -> tuple[dict | None, list[str]]:
    path = _run_dir(project, scene_id, run_id) / "manifest.json"
    if not path.exists():
        return None, [f"scene run {run_id!r} does not exist"]
    try:
        value = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [str(exc)]
    errors = schema.validate_named(value, "scene-run-manifest")
    if value.get("scene_id") != scene_id:
        errors.append("scene-run manifest scene_id does not match request")
    if value.get("run_id") != run_id:
        errors.append("scene-run manifest run_id does not match request")
    return value, errors


def start(project: Path, scene_id: str, steps: list[dict], budgets: dict | None = None,
          run_id: str | None = None) -> dict:
    """Create a run manifest, or idempotently resume the same caller-supplied run id."""
    project = Path(project)
    validate_scene_id(scene_id)
    try:
        normalized_steps = _normalize_steps(steps)
        normalized_budgets = _normalize_budgets(budgets)
    except ValueError as exc:
        return {"error": str(exc)}
    run_id = run_id or _new_run_id()
    try:
        run_dir = _run_dir(project, scene_id, run_id)
    except ValueError as exc:
        return {"error": str(exc)}

    path = run_dir / "manifest.json"
    if path.exists():
        existing, errors = _manifest(project, scene_id, run_id)
        if existing is None or errors:
            return {"error": "invalid existing scene run", "details": errors}
        if existing.get("steps") != normalized_steps or existing.get("budgets", {}) != normalized_budgets:
            return {"error": "run_id already exists with different steps or budgets"}
        result = status(project, scene_id, run_id)
        result["resumed"] = True
        return result
    if run_dir.exists() and any(run_dir.iterdir()):
        return {"error": f"scene-run directory exists without a manifest: {run_dir}"}

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "scene_id": scene_id,
        "steps": normalized_steps,
        "budgets": normalized_budgets,
        "created_at": _now().isoformat(),
    }
    errors = schema.validate_named(manifest, "scene-run-manifest")
    if errors:
        return {"error": "invalid scene-run manifest: " + "; ".join(errors)}
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(manifest))
    result = status(project, scene_id, run_id)
    result["resumed"] = False
    return result


def _candidate_snapshot(project: Path, scene_id: str, run_id: str, candidate: str,
                        expected_sha256: str | None = None) -> tuple[dict | None, str | None]:
    try:
        path = resolve_scene_candidate(project, scene_id, candidate)
    except ValueError as exc:
        return None, str(exc)
    name = path.name
    run_dir = _run_dir(project, scene_id, run_id)
    if expected_sha256 is not None:
        if SHA256_RE.fullmatch(expected_sha256) is None:
            return None, "expected candidate sha256 must be 64 lowercase hexadecimal characters"
        frozen = run_dir / "candidates" / f"{expected_sha256}.md"
        if not frozen.resolve().is_relative_to(run_dir.resolve()):
            return None, "candidate snapshot path escapes scene-run directory"
        if frozen.exists():
            raw = frozen.read_bytes()
            if acceptance.sha256_bytes(raw) != expected_sha256:
                return None, f"frozen candidate snapshot {frozen.name} has a content-hash mismatch"
            return {"name": name, "sha256": expected_sha256,
                    "snapshot": str(frozen.relative_to(run_dir))}, None
    if not path.exists() or not path.is_file():
        return None, f"candidate does not exist: {candidate!r}"
    raw = path.read_bytes()
    digest = acceptance.sha256_bytes(raw)
    if expected_sha256 is not None and digest != expected_sha256:
        return None, (
            f"candidate {name!r} no longer matches reviewed bytes: expected {expected_sha256}, got {digest}"
        )
    frozen = run_dir / "candidates" / f"{digest}.md"
    if not frozen.resolve().is_relative_to(run_dir.resolve()):
        return None, "candidate snapshot path escapes scene-run directory"
    if frozen.exists():
        if frozen.read_bytes() != raw:
            return None, f"candidate snapshot collision/corruption at {frozen}"
    else:
        acceptance.atomic_write(frozen, raw)
    return {"name": name, "sha256": digest, "snapshot": str(frozen.relative_to(run_dir))}, None


def _operations(project: Path, manifest: dict) -> tuple[list[dict], list[str]]:
    run_dir = _run_dir(project, manifest["scene_id"], manifest["run_id"])
    records: list[dict] = []
    errors: list[str] = []
    for path in sorted((run_dir / "operations").glob("*.json")):
        try:
            item = _load_json(path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"unreadable operation {path.name}: {exc}")
            continue
        validation = schema.validate_named(item, "scene-run-operation")
        if item.get("operation_id") and path.stem != item.get("operation_id"):
            validation.append("operation_id does not match artifact filename")
        if item.get("run_id") != manifest["run_id"] or item.get("scene_id") != manifest["scene_id"]:
            validation.append("operation run/scene identity does not match manifest")
        step = next((s for s in manifest["steps"] if s["step_id"] == item.get("step_id")), None)
        if step is None:
            validation.append(f"unknown step_id {item.get('step_id')!r}")
        elif step["phase"] != item.get("phase"):
            validation.append("operation phase does not match declared step")
        if item.get("status") == "failure" and not item.get("failure_reason"):
            validation.append("failed operation needs failure_reason")
        if item.get("status") == "success" and item.get("failure_reason") is not None:
            validation.append("successful operation cannot carry failure_reason")
        if (item.get("input_tokens") is not None and item.get("output_tokens") is not None and
                item.get("total_tokens") is not None and
                item["total_tokens"] != item["input_tokens"] + item["output_tokens"]):
            validation.append("total_tokens must equal input_tokens + output_tokens when all are supplied")
        if validation:
            errors.extend(f"{path.name}: {problem}" for problem in validation)
            continue
        records.append(item)
    seen_idempotency: dict[str, str] = {}
    for item in records:
        key = item.get("idempotency_key")
        if key is None:
            continue
        prior = seen_idempotency.get(key)
        if prior is not None:
            errors.append(
                f"duplicate idempotency_key {key!r} on operations {prior} and {item['operation_id']}"
            )
        else:
            seen_idempotency[key] = item["operation_id"]
    records.sort(key=lambda item: (item.get("recorded_at", ""), item.get("operation_id", "")))
    return records, errors


def _signature(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in {"operation_id", "recorded_at"}}


def record_operation(project: Path, scene_id: str, run_id: str, step_id: str, status_value: str,
                     *, candidate: str | None = None, executor_kind: str | None = None,
                     provider: str | None = None, model: str | None = None,
                     provider_request_id: str | None = None, response_model: str | None = None,
                     finish_reason: str | None = None, input_tokens: int | None = None,
                     output_tokens: int | None = None, total_tokens: int | None = None,
                     cost_usd: float | None = None, latency_ms: float | None = None,
                     failure_reason: str | None = None, idempotency_key: str | None = None,
                     metadata: dict | None = None, _candidate_binding: dict | None = None,
                     _source_artifact: dict | None = None) -> dict:
    """Append one immutable operation. Budget overruns never suppress evidence already produced."""
    project = Path(project)
    try:
        manifest, errors = _manifest(project, scene_id, run_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid scene run", "details": errors}
    step = next((item for item in manifest["steps"] if item["step_id"] == step_id), None)
    if step is None:
        return {"error": f"unknown scene-run step {step_id!r}"}
    if status_value not in {"success", "failure"}:
        return {"error": "operation status must be 'success' or 'failure'"}
    if status_value == "failure" and not failure_reason:
        return {"error": "failed operation needs a failure_reason"}
    if status_value == "success" and failure_reason is not None:
        return {"error": "successful operation cannot carry failure_reason"}
    if executor_kind is None:
        executor_kind = "external_model" if provider or model else "unknown"
    if executor_kind not in EXECUTOR_KINDS:
        return {"error": f"invalid executor_kind {executor_kind!r}"}
    if idempotency_key is not None and (not isinstance(idempotency_key, str) or not idempotency_key.strip()):
        return {"error": "idempotency_key must be a non-empty string"}
    if metadata is not None and not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}

    try:
        input_tokens = _non_negative_int("input_tokens", input_tokens)
        output_tokens = _non_negative_int("output_tokens", output_tokens)
        total_tokens = _non_negative_int("total_tokens", total_tokens)
        cost_usd = _non_negative_number("cost_usd", cost_usd)
        latency_ms = _non_negative_number("latency_ms", latency_ms)
    except ValueError as exc:
        return {"error": str(exc)}
    if (total_tokens is not None and input_tokens is not None and output_tokens is not None and
            total_tokens != input_tokens + output_tokens):
        return {"error": "total_tokens must equal input_tokens + output_tokens when all are supplied"}

    binding = _candidate_binding
    if candidate is not None and binding is None:
        binding, error = _candidate_snapshot(project, scene_id, run_id, candidate)
        if error:
            return {"error": error}
    if binding is not None and candidate is not None and binding.get("name") != Path(candidate).name:
        return {"error": "candidate binding filename does not match candidate"}
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    record: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "scene_id": scene_id,
        "operation_id": f"op-{uuid.uuid4().hex}",
        "step_id": step_id,
        "phase": step["phase"],
        "status": status_value,
        "executor_kind": executor_kind,
        "recorded_at": _now().isoformat(),
    }
    optional = {
        "candidate": binding,
        "source_artifact": _source_artifact,
        "provider": provider,
        "model": model,
        "provider_request_id": provider_request_id,
        "response_model": response_model,
        "finish_reason": finish_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "failure_reason": failure_reason,
        "idempotency_key": idempotency_key,
        "metadata": metadata,
    }
    record.update({key: value for key, value in optional.items() if value is not None})
    validation = schema.validate_named(record, "scene-run-operation")
    if validation:
        return {"error": "invalid scene-run operation: " + "; ".join(validation)}

    existing, existing_errors = _operations(project, manifest)
    if existing_errors:
        return {"error": "existing scene-run operations are invalid", "details": existing_errors}
    if idempotency_key is not None:
        match = next((item for item in existing if item.get("idempotency_key") == idempotency_key), None)
        if match is not None:
            if _signature(match) != _signature(record):
                return {"error": f"idempotency_key {idempotency_key!r} already records different evidence"}
            return {"resumed": True, **match}

    path = _run_dir(project, scene_id, run_id) / "operations" / f"{record['operation_id']}.json"
    if path.exists():
        return {"error": f"operation id collision at {path.name}"}
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), "resumed": False, **record}


def link_review_attempt(project: Path, scene_id: str, run_id: str, step_id: str,
                        review_run_id: str, cost_usd: float | None = None,
                        candidate: str | None = None) -> dict:
    """Import one existing role-runner attempt without repeating the provider call."""
    project = Path(project)
    try:
        validate_scene_id(scene_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if ROLE_RUN_ID_RE.fullmatch(review_run_id) is None:
        return {"error": f"invalid role-runner run id {review_run_id!r}"}
    attempt_path = project / ".runs" / "reviews" / scene_id / f"{review_run_id}.json"
    if not attempt_path.exists():
        return {"error": f"role-runner attempt does not exist: {attempt_path.relative_to(project)}"}
    raw = attempt_path.read_bytes()
    try:
        attempt = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"error": f"role-runner attempt is unreadable: {exc}"}
    if not isinstance(attempt, dict):
        return {"error": "role-runner attempt is not an object"}
    packet = attempt.get("packet") if isinstance(attempt.get("packet"), dict) else {}
    if packet.get("run_id") != review_run_id or packet.get("scene_id") != scene_id:
        return {"error": "role-runner attempt identity does not match request"}
    packet_candidate = packet.get("candidate") if isinstance(packet.get("candidate"), dict) else {}
    expected_sha = packet_candidate.get("sha256")
    if not isinstance(expected_sha, str) or SHA256_RE.fullmatch(expected_sha) is None:
        return {"error": "role-runner attempt lacks a valid candidate sha256 binding"}
    name = candidate
    if name is None:
        candidate_dir = project / "scenes" / scene_id / "candidates"
        matches = [
            path.name for path in sorted(candidate_dir.glob("*.md"))
            if path.is_file() and acceptance.sha256_bytes(path.read_bytes()) == expected_sha
        ]
        if len(matches) != 1:
            return {"error": (
                "role-runner packet intentionally blinds the candidate filename; pass candidate explicitly "
                f"when its hash matches {len(matches)} current candidates"
            )}
        name = matches[0]
    binding, error = _candidate_snapshot(project, scene_id, run_id, name, expected_sha256=expected_sha)
    if error:
        return {"error": error}
    response = attempt.get("provider_response") if isinstance(attempt.get("provider_response"), dict) else {}
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    validation = attempt.get("validation") if isinstance(attempt.get("validation"), dict) else {}
    validation_status = validation.get("status")
    ok = validation_status == "valid"
    failure = None if ok else (validation.get("error") or validation.get("error_type") or
                               f"role-runner validation status {validation_status!r}")
    source = {
        "path": str(attempt_path.relative_to(project)),
        "sha256": acceptance.sha256_bytes(raw),
    }
    return record_operation(
        project, scene_id, run_id, step_id, "success" if ok else "failure",
        candidate=name, executor_kind="role_runner", provider=packet.get("vendor"),
        model=packet.get("model"), provider_request_id=response.get("provider_request_id"),
        response_model=response.get("response_model"), finish_reason=response.get("finish_reason"),
        input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
        total_tokens=usage.get("total_tokens"), cost_usd=cost_usd,
        latency_ms=response.get("latency_ms"), failure_reason=failure,
        idempotency_key=f"role-review:{review_run_id}",
        metadata={"role": packet.get("role"), "packet_sha256": attempt.get("packet_sha256"),
                  "validation_status": validation_status},
        _candidate_binding=binding, _source_artifact=source,
    )


def _accounting(operations: list[dict]) -> dict:
    token_known = 0
    token_unknown: list[str] = []
    cost_known = 0.0
    cost_unknown: list[str] = []
    for item in operations:
        metered = item.get("executor_kind") in {"external_model", "role_runner", "unknown"}
        total = item.get("total_tokens")
        if total is None and item.get("input_tokens") is not None and item.get("output_tokens") is not None:
            total = item["input_tokens"] + item["output_tokens"]
        if total is not None:
            token_known += total
        elif metered:
            token_unknown.append(item["operation_id"])
        if item.get("cost_usd") is not None:
            cost_known += float(item["cost_usd"])
        elif metered:
            cost_unknown.append(item["operation_id"])
    return {
        "operations": len(operations),
        "total_tokens": {"known": token_known, "unknown_operations": token_unknown},
        "cost_usd": {"known": cost_known, "unknown_operations": cost_unknown},
    }


def _limit_state(current: float, limit: float, unknown: list[str] | None = None) -> str:
    if current > limit:
        return "exceeded"
    if current == limit:
        return "exhausted"
    if unknown:
        return "indeterminate"
    return "under"


def _budget_report(manifest: dict, accounting: dict) -> dict:
    budgets = manifest.get("budgets", {})
    metrics: dict[str, dict] = {}
    if "max_operations" in budgets:
        metrics["operations"] = {
            "current": accounting["operations"], "limit": budgets["max_operations"],
            "state": _limit_state(accounting["operations"], budgets["max_operations"]),
        }
    if "max_total_tokens" in budgets:
        tokens = accounting["total_tokens"]
        metrics["total_tokens"] = {
            "known": tokens["known"], "unknown_operations": tokens["unknown_operations"],
            "limit": budgets["max_total_tokens"],
            "state": _limit_state(tokens["known"], budgets["max_total_tokens"], tokens["unknown_operations"]),
        }
    if "max_cost_usd" in budgets:
        cost = accounting["cost_usd"]
        metrics["cost_usd"] = {
            "known": cost["known"], "unknown_operations": cost["unknown_operations"],
            "limit": budgets["max_cost_usd"],
            "state": _limit_state(cost["known"], budgets["max_cost_usd"], cost["unknown_operations"]),
        }
    states = {item["state"] for item in metrics.values()}
    gate = "block" if states & {"exceeded", "exhausted"} else ("unknown" if "indeterminate" in states else "allow")
    return {"gate": gate, "metrics": metrics}


def status(project: Path, scene_id: str, run_id: str) -> dict:
    """Derive resumable step, evidence-integrity, candidate-freshness, and budget status."""
    project = Path(project)
    try:
        manifest, manifest_errors = _manifest(project, scene_id, run_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None:
        return {"error": "scene run does not exist", "details": manifest_errors}
    run_dir = _run_dir(project, scene_id, run_id)
    if manifest_errors:
        return {
            "run_id": run_id, "scene_id": scene_id, "status": "invalid",
            "integrity_errors": manifest_errors, "path": str(run_dir.relative_to(project)),
        }
    operations, operation_errors = _operations(project, manifest)
    stale: list[dict] = []
    integrity_errors = list(manifest_errors) + operation_errors
    for item in operations:
        source = item.get("source_artifact")
        if isinstance(source, dict):
            source_path = (project / source["path"]).resolve()
            try:
                confined = source_path.is_relative_to(project.resolve())
            except (OSError, ValueError):
                confined = False
            if not confined or not source_path.exists():
                integrity_errors.append(f"operation {item['operation_id']} source artifact is missing/outside project")
            elif acceptance.sha256_bytes(source_path.read_bytes()) != source["sha256"]:
                integrity_errors.append(f"operation {item['operation_id']} source artifact hash changed")
        binding = item.get("candidate")
        if not isinstance(binding, dict):
            continue
        snapshot = (run_dir / binding["snapshot"]).resolve()
        if (not snapshot.is_relative_to(run_dir.resolve()) or not snapshot.exists() or
                acceptance.sha256_bytes(snapshot.read_bytes()) != binding["sha256"]):
            integrity_errors.append(f"operation {item['operation_id']} candidate snapshot is missing/corrupt")
            continue
        try:
            current = resolve_scene_candidate(project, scene_id, binding["name"])
        except ValueError as exc:
            stale.append({"operation_id": item["operation_id"], "candidate": binding["name"],
                          "reason": str(exc)})
            continue
        if not current.exists():
            stale.append({"operation_id": item["operation_id"], "candidate": binding["name"],
                          "reason": "candidate file is missing"})
        else:
            current_sha = acceptance.sha256_bytes(current.read_bytes())
            if current_sha != binding["sha256"]:
                stale.append({"operation_id": item["operation_id"], "candidate": binding["name"],
                              "recorded_sha256": binding["sha256"], "current_sha256": current_sha,
                              "reason": "candidate bytes changed after operation"})

    step_rows: list[dict] = []
    completed: list[str] = []
    pending: list[str] = []
    failed: list[str] = []
    for step in manifest["steps"]:
        attempts = [item for item in operations if item["step_id"] == step["step_id"]]
        if any(item["status"] == "success" for item in attempts):
            state = "completed"
            completed.append(step["step_id"])
        elif attempts:
            state = "failed"
            failed.append(step["step_id"])
        else:
            state = "pending"
            pending.append(step["step_id"])
        step_rows.append({**step, "state": state, "attempts": len(attempts),
                          "operation_ids": [item["operation_id"] for item in attempts]})
    accounting = _accounting(operations)
    budget = _budget_report(manifest, accounting)
    overall = "invalid" if integrity_errors else (
        "complete" if len(completed) == len(manifest["steps"]) else
        "blocked" if budget["gate"] == "block" else "incomplete"
    )
    return {
        "run_id": run_id, "scene_id": scene_id, "status": overall,
        "created_at": manifest["created_at"], "steps": step_rows,
        "completed_steps": completed, "failed_steps": failed, "pending_steps": pending,
        "operation_count": len(operations), "accounting": accounting, "budget": budget,
        "stale_candidate_bindings": stale, "integrity_errors": integrity_errors,
        "path": str(run_dir.relative_to(project)),
    }


def operation_evidence(project: Path, scene_id: str, run_id: str) -> dict:
    """Return validated immutable operation records for evidence workflows that compose scene runs."""
    project = Path(project)
    current = status(project, scene_id, run_id)
    if "error" in current:
        return current
    if current.get("status") == "invalid":
        return {
            "status": "invalid", "run_id": run_id, "scene_id": scene_id,
            "errors": list(current.get("integrity_errors", [])),
        }
    try:
        manifest, manifest_errors = _manifest(project, scene_id, run_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None:
        return {"error": "scene run does not exist", "details": manifest_errors}
    operations, operation_errors = _operations(project, manifest)
    errors = [*manifest_errors, *operation_errors]
    if errors:
        return {"status": "invalid", "run_id": run_id, "scene_id": scene_id, "errors": errors}
    return {
        "status": "valid",
        "run_id": run_id,
        "scene_id": scene_id,
        "operations": operations,
        "accounting": current["accounting"],
        "stale_candidate_bindings": current["stale_candidate_bindings"],
    }


def check_budget(project: Path, scene_id: str, run_id: str, *,
                 estimated_total_tokens: int | None = None,
                 estimated_cost_usd: float | None = None) -> dict:
    """Preflight the next operation against current evidence and optional cost/token estimates."""
    try:
        estimated_total_tokens = _non_negative_int("estimated_total_tokens", estimated_total_tokens)
        estimated_cost_usd = _non_negative_number("estimated_cost_usd", estimated_cost_usd)
    except ValueError as exc:
        return {"error": str(exc)}
    current = status(project, scene_id, run_id)
    if "error" in current or current.get("status") == "invalid":
        return current
    report = json.loads(json.dumps(current["budget"]))
    metrics = report["metrics"]
    if "operations" in metrics:
        metric = metrics["operations"]
        metric["projected"] = metric["current"] + 1
        metric["projected_state"] = _limit_state(metric["projected"], metric["limit"])
    if "total_tokens" in metrics:
        metric = metrics["total_tokens"]
        if metric["unknown_operations"]:
            metric["projected_state"] = "indeterminate"
        elif estimated_total_tokens is None:
            metric["projected_state"] = "indeterminate"
            metric["estimate_missing"] = True
        else:
            metric["projected"] = metric["known"] + estimated_total_tokens
            metric["projected_state"] = _limit_state(metric["projected"], metric["limit"])
    if "cost_usd" in metrics:
        metric = metrics["cost_usd"]
        if metric["unknown_operations"]:
            metric["projected_state"] = "indeterminate"
        elif estimated_cost_usd is None:
            metric["projected_state"] = "indeterminate"
            metric["estimate_missing"] = True
        else:
            metric["projected"] = metric["known"] + estimated_cost_usd
            metric["projected_state"] = _limit_state(metric["projected"], metric["limit"])
    projected_states = {item.get("projected_state", item["state"]) for item in metrics.values()}
    decision = "block" if current["budget"]["gate"] == "block" or "exceeded" in projected_states else (
        "unknown" if "indeterminate" in projected_states else "allow"
    )
    return {"run_id": run_id, "scene_id": scene_id, "decision": decision,
            "current_gate": current["budget"]["gate"], "metrics": metrics}
