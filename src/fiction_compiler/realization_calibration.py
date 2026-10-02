"""Calibration evidence for the plan-blind extraction -> plan-aware alignment boundary.

ADR 0024 made missing alignment explicitly uncertain.  This module tests the empirical assumption
behind that boundary on frozen planted controls without changing promotion policy.  It keeps extractor
coverage and aligner correctness separate so an extractor miss can never be re-labelled as a proved
prose omission.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, schema
from .workspace import ROOT


CORPUS = ROOT / "evals" / "realization-cases.json"
_STUDY_ID_RE = re.compile(r"^realization-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _study_id(now: datetime | None = None) -> str:
    now = now or _now()
    return f"realization-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"


def _validate_study_id(study_id: str) -> str:
    if not isinstance(study_id, str) or _STUDY_ID_RE.fullmatch(study_id) is None:
        raise ValueError(f"invalid study_id {study_id!r}")
    return study_id


def _root(project: Path, study_id: str) -> Path:
    return Path(project) / ".runs" / "realization-calibration" / _validate_study_id(study_id)


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def _load_corpus() -> list[dict]:
    if not CORPUS.exists():
        return []
    return _load_json(CORPUS).get("cases", [])


def _case_snapshot(case: dict) -> dict:
    prose = str(case["prose"])
    return {
        "id": case["id"],
        "source_kind": case.get("source_kind", "local_control"),
        "label_source": case.get("label_source", "provisional_fixture"),
        "prose": prose,
        "prose_sha256": acceptance.sha256_bytes(prose.encode("utf-8")),
        "required_events": case["required_events"],
    }


def start_study(project: Path, name: str, case_ids: list[str] | None = None,
                criteria: dict | None = None) -> dict:
    project = Path(project)
    corpus = _load_corpus()
    by_id = {case["id"]: case for case in corpus if isinstance(case, dict) and case.get("id")}
    selected = case_ids if case_ids is not None else list(by_id)
    if not selected:
        return {"error": "realization calibration needs at least one case"}
    if len(set(selected)) != len(selected):
        return {"error": "realization calibration case_ids contain duplicates"}
    unknown = [case_id for case_id in selected if case_id not in by_id]
    if unknown:
        return {"error": f"unknown realization calibration case ids: {unknown}"}
    if not isinstance(name, str) or not name.strip():
        return {"error": "realization calibration study name must be non-empty"}
    if criteria is not None and not isinstance(criteria, dict):
        return {"error": "criteria must be an object"}
    created = _now()
    study_id = _study_id(created)
    manifest = {
        "schema_version": 1,
        "study_id": study_id,
        "name": name.strip(),
        "source_corpus_sha256": acceptance.sha256_bytes(CORPUS.read_bytes()),
        "cases": [_case_snapshot(by_id[case_id]) for case_id in selected],
        "criteria": dict(criteria or {}),
        "created_at": created.isoformat(),
    }
    errors = schema.validate_named(manifest, "realization-calibration-study")
    if errors:
        return {"error": "invalid realization calibration study: " + "; ".join(errors)}
    path = _root(project, study_id) / "study.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(manifest))
    return {"study_id": study_id, "cases": selected, "path": str(path.relative_to(project)),
            "authority": "not_a_prose_audit_gate"}


def _load_study(project: Path, study_id: str) -> tuple[dict | None, list[str]]:
    path = _root(project, study_id) / "study.json"
    if not path.exists():
        return None, [f"realization calibration study {study_id!r} does not exist"]
    try:
        manifest = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [str(exc)]
    errors = schema.validate_named(manifest, "realization-calibration-study")
    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        digest = acceptance.sha256_bytes(str(case.get("prose", "")).encode("utf-8"))
        if digest != case.get("prose_sha256"):
            errors.append(f"case {case.get('id')!r} prose hash is stale")
    return manifest, errors


def extractor_packet(project: Path, study_id: str, case_id: str) -> dict:
    """Return prose only: no required events, plan, expected label, or evidence anchors."""
    project = Path(project)
    try:
        manifest, errors = _load_study(project, study_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid realization calibration study", "details": errors}
    case = next((item for item in manifest["cases"] if item["id"] == case_id), None)
    if case is None:
        return {"error": f"case {case_id!r} is not in study"}
    return {
        "study_id": study_id,
        "submission_id": acceptance.sha256_bytes(
            acceptance.canonical_json_bytes({"study": study_id, "case": case_id, "stage": "extract"})
        )[:16],
        "prose": case["prose"],
        "instructions": (
            "Without any plan or canonical event IDs, list events actually present in the prose. "
            "Each observed event must quote exact prose evidence and mark whether it is consequential."
        ),
    }


def _case(manifest: dict, case_id: str) -> dict | None:
    return next((item for item in manifest.get("cases", []) if item.get("id") == case_id), None)


def record_extraction(project: Path, study_id: str, case_id: str, extractor_family: str,
                      extractor_id: str, trial_index: int, observed_events: list[dict]) -> dict:
    project = Path(project)
    manifest, errors = _load_study(project, study_id)
    if manifest is None or errors:
        return {"error": "invalid realization calibration study", "details": errors}
    case = _case(manifest, case_id)
    if case is None:
        return {"error": f"case {case_id!r} is not in study"}
    if not isinstance(observed_events, list):
        return {"error": "observed_events must be an array"}
    ids: set[str] = set()
    for item in observed_events:
        if not isinstance(item, dict):
            return {"error": "observed_events entries must be objects"}
        oid = item.get("id")
        if oid in ids:
            return {"error": f"duplicate observed event id: {oid}"}
        ids.add(oid)
        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence not in case["prose"]:
            return {"error": f"observed event evidence is not in frozen prose: {evidence!r}"}

    existing, existing_errors = _validated_records(
        _root(project, study_id) / "extractions", "realization-extraction", manifest
    )
    if existing_errors:
        return {"error": "existing realization extraction evidence is invalid", "details": existing_errors}
    if any(item["case_id"] == case_id and item["extractor_id"] == extractor_id
           and item["trial_index"] == trial_index for item in existing):
        return {"error": "duplicate extraction for case/extractor/trial"}
    record = {
        "schema_version": 1,
        "study_id": study_id,
        "extraction_id": f"extract-{uuid.uuid4().hex}",
        "case_id": case_id,
        "prose_sha256": case["prose_sha256"],
        "extractor_family": extractor_family,
        "extractor_id": extractor_id,
        "trial_index": trial_index,
        "observed_events": observed_events,
        "recorded_at": _now().isoformat(),
    }
    validation = schema.validate_named(record, "realization-extraction")
    if validation:
        return {"error": "invalid realization extraction: " + "; ".join(validation)}
    path = _root(project, study_id) / "extractions" / f"{record['extraction_id']}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _extraction_by_id(project: Path, manifest: dict, extraction_id: str) -> tuple[dict | None, list[str]]:
    extractions, errors = _validated_records(
        _root(project, manifest["study_id"]) / "extractions", "realization-extraction", manifest
    )
    return next((item for item in extractions if item["extraction_id"] == extraction_id), None), errors


def aligner_packet(project: Path, study_id: str, extraction_id: str) -> dict:
    """Show prose, required-event descriptions and observations, but hide expected status/anchors."""
    project = Path(project)
    manifest, errors = _load_study(project, study_id)
    if manifest is None or errors:
        return {"error": "invalid realization calibration study", "details": errors}
    extraction, extraction_errors = _extraction_by_id(project, manifest, extraction_id)
    if extraction_errors:
        return {"error": "invalid extraction evidence", "details": extraction_errors}
    if extraction is None:
        return {"error": f"extraction {extraction_id!r} is not in study"}
    case = _case(manifest, extraction["case_id"])
    return {
        "study_id": study_id,
        "extraction_id": extraction_id,
        "prose": case["prose"],
        "observed_events": extraction["observed_events"],
        "required_events": [
            {"event_id": item["event_id"], "description": item["description"]}
            for item in case["required_events"]
        ],
        "instructions": (
            "Re-inspect the frozen prose while mapping each required event to the plan-blind observations. "
            "Mark omitted only when the prose itself supports absence; use unverified when an extractor miss "
            "or semantic uncertainty prevents that conclusion. A realized event must map to an observation."
        ),
    }


def record_alignment(project: Path, study_id: str, extraction_id: str, aligner_family: str,
                     aligner_id: str, event_alignment: list[dict]) -> dict:
    project = Path(project)
    manifest, errors = _load_study(project, study_id)
    if manifest is None or errors:
        return {"error": "invalid realization calibration study", "details": errors}
    extraction, extraction_errors = _extraction_by_id(project, manifest, extraction_id)
    if extraction_errors:
        return {"error": "invalid extraction evidence", "details": extraction_errors}
    if extraction is None:
        return {"error": f"extraction {extraction_id!r} is not in study"}
    if not isinstance(event_alignment, list):
        return {"error": "event_alignment must be an array"}
    case = _case(manifest, extraction["case_id"])
    required = {item["event_id"] for item in case["required_events"]}
    observed = {item["id"] for item in extraction["observed_events"]}
    seen: set[str] = set()
    for item in event_alignment:
        if not isinstance(item, dict):
            return {"error": "event_alignment entries must be objects"}
        event_id = item.get("event_id")
        if event_id not in required:
            return {"error": f"alignment references non-required event {event_id!r}"}
        if event_id in seen:
            return {"error": f"duplicate event alignment: {event_id}"}
        seen.add(event_id)
        status = item.get("status")
        observed_id = item.get("observed_id")
        if status == "realized" and observed_id not in observed:
            return {"error": f"realized event {event_id!r} references unknown observed event {observed_id!r}"}
        if status != "realized" and observed_id:
            return {"error": f"{status} event {event_id!r} must not reference observed_id"}
    if seen != required:
        return {"error": f"alignment must assess every required event; missing {sorted(required - seen)}"}
    existing, existing_errors = _validated_records(
        _root(project, study_id) / "alignments", "realization-alignment", manifest
    )
    if existing_errors:
        return {"error": "existing realization alignment evidence is invalid", "details": existing_errors}
    if any(item["extraction_id"] == extraction_id and item["aligner_id"] == aligner_id for item in existing):
        return {"error": "duplicate alignment for extraction/aligner"}
    record = {
        "schema_version": 1,
        "study_id": study_id,
        "alignment_id": f"align-{uuid.uuid4().hex}",
        "case_id": extraction["case_id"],
        "prose_sha256": extraction["prose_sha256"],
        "extraction_id": extraction_id,
        "aligner_family": aligner_family,
        "aligner_id": aligner_id,
        "event_alignment": event_alignment,
        "recorded_at": _now().isoformat(),
    }
    validation = schema.validate_named(record, "realization-alignment")
    if validation:
        return {"error": "invalid realization alignment: " + "; ".join(validation)}
    path = _root(project, study_id) / "alignments" / f"{record['alignment_id']}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _validated_records(path: Path, schema_name: str, manifest: dict) -> tuple[list[dict], list[str]]:
    valid: list[dict] = []
    errors: list[str] = []
    case_by_id = {case["id"]: case for case in manifest.get("cases", [])}
    for record_path in sorted(path.glob("*.json")):
        try:
            record = _load_json(record_path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"{record_path.name}: unreadable evidence ({exc})")
            continue
        problems = schema.validate_named(record, schema_name)
        if record.get("study_id") != manifest.get("study_id"):
            problems.append("study_id does not match study")
        case = case_by_id.get(record.get("case_id"))
        if case is None:
            problems.append("case_id is not part of frozen study")
        elif record.get("prose_sha256") != case.get("prose_sha256"):
            problems.append("prose_sha256 does not match frozen case")
        if case is not None and schema_name == "realization-extraction":
            for item in record.get("observed_events", []):
                evidence = item.get("evidence") if isinstance(item, dict) else None
                if isinstance(evidence, str) and evidence not in case["prose"]:
                    problems.append(f"observed evidence is not in frozen prose: {evidence!r}")
        if problems:
            errors.append(f"{record_path.name}: {'; '.join(problems)}")
        else:
            valid.append(record)
    return valid, errors


def _anchor_matches(case_event: dict, extraction: dict) -> list[str]:
    matches: list[str] = []
    anchors = case_event.get("evidence_anchors", [])
    for observed in extraction.get("observed_events", []):
        evidence = observed.get("evidence", "")
        if any(anchor in evidence or evidence in anchor for anchor in anchors):
            matches.append(observed["id"])
    return matches


def _classify(case_event: dict, extraction: dict, alignment: dict | None) -> dict:
    expected = case_event["expected_status"]
    anchor_ids = _anchor_matches(case_event, extraction) if expected == "realized" else []
    result: dict[str, Any] = {
        "event_id": case_event["event_id"],
        "expected_status": expected,
        "extractor_anchor_matches": anchor_ids,
        "extractor_status": (
            "recognized_fixture_evidence" if anchor_ids else
            "missed_fixture_evidence" if expected == "realized" else
            "not_applicable_for_omission"
        ),
        "pipeline_status": "unverified",
    }
    if alignment is None:
        result["reason"] = "no alignment evidence"
        return result
    item = next((row for row in alignment["event_alignment"] if row["event_id"] == case_event["event_id"]), None)
    if item is None or item["status"] == "unverified":
        result["reason"] = "alignment remained unverified"
        return result
    result["aligner_status"] = item["status"]
    if expected == "omitted":
        if item["status"] == "omitted":
            result["pipeline_status"] = "correct_omission"
        else:
            result["pipeline_status"] = "false_realization"
        return result
    if not anchor_ids:
        result["pipeline_status"] = "unverified_extractor_miss"
        result["reason"] = "fixture evidence was not extracted; omission cannot be inferred"
        return result
    if item["status"] == "omitted":
        result["pipeline_status"] = "alignment_false_omission"
    elif item.get("observed_id") in anchor_ids:
        result["pipeline_status"] = "correct_realization"
    else:
        result["pipeline_status"] = "alignment_wrong_observation"
    return result


def report(project: Path, study_id: str) -> dict:
    project = Path(project)
    manifest, study_errors = _load_study(project, study_id)
    if manifest is None:
        return {"error": "realization calibration study not found", "details": study_errors}
    extractions, extraction_errors = _validated_records(
        _root(project, study_id) / "extractions", "realization-extraction", manifest
    )
    alignments, alignment_errors = _validated_records(
        _root(project, study_id) / "alignments", "realization-alignment", manifest
    )
    extraction_by_id = {item["extraction_id"]: item for item in extractions}
    integrity_errors = [*study_errors, *extraction_errors, *alignment_errors]
    for alignment in alignments:
        extraction = extraction_by_id.get(alignment["extraction_id"])
        if extraction is None:
            integrity_errors.append(f"alignment {alignment['alignment_id']} references missing extraction")
            continue
        if alignment["case_id"] != extraction["case_id"]:
            integrity_errors.append(f"alignment {alignment['alignment_id']} case does not match extraction")
        observed = {item["id"] for item in extraction["observed_events"]}
        required = {item["event_id"] for item in _case(manifest, extraction["case_id"])["required_events"]}
        aligned_ids = [item["event_id"] for item in alignment["event_alignment"]]
        if set(aligned_ids) != required or len(aligned_ids) != len(required):
            integrity_errors.append(f"alignment {alignment['alignment_id']} does not assess each required event exactly once")
        for item in alignment["event_alignment"]:
            if item["status"] == "realized" and item.get("observed_id") not in observed:
                integrity_errors.append(f"alignment {alignment['alignment_id']} references unknown observed event")
            if item["status"] != "realized" and item.get("observed_id"):
                integrity_errors.append(f"alignment {alignment['alignment_id']} has observed_id for {item['status']}")
    extraction_keys = [(item["case_id"], item["extractor_id"], item["trial_index"]) for item in extractions]
    duplicates = [key for key, count in Counter(extraction_keys).items() if count > 1]
    if duplicates:
        integrity_errors.append(f"duplicate extraction keys: {duplicates}")
    alignment_keys = [(item["extraction_id"], item["aligner_id"]) for item in alignments]
    duplicates = [key for key, count in Counter(alignment_keys).items() if count > 1]
    if duplicates:
        integrity_errors.append(f"duplicate alignment keys: {duplicates}")
    if integrity_errors:
        return {"study_id": study_id, "evidence_status": "invalid", "authority": "none",
                "integrity_errors": integrity_errors}

    alignments_by_extraction: dict[str, list[dict]] = defaultdict(list)
    for item in alignments:
        alignments_by_extraction[item["extraction_id"]].append(item)
    rows: list[dict] = []
    for extraction in extractions:
        case = _case(manifest, extraction["case_id"])
        candidate_alignments = alignments_by_extraction.get(extraction["extraction_id"], [])
        if not candidate_alignments:
            candidate_alignments = [None]
        for alignment in candidate_alignments:
            for event in case["required_events"]:
                rows.append({
                    "case_id": case["id"],
                    "extraction_id": extraction["extraction_id"],
                    "extractor_family": extraction["extractor_family"],
                    "extractor_id": extraction["extractor_id"],
                    "trial_index": extraction["trial_index"],
                    "alignment_id": alignment["alignment_id"] if alignment else None,
                    "aligner_family": alignment["aligner_family"] if alignment else None,
                    "aligner_id": alignment["aligner_id"] if alignment else None,
                    **_classify(event, extraction, alignment),
                })
    realized = [row for row in rows if row["expected_status"] == "realized"]
    omitted = [row for row in rows if row["expected_status"] == "omitted"]
    extraction_hit_rate = (
        sum(row["extractor_status"] == "recognized_fixture_evidence" for row in realized) / len(realized)
        if realized else None
    )
    aligned_realized = [row for row in realized if row["extractor_status"] == "recognized_fixture_evidence"
                        and row["alignment_id"] is not None]
    alignment_realization_rate = (
        sum(row["pipeline_status"] == "correct_realization" for row in aligned_realized) / len(aligned_realized)
        if aligned_realized else None
    )
    aligned_omitted = [row for row in omitted if row["alignment_id"] is not None]
    omission_rate = (
        sum(row["pipeline_status"] == "correct_omission" for row in aligned_omitted) / len(aligned_omitted)
        if aligned_omitted else None
    )
    current_sha = acceptance.sha256_bytes(CORPUS.read_bytes()) if CORPUS.exists() else None
    return {
        "study_id": study_id,
        "name": manifest["name"],
        "evidence_status": "descriptive",
        "authority": "not_a_prose_audit_gate",
        "criteria": manifest["criteria"],
        "counts": {"cases": len(manifest["cases"]), "extractions": len(extractions), "alignments": len(alignments)},
        "source_corpus": {"frozen_sha256": manifest["source_corpus_sha256"], "current_sha256": current_sha,
                          "changed_since_freeze": current_sha != manifest["source_corpus_sha256"]},
        "metrics": {
            "realized_fixture_extraction_hit_rate": extraction_hit_rate,
            "alignment_accuracy_given_fixture_evidence": alignment_realization_rate,
            "planted_omission_alignment_rate": omission_rate,
        },
        "rows": rows,
        "open_evidence": {
            "semantic_generalization": "fixture anchors do not prove reliable semantic extraction outside these controls",
            "free_text_turn_and_affect": "unverified; this calibration does not make them deterministic",
            "gate_enablement": "requires predeclared tolerances and adequate hidden/independent calibration evidence",
        },
    }
