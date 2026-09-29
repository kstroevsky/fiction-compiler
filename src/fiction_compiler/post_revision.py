"""Fresh subjective evidence plus deterministic prose revalidation after backward revision.

Backward revision conservatively invalidates literary, reader, voice and whole-work evidence.  This
module closes the loop without pretending those scopes are deterministic: it builds content-bound
packets from active immutable acceptances, records append-only evidence, and requires a separate
explicit resolution transaction before a pending subjective scope is removed. Projects that froze a
policy requiring prose audit also get a separate deterministic rerun path whose claims must rebind to
the current accepted scene context.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, integrity, prose_audit, schema
from .state import scene_sort_key
from .workspace import validate_scene_id


SCOPES = {"literary", "reader", "voice", "whole_work"}
_SERIOUS = {"material", "fatal"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_segments(project: Path, index: dict) -> list[dict]:
    mapping = index.get("acceptance_objects", {})
    if not isinstance(mapping, dict):
        raise ValueError("canon index acceptance_objects is invalid")
    scene_ids = sorted(
        [item for item in index.get("accepted_state_deltas", []) if isinstance(item, str)],
        key=scene_sort_key,
    )
    segments: list[dict] = []
    for scene_id in scene_ids:
        object_id = mapping.get(scene_id)
        if not isinstance(object_id, str):
            raise ValueError(f"accepted scene {scene_id} has no immutable acceptance object")
        snapshot = acceptance.load_object(project, object_id)
        prose = acceptance.frozen_bytes(snapshot, "candidate").decode("utf-8")
        segments.append({
            "scene_id": scene_id,
            "acceptance_object": object_id,
            "candidate_sha256": snapshot["candidate"]["sha256"],
            "prose": prose,
        })
    return segments


def _revision_event_for(index: dict, scene_id: str, acceptance_object: str) -> str | None:
    for event in reversed(index.get("revision_events", [])):
        if not isinstance(event, dict):
            continue
        rebased = event.get("rebased", {})
        item = rebased.get(scene_id) if isinstance(rebased, dict) else None
        if isinstance(item, dict) and item.get("to") == acceptance_object:
            value = event.get("id")
            return value if isinstance(value, str) else None
    return None


def packet(project: Path, scope: str, scene_id: str | None = None) -> dict:
    """Build the current exact post-revision packet for one pending subjective scope."""
    project = Path(project).resolve()
    if scope not in SCOPES:
        return {"error": f"unsupported recheck scope {scope!r}"}
    report = integrity.verify_report(project)
    if report.get("status") != "verified":
        return {"error": "canon must verify before subjective post-revision review",
                "canon_status": report.get("status")}
    index = acceptance.load_index(project)
    rechecks = index.get("rechecks_required", {})
    if not isinstance(rechecks, dict):
        return {"error": "canon index rechecks_required is invalid"}
    try:
        segments = _active_segments(project, index)
    except ValueError as exc:
        return {"error": str(exc)}

    if scope == "whole_work":
        if scene_id is not None:
            return {"error": "whole_work recheck is global; do not pass scene_id"}
        pending = [
            sid for sid, entry in rechecks.items()
            if isinstance(entry, dict) and scope in entry.get("required_scopes", [])
        ]
        pending = sorted(pending, key=scene_sort_key)
        if not pending:
            return {"error": "no pending whole_work recheck"}
        value = {
            "schema_version": 1,
            "scope": scope,
            "head_acceptance": index.get("head_acceptance"),
            "pending_scenes": pending,
            "segments": segments,
            "instructions": (
                "Assess the accepted work as a whole after the recorded backward revision. Report exact "
                "evidence for global structure, pacing, promise/payoff, voice drift and reader experience. "
                "A non-pass may target an earlier scene for another explicit backward revision."
            ),
        }
    else:
        if not isinstance(scene_id, str):
            return {"error": f"{scope} recheck requires scene_id"}
        try:
            validate_scene_id(scene_id)
        except ValueError as exc:
            return {"error": str(exc)}
        entry = rechecks.get(scene_id)
        if not isinstance(entry, dict) or scope not in entry.get("required_scopes", []):
            return {"error": f"scope {scope!r} is not pending for {scene_id}"}
        target_pos = next((i for i, item in enumerate(segments) if item["scene_id"] == scene_id), None)
        if target_pos is None:
            return {"error": f"pending scene {scene_id} is not active canon"}
        if scope == "reader":
            visible = segments[:target_pos + 1]
            instructions = (
                "Read only this accepted prefix. Record observed comprehension, expectation, ambiguity and "
                "engagement without access to planned outcomes, hidden canon or later prose."
            )
        elif scope == "voice":
            visible = segments
            instructions = (
                "Assess the target scene's voice against the active accepted work after the upstream revision. "
                "Use exact prose evidence; distinguish intentional modulation from unexplained drift."
            )
        else:
            visible = segments
            instructions = (
                "Assess the target scene's literary function in the active accepted work after the upstream "
                "revision, using exact prose evidence and routing defects to the responsible layer."
            )
        acceptance_object = entry.get("acceptance_object")
        value = {
            "schema_version": 1,
            "scope": scope,
            "scene_id": scene_id,
            "acceptance_object": acceptance_object,
            "head_acceptance": index.get("head_acceptance"),
            "caused_by_scene": entry.get("caused_by_scene"),
            "revision_event": _revision_event_for(index, scene_id, str(acceptance_object)),
            "known_state_dependency": entry.get("known_state_dependency"),
            "target_candidate_sha256": segments[target_pos]["candidate_sha256"],
            "segments": visible,
            "instructions": instructions,
        }
    digest = acceptance.sha256_bytes(acceptance.canonical_json_bytes(value))
    return {"packet_sha256": digest, "packet": value}


def _evidence_path(project: Path, evidence_id: str) -> Path:
    return Path(project) / ".runs" / "post-revision" / "evidence" / f"{evidence_id}.json"


def _resolution_path(project: Path, resolution_id: str) -> Path:
    return Path(project) / ".runs" / "post-revision" / "resolutions" / f"{resolution_id}.json"


def _prose_audit_evidence_path(project: Path, evidence_id: str) -> Path:
    return Path(project) / ".runs" / "post-revision" / "prose-audit" / f"{evidence_id}.json"


def _load_evidence(project: Path, evidence_id: str) -> tuple[dict | None, list[str]]:
    path = _evidence_path(project, evidence_id)
    if not path.exists():
        return None, [f"post-revision evidence {evidence_id!r} does not exist"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"invalid evidence JSON: {exc}"]
    if not isinstance(value, dict):
        return None, ["post-revision evidence is not an object"]
    errors = schema.validate_named(value, "post-revision-evidence")
    expected_id = "recheck-" + acceptance.sha256_bytes(acceptance.canonical_json_bytes({
        key: value[key] for key in value if key not in {"evidence_id", "recorded_at"}
    }))
    if value.get("evidence_id") != expected_id:
        errors.append("evidence_id does not match content")
    actual_packet_sha = acceptance.sha256_bytes(acceptance.canonical_json_bytes(value.get("packet", {})))
    if value.get("packet_sha256") != actual_packet_sha:
        errors.append("packet_sha256 does not match embedded packet")
    return value, errors


def record_evidence(project: Path, scope: str, packet_sha256: str, evaluator_kind: str,
                    evaluator_id: str, cohort_kind: str, verdict: str, findings: list[dict],
                    provenance: dict | None = None, scene_id: str | None = None) -> dict:
    """Persist fresh evidence. Recording alone never clears a pending scope."""
    project = Path(project).resolve()
    current = packet(project, scope, scene_id)
    if "error" in current:
        return current
    if packet_sha256 != current["packet_sha256"]:
        return {"error": "packet is stale; rebuild the post-revision packet before recording evidence",
                "current_packet_sha256": current["packet_sha256"]}
    if verdict == "pass" and any(
        isinstance(item, dict) and item.get("severity") in _SERIOUS for item in findings
    ):
        return {"error": "pass verdict cannot carry material/fatal findings"}
    identity: dict[str, Any] = {
        "schema_version": 1,
        "scope": scope,
        "packet_sha256": packet_sha256,
        "packet": current["packet"],
        "evaluator_kind": evaluator_kind,
        "evaluator_id": evaluator_id,
        "cohort_kind": cohort_kind,
        "verdict": verdict,
        "findings": findings,
        "provenance": dict(provenance or {}),
    }
    if scene_id is not None:
        identity["target_scene"] = scene_id
    evidence_id = "recheck-" + acceptance.sha256_bytes(acceptance.canonical_json_bytes(identity))
    path = _evidence_path(project, evidence_id)
    if path.exists():
        existing, errors = _load_evidence(project, evidence_id)
        if errors:
            return {"error": "existing evidence artifact is invalid", "details": errors}
        return {"idempotent": True, "path": str(path.relative_to(project)), **existing}
    record = {**identity, "evidence_id": evidence_id, "recorded_at": _now()}
    errors = schema.validate_named(record, "post-revision-evidence")
    if errors:
        return {"error": "invalid post-revision evidence: " + "; ".join(errors)}
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"idempotent": False, "path": str(path.relative_to(project)), **record}


def resolve_scope(project: Path, evidence_id: str, decided_by: str, reason: str) -> dict:
    """Explicitly close a pending scope from one fresh, clean evidence artifact."""
    project = Path(project).resolve()
    if not decided_by.strip() or not reason.strip():
        return {"error": "decided_by and reason are required for subjective-scope resolution"}
    with integrity.PromotionLock(project):
        evidence, errors = _load_evidence(project, evidence_id)
        if evidence is None or errors:
            return {"error": "invalid post-revision evidence", "details": errors}
        if evidence.get("verdict") != "pass" or any(
            item.get("severity") in _SERIOUS for item in evidence.get("findings", []) if isinstance(item, dict)
        ):
            return {"error": "only clean pass evidence can resolve a pending subjective scope"}
        scope = evidence["scope"]
        scene_id = evidence.get("target_scene")
        current = packet(project, scope, scene_id)
        if "error" in current:
            return current
        if current["packet_sha256"] != evidence["packet_sha256"]:
            return {"error": "evidence is stale against the current acceptance head"}

        index = acceptance.load_index(project)
        rechecks = index.get("rechecks_required", {})
        if not isinstance(rechecks, dict):
            return {"error": "canon index rechecks_required is invalid"}
        if scope == "whole_work":
            resolved_scenes = list(evidence["packet"]["pending_scenes"])
        else:
            resolved_scenes = [str(scene_id)]
        for sid in resolved_scenes:
            entry = rechecks.get(sid)
            if not isinstance(entry, dict) or scope not in entry.get("required_scopes", []):
                return {"error": f"scope {scope!r} is no longer pending for {sid}"}

        resolution_identity: dict[str, Any] = {
            "schema_version": 1,
            "evidence_id": evidence_id,
            "scope": scope,
            "decided_by": decided_by.strip(),
            "reason": reason.strip(),
            "resolved_scenes": resolved_scenes,
        }
        if scene_id is not None:
            resolution_identity["target_scene"] = scene_id
        resolution_id = "resolve-" + acceptance.sha256_bytes(
            acceptance.canonical_json_bytes(resolution_identity)
        )
        resolution_path = _resolution_path(project, resolution_id)
        if resolution_path.exists():
            resolution = json.loads(resolution_path.read_text(encoding="utf-8"))
        else:
            resolution = {**resolution_identity, "resolution_id": resolution_id, "resolved_at": _now()}
            validation = schema.validate_named(resolution, "post-revision-resolution")
            if validation:
                return {"error": "invalid post-revision resolution: " + "; ".join(validation)}
            acceptance.atomic_write(resolution_path, acceptance.canonical_json_bytes(resolution))

        for sid in resolved_scenes:
            entry = rechecks[sid]
            entry["required_scopes"] = [item for item in entry["required_scopes"] if item != scope]
            resolutions = entry.setdefault("scope_resolutions", [])
            if not isinstance(resolutions, list):
                return {"error": f"recheck resolution ledger for {sid} is invalid"}
            if resolution_id not in resolutions:
                resolutions.append(resolution_id)
        acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))
        return {"resolution_id": resolution_id, "evidence_id": evidence_id, "scope": scope,
                "resolved_scenes": resolved_scenes, "remaining": {
                    sid: rechecks[sid]["required_scopes"] for sid in resolved_scenes
                }, "path": str(resolution_path.relative_to(project))}


def recheck_prose_audit(project: Path, scene_id: str, claims: dict) -> dict:
    """Re-run a policy-required prose audit against the current post-revision scene context.

    The extractor must supply newly rebound ``prose-claims``. The deterministic verifier rejects
    stale state/context hashes; only a clean pass clears the pending ``prose_audit`` scope.
    """
    project = Path(project).resolve()
    validate_scene_id(scene_id)
    if not isinstance(claims, dict):
        return {"error": "prose claims must be an object"}

    with integrity.PromotionLock(project):
        report = integrity.verify_report(project)
        if report.get("status") != "verified":
            return {"error": "canon must verify before a post-revision prose audit",
                    "canon_status": report.get("status")}
        index = acceptance.load_index(project)
        rechecks = index.get("rechecks_required", {})
        if not isinstance(rechecks, dict):
            return {"error": "canon index rechecks_required is invalid"}
        entry = rechecks.get(scene_id)
        if not isinstance(entry, dict) or "prose_audit" not in entry.get("required_scopes", []):
            return {"error": f"prose_audit is not pending for {scene_id}"}

        mapping = index.get("acceptance_objects", {})
        object_id = entry.get("acceptance_object")
        if not isinstance(mapping, dict) or mapping.get(scene_id) != object_id or not isinstance(object_id, str):
            return {"error": f"pending prose audit for {scene_id} is not bound to the active acceptance"}
        snapshot = acceptance.load_object(project, object_id)
        candidate_artifact = snapshot.get("candidate", {})
        candidate_rel = candidate_artifact.get("path") if isinstance(candidate_artifact, dict) else None
        candidate_sha = candidate_artifact.get("sha256") if isinstance(candidate_artifact, dict) else None
        if not isinstance(candidate_rel, str) or not isinstance(candidate_sha, str):
            return {"error": "active acceptance has no frozen candidate artifact"}
        candidate_name = Path(candidate_rel).name
        if claims.get("candidate") != candidate_name or claims.get("candidate_sha256") != candidate_sha:
            return {"error": "prose claims are not bound to the active accepted candidate"}
        candidate_path = project / candidate_rel
        if not candidate_path.exists() or integrity.sha256_file(candidate_path) != candidate_sha:
            return {"error": "accepted candidate source is missing or changed; restore its frozen bytes before rechecking"}
        for field, live_path in (
            ("spec", project / "scenes" / scene_id / "spec.json"),
            ("state_delta", project / "scenes" / scene_id / "state-delta.json"),
        ):
            expected = acceptance.frozen_bytes(snapshot, field)
            if not live_path.exists() or live_path.read_bytes() != expected:
                return {"error": f"accepted {field} view is missing or changed; restore the frozen bytes before rechecking"}

        result = prose_audit.audit_prose(project, scene_id, claims)
        if "error" in result:
            return result
        bindings = prose_audit.prose_claim_bindings(project, scene_id, candidate_name)
        if bindings.get("candidate_sha256") != candidate_sha:
            return {"error": "accepted candidate changed during prose-audit recheck"}
        serious = [
            item for item in result.get("findings", [])
            if isinstance(item, dict) and item.get("severity") in _SERIOUS
        ]
        clean = result.get("verdict") == "pass" and not serious
        status = "pass" if clean else "needs_attention"

        identity = {
            "schema_version": 1,
            "scene_id": scene_id,
            "acceptance_object": object_id,
            "head_acceptance": index.get("head_acceptance"),
            "caused_by_scene": entry.get("caused_by_scene"),
            "candidate_sha256": candidate_sha,
            "bindings": bindings,
            "claims_sha256": acceptance.sha256_bytes(acceptance.canonical_json_bytes(claims)),
            "claims": claims,
            "audit_result": result,
            "status": status,
        }
        evidence_id = "prose-recheck-" + acceptance.sha256_bytes(
            acceptance.canonical_json_bytes(identity)
        )
        record = {**identity, "evidence_id": evidence_id, "recorded_at": _now()}
        errors = schema.validate_named(record, "post-revision-prose-audit")
        if errors:
            return {"error": "invalid post-revision prose-audit evidence: " + "; ".join(errors)}
        path = _prose_audit_evidence_path(project, evidence_id)
        if not path.exists():
            acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))

        entry["prose_audit"] = {
            "status": status,
            "verdict": result.get("verdict"),
            "findings": result.get("findings", []),
            "evidence_id": evidence_id,
            "bindings": bindings,
        }
        if clean:
            entry["required_scopes"] = [
                scope for scope in entry.get("required_scopes", []) if scope != "prose_audit"
            ]
        acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))
        return {
            "scene_id": scene_id,
            "status": status,
            "verdict": result.get("verdict"),
            "evidence_id": evidence_id,
            "path": str(path.relative_to(project)),
            "remaining": entry.get("required_scopes", []),
            "findings": result.get("findings", []),
        }


def status(project: Path) -> dict:
    project = Path(project).resolve()
    report = integrity.verify_report(project)
    rechecks = report.get("rechecks_required", {})
    pending: dict[str, dict] = {}
    completed: dict[str, dict] = {}
    if isinstance(rechecks, dict):
        for scene_id, entry in rechecks.items():
            target = pending if isinstance(entry, dict) and entry.get("required_scopes") else completed
            target[scene_id] = entry
    return {
        "canon_status": report["status"],
        "rechecks_required": rechecks,
        "pending_rechecks": pending,
        "completed_rechecks": completed,
        "revision_events": report.get("revision_events", []),
    }
