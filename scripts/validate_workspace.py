#!/usr/bin/env python3
"""Structural + schema validation for the whole workspace.

Every JSON artifact must parse; every typed artifact (project, character, scene,
event, state-delta, critique) must validate against its schema in ``schemas/``;
and a handful of cross-file invariants must hold (ids match directory names, no
duplicate ids, a promoted scene has a recorded state delta). This is the cheap
gate that runs before any expensive work — if it fails, nothing downstream is
trustworthy.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import integrity, schema  # noqa: E402


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON {path.relative_to(ROOT)}: {exc}") from exc


def check_schema(errors: list[str], path: Path, instance: Any, name: str) -> None:
    rel = path.relative_to(ROOT)
    for message in schema.validate_named(instance, name, path=str(rel)):
        errors.append(f"{name} schema: {message}")


def validate_json_files(errors: list[str]) -> None:
    for path in ROOT.rglob("*.json"):
        if any(part in {".git", ".runs"} for part in path.parts):
            continue
        try:
            read_json(path)
        except ValueError as exc:
            errors.append(str(exc))


def validate_characters(errors: list[str], project: Path) -> None:
    for path in sorted((project / "canon" / "characters").glob("*.json")):
        check_schema(errors, path, read_json(path), "character")


def validate_event_graph(errors: list[str], project: Path) -> None:
    graph_path = project / "planning" / "event-graph.json"
    if not graph_path.exists():
        return
    graph = read_json(graph_path)
    for event in graph.get("events", []):
        check_schema(errors, graph_path, event, "event")


def validate_scenes(errors: list[str], project: Path) -> list[str]:
    scene_ids: list[str] = []
    scene_root = project / "scenes"
    if not scene_root.exists():
        return scene_ids
    for scene_dir in sorted(scene_root.iterdir()):
        if not scene_dir.is_dir():
            continue
        spec = scene_dir / "spec.json"
        if not spec.exists():
            errors.append(f"{project.name}/{scene_dir.name}: missing spec.json")
            continue
        scene = read_json(spec)
        check_schema(errors, spec, scene, "scene")
        scene_id = scene.get("id")
        scene_ids.append(scene_id)
        if scene_id != scene_dir.name:
            errors.append(f"{project.name}/{scene_dir.name}: scene id does not match directory")

        delta_path = scene_dir / "state-delta.json"
        if delta_path.exists():
            check_schema(errors, delta_path, read_json(delta_path), "state-delta")

        for critique in sorted((scene_dir / "critiques").glob("*.json")):
            check_schema(errors, critique, read_json(critique), "critique")

        manuscript = project / "manuscript" / "chapters" / f"{scene_dir.name}.md"
        if manuscript.exists() and not delta_path.exists():
            errors.append(f"{project.name}/{scene_dir.name}: promoted scene lacks state-delta.json")

    duplicates = [item for item, count in Counter(scene_ids).items() if count > 1]
    if duplicates:
        errors.append(f"{project.name}: duplicate scene ids: {duplicates}")
    return scene_ids


def validate_projects(errors: list[str]) -> None:
    projects = ROOT / "projects"
    if not projects.exists():
        return
    for project in sorted(projects.iterdir()):
        if not project.is_dir() or project.name.startswith("_"):
            continue
        project_file = project / "brief" / "project.json"
        if not project_file.exists():
            errors.append(f"{project.name}: missing brief/project.json")
            continue
        data = read_json(project_file)
        check_schema(errors, project_file, data, "project")
        if data.get("id") != project.name:
            errors.append(f"{project.name}: project id must equal directory name")

        ontology_path = project / "canon" / "ontology.json"
        if ontology_path.exists():
            check_schema(errors, ontology_path, read_json(ontology_path), "ontology")

        validate_characters(errors, project)
        validate_event_graph(errors, project)
        validate_scenes(errors, project)
        # Tamper-evidence: any manifest-bearing accepted delta edited since promotion fails here.
        # Legacy scenes (promoted before ADR 0003, no manifest) are skipped, not failed.
        for message in integrity.verify_canon(project):
            errors.append(f"{project.name}: canon integrity — {message}")


def validate_source_register(errors: list[str]) -> None:
    path = ROOT / "kb" / "source-register.json"
    data = read_json(path)
    ids = [source.get("id") for source in data.get("sources", [])]
    duplicates = [item for item, count in Counter(ids).items() if item and count > 1]
    if duplicates:
        errors.append(f"source-register: duplicate ids {duplicates}")


def validate_kb(errors: list[str]) -> None:
    """Prove the knowledge base has substance, not just directories.

    Every indexed concept must point to a card file that exists and to source ids that are
    registered; and no card may be orphaned (present but unindexed). This is the check that
    stops 'the folder exists' from being mistaken for 'the KB is populated'.
    """
    kb = ROOT / "kb"
    index_path = kb / "index.json"
    if not index_path.exists():
        errors.append("kb/index.json is missing (knowledge base has no Level-0 index)")
        return
    index = read_json(index_path)
    source_ids = {s.get("id") for s in read_json(kb / "source-register.json").get("sources", [])}
    referenced: set[Path] = set()
    for concept in index.get("concepts", []):
        cid = concept.get("id")
        card = concept.get("card")
        if not card:
            errors.append(f"kb concept {cid!r}: missing 'card'")
            continue
        card_path = (kb / card).resolve()
        referenced.add(card_path)
        if not card_path.exists():
            errors.append(f"kb concept {cid!r}: card file not found: kb/{card}")
        for source_id in concept.get("sources", []):
            if source_id not in source_ids:
                errors.append(f"kb concept {cid!r}: cites unregistered source {source_id!r}")

    for card in kb.rglob("*.md"):
        if card.name.lower() == "readme.md":
            continue
        if card.resolve() not in referenced:
            errors.append(f"kb card kb/{card.relative_to(kb)} is not referenced in kb/index.json")


def main() -> int:
    errors: list[str] = []
    validate_json_files(errors)
    validate_projects(errors)
    validate_source_register(errors)
    validate_kb(errors)
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
