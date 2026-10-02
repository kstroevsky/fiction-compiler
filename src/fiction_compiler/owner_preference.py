"""Owner-taste evidence kept separate from general-reader evaluation.

Choices live in the project decision record with exact alternative snapshots.  Critic calibration
uses a packet that omits the owner's selected alternative and reason, then stores packet-bound
predictions under ``.runs``.  Agreement is descriptive; it is not a claim about general literary
quality or target-audience preference.
"""
from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import acceptance, schema


DECISION_KINDS = {"premise", "ending", "plan", "candidate", "revision", "other"}
_PREFERENCE_ID_RE = re.compile(r"^pref-[0-9a-f]{32}$")
_CRITIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _records_dir(project: Path) -> Path:
    return Path(project) / "decisions" / "preferences" / "records"


def _artifacts_dir(project: Path) -> Path:
    return Path(project) / "decisions" / "preferences" / "artifacts"


def _predictions_dir(project: Path, preference_id: str) -> Path:
    return Path(project) / ".runs" / "owner-preference-calibration" / preference_id / "predictions"


def _project_id(project: Path) -> str:
    path = Path(project) / "brief" / "project.json"
    if not path.exists():
        return Path(project).name
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("id", Path(project).name)


def _load_record(project: Path, preference_id: str) -> tuple[dict | None, str | None, bytes | None]:
    if not isinstance(preference_id, str) or _PREFERENCE_ID_RE.fullmatch(preference_id) is None:
        return None, "invalid preference_id", None
    path = _records_dir(project) / f"{preference_id}.json"
    if not path.exists():
        return None, "owner preference not found", None
    raw = path.read_bytes()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"owner preference is unreadable: {exc}", raw
    errors = schema.validate_named(record, "owner-preference")
    if record.get("preference_id") != preference_id:
        errors.append("preference_id does not match record filename")
    if record.get("project_id") != _project_id(project):
        errors.append("preference project_id does not match project")
    ids = [item.get("id") for item in record.get("alternatives", []) if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append("alternative ids must be unique")
    if record.get("chosen_id") not in ids:
        errors.append("chosen_id is not one of the frozen alternatives")
    for alternative in record.get("alternatives", []):
        if not isinstance(alternative, dict):
            continue
        snapshot = (Path(project) / alternative.get("snapshot", "")).resolve()
        root = _artifacts_dir(project).resolve()
        if not snapshot.is_relative_to(root) or not snapshot.exists():
            errors.append(f"alternative {alternative.get('id')!r} snapshot is missing/outside preference artifacts")
            continue
        if acceptance.sha256_bytes(snapshot.read_bytes()) != alternative.get("sha256"):
            errors.append(f"alternative {alternative.get('id')!r} snapshot hash changed")
    return record, "; ".join(errors) if errors else None, raw


def _freeze_alternative(project: Path, alternative: dict) -> tuple[dict | None, str | None]:
    if not isinstance(alternative, dict):
        return None, "each alternative must be an object"
    alternative_id = alternative.get("id")
    if not isinstance(alternative_id, str) or not alternative_id or len(alternative_id) > 64:
        return None, "alternative id must be a non-empty slug of at most 64 characters"
    if any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in alternative_id) or not alternative_id[0].isalnum():
        return None, f"invalid alternative id {alternative_id!r}"
    has_text = isinstance(alternative.get("text"), str)
    has_path = isinstance(alternative.get("path"), str)
    if has_text == has_path:
        return None, f"alternative {alternative_id!r} must provide exactly one of text or path"
    source_path = None
    if has_text:
        data = alternative["text"].encode("utf-8")
        source_kind = "inline_text"
    else:
        raw = Path(alternative["path"])
        candidate = raw if raw.is_absolute() else Path(project) / raw
        resolved = candidate.resolve()
        if not resolved.is_relative_to(Path(project).resolve()):
            return None, f"alternative {alternative_id!r} path escapes project"
        if not resolved.is_file():
            return None, f"alternative {alternative_id!r} path does not exist"
        data = resolved.read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return None, f"alternative {alternative_id!r} must be UTF-8 text"
        source_kind = "project_file"
        source_path = str(resolved.relative_to(Path(project).resolve()))
    digest = acceptance.sha256_bytes(data)
    snapshot = _artifacts_dir(project) / f"{digest}.txt"
    if snapshot.exists() and snapshot.read_bytes() != data:
        return None, f"content-addressed preference artifact collision at {snapshot}"
    if not snapshot.exists():
        acceptance.atomic_write(snapshot, data)
    result = {
        "id": alternative_id,
        "sha256": digest,
        "snapshot": str(snapshot.relative_to(project)),
        "source_kind": source_kind,
    }
    if isinstance(alternative.get("label"), str) and alternative["label"]:
        result["label"] = alternative["label"]
    if source_path is not None:
        result["source_path"] = source_path
    return result, None


def record_choice(project: Path, decision_kind: str, alternatives: list[dict], chosen_id: str,
                  reason: str, decided_at: str, metadata: dict | None = None) -> dict:
    """Persist one immutable owner choice with exact snapshots of every shown alternative."""
    project = Path(project)
    if decision_kind not in DECISION_KINDS:
        return {"error": f"decision_kind must be one of {sorted(DECISION_KINDS)}"}
    if not isinstance(alternatives, list) or len(alternatives) < 2:
        return {"error": "owner preference needs at least two alternatives"}
    if not isinstance(reason, str) or not reason.strip():
        return {"error": "reason must be a non-empty string"}
    if not isinstance(decided_at, str) or not decided_at.strip():
        return {"error": "decided_at must be a non-empty timestamp/date string"}
    if metadata is not None and not isinstance(metadata, dict):
        return {"error": "metadata must be an object"}
    raw_ids: list[str] = []
    for alternative in alternatives:
        if not isinstance(alternative, dict):
            return {"error": "each alternative must be an object"}
        alternative_id = alternative.get("id")
        if (not isinstance(alternative_id, str) or not alternative_id or len(alternative_id) > 64
                or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in alternative_id)
                or not alternative_id[0].isalnum()):
            return {"error": f"invalid alternative id {alternative_id!r}"}
        raw_ids.append(alternative_id)
    if len(raw_ids) != len(set(raw_ids)):
        return {"error": "alternative ids must be unique"}
    if chosen_id not in raw_ids:
        return {"error": "chosen_id must name one of the alternatives"}
    frozen: list[dict] = []
    for alternative in alternatives:
        item, error = _freeze_alternative(project, alternative)
        if error:
            return {"error": error}
        assert item is not None
        frozen.append(item)
    preference_id = f"pref-{uuid.uuid4().hex}"
    record = {
        "schema_version": 1,
        "preference_id": preference_id,
        "project_id": _project_id(project),
        "decision_kind": decision_kind,
        "alternatives": frozen,
        "chosen_id": chosen_id,
        "reason": reason.strip(),
        "decided_at": decided_at,
        "recorded_at": _now(),
        **({"metadata": metadata} if metadata is not None else {}),
    }
    errors = schema.validate_named(record, "owner-preference")
    if errors:
        return {"error": "; ".join(errors)}
    path = _records_dir(project) / f"{preference_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"status": "recorded", "preference_id": preference_id,
            "path": str(path.relative_to(project)), "alternative_count": len(frozen)}


def packet(project: Path, preference_id: str) -> dict:
    """Return exact alternatives while withholding the owner's choice and stated reason."""
    project = Path(project)
    record, error, raw = _load_record(project, preference_id)
    if error or record is None or raw is None:
        return {"error": error or "owner preference not found"}
    alternatives = []
    for item in record["alternatives"]:
        text = (project / item["snapshot"]).read_text(encoding="utf-8")
        alternatives.append({"id": item["id"], "text": text,
                             **({"label": item["label"]} if item.get("label") else {})})
    payload = {
        "preference_id": preference_id,
        "project_id": record["project_id"],
        "decision_kind": record["decision_kind"],
        "alternatives": alternatives,
        "preference_sha256": acceptance.sha256_bytes(raw),
    }
    payload["packet_sha256"] = acceptance.sha256_bytes(acceptance.canonical_json_bytes(payload))
    return payload


def record_prediction(project: Path, preference_id: str, critic: str, packet_sha256: str,
                      predicted_id: str | None, provenance: dict | None = None) -> dict:
    """Persist one critic prediction bound to the exact choice-hidden packet."""
    project = Path(project)
    current = packet(project, preference_id)
    if "error" in current:
        return current
    if packet_sha256 != current["packet_sha256"]:
        return {"error": "packet_sha256 is stale or does not match the choice-hidden packet"}
    if not isinstance(critic, str) or _CRITIC_RE.fullmatch(critic) is None:
        return {"error": "critic must be a lowercase slug"}
    alternative_ids = {item["id"] for item in current["alternatives"]}
    if predicted_id is not None and predicted_id not in alternative_ids:
        return {"error": "predicted_id must name an alternative or be omitted to abstain"}
    if provenance is not None and not isinstance(provenance, dict):
        return {"error": "provenance must be an object"}
    predictions_dir = _predictions_dir(project, preference_id)
    for existing_path in sorted(predictions_dir.glob("*.json")):
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return {"error": f"existing prediction evidence is unreadable: {existing_path.name}: {exc}"}
        if existing.get("critic") == critic:
            return {"error": f"critic {critic!r} already predicted this owner preference"}
    prediction_id = f"prediction-{uuid.uuid4().hex}"
    record = {
        "schema_version": 1,
        "prediction_id": prediction_id,
        "preference_id": preference_id,
        "preference_sha256": current["preference_sha256"],
        "packet_sha256": packet_sha256,
        "project_id": current["project_id"],
        "critic": critic,
        "prediction": ({"kind": "pick", "alternative_id": predicted_id}
                       if predicted_id is not None else {"kind": "abstain"}),
        **({"provenance": provenance} if provenance is not None else {}),
        "recorded_at": _now(),
    }
    errors = schema.validate_named(record, "owner-preference-prediction")
    if errors:
        return {"error": "; ".join(errors)}
    path = predictions_dir / f"{prediction_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"status": "recorded", "prediction_id": prediction_id,
            "path": str(path.relative_to(project))}


def report(project: Path) -> dict:
    """Describe critic agreement with recorded owner choices without audience-quality claims."""
    project = Path(project)
    preferences: list[dict] = []
    errors: list[str] = []
    for path in sorted(_records_dir(project).glob("*.json")):
        record, error, raw = _load_record(project, path.stem)
        if error or record is None or raw is None:
            errors.append(f"{path.name}: {error or 'invalid record'}")
            continue
        preference_sha = acceptance.sha256_bytes(raw)
        predictions: list[dict] = []
        for prediction_path in sorted(_predictions_dir(project, record["preference_id"]).glob("*.json")):
            try:
                prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"{prediction_path.name}: unreadable prediction ({exc})")
                continue
            problems = schema.validate_named(prediction, "owner-preference-prediction")
            if prediction.get("prediction_id") != prediction_path.stem:
                problems.append("prediction_id does not match record filename")
            if prediction.get("preference_id") != record["preference_id"]:
                problems.append("preference_id does not match prediction directory")
            current_packet = packet(project, record["preference_id"])
            if prediction.get("preference_sha256") != preference_sha:
                problems.append("preference_sha256 is stale")
            if prediction.get("packet_sha256") != current_packet.get("packet_sha256"):
                problems.append("packet_sha256 is stale")
            if prediction.get("project_id") != record["project_id"]:
                problems.append("project_id does not match preference")
            pick = prediction.get("prediction", {})
            if pick.get("kind") == "pick" and pick.get("alternative_id") not in {
                item["id"] for item in record["alternatives"]
            }:
                problems.append("prediction names an unknown alternative")
            if problems:
                errors.append(f"{prediction_path.name}: {'; '.join(problems)}")
                continue
            predictions.append(prediction)
        preferences.append({"record": record, "predictions": predictions})

    by_critic: dict[str, dict] = defaultdict(lambda: {"records": 0, "picks": 0, "correct": 0, "abstentions": 0})
    prediction_count = 0
    for item in preferences:
        chosen = item["record"]["chosen_id"]
        for prediction in item["predictions"]:
            prediction_count += 1
            row = by_critic[prediction["critic"]]
            row["records"] += 1
            if prediction["prediction"]["kind"] == "abstain":
                row["abstentions"] += 1
                continue
            row["picks"] += 1
            if prediction["prediction"]["alternative_id"] == chosen:
                row["correct"] += 1
    critics = {}
    for critic, values in sorted(by_critic.items()):
        critics[critic] = {
            **values,
            "agreement_among_picks": (values["correct"] / values["picks"] if values["picks"] else None),
        }
    return {
        "status": "valid" if not errors else "invalid",
        "project_id": _project_id(project),
        "preference_records": len(preferences),
        "prediction_records": prediction_count,
        "critics": critics,
        "errors": errors,
        "evidence_status": (
            "no_owner_preferences_recorded" if not preferences else
            "owner_choices_without_critic_predictions" if not prediction_count else
            "descriptive_agreement_available"
        ),
        "note": (
            "Agreement estimates critic ability to predict this owner's recorded choices only. It is "
            "not target-reader preference, general literary quality, or a powered population estimate."
        ),
    }


def persistent_validation_errors(project: Path) -> list[str]:
    """Validate durable owner-choice records and their content-addressed alternative snapshots."""
    project = Path(project)
    errors: list[str] = []
    for path in sorted(_records_dir(project).glob("*.json")):
        _, error, _ = _load_record(project, path.stem)
        if error:
            errors.append(f"{path.name}: {error}")
    return errors
