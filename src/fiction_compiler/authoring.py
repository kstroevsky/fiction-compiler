"""Schema-aware authoring mutations for MCP and CLI clients.

The existing compiler tools are strong once a project, scene spec, state delta and candidate prose
already exist.  This module covers the missing authoring seam without exposing a generic filesystem
write primitive: every operation is confined to a known project artifact, validates what the
repository knows how to validate, and preserves accepted-scene/seed-canon immutability.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from . import acceptance, integrity, ontology, premise, schema
from .state import accepted_scene_ids, seed_state
from .workspace import PROJECTS, validate_leaf_filename, validate_scene_id


_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

PROJECT_ARTIFACTS: dict[str, tuple[str, str | None]] = {
    "project": ("brief/project.json", "project"),
    "creative_brief": ("brief/creative-brief.md", None),
    "contract_coverage": ("brief/contract-coverage.json", "contract-coverage"),
    "style_profile": ("planning/style-profile.json", None),
    "discourse_plan": ("planning/discourse-plan.json", None),
    "event_graph": ("planning/event-graph.json", None),
    "reader_disclosure": ("planning/reader-disclosure.json", "reader-disclosure"),
    "reader_probes": ("planning/reader-probes.json", "reader-probes"),
    "story_repertoire": ("planning/story-repertoire.json", "story-repertoire"),
    "ontology": ("canon/ontology.json", "ontology"),
    "entity_registry": ("canon/entity-registry.json", "entity-registry"),
    "canon_index": ("canon/index.json", None),
}

SEED_LEDGERS: dict[str, str] = {
    "facts": "facts.jsonl",
    "knowledge": "knowledge-state.jsonl",
    "beliefs": "belief-state.jsonl",
    "relationships": "relationship-state.jsonl",
    "world_state": "world-state.jsonl",
    "resources": "resources.jsonl",
    "promises": "promises.jsonl",
    "timeline": "timeline.jsonl",
    "propositions": "propositions.jsonl",
}

_CANON_INDEX_AUTHOR_FIELDS = {"world_rules", "locations", "objects", "factions"}
_PROJECT_ID_ARTIFACTS = {"contract_coverage", "reader_disclosure", "reader_probes", "story_repertoire"}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _jsonl_bytes(records: list[dict]) -> bytes:
    return b"".join(
        (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        for record in records
    )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_no}: expected a JSON object")
        rows.append(value)
    return rows


def _schema_guard(value: Any, schema_name: str, label: str) -> None:
    errors = schema.validate_named(value, schema_name, path=label)
    if errors:
        raise ValueError("; ".join(errors))


def _scene_is_accepted(project: Path, scene_id: str) -> bool:
    return scene_id in accepted_scene_ids(project) or acceptance.load_scene_snapshot(project, scene_id) is not None


def create_project(slug: str, project_data: dict | None = None, creative_brief: str | None = None,
                   *, projects_root: Path = PROJECTS) -> dict:
    """Create a project from the repository template and bind template project ids to ``slug``."""
    if not isinstance(slug, str) or _SLUG_RE.fullmatch(slug) is None:
        raise ValueError("slug must match [a-z0-9-]+")
    target = Path(projects_root) / slug
    if target.exists():
        raise ValueError(f"project already exists: {target}")

    if project_data is None:
        project_value = _read_json(PROJECTS / "_template" / "brief" / "project.json", {})
        project_value["id"] = slug
    else:
        project_value = dict(project_data)
        if project_value.get("id") not in (None, slug):
            raise ValueError(f"project id must equal slug {slug!r}")
        project_value["id"] = slug
    _schema_guard(project_value, "project", "$project_create.project_data")
    if creative_brief is not None and not isinstance(creative_brief, str):
        raise ValueError("creative_brief must be a string")

    source = PROJECTS / "_template"
    try:
        shutil.copytree(source, target)
        acceptance.atomic_write(target / "brief" / "project.json", _json_bytes(project_value))
        for rel in (
            "brief/contract-coverage.json",
            "planning/reader-disclosure.json",
            "planning/reader-probes.json",
            "planning/story-repertoire.json",
        ):
            path = target / rel
            value = _read_json(path, {})
            value["project_id"] = slug
            acceptance.atomic_write(path, _json_bytes(value))
        if creative_brief is not None:
            acceptance.atomic_write(
                target / "brief" / "creative-brief.md",
                (creative_brief.rstrip() + "\n").encode("utf-8"),
            )
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return project_overview(target)


def project_overview(project: Path) -> dict:
    """Return the author-facing project state without expanding candidate/manuscript prose."""
    project = Path(project)
    if not project.exists():
        raise ValueError(f"project does not exist: {project}")

    planning: dict[str, Any] = {}
    for name in (
        "style_profile", "discourse_plan", "event_graph", "reader_disclosure",
        "reader_probes", "story_repertoire",
    ):
        rel, _ = PROJECT_ARTIFACTS[name]
        planning[name] = _read_json(project / rel, {})

    characters = []
    for path in sorted((project / "canon" / "characters").glob("*.json")):
        characters.append(_read_json(path, {}))

    ledgers = {
        name: _read_jsonl(project / "canon" / filename)
        for name, filename in SEED_LEDGERS.items()
        if (project / "canon" / filename).exists()
    }

    accepted = set(accepted_scene_ids(project))
    scenes = []
    scene_root = project / "scenes"
    if scene_root.exists():
        for scene_dir in sorted(path for path in scene_root.iterdir() if path.is_dir()):
            candidate_dir = scene_dir / "candidates"
            candidates = []
            if candidate_dir.exists():
                for candidate in sorted(candidate_dir.glob("*.md")):
                    candidates.append({
                        "name": candidate.name,
                        "sha256": integrity.sha256_file(candidate),
                        "bytes": candidate.stat().st_size,
                    })
            scenes.append({
                "scene_id": scene_dir.name,
                "accepted": scene_dir.name in accepted,
                "spec": _read_json(scene_dir / "spec.json", None),
                "state_delta": _read_json(scene_dir / "state-delta.json", None),
                "candidates": candidates,
            })

    creative_path = project / "brief" / "creative-brief.md"
    return {
        "project": _read_json(project / "brief" / "project.json", {}),
        "creative_brief": creative_path.read_text(encoding="utf-8") if creative_path.exists() else "",
        "contract_coverage": _read_json(project / "brief" / "contract-coverage.json", {}),
        "planning": planning,
        "canon": {
            "index": _read_json(project / "canon" / "index.json", {}),
            "ontology": _read_json(project / "canon" / "ontology.json", None),
            "entity_registry": _read_json(project / "canon" / "entity-registry.json", None),
            "characters": characters,
            "seed_ledgers": ledgers,
        },
        "scenes": scenes,
    }


def premise_report(candidates: list[dict], profile: str = "core") -> dict:
    return premise.probe_report(candidates, profile=profile)


def write_project_artifact(project: Path, artifact: str, value: Any) -> dict:
    """Write one known project artifact, validating schema/identity and protected canon fields."""
    project = Path(project)
    if artifact not in PROJECT_ARTIFACTS:
        raise ValueError(f"unknown project artifact {artifact!r}")
    rel, schema_name = PROJECT_ARTIFACTS[artifact]
    path = project / rel

    if artifact == "creative_brief":
        if not isinstance(value, str):
            raise ValueError("creative_brief value must be a string")
        acceptance.atomic_write(path, (value.rstrip() + "\n").encode("utf-8"))
        return {"artifact": artifact, "path": str(path), "bytes": path.stat().st_size}

    if not isinstance(value, dict):
        raise ValueError(f"{artifact} value must be an object")

    if artifact == "canon_index":
        unknown = set(value) - _CANON_INDEX_AUTHOR_FIELDS
        if unknown:
            raise ValueError(
                "canon_index authoring may only set world_rules, locations, objects, factions; "
                f"protected fields: {sorted(unknown)}"
            )
        for key, items in value.items():
            if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
                raise ValueError(f"canon_index.{key} must be an array of strings")
        merged = _read_json(path, {})
        merged.update(value)
        value = merged
    else:
        if schema_name is not None:
            _schema_guard(value, schema_name, f"${artifact}")
        if artifact == "project" and value.get("id") != project.name:
            raise ValueError(f"project id must equal directory name {project.name!r}")
        if artifact in _PROJECT_ID_ARTIFACTS and value.get("project_id") != project.name:
            raise ValueError(f"{artifact}.project_id must equal directory name {project.name!r}")
        if artifact == "event_graph":
            events = value.get("events")
            edges = value.get("edges")
            if not isinstance(events, list) or not isinstance(edges, list):
                raise ValueError("event_graph requires array fields 'events' and 'edges'")
            ids: list[str] = []
            for index, event in enumerate(events):
                _schema_guard(event, "event", f"$event_graph.events[{index}]")
                ids.append(str(event.get("id")))
            if len(ids) != len(set(ids)):
                raise ValueError("event_graph event ids must be unique")
        if artifact == "ontology":
            semantic = ontology.ontology_definition_errors(value)
            if semantic:
                raise ValueError("; ".join(semantic))
        if artifact == "entity_registry":
            semantic = ontology.entity_registry_errors(value)
            if semantic:
                raise ValueError("; ".join(semantic))

    acceptance.atomic_write(path, _json_bytes(value))
    return {"artifact": artifact, "path": str(path), "value": value}


def write_seed_ledger(project: Path, ledger: str, records: list[dict]) -> dict:
    """Replace one seed ledger before any scene is accepted; rollback on state-loader failure."""
    project = Path(project)
    if ledger not in SEED_LEDGERS:
        raise ValueError(f"unknown seed ledger {ledger!r}")
    if accepted_scene_ids(project):
        raise ValueError("seed canon is immutable after the first accepted scene")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("records must be an array of objects")
    path = project / "canon" / SEED_LEDGERS[ledger]
    previous = path.read_bytes() if path.exists() else None
    acceptance.atomic_write(path, _jsonl_bytes(records))
    try:
        seed_state(project)
    except Exception:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            acceptance.atomic_write(path, previous)
        raise
    return {
        "ledger": ledger,
        "path": str(path),
        "records": len(records),
        "seed_hash": integrity.seed_hash(project),
    }


def write_character(project: Path, character: dict, *, overwrite: bool = False) -> dict:
    project = Path(project)
    _schema_guard(character, "character", "$character")
    char_id = str(character["id"])
    filename = validate_leaf_filename(f"{char_id}.json", ".json")
    path = project / "canon" / "characters" / filename
    if path.exists() and not overwrite:
        raise ValueError(f"character already exists: {char_id}")
    if path.exists() and accepted_scene_ids(project):
        raise ValueError("existing character sheets are immutable after scenes have been accepted")
    acceptance.atomic_write(path, _json_bytes(character))

    index_path = project / "canon" / "index.json"
    index = _read_json(index_path, {})
    characters = list(index.get("characters", []))
    if char_id not in characters:
        characters.append(char_id)
        index["characters"] = characters
        acceptance.atomic_write(index_path, _json_bytes(index))
    return {"character": character, "path": str(path)}


def write_scene_spec(project: Path, scene_id: str, spec: dict, *, overwrite: bool = False) -> dict:
    project = Path(project)
    validate_scene_id(scene_id)
    if spec.get("id") != scene_id:
        raise ValueError("scene spec id must match scene_id")
    _schema_guard(spec, "scene", "$scene_spec")
    if _scene_is_accepted(project, scene_id):
        raise ValueError("accepted scene specs are immutable; use the backward-revision workflow")
    scene = project / "scenes" / scene_id
    path = scene / "spec.json"
    if path.exists() and not overwrite:
        raise ValueError(f"scene spec already exists: {scene_id}")
    (scene / "candidates").mkdir(parents=True, exist_ok=True)
    (scene / "critiques").mkdir(parents=True, exist_ok=True)
    acceptance.atomic_write(path, _json_bytes(spec))
    return {"scene_id": scene_id, "path": str(path), "spec": spec}


def write_state_delta(project: Path, scene_id: str, delta: dict, *, overwrite: bool = False) -> dict:
    project = Path(project)
    validate_scene_id(scene_id)
    if delta.get("scene_id") != scene_id:
        raise ValueError("state delta scene_id must match scene_id")
    _schema_guard(delta, "state-delta", "$state_delta")
    if _scene_is_accepted(project, scene_id):
        raise ValueError("accepted state deltas are immutable; use the backward-revision workflow")
    scene = project / "scenes" / scene_id
    if not (scene / "spec.json").exists():
        raise ValueError("write a valid scene spec before its state delta")
    path = scene / "state-delta.json"
    if path.exists() and not overwrite:
        raise ValueError(f"state delta already exists: {scene_id}")
    acceptance.atomic_write(path, _json_bytes(delta))
    return {"scene_id": scene_id, "path": str(path), "state_delta": delta}


def write_candidate(project: Path, scene_id: str, filename: str, text: str) -> dict:
    """Persist a new prose branch. Existing candidates are never overwritten."""
    project = Path(project)
    validate_scene_id(scene_id)
    filename = validate_leaf_filename(filename, ".md")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("candidate text must be a non-empty string")
    scene = project / "scenes" / scene_id
    if not (scene / "spec.json").exists():
        raise ValueError("write a valid scene spec before drafting candidates")
    path = scene / "candidates" / filename
    if path.exists():
        raise ValueError(
            f"candidate already exists: {filename}; write revisions under a new filename to preserve branches"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    acceptance.atomic_write(path, (text.rstrip() + "\n").encode("utf-8"))
    return {
        "scene_id": scene_id,
        "candidate": filename,
        "path": str(path),
        "sha256": integrity.sha256_file(path),
        "bytes": path.stat().st_size,
        "words": len(path.read_text(encoding="utf-8").split()),
    }


def get_candidate(project: Path, scene_id: str, candidate: str) -> dict:
    project = Path(project)
    validate_scene_id(scene_id)
    candidate = validate_leaf_filename(candidate, ".md")
    path = project / "scenes" / scene_id / "candidates" / candidate
    if not path.exists():
        raise ValueError(f"candidate does not exist: {candidate}")
    text = path.read_text(encoding="utf-8")
    return {
        "scene_id": scene_id,
        "candidate": candidate,
        "sha256": integrity.sha256_file(path),
        "text": text,
        "words": len(text.split()),
    }
