"""Rights-bound public-domain literature controls for false positives and representation limits.

Controls live outside projects because they are evaluation material, not canon. Exact source bytes are
hash-bound, story-format limitations are explicitly manual annotations, and absent live critic evidence
stays absent rather than being inferred from a work's reputation.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from . import acceptance, defaultness, schema
from .workspace import KB


CONTROL_ROOT = KB / "corpus-controls"
SOURCE_REGISTER = KB / "source-register.json"
_CONTROL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SCENE_FILE_RE = re.compile(r"^scene-[0-9]{2}\.txt$")
_SPEC_FILE_RE = re.compile(r"^scene-[0-9]{2}\.spec\.json$")
_DELTA_FILE_RE = re.compile(r"^scene-[0-9]{2}\.delta\.json$")


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _source_by_id(source_register_path: Path, source_id: str) -> dict | None:
    data = _load_json(source_register_path)
    for source in data.get("sources", []):
        if isinstance(source, dict) and source.get("id") == source_id:
            return source
    return None


def _control_dir(controls_root: Path, control_id: str) -> Path:
    if not isinstance(control_id, str) or _CONTROL_ID_RE.fullmatch(control_id) is None:
        raise ValueError(f"invalid literature control id {control_id!r}")
    return Path(controls_root) / control_id


def _bound_json_artifact_errors(
    control_dir: Path,
    rel: object,
    expected_hash: object,
    filename_re: re.Pattern[str],
    schema_name: str,
    label: str,
) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if not isinstance(rel, str) or filename_re.fullmatch(rel) is None:
        return None, [f"{label} has an invalid path"]
    path = (control_dir / rel).resolve()
    if not path.is_relative_to(control_dir.resolve()):
        return None, [f"{label} path escapes the control directory"]
    if not path.is_file():
        return None, [f"{label} is missing"]
    raw = path.read_bytes()
    if acceptance.sha256_bytes(raw) != expected_hash:
        errors.append(f"{label} content hash changed")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, errors + [f"{label} is unreadable: {exc}"]
    if not isinstance(value, dict):
        return None, errors + [f"{label} is not a JSON object"]
    errors.extend(f"{label}: {message}" for message in schema.validate_named(value, schema_name))
    return value, errors


def _load_and_validate(
    control_id: str,
    controls_root: Path = CONTROL_ROOT,
    source_register_path: Path = SOURCE_REGISTER,
) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    try:
        control_dir = _control_dir(Path(controls_root), control_id)
    except ValueError as exc:
        return None, [str(exc)]
    manifest_path = control_dir / "control.json"
    if not manifest_path.exists():
        return None, [f"literature control {control_id!r} has no control.json"]
    try:
        manifest = _load_json(manifest_path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"control.json is unreadable: {exc}"]

    errors.extend(schema.validate_named(manifest, "literature-control"))
    if manifest.get("control_id") != control_id:
        errors.append("control_id does not match control directory")

    source_id = manifest.get("source_id")
    try:
        source = _source_by_id(Path(source_register_path), source_id)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        source = None
        errors.append(f"source register is unreadable: {exc}")
    if source is None:
        errors.append(f"source_id {source_id!r} is not registered")
    else:
        if source.get("stream") != "fiction-corpus":
            errors.append("literature control source must use the fiction-corpus stream")
        rights = source.get("rights") if isinstance(source.get("rights"), dict) else {}
        if rights.get("eu_de_status") not in {"cleared", "repository-owned"}:
            errors.append("literature control source is not cleared for EU/DE full-text use")
        if rights.get("full_text_policy") != "allowed":
            errors.append("literature control source does not allow full-text use")
        if not rights.get("verified_on"):
            errors.append("literature control source lacks a rights verification date")

    scene_ids: list[str] = []
    scene_paths: list[str] = []
    format_scene_ids: list[str] = []
    raw_scenes: list[bytes] = []
    root = control_dir.resolve()
    scenes = manifest.get("scenes", []) if isinstance(manifest.get("scenes"), list) else []
    for item in scenes:
        if not isinstance(item, dict):
            continue
        scene_id = item.get("id")
        rel = item.get("path")
        if isinstance(scene_id, str):
            scene_ids.append(scene_id)
        if not isinstance(rel, str) or _SCENE_FILE_RE.fullmatch(rel) is None:
            errors.append(f"scene {scene_id!r} has an invalid control text path")
            continue
        scene_paths.append(rel)
        path = (control_dir / rel).resolve()
        if not path.is_relative_to(root):
            errors.append(f"scene {scene_id!r} path escapes the control directory")
            continue
        if not path.is_file():
            errors.append(f"scene {scene_id!r} text is missing")
            continue
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"scene {scene_id!r} text is not UTF-8")
            continue
        if not raw:
            errors.append(f"scene {scene_id!r} text is empty")
            continue
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
            errors.append(
                f"scene {scene_id!r} text must end with exactly one newline for canonical reassembly"
            )
        if acceptance.sha256_bytes(raw) != item.get("sha256"):
            errors.append(f"scene {scene_id!r} content hash changed")
        raw_scenes.append(raw)

        probe = item.get("format_probe") if isinstance(item.get("format_probe"), dict) else {}
        expected_prefix = rel[:-4]
        if probe.get("spec_path") != f"{expected_prefix}.spec.json":
            errors.append(f"scene {scene_id!r} spec probe does not correspond to its text segment")
        if probe.get("delta_path") != f"{expected_prefix}.delta.json":
            errors.append(f"scene {scene_id!r} delta probe does not correspond to its text segment")
        format_scene_id = probe.get("scene_id")
        if isinstance(format_scene_id, str):
            format_scene_ids.append(format_scene_id)
        spec, spec_errors = _bound_json_artifact_errors(
            control_dir, probe.get("spec_path"), probe.get("spec_sha256"), _SPEC_FILE_RE,
            "scene", f"scene {scene_id!r} spec probe",
        )
        delta, delta_errors = _bound_json_artifact_errors(
            control_dir, probe.get("delta_path"), probe.get("delta_sha256"), _DELTA_FILE_RE,
            "state-delta", f"scene {scene_id!r} delta probe",
        )
        errors.extend(spec_errors)
        errors.extend(delta_errors)
        if spec is not None and spec.get("id") != format_scene_id:
            errors.append(f"scene {scene_id!r} spec id does not match format_probe.scene_id")
        if delta is not None and delta.get("scene_id") != format_scene_id:
            errors.append(f"scene {scene_id!r} delta id does not match format_probe.scene_id")
    if len(scene_ids) != len(set(scene_ids)):
        errors.append("literature control scene ids must be unique")
    if len(scene_paths) != len(set(scene_paths)):
        errors.append("literature control scene paths must be unique")
    if len(format_scene_ids) != len(set(format_scene_ids)):
        errors.append("literature control format-probe scene ids must be unique")
    if len(raw_scenes) == len(scenes):
        actual_story_hash = acceptance.sha256_bytes(b"\n".join(raw_scenes))
        if actual_story_hash != manifest.get("full_story_sha256"):
            errors.append("full_story_sha256 does not match concatenated control scenes")
    return manifest, errors


def validation_errors(
    control_id: str,
    controls_root: Path = CONTROL_ROOT,
    source_register_path: Path = SOURCE_REGISTER,
) -> list[str]:
    """Return integrity/rights/schema errors for one control without running literary judgment."""
    _, errors = _load_and_validate(control_id, controls_root, source_register_path)
    return errors


def workspace_validation_errors(
    controls_root: Path = CONTROL_ROOT,
    source_register_path: Path = SOURCE_REGISTER,
) -> list[str]:
    """Validate every declared control directory for workspace verification."""
    root = Path(controls_root)
    if not root.exists():
        return []
    errors: list[str] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        if _CONTROL_ID_RE.fullmatch(directory.name) is None:
            errors.append(f"invalid literature control directory name {directory.name!r}")
            continue
        for error in validation_errors(directory.name, root, source_register_path):
            errors.append(f"{directory.name}: {error}")
    return errors


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def report(
    control_id: str,
    controls_root: Path = CONTROL_ROOT,
    source_register_path: Path = SOURCE_REGISTER,
) -> dict:
    """Run deterministic lint and expose manual representation limits for a frozen control."""
    manifest, errors = _load_and_validate(control_id, controls_root, source_register_path)
    if manifest is None:
        return {"status": "invalid", "control_id": control_id, "errors": errors}
    if errors:
        return {"status": "invalid", "control_id": control_id, "errors": errors}

    control_dir = _control_dir(Path(controls_root), control_id)
    scene_reports: list[dict] = []
    total_findings = 0
    blocking_scenes: list[str] = []
    for item in manifest["scenes"]:
        path = control_dir / item["path"]
        text = path.read_text(encoding="utf-8")
        lint = defaultness.lint_file(path)
        severity_counts = Counter(finding["severity"] for finding in lint["findings"])
        dimension_counts = Counter(finding["dimension"] for finding in lint["findings"])
        total_findings += len(lint["findings"])
        if lint["verdict"] != "pass":
            blocking_scenes.append(item["id"])
        scene_reports.append({
            "scene_id": item["id"],
            "path": item["path"],
            "sha256": item["sha256"],
            "word_count": _word_count(text),
            "defaultness": {
                "verdict": lint["verdict"],
                "finding_count": len(lint["findings"]),
                "by_severity": dict(sorted(severity_counts.items())),
                "by_dimension": dict(sorted(dimension_counts.items())),
                "findings": lint["findings"],
            },
            "story_format": {
                "evidence_kind": "manual_annotation",
                **item["representation"],
            },
            "format_probe": {
                "evidence_kind": "schema_validation",
                "scene_id": item["format_probe"]["scene_id"],
                "spec_path": item["format_probe"]["spec_path"],
                "delta_path": item["format_probe"]["delta_path"],
                "schema_status": "valid",
                "note": (
                    "Schema-valid means these analyst-authored spec/delta artifacts fit the current "
                    "JSON shapes. It does not prove the typed model preserves every literary effect."
                ),
            },
            "boundary_note": item["boundary_note"],
        })

    return {
        "status": "valid",
        "control_id": control_id,
        "source_id": manifest["source_id"],
        "full_story_sha256": manifest["full_story_sha256"],
        "segmentation": manifest["segmentation"],
        "deterministic_lint": {
            "scene_count": len(scene_reports),
            "total_findings": total_findings,
            "blocking_scene_ids": blocking_scenes,
            "note": (
                "Defaultness findings are heuristic evidence. Under the current gate only material/fatal "
                "findings make the linter verdict revise; a minor hit is not a proof of defective prose."
            ),
        },
        "scenes": scene_reports,
        "critic_evidence": manifest["critic_evidence"],
        "evidence_status": "deterministic_only_critics_unrun",
        "control_note": manifest["control_note"],
    }
