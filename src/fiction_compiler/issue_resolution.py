"""Artifact-bound disposition of findings carried across candidate lineage.

Revision findings cannot silently disappear because a new candidate filename was created, and a
finding on a sibling candidate cannot silently become a finding on the target candidate either.
This module makes both transitions explicit.  The revision log supplies predecessor lineage; every
other reviewed candidate is a sibling.  Serious findings require a target-bound resolution record
before promotion can credit the target as fully reviewed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import acceptance, integrity, revision, schema
from .workspace import resolve_scene_candidate, validate_leaf_filename, validate_scene_id

SERIOUS = {"material", "fatal"}
CLOSED = {"resolved", "rechecked", "waived", "adjudicated"}


def finding_id(finding: dict) -> str:
    """Stable identity independent of severity changes across a revision."""
    dimension, evidence = revision.finding_fingerprint(finding)
    payload = json.dumps([dimension, evidence], separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def predecessor_of(scene_dir: Path, target_candidate: str) -> str | None:
    """Return the latest explicitly recorded predecessor of ``target_candidate``."""
    predecessor = None
    for record in revision.revision_history(scene_dir):
        if record.get("after") == target_candidate and isinstance(record.get("before"), str):
            predecessor = record["before"]
    return predecessor


def _load_records(scene_dir: Path) -> list[tuple[Path, dict | None, str | None]]:
    root = scene_dir / "resolutions"
    loaded: list[tuple[Path, dict | None, str | None]] = []
    for path in sorted(root.glob("*.json")) if root.exists() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            loaded.append((path, None, str(exc)))
            continue
        errors = schema.validate_named(data, "issue-resolution")
        loaded.append((path, data, "; ".join(errors) if errors else None))
    return loaded


def evaluate_gate(
    scene_dir: Path,
    target_candidate: str,
    target_sha256: str,
    critiques: list[tuple[str, dict | None, str | None]],
) -> tuple[list[str], list[dict]]:
    """Require explicit disposition of serious predecessor/sibling findings.

    Returns blocking reasons and exact resolution/source paths that must be frozen by acceptance.
    """
    predecessor = predecessor_of(scene_dir, target_candidate)
    records = _load_records(scene_dir)
    reasons: list[str] = []
    bindings: list[dict] = []

    for path, data, error in records:
        if error:
            reasons.append(f"{path.name}: invalid issue-resolution: {error}")

    valid_records = [(path, data) for path, data, error in records if data is not None and error is None]
    seen_bindings: set[Path] = set()

    for label, critique, parse_error in critiques:
        if parse_error or not isinstance(critique, dict):
            continue
        source_candidate = critique.get("candidate")
        source_sha = critique.get("candidate_sha256")
        if not isinstance(source_candidate, str) or not isinstance(source_sha, str):
            continue
        if source_candidate == target_candidate and source_sha == target_sha256:
            continue
        relationship = "predecessor" if source_candidate == predecessor else "sibling"
        source_path = scene_dir / "critiques" / label
        if not source_path.exists():
            continue
        source_digest = integrity.sha256_file(source_path)

        for finding in critique.get("findings", []):
            if not isinstance(finding, dict) or finding.get("severity") not in SERIOUS:
                continue
            fid = finding_id(finding)
            matching: list[tuple[Path, dict]] = []
            for path, record in valid_records:
                source = record.get("source", {})
                target = record.get("target", {})
                if (
                    record.get("finding_id") == fid
                    and record.get("relationship") == relationship
                    and source.get("critique_file") == label
                    and source.get("critique_sha256") == source_digest
                    and source.get("candidate") == source_candidate
                    and source.get("candidate_sha256") == source_sha
                    and source.get("critic") == critique.get("critic")
                    and target.get("candidate") == target_candidate
                    and target.get("candidate_sha256") == target_sha256
                ):
                    matching.append((path, record))

            if not matching:
                reasons.append(
                    f"{label}: serious {relationship} finding {fid[:12]} lacks an exact "
                    "applicability/resolution record for this candidate"
                )
                continue

            path, record = matching[-1]
            applicability = record.get("applicability")
            resolution_state = record.get("resolution")
            if relationship == "predecessor" and applicability != "applies":
                reasons.append(
                    f"{path.name}: predecessor finding must be treated as applicable before disposition"
                )
                continue
            if resolution_state not in CLOSED:
                reasons.append(f"{path.name}: finding remains open")
                continue
            if path not in seen_bindings:
                bindings.append({"resolution_path": path, "source_critique_path": source_path})
                seen_bindings.add(path)

    return reasons, bindings


def record_resolution(
    project: Path,
    scene_id: str,
    target_candidate: str,
    source_critique: str,
    source_finding_id: str,
    relationship: str,
    applicability: str,
    resolution_state: str,
    reason: str,
    decided_by: str,
) -> dict:
    """Record one immutable, source- and target-bound issue disposition."""
    project = Path(project).resolve()
    validate_scene_id(scene_id)
    scene_dir = project / "scenes" / scene_id
    target_path = resolve_scene_candidate(project, scene_id, target_candidate)
    if not target_path.exists():
        return {"error": f"target candidate not found: {target_candidate}"}
    try:
        source_critique = validate_leaf_filename(source_critique, ".json")
    except ValueError as exc:
        return {"error": str(exc)}
    source_path = (scene_dir / "critiques" / source_critique).resolve()
    critique_root = (scene_dir / "critiques").resolve()
    if not source_path.is_relative_to(critique_root) or not source_path.exists():
        return {"error": f"source critique not found: {source_critique}"}
    try:
        critique = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"error": f"source critique is invalid JSON: {exc}"}
    critique_errors = schema.validate_named(critique, "critique")
    if critique_errors:
        return {"error": "source critique is invalid: " + "; ".join(critique_errors)}
    source_sha = critique.get("candidate_sha256")
    if not isinstance(source_sha, str):
        return {"error": "source critique is not candidate-bound"}
    ids = {finding_id(f): f for f in critique.get("findings", []) if isinstance(f, dict)}
    if source_finding_id not in ids:
        return {"error": f"finding_id {source_finding_id!r} is not present in {source_critique}"}
    if ids[source_finding_id].get("severity") not in SERIOUS:
        return {"error": "only material/fatal findings require cross-candidate resolution"}

    predecessor = predecessor_of(scene_dir, target_path.name)
    expected_relationship = "predecessor" if critique.get("candidate") == predecessor else "sibling"
    if relationship != expected_relationship:
        return {"error": f"relationship must be {expected_relationship!r} for this source/target lineage"}
    if relationship == "predecessor" and applicability != "applies":
        return {"error": "predecessor findings must be marked applicability='applies'"}

    record = {
        "version": "issue-resolution@1",
        "finding_id": source_finding_id,
        "relationship": relationship,
        "applicability": applicability,
        "resolution": resolution_state,
        "reason": reason,
        "decided_by": decided_by,
        "source": {
            "critique_file": source_path.name,
            "critique_sha256": integrity.sha256_file(source_path),
            "candidate": critique.get("candidate"),
            "candidate_sha256": source_sha,
            "critic": critique.get("critic"),
        },
        "target": {
            "candidate": target_path.name,
            "candidate_sha256": integrity.sha256_file(target_path),
        },
    }
    errors = schema.validate_named(record, "issue-resolution")
    if errors:
        return {"error": "invalid issue resolution: " + "; ".join(errors)}
    if resolution_state == "open":
        # An explicit open record is useful evidence but cannot satisfy the gate.
        pass

    safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", target_path.stem).strip(".-") or "candidate"
    root = scene_dir / "resolutions"
    root.mkdir(parents=True, exist_ok=True)
    base = f"{source_finding_id[:16]}-to-{safe}-{record['target']['candidate_sha256'][:12]}"
    out = root / f"{base}.json"
    attempt = 2
    while out.exists():
        out = root / f"{base}-attempt{attempt}.json"
        attempt += 1
    acceptance.atomic_write(
        out, (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return {
        "written": str(out.relative_to(project)),
        "finding_id": source_finding_id,
        "relationship": relationship,
        "applicability": applicability,
        "resolution": resolution_state,
        "target_candidate_sha256": record["target"]["candidate_sha256"],
    }
