"""Evidence-bound framework improvement transactions.

The framework loop changes prompts, rubrics, schemas, skills, configuration, or deterministic code.
Those edits happen in the working tree; this module supplies the governance envelope around them:
freeze a clean baseline and rollback bytes, detect undeclared framework edits, bind blind before/after
comparisons, require a human decision, and restore the declared paths only when the evaluated state is
still current.

It deliberately does not decide literary quality. Subjective thresholds are predeclared as simple
observation counts and a human remains the final authority.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import acceptance, integrity, regression, schema
from .workspace import ROOT

_CHANGE_RE = re.compile(r"^framework-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_change_id(now: datetime | None = None) -> str:
    now = now or _now()
    return f"framework-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"


def _change_dir(project: Path, change_id: str) -> Path:
    if _CHANGE_RE.fullmatch(change_id) is None:
        raise ValueError(f"invalid framework change id: {change_id!r}")
    return Path(project).resolve() / ".runs" / "framework-changes" / change_id


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    acceptance.atomic_write(
        path, (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )


def _repo_rel(root: Path, raw: str) -> tuple[str, Path]:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"framework changed_paths must be repository-relative: {raw!r}")
    if path.parts[0] in {".git", ".runs"} or ".runs" in path.parts:
        raise ValueError(f"framework transaction cannot target internal metadata: {raw!r}")
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"framework path escapes repository root: {raw!r}") from exc
    return path.as_posix(), resolved


def _path_state(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    if not path.is_file():
        raise ValueError(f"framework transaction supports files only: {path}")
    return {"exists": True, "sha256": integrity.sha256_file(path), "bytes": path.stat().st_size}


def _changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return sorted(path for path in set(before) | set(after) if before.get(path) != after.get(path))


def _transaction(project: Path, change_id: str) -> tuple[Path, dict]:
    directory = _change_dir(project, change_id)
    path = directory / "transaction.json"
    if not path.exists():
        raise FileNotFoundError(f"framework change not found: {change_id}")
    payload = _json(path)
    errors = schema.validate_named(payload, "framework-change")
    if errors:
        raise ValueError("invalid framework change transaction: " + "; ".join(errors))
    return directory, payload


def start(project: Path, *, title: str, failure_observed: str, evidence: list[str],
          root_layer: str, minimal_change: str, regression_case: str,
          blind_comparison_plan: str, tradeoffs: list[str], changed_paths: list[str],
          proposed_by: str, proposer_kind: str, minimum_observations: int,
          minimum_after_wins: int, maximum_before_wins: int,
          root: Path = ROOT) -> dict:
    """Freeze a clean baseline plus exact rollback bytes before a framework edit is made."""
    root = Path(root).resolve()
    project = Path(project).resolve()
    if proposer_kind not in {"human", "agent"}:
        return {"error": "proposer_kind must be 'human' or 'agent'"}
    if len(set(changed_paths)) != len(changed_paths) or not changed_paths:
        return {"error": "changed_paths must contain one or more distinct repository-relative files"}
    if minimum_observations < 1:
        return {"error": "comparison policy requires at least one blind before/after observation"}
    if min(minimum_after_wins, maximum_before_wins) < 0:
        return {"error": "comparison policy counts must be non-negative"}
    if minimum_after_wins > minimum_observations:
        return {"error": "minimum_after_wins cannot exceed minimum_observations"}

    try:
        normalized = [_repo_rel(root, raw) for raw in changed_paths]
        unrelated = [rel for rel, _ in normalized if not regression.is_framework_path(rel)]
        if unrelated:
            return {
                "error": (
                    "changed_paths must name behavior-relevant framework files; unrelated: "
                    + ", ".join(unrelated)
                )
            }
        states = [(rel, path, _path_state(path)) for rel, path in normalized]
    except ValueError as exc:
        return {"error": str(exc)}

    baseline = regression.run_regressions(root=root)
    if not baseline["ok"]:
        return {
            "error": "framework baseline regression is not clean; fix the baseline before starting a change",
            "failed": baseline["failed"],
        }
    if baseline.get("runtime_source", {}).get("fresh") is False:
        return {
            "error": (
                "framework source changed after this Python process imported it; restart the MCP/CLI "
                "runtime before freezing a baseline"
            )
        }

    change_id = _new_change_id()
    directory = _change_dir(project, change_id)
    if directory.exists():
        return {"error": f"framework change collision at {change_id}"}

    snapshots: list[dict] = []
    for rel, path, state in states:
        item = {"path": rel, **state}
        if state["exists"]:
            backup = directory / "before" / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, backup)
            item["backup"] = str(backup.relative_to(directory))
        snapshots.append(item)

    now = _now().isoformat()
    payload = {
        "schema_version": 1,
        "change_id": change_id,
        "title": title,
        "project": str(project),
        "proposal": {
            "failure_observed": failure_observed,
            "evidence": evidence,
            "root_layer": root_layer,
            "minimal_change": minimal_change,
            "regression_case": regression_case,
            "blind_comparison_plan": blind_comparison_plan,
            "tradeoffs": tradeoffs,
            "human_approval_status": "pending",
        },
        "proposed_by": proposed_by,
        "proposer_kind": proposer_kind,
        "changed_paths": [rel for rel, _, _ in states],
        "comparison_policy": {
            "minimum_observations": minimum_observations,
            "minimum_after_wins": minimum_after_wins,
            "maximum_before_wins": maximum_before_wins,
        },
        "baseline": {
            "regression": baseline,
            "framework_files": regression.framework_file_manifest(root),
        },
        "snapshots": snapshots,
        "started_at": now,
    }
    errors = schema.validate_named(payload, "framework-change")
    if errors:
        shutil.rmtree(directory, ignore_errors=True)
        return {"error": "invalid framework change transaction: " + "; ".join(errors)}
    _write(directory / "transaction.json", payload)
    return {
        "change_id": change_id,
        "path": str((directory / "transaction.json").relative_to(project)),
        "baseline_fingerprint": baseline["manifest"]["framework_fingerprint"],
        "changed_paths": payload["changed_paths"],
    }


def _evaluation_files(directory: Path) -> list[Path]:
    return sorted((directory / "evaluations").glob("evaluation-*.json"))


def latest_evaluation(project: Path, change_id: str) -> dict | None:
    directory, _ = _transaction(project, change_id)
    files = _evaluation_files(directory)
    return _json(files[-1]) if files else None


def evaluate(project: Path, change_id: str, *, root: Path = ROOT) -> dict:
    """Freeze the current edited framework state and deterministic regression result."""
    root = Path(root).resolve()
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    if (directory / "decision.json").exists():
        return {"error": "framework change already has a human decision"}

    after_regression = regression.run_regressions(root=root)
    after_files = regression.framework_file_manifest(root)
    changed_framework = _changed_files(transaction["baseline"]["framework_files"], after_files)
    declared = set(transaction["changed_paths"])
    unexpected = sorted(set(changed_framework) - declared)
    declared_states = []
    declared_changes = []
    try:
        before_by_path = {item["path"]: item for item in transaction["snapshots"]}
        for rel in transaction["changed_paths"]:
            _, path = _repo_rel(root, rel)
            state = _path_state(path)
            declared_states.append({"path": rel, **state})
            before = {k: v for k, v in before_by_path[rel].items() if k in {"exists", "sha256", "bytes"}}
            if state != before:
                declared_changes.append(rel)
    except ValueError as exc:
        return {"error": str(exc)}

    now = _now()
    runtime_fresh = after_regression.get("runtime_source", {}).get("fresh")
    result = {
        "schema_version": 1,
        "change_id": change_id,
        "evaluation_id": f"evaluation-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}",
        "baseline_fingerprint": transaction["baseline"]["regression"]["manifest"]["framework_fingerprint"],
        "after_fingerprint": after_regression["manifest"]["framework_fingerprint"],
        "regression": after_regression,
        "changed_framework_paths": changed_framework,
        "unexpected_framework_paths": unexpected,
        "declared_path_states": declared_states,
        "declared_changes": declared_changes,
        "mechanically_ready": bool(
            after_regression["ok"] and runtime_fresh is not False
            and not unexpected and declared_changes
        ),
        "evaluated_at": now.isoformat(),
    }
    errors = schema.validate_named(result, "framework-change-evaluation")
    if errors:
        return {"error": "invalid framework evaluation: " + "; ".join(errors)}
    path = directory / "evaluations" / f"{result['evaluation_id']}.json"
    _write(path, result)
    return {"path": str(path.relative_to(Path(project).resolve())), **result}


def _fresh_evaluation(project: Path, change_id: str, root: Path) -> tuple[dict | None, str | None]:
    evaluation = latest_evaluation(project, change_id)
    if evaluation is None:
        return None, "framework change has not been evaluated"
    current = regression.framework_manifest(root)["framework_fingerprint"]
    if current != evaluation["after_fingerprint"]:
        return None, "framework changed after the latest evaluation; evaluate again"
    return evaluation, None


def prepare_comparison(project: Path, change_id: str, *, objective: str,
                       before_output: str, after_output: str, prepared_by: str,
                       root: Path = ROOT) -> dict:
    """Freeze and blind one before/after output pair against the current evaluated framework."""
    root = Path(root).resolve()
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    evaluation, error = _fresh_evaluation(project, change_id, root)
    if error:
        return {"error": error}
    if not evaluation["mechanically_ready"]:
        return {"error": "latest framework evaluation is not mechanically ready"}
    comparison_id = f"comparison-{uuid.uuid4().hex}"
    digest = integrity.sha256_bytes(f"{change_id}:{comparison_id}".encode("utf-8"))
    before_label, after_label = ("A", "B") if int(digest[0], 16) % 2 == 0 else ("B", "A")
    private = {
        "schema_version": 1,
        "change_id": change_id,
        "comparison_id": comparison_id,
        "objective": objective,
        "prepared_by": prepared_by,
        "baseline_fingerprint": transaction["baseline"]["regression"]["manifest"]["framework_fingerprint"],
        "after_fingerprint": evaluation["after_fingerprint"],
        "outputs": {
            "before": {"text": before_output,
                       "sha256": integrity.sha256_bytes(before_output.encode("utf-8"))},
            "after": {"text": after_output,
                      "sha256": integrity.sha256_bytes(after_output.encode("utf-8"))},
        },
        "label_map": {before_label: "before", after_label: "after"},
        "prepared_at": _now().isoformat(),
    }
    errors = schema.validate_named(private, "framework-comparison")
    if errors:
        return {"error": "invalid framework comparison: " + "; ".join(errors)}
    path = directory / "comparisons" / f"{comparison_id}.json"
    _write(path, private)
    return comparison_packet(project, change_id, comparison_id)


def comparison_packet(project: Path, change_id: str, comparison_id: str) -> dict:
    try:
        directory, _ = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    path = directory / "comparisons" / f"{comparison_id}.json"
    if not path.exists():
        return {"error": f"framework comparison not found: {comparison_id}"}
    comparison = _json(path)
    return {
        "change_id": change_id,
        "comparison_id": comparison_id,
        "objective": comparison["objective"],
        "outputs": {
            "A": comparison["outputs"][comparison["label_map"]["A"]]["text"],
            "B": comparison["outputs"][comparison["label_map"]["B"]]["text"],
        },
        "note": "Blind before/after pair. The packet does not reveal which label is before or after.",
    }


def record_comparison(project: Path, change_id: str, comparison_id: str, *,
                      evaluator_kind: str, evaluator_id: str, preferred: str,
                      rationale: str) -> dict:
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    if evaluator_kind not in {"human", "model"}:
        return {"error": "evaluator_kind must be 'human' or 'model'"}
    if preferred not in {"A", "B", "tie", "abstain"}:
        return {"error": "preferred must be A, B, tie, or abstain"}
    comparison_path = directory / "comparisons" / f"{comparison_id}.json"
    if not comparison_path.exists():
        return {"error": f"framework comparison not found: {comparison_id}"}
    evidence_dir = directory / "comparison-evidence"
    existing = list(evidence_dir.glob(f"{comparison_id}-*.json"))
    for path in existing:
        item = _json(path)
        if item.get("evaluator_kind") == evaluator_kind and item.get("evaluator_id") == evaluator_id:
            return {"error": "this evaluator already recorded evidence for the comparison"}
    comparison = _json(comparison_path)
    if preferred in {"A", "B"}:
        outcome = comparison["label_map"][preferred]
    else:
        outcome = preferred
    independent = evaluator_kind == "human" or evaluator_id != transaction["proposed_by"]
    record = {
        "schema_version": 1,
        "change_id": change_id,
        "comparison_id": comparison_id,
        "evaluator_kind": evaluator_kind,
        "evaluator_id": evaluator_id,
        "preferred_label": preferred,
        "outcome": outcome,
        "rationale": rationale,
        "independent_of_agent_proposer": independent,
        "recorded_at": _now().isoformat(),
    }
    errors = schema.validate_named(record, "framework-comparison-evidence")
    if errors:
        return {"error": "invalid comparison evidence: " + "; ".join(errors)}
    evidence_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_dir / f"{comparison_id}-{uuid.uuid4().hex}.json"
    _write(path, record)
    return {"path": str(path.relative_to(Path(project).resolve())), **record}


def _comparison_summary(directory: Path, transaction: dict) -> dict:
    evidence = []
    for path in sorted((directory / "comparison-evidence").glob("*.json")):
        item = _json(path)
        errors = schema.validate_named(item, "framework-comparison-evidence")
        if not errors and item.get("independent_of_agent_proposer"):
            evidence.append(item)
    outcomes = {key: 0 for key in ("after", "before", "tie", "abstain")}
    for item in evidence:
        outcomes[item["outcome"]] += 1
    observed = outcomes["after"] + outcomes["before"] + outcomes["tie"]
    policy = transaction["comparison_policy"]
    met = (
        observed >= policy["minimum_observations"]
        and outcomes["after"] >= policy["minimum_after_wins"]
        and outcomes["before"] <= policy["maximum_before_wins"]
    )
    return {
        "eligible_evidence": len(evidence),
        "observations": observed,
        "outcomes": outcomes,
        "policy": policy,
        "policy_met": met,
    }


def status(project: Path, change_id: str, *, root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    evaluation = latest_evaluation(project, change_id)
    current_fingerprint = regression.framework_manifest(root)["framework_fingerprint"]
    comparison = _comparison_summary(directory, transaction)
    decision = _json(directory / "decision.json") if (directory / "decision.json").exists() else None
    rollback = _json(directory / "rollback.json") if (directory / "rollback.json").exists() else None
    evaluation_fresh = bool(evaluation and evaluation["after_fingerprint"] == current_fingerprint)
    ready = bool(
        evaluation and evaluation_fresh and evaluation["mechanically_ready"]
        and comparison["policy_met"] and decision is None and rollback is None
    )
    return {
        "change_id": change_id,
        "title": transaction["title"],
        "baseline_fingerprint": transaction["baseline"]["regression"]["manifest"]["framework_fingerprint"],
        "current_fingerprint": current_fingerprint,
        "latest_evaluation": evaluation,
        "evaluation_fresh": evaluation_fresh,
        "comparison": comparison,
        "ready_for_human_decision": ready,
        "decision": decision,
        "rollback": rollback,
    }


def decide(project: Path, change_id: str, *, decision: str, decided_by: str, decider_kind: str,
           reason: str,
           root: Path = ROOT) -> dict:
    """Record the human authority decision; approval is impossible until the frozen criteria pass."""
    root = Path(root).resolve()
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    if decision not in {"approve", "reject"}:
        return {"error": "decision must be 'approve' or 'reject'"}
    if decider_kind != "human":
        return {"error": "framework decisions require a human decider"}
    if (directory / "decision.json").exists():
        return {"error": "framework change already has a human decision"}
    current = status(project, change_id, root=root)
    if decision == "approve" and not current.get("ready_for_human_decision"):
        return {"error": "framework change is not ready for approval", "status": current}
    evaluation = current.get("latest_evaluation")
    record = {
        "schema_version": 1,
        "change_id": change_id,
        "decision": decision,
        "decided_by": decided_by,
        "decider_kind": decider_kind,
        "reason": reason,
        "evaluation_id": evaluation["evaluation_id"] if evaluation else None,
        "framework_fingerprint": current["current_fingerprint"],
        "comparison_summary": current["comparison"],
        "proposal_sha256": acceptance.sha256_bytes(
            acceptance.canonical_json_bytes(transaction["proposal"])
        ),
        "decided_at": _now().isoformat(),
    }
    errors = schema.validate_named(record, "framework-change-decision")
    if errors:
        return {"error": "invalid framework decision: " + "; ".join(errors)}
    _write(directory / "decision.json", record)
    return record


def rollback(project: Path, change_id: str, *, decided_by: str, decider_kind: str, reason: str,
             confirm: bool = False, root: Path = ROOT) -> dict:
    """Restore declared pre-change bytes, refusing to clobber edits made after evaluation."""
    root = Path(root).resolve()
    if not confirm:
        return {"error": "rollback requires confirm=True"}
    if decider_kind != "human":
        return {"error": "framework rollback requires a human decider"}
    try:
        directory, transaction = _transaction(project, change_id)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}
    if (directory / "rollback.json").exists():
        return {"error": "framework change is already rolled back"}
    evaluation, error = _fresh_evaluation(project, change_id, root)
    if error:
        return {"error": error}
    expected_states = {item["path"]: item for item in evaluation["declared_path_states"]}
    for rel in transaction["changed_paths"]:
        try:
            _, path = _repo_rel(root, rel)
            current = _path_state(path)
        except ValueError as exc:
            return {"error": str(exc)}
        expected = {k: v for k, v in expected_states[rel].items() if k in {"exists", "sha256", "bytes"}}
        if current != expected:
            return {"error": f"rollback refused: {rel} changed after evaluation"}

    restore_plan: list[tuple[Path, bytes | None]] = []
    for snapshot in transaction["snapshots"]:
        _, target = _repo_rel(root, snapshot["path"])
        if snapshot["exists"]:
            backup = directory / snapshot["backup"]
            if not backup.exists() or integrity.sha256_file(backup) != snapshot["sha256"]:
                return {"error": f"rollback backup is missing or corrupt: {snapshot['path']}"}
            restore_plan.append((target, backup.read_bytes()))
        else:
            restore_plan.append((target, None))

    batch = integrity.AtomicBatch()
    for target, data in restore_plan:
        if data is None:
            batch.delete(target)
        else:
            batch.write(target, data)
    try:
        batch.commit()
    except Exception as exc:  # noqa: BLE001 — rollback must repair earlier staged writes on any failure
        batch.rollback()
        return {"error": f"rollback failed and prior working-tree state was restored: {type(exc).__name__}: {exc}"}

    after = regression.run_regressions(root=root)
    runtime_fresh = after.get("runtime_source", {}).get("fresh")
    baseline_fingerprint = transaction["baseline"]["regression"]["manifest"]["framework_fingerprint"]
    record = {
        "schema_version": 1,
        "change_id": change_id,
        "decided_by": decided_by,
        "decider_kind": decider_kind,
        "reason": reason,
        "from_evaluation_id": evaluation["evaluation_id"],
        "restored_fingerprint": after["manifest"]["framework_fingerprint"],
        "baseline_fingerprint": baseline_fingerprint,
        "baseline_restored": after["manifest"]["framework_fingerprint"] == baseline_fingerprint,
        "regression_ok": bool(after["ok"] and runtime_fresh is not False),
        "rolled_back_at": _now().isoformat(),
    }
    errors = schema.validate_named(record, "framework-rollback")
    if errors:
        return {"error": "rollback completed but record is invalid: " + "; ".join(errors)}
    _write(directory / "rollback.json", record)
    return record
