"""Evidence-bound behavioural calibration for live literary critics.

This module extends the small planted-defect corpus in :mod:`critic_eval` without turning it into a
production gate.  A study freezes the exact cases and provisional labels before observations arrive,
then records repeated/cross-family critic runs and independent human labels.  Reports keep
repeatability, conditional invariance, provisional fixture accuracy, crossed-family behaviour, and
human agreement separate.  Missing or disputed evidence remains explicit.
"""
from __future__ import annotations

import itertools
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance, critic_eval, schema


_STUDY_ID_RE = re.compile(r"^critic-[0-9]{8}T[0-9]{12}Z-[0-9a-f]{12}$")
_BLOCKING = {"material", "fatal"}
_INVARIANT_TRANSFORMS = {"metadata_relabel", "presentation_order", "formatting"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _study_id(now: datetime | None = None) -> str:
    now = now or _now()
    return f"critic-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex[:12]}"


def _validate_study_id(study_id: str) -> str:
    if not isinstance(study_id, str) or _STUDY_ID_RE.fullmatch(study_id) is None:
        raise ValueError(f"invalid study_id {study_id!r}")
    return study_id


def _root(project: Path, study_id: str) -> Path:
    return Path(project) / ".runs" / "critic-calibration" / _validate_study_id(study_id)


def _study_path(project: Path, study_id: str) -> Path:
    return _root(project, study_id) / "study.json"


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return value


def _case_snapshot(case: dict) -> dict:
    inp = case.get("input", {}) if isinstance(case.get("input", {}), dict) else {}
    return {
        "id": case["id"],
        "critic": str(case.get("critic", "")),
        "kind": case.get("kind", "defect"),
        "signals": [str(item) for item in case.get("signals", [])],
        "expect_caught": bool(case.get("expect_caught", True)),
        "input": inp,
        "input_sha256": acceptance.sha256_bytes(acceptance.canonical_json_bytes(inp)),
        "label_source": case.get("label_source", "provisional_fixture"),
        "source_kind": case.get("source_kind", "local_control"),
    }


def start_study(project: Path, name: str, case_ids: list[str] | None = None,
                criteria: dict | None = None) -> dict:
    """Freeze a calibration case set before live critic/human observations are collected."""
    project = Path(project)
    corpus = critic_eval.load_corpus()
    by_id = {case.get("id"): case for case in corpus if isinstance(case, dict) and case.get("id")}
    selected_ids = case_ids if case_ids is not None else [
        case["id"] for case in corpus if case.get("detector") == "llm"
    ]
    if not selected_ids:
        return {"error": "critic calibration study needs at least one case"}
    if len(set(selected_ids)) != len(selected_ids):
        return {"error": "critic calibration case_ids contain duplicates"}
    unknown = [case_id for case_id in selected_ids if case_id not in by_id]
    if unknown:
        return {"error": f"unknown critic calibration case ids: {unknown}"}
    if not isinstance(name, str) or not name.strip():
        return {"error": "critic calibration study name must be non-empty"}
    if criteria is not None and not isinstance(criteria, dict):
        return {"error": "criteria must be an object"}

    created = _now()
    study_id = _study_id(created)
    cases = [_case_snapshot(by_id[case_id]) for case_id in selected_ids]
    source_raw = critic_eval.CORPUS.read_bytes() if critic_eval.CORPUS.exists() else b""
    manifest = {
        "schema_version": 1,
        "study_id": study_id,
        "name": name.strip(),
        "source_corpus_sha256": acceptance.sha256_bytes(source_raw),
        "cases": cases,
        "criteria": dict(criteria or {}),
        "created_at": created.isoformat(),
    }
    errors = schema.validate_named(manifest, "critic-calibration-study")
    if errors:
        return {"error": "invalid critic calibration study: " + "; ".join(errors)}
    path = _study_path(project, study_id)
    if path.exists():
        return {"error": f"critic calibration study collision at {study_id}"}
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(manifest))
    return {
        "study_id": study_id,
        "name": manifest["name"],
        "cases": [case["id"] for case in cases],
        "criteria": manifest["criteria"],
        "path": str(path.relative_to(project)),
        "note": "Frozen provisional labels are screening evidence, not human calibration or promotion authority.",
    }


def _load_study(project: Path, study_id: str) -> tuple[dict | None, list[str]]:
    path = _study_path(project, study_id)
    if not path.exists():
        return None, [f"critic calibration study {study_id!r} does not exist"]
    try:
        manifest = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [str(exc)]
    errors = schema.validate_named(manifest, "critic-calibration-study")
    for case in manifest.get("cases", []):
        if not isinstance(case, dict):
            continue
        digest = acceptance.sha256_bytes(acceptance.canonical_json_bytes(case.get("input", {})))
        if digest != case.get("input_sha256"):
            errors.append(f"case {case.get('id')!r} input hash is stale")
    return manifest, errors


def judge_packet(project: Path, study_id: str, case_id: str) -> dict:
    """Return one frozen input without defect/control labels, signals, or expected outcome."""
    project = Path(project)
    try:
        manifest, errors = _load_study(project, study_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid critic calibration study", "details": errors}
    case = next((item for item in manifest["cases"] if item["id"] == case_id), None)
    if case is None:
        return {"error": f"case {case_id!r} is not in study"}
    submission_id = acceptance.sha256_bytes(
        acceptance.canonical_json_bytes({"study": study_id, "case": case_id})
    )[:16]
    return {
        "study_id": study_id,
        "submission_id": submission_id,
        "input": case["input"],
        "instructions": (
            "Judge this frozen input without attempting to infer its calibration label. Return the normal "
            "critique verdict/confidence/findings. Repeated trials must be independent runs."
        ),
    }


def _validated_existing(path: Path, schema_name: str, manifest: dict) -> tuple[list[dict], list[str]]:
    valid: list[dict] = []
    errors: list[str] = []
    case_by_id = {case["id"]: case for case in manifest.get("cases", []) if isinstance(case, dict)}
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
            problems.append("case_id is not part of the frozen study")
        elif record.get("case_input_sha256") != case.get("input_sha256"):
            problems.append("case_input_sha256 does not match frozen study")
        if schema_name == "critic-calibration-observation" and case is not None:
            expected_caught = critic_eval.score_findings(case, record.get("findings", []))
            expected_signals = critic_eval.matching_signals(case, record.get("findings", []))
            if record.get("caught") != expected_caught:
                problems.append("derived caught value does not match findings")
            if record.get("matched_signals") != expected_signals:
                problems.append("derived matched_signals do not match findings")
            if (record.get("transform_kind") in _INVARIANT_TRANSFORMS
                    and record.get("behavioral_expectation") != "invariant"):
                problems.append("declared invariant transform is not marked invariant")
            if (record.get("behavioral_expectation") in {"invariant", "directional_worse"}
                    and not record.get("invariance_group")):
                problems.append("behavioral comparison is missing invariance_group")
        if problems:
            errors.append(f"{record_path.name}: {'; '.join(problems)}")
        else:
            valid.append(record)
    return valid, errors


def record_observation(project: Path, study_id: str, case_id: str, judge_family: str,
                       judge_id: str, writer_family: str, trial_index: int, variant_id: str,
                       transform_kind: str, behavioral_expectation: str, verdict: str,
                       findings: list, confidence: float = 1.0,
                       invariance_group: str | None = None) -> dict:
    """Persist one live critic result and derive target localization from the frozen case."""
    project = Path(project)
    try:
        manifest, errors = _load_study(project, study_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid critic calibration study", "details": errors}
    case = next((item for item in manifest["cases"] if item["id"] == case_id), None)
    if case is None:
        return {"error": f"case {case_id!r} is not in study"}
    if transform_kind in _INVARIANT_TRANSFORMS and behavioral_expectation != "invariant":
        return {"error": f"{transform_kind} must be explicitly recorded as an invariant transformation"}
    if behavioral_expectation in {"invariant", "directional_worse"} and not invariance_group:
        return {"error": f"{behavioral_expectation} observation needs an invariance_group"}

    critique_probe = {
        "candidate": "submission.md",
        "critic": "calibration",
        "verdict": verdict,
        "confidence": confidence,
        "findings": findings,
    }
    validation = schema.validate_named(critique_probe, "critique")
    if verdict == "pass" and any(f.get("severity") in _BLOCKING for f in findings if isinstance(f, dict)):
        validation.append("pass verdict cannot carry material/fatal findings")
    if validation:
        return {"error": "invalid critic observation: " + "; ".join(validation)}

    observations_dir = _root(project, study_id) / "observations"
    existing, existing_errors = _validated_existing(
        observations_dir, "critic-calibration-observation", manifest
    )
    if existing_errors:
        return {"error": "existing critic calibration evidence is invalid", "details": existing_errors}
    key = (case_id, judge_id, writer_family, trial_index, variant_id)
    if any((item["case_id"], item["judge_id"], item["writer_family"], item["trial_index"],
            item["variant_id"]) == key for item in existing):
        return {"error": "duplicate critic observation for case/judge/writer/trial/variant"}
    if behavioral_expectation == "baseline" and invariance_group:
        if any(item.get("case_id") == case_id and item.get("judge_id") == judge_id
               and item.get("writer_family") == writer_family
               and item.get("trial_index") == trial_index
               and item.get("invariance_group") == invariance_group
               and item.get("behavioral_expectation") == "baseline" for item in existing):
            return {"error": "an invariance group may have only one baseline per matched trial"}

    observation_id = f"obs-{uuid.uuid4().hex}"
    record: dict[str, Any] = {
        "schema_version": 1,
        "study_id": study_id,
        "observation_id": observation_id,
        "case_id": case_id,
        "case_input_sha256": case["input_sha256"],
        "judge_family": judge_family,
        "judge_id": judge_id,
        "writer_family": writer_family,
        "trial_index": trial_index,
        "variant_id": variant_id,
        "transform_kind": transform_kind,
        "behavioral_expectation": behavioral_expectation,
        "verdict": verdict,
        "confidence": confidence,
        "findings": findings,
        "caught": critic_eval.score_findings(case, findings),
        "matched_signals": critic_eval.matching_signals(case, findings),
        "recorded_at": _now().isoformat(),
    }
    if invariance_group:
        record["invariance_group"] = invariance_group
    validation = schema.validate_named(record, "critic-calibration-observation")
    if validation:
        return {"error": "invalid critic calibration observation: " + "; ".join(validation)}
    path = observations_dir / f"{observation_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def record_human_label(project: Path, study_id: str, case_id: str, annotator_id: str,
                       annotator_role: str, label: str, severity: str | None = None,
                       signals: list[str] | None = None, notes: str | None = None) -> dict:
    """Record one independent human defect/control label; disagreement is preserved, never averaged."""
    project = Path(project)
    try:
        manifest, errors = _load_study(project, study_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None or errors:
        return {"error": "invalid critic calibration study", "details": errors}
    case = next((item for item in manifest["cases"] if item["id"] == case_id), None)
    if case is None:
        return {"error": f"case {case_id!r} is not in study"}
    labels_dir = _root(project, study_id) / "human-labels"
    existing, existing_errors = _validated_existing(labels_dir, "critic-human-label", manifest)
    if existing_errors:
        return {"error": "existing critic human-label evidence is invalid", "details": existing_errors}
    if any(item["case_id"] == case_id and item["annotator_id"] == annotator_id for item in existing):
        return {"error": "annotator already labeled this calibration case"}

    label_id = f"label-{uuid.uuid4().hex}"
    record: dict[str, Any] = {
        "schema_version": 1,
        "study_id": study_id,
        "label_id": label_id,
        "case_id": case_id,
        "case_input_sha256": case["input_sha256"],
        "annotator_id": annotator_id,
        "annotator_role": annotator_role,
        "label": label,
        "signals": list(signals or []),
        "recorded_at": _now().isoformat(),
    }
    if severity is not None:
        record["severity"] = severity
    if notes is not None:
        record["notes"] = notes
    validation = schema.validate_named(record, "critic-human-label")
    if validation:
        return {"error": "invalid critic human label: " + "; ".join(validation)}
    path = labels_dir / f"{label_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"path": str(path.relative_to(project)), **record}


def _fixture_metrics(manifest: dict, observations: list[dict]) -> dict:
    case_by_id = {case["id"]: case for case in manifest["cases"]}
    by_family: dict[str, dict] = {}
    for family in sorted({item["judge_family"] for item in observations}):
        rows = [item for item in observations if item["judge_family"] == family]
        correct = [item["caught"] == case_by_id[item["case_id"]]["expect_caught"] for item in rows]
        defects = [item for item in rows if case_by_id[item["case_id"]]["kind"] == "defect"]
        controls = [item for item in rows if case_by_id[item["case_id"]]["kind"] == "control"]
        by_family[family] = {
            "observations": len(rows),
            "provisional_correct": sum(correct),
            "provisional_accuracy": (sum(correct) / len(correct)) if correct else None,
            "defect_localization_rate": (
                sum(1 for item in defects if item["caught"]) / len(defects) if defects else None
            ),
            "control_false_positive_rate": (
                sum(1 for item in controls if item["caught"]) / len(controls) if controls else None
            ),
        }
    return {
        "label_status": "provisional_fixture_only",
        "by_judge_family": by_family,
        "warning": "Fixture labels are diagnostic expectations; they are not substituted for qualified human labels.",
    }


def _pairwise_repeatability(outcomes: list[bool]) -> float | None:
    pairs = list(itertools.combinations(outcomes, 2))
    if not pairs:
        return None
    return sum(1 for left, right in pairs if left == right) / len(pairs)


def _repeatability(observations: list[dict]) -> dict:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for item in observations:
        key = (item["judge_id"], item["judge_family"], item["case_id"], item["writer_family"],
               item["variant_id"], item["transform_kind"])
        groups[key].append(item)
    rows: list[dict] = []
    for key, items in sorted(groups.items(), key=lambda entry: entry[0]):
        if len(items) < 2:
            continue
        outcomes = [item["caught"] for item in sorted(items, key=lambda row: row["trial_index"])]
        rows.append({
            "judge_id": key[0], "judge_family": key[1], "case_id": key[2],
            "writer_family": key[3], "variant_id": key[4], "transform_kind": key[5],
            "trials": len(items), "caught_values": outcomes,
            "pairwise_agreement": _pairwise_repeatability(outcomes),
        })
    return {
        "status": "measured" if rows else "insufficient_repeated_runs",
        "groups": rows,
        "note": "Agreement measures run-to-run stability only; it does not establish correctness.",
    }


def _behavioral_pairs(observations: list[dict], expectation: str) -> dict:
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for item in observations:
        group = item.get("invariance_group")
        if group:
            key = (item["judge_id"], item["case_id"], item["writer_family"], item["trial_index"], group)
            grouped[key].append(item)
    rows: list[dict] = []
    ambiguous = 0
    for key, items in sorted(grouped.items(), key=lambda entry: entry[0]):
        baselines = [item for item in items if item["behavioral_expectation"] == "baseline"]
        transformed = [item for item in items if item["behavioral_expectation"] == expectation]
        if not transformed:
            continue
        if len(baselines) != 1:
            ambiguous += 1
            continue
        base = baselines[0]
        for item in transformed:
            if expectation == "invariant":
                satisfied = item["caught"] == base["caught"]
            else:
                satisfied = (not base["caught"]) and item["caught"]
            rows.append({
                "judge_id": key[0], "case_id": key[1], "writer_family": key[2],
                "trial_index": key[3], "group": key[4], "baseline_variant": base["variant_id"],
                "variant": item["variant_id"], "transform_kind": item["transform_kind"],
                "baseline_caught": base["caught"], "transformed_caught": item["caught"],
                "expectation_satisfied": satisfied,
            })
    return {
        "status": "measured" if rows else "insufficient_matched_pairs",
        "matched_pairs": rows,
        "ambiguous_groups": ambiguous,
        "satisfaction_rate": (
            sum(1 for row in rows if row["expectation_satisfied"]) / len(rows) if rows else None
        ),
    }


def _human_consensus(manifest: dict, labels: list[dict]) -> dict:
    result: dict[str, dict] = {}
    for case in manifest["cases"]:
        expert = [item for item in labels if item["case_id"] == case["id"]
                  and item["annotator_role"] == "expert"]
        usable = [item for item in expert if item["label"] in {"defect", "control"}]
        counts = Counter(item["label"] for item in expert)
        if len(usable) < 2:
            status, consensus = "insufficient", None
        elif len({item["label"] for item in usable}) == 1:
            status, consensus = "agreed", usable[0]["label"]
        else:
            status, consensus = "disputed", None
        result[case["id"]] = {
            "status": status,
            "consensus": consensus,
            "expert_labels": dict(sorted(counts.items())),
            "labels": [
                {"annotator_id": item["annotator_id"], "role": item["annotator_role"],
                 "label": item["label"], "severity": item.get("severity"), "signals": item.get("signals", [])}
                for item in expert
            ],
        }
    return result


def _human_agreement(consensus: dict[str, dict], observations: list[dict]) -> dict:
    rows = [item for item in observations if consensus.get(item["case_id"], {}).get("status") == "agreed"]
    if not rows:
        return {"status": "insufficient_human_labels", "by_judge_family": {}}
    by_family: dict[str, dict] = {}
    for family in sorted({item["judge_family"] for item in rows}):
        family_rows = [item for item in rows if item["judge_family"] == family]
        matches = []
        for item in family_rows:
            expected = consensus[item["case_id"]]["consensus"] == "defect"
            matches.append(item["caught"] == expected)
        by_family[family] = {
            "observations": len(family_rows),
            "agreed_with_human_label": sum(matches),
            "agreement_rate": sum(matches) / len(matches),
        }
    return {"status": "measured", "by_judge_family": by_family}


def _family_matrix(manifest: dict, observations: list[dict]) -> dict:
    case_by_id = {case["id"]: case for case in manifest["cases"]}
    cells: dict[str, dict] = {}
    writer_families = sorted({item["writer_family"] for item in observations})
    judge_families = sorted({item["judge_family"] for item in observations})
    for writer in writer_families:
        for judge in judge_families:
            rows = [item for item in observations
                    if item["writer_family"] == writer and item["judge_family"] == judge]
            if not rows:
                continue
            correct = sum(
                item["caught"] == case_by_id[item["case_id"]]["expect_caught"] for item in rows
            )
            cells[f"{writer} -> {judge}"] = {
                "writer_family": writer,
                "judge_family": judge,
                "observations": len(rows),
                "provisional_correct": correct,
                "provisional_accuracy": correct / len(rows),
            }
    return {
        "status": (
            "crossed" if len(writer_families) >= 2 and len(judge_families) >= 2
            else "insufficient_crossed_families"
        ),
        "writer_families": writer_families,
        "judge_families": judge_families,
        "cells": cells,
        "note": "Crossed-family cells are descriptive; provider diversity is not treated as statistical independence.",
    }


def _error_overlap(manifest: dict, observations: list[dict]) -> dict:
    case_by_id = {case["id"]: case for case in manifest["cases"]}
    keyed: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for item in observations:
        key = (item["case_id"], item["writer_family"], item["trial_index"], item["variant_id"],
               item["transform_kind"])
        keyed[key][item["judge_family"]].append(item)
    families = sorted({item["judge_family"] for item in observations})
    rows: list[dict] = []
    for left, right in itertools.combinations(families, 2):
        both_wrong = one_wrong = both_correct = shared = ambiguous = 0
        for key, by_family in keyed.items():
            left_items, right_items = by_family.get(left, []), by_family.get(right, [])
            if not left_items or not right_items:
                continue
            if len(left_items) != 1 or len(right_items) != 1:
                ambiguous += 1
                continue
            shared += 1
            expected = case_by_id[key[0]]["expect_caught"]
            left_wrong = left_items[0]["caught"] != expected
            right_wrong = right_items[0]["caught"] != expected
            if left_wrong and right_wrong:
                both_wrong += 1
            elif left_wrong or right_wrong:
                one_wrong += 1
            else:
                both_correct += 1
        if shared or ambiguous:
            rows.append({
                "judge_families": [left, right], "shared_trials": shared,
                "both_wrong": both_wrong, "one_wrong": one_wrong, "both_correct": both_correct,
                "ambiguous_trials_skipped": ambiguous,
            })
    return {
        "status": "descriptive" if any(row["shared_trials"] for row in rows) else "insufficient_shared_trials",
        "pairs": rows,
        "note": "Joint provisional errors are reported directly; no independence or correlation claim is inferred from small counts.",
    }


def report(project: Path, study_id: str) -> dict:
    """Build a descriptive B2 calibration report without granting critic gate authority."""
    project = Path(project)
    try:
        manifest, study_errors = _load_study(project, study_id)
    except ValueError as exc:
        return {"error": str(exc)}
    if manifest is None:
        return {"error": "critic calibration study not found", "details": study_errors}
    observations, observation_errors = _validated_existing(
        _root(project, study_id) / "observations", "critic-calibration-observation", manifest
    )
    labels, label_errors = _validated_existing(
        _root(project, study_id) / "human-labels", "critic-human-label", manifest
    )
    integrity_errors = [*study_errors, *observation_errors, *label_errors]
    observation_keys = [
        (item["case_id"], item["judge_id"], item["writer_family"], item["trial_index"], item["variant_id"])
        for item in observations
    ]
    duplicate_observations = [key for key, count in Counter(observation_keys).items() if count > 1]
    if duplicate_observations:
        integrity_errors.append(f"duplicate critic observation keys: {duplicate_observations}")
    label_keys = [(item["case_id"], item["annotator_id"]) for item in labels]
    duplicate_labels = [key for key, count in Counter(label_keys).items() if count > 1]
    if duplicate_labels:
        integrity_errors.append(f"duplicate human label keys: {duplicate_labels}")
    if integrity_errors:
        return {
            "study_id": study_id,
            "evidence_status": "invalid",
            "integrity_errors": integrity_errors,
            "authority": "none",
        }

    consensus = _human_consensus(manifest, labels)
    current_corpus_sha = acceptance.sha256_bytes(
        critic_eval.CORPUS.read_bytes() if critic_eval.CORPUS.exists() else b""
    )
    return {
        "study_id": study_id,
        "name": manifest["name"],
        "evidence_status": "descriptive",
        "authority": "not_a_promotion_gate",
        "criteria": manifest["criteria"],
        "counts": {"cases": len(manifest["cases"]), "observations": len(observations), "human_labels": len(labels)},
        "source_corpus": {
            "frozen_sha256": manifest["source_corpus_sha256"],
            "current_sha256": current_corpus_sha,
            "changed_since_freeze": current_corpus_sha != manifest["source_corpus_sha256"],
        },
        "fixture_metrics": _fixture_metrics(manifest, observations),
        "repeatability": _repeatability(observations),
        "invariance": _behavioral_pairs(observations, "invariant"),
        "directional": _behavioral_pairs(observations, "directional_worse"),
        "crossed_families": _family_matrix(manifest, observations),
        "joint_error_evidence": _error_overlap(manifest, observations),
        "human_labels": consensus,
        "human_agreement": _human_agreement(consensus, observations),
        "open_evidence": {
            "priority": "insufficient unless qualified human severity/priority labels are collected and analyzed",
            "repair_benefit": "not measured by critic verdict runs; requires independently evaluated before/after repairs",
            "population_claim": "not supported by this descriptive report without an appropriate study design",
        },
    }
