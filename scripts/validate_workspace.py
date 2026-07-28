#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid JSON {path.relative_to(ROOT)}: {exc}") from exc


def validate_json_files(errors: list[str]) -> None:
    for path in ROOT.rglob("*.json"):
        if any(part in {".git", ".runs"} for part in path.parts):
            continue
        try:
            read_json(path)
        except ValueError as exc:
            errors.append(str(exc))


def validate_projects(errors: list[str]) -> None:
    projects = ROOT / "projects"
    for project in projects.iterdir():
        if not project.is_dir() or project.name.startswith("_"):
            continue
        project_file = project / "brief" / "project.json"
        if not project_file.exists():
            errors.append(f"{project.name}: missing brief/project.json")
            continue
        data = read_json(project_file)
        if data.get("id") != project.name:
            errors.append(f"{project.name}: project id must equal directory name")

        scene_ids: list[str] = []
        scene_root = project / "scenes"
        if scene_root.exists():
            for scene_dir in scene_root.iterdir():
                if not scene_dir.is_dir():
                    continue
                spec = scene_dir / "spec.json"
                if not spec.exists():
                    errors.append(f"{project.name}/{scene_dir.name}: missing spec.json")
                    continue
                scene = read_json(spec)
                scene_id = scene.get("id")
                scene_ids.append(scene_id)
                if scene_id != scene_dir.name:
                    errors.append(f"{project.name}/{scene_dir.name}: scene id does not match directory")
                manuscript = project / "manuscript" / "chapters" / f"{scene_dir.name}.md"
                if manuscript.exists() and not (scene_dir / "state-delta.json").exists():
                    errors.append(f"{project.name}/{scene_dir.name}: promoted scene lacks state-delta.json")
        duplicates = [item for item, count in Counter(scene_ids).items() if count > 1]
        if duplicates:
            errors.append(f"{project.name}: duplicate scene ids: {duplicates}")


def validate_source_register(errors: list[str]) -> None:
    path = ROOT / "kb" / "source-register.json"
    data = read_json(path)
    ids = [source.get("id") for source in data.get("sources", [])]
    duplicates = [item for item, count in Counter(ids).items() if item and count > 1]
    if duplicates:
        errors.append(f"source-register: duplicate ids {duplicates}")


def main() -> int:
    errors: list[str] = []
    validate_json_files(errors)
    validate_projects(errors)
    validate_source_register(errors)
    if errors:
        print("VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
