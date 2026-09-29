"""Cross-project repertoire evidence without an originality score.

Project-owned annotations describe a small set of comparable discourse features.  The report counts
exact repeated tags across complete manuscripts and keeps partial/planned work out of observed-story
frequency claims.  It is a diagnostic for noticing local repetition, not a quality metric or a rule
that every story must differ from every earlier story.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from . import schema
from .workspace import PROJECTS


PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FEATURE_FIELDS = (
    "ending_form_tags",
    "turn_tags",
    "resolution_tags",
    "object_motifs",
    "focalization_tags",
)


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _planned_scene_ids(project: Path) -> list[str]:
    discourse = _load(project / "planning" / "discourse-plan.json", {})
    scene_ids: list[str] = []
    for chapter in discourse.get("chapter_map", []) if isinstance(discourse.get("chapter_map", []), list) else []:
        if not isinstance(chapter, dict):
            continue
        for scene_id in chapter.get("scenes", []) if isinstance(chapter.get("scenes", []), list) else []:
            if isinstance(scene_id, str) and scene_id not in scene_ids:
                scene_ids.append(scene_id)
    return scene_ids


def annotation(project: Path) -> dict:
    """Validate one project's repertoire annotation and manuscript-completeness claim."""
    project = Path(project)
    brief = _load(project / "brief" / "project.json", {})
    path = project / "planning" / "story-repertoire.json"
    if not path.exists():
        return {
            "project_id": brief.get("id", project.name),
            "status": "missing",
            "errors": ["planning/story-repertoire.json is missing"],
        }
    data = _load(path, {})
    errors = schema.validate_named(data, "story-repertoire")
    project_id = brief.get("id", project.name)
    if data.get("project_id") != project_id or project_id != project.name:
        errors.append("story repertoire project_id must match brief/project.json and directory name")

    features = data.get("features", {}) if isinstance(data.get("features"), dict) else {}
    for field in FEATURE_FIELDS:
        values = features.get(field, [])
        if isinstance(values, list) and len(values) != len(set(values)):
            errors.append(f"{field} contains duplicate tags")

    planned = _planned_scene_ids(project)
    present = [
        scene_id for scene_id in planned
        if (project / "manuscript" / "chapters" / f"{scene_id}.md").exists()
    ]
    missing = [scene_id for scene_id in planned if scene_id not in present]
    observed_complete = bool(planned) and not missing
    declared_complete = data.get("complete_story") is True
    basis = data.get("evidence_basis")
    if not planned:
        errors.append("cannot verify repertoire completeness without discourse-plan chapter_map scenes")
    if declared_complete != observed_complete:
        errors.append(
            f"complete_story={declared_complete} does not match manuscript chapter coverage "
            f"({len(present)}/{len(planned)} planned scenes present)"
        )
    if declared_complete and basis != "complete-manuscript":
        errors.append("a complete story must use evidence_basis='complete-manuscript'")
    if not declared_complete and basis == "complete-manuscript":
        errors.append("an incomplete story cannot use evidence_basis='complete-manuscript'")
    if basis == "partial-manuscript" and (not present or observed_complete):
        errors.append("partial-manuscript requires some but not all planned manuscript chapters")
    if basis == "plan-only" and present:
        errors.append("plan-only cannot be used when manuscript chapters are already present")
    if declared_complete:
        for field in FEATURE_FIELDS:
            if not features.get(field):
                errors.append(f"complete story needs at least one {field} tag")

    return {
        "project_id": project_id,
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "evidence_basis": basis,
        "complete_story": declared_complete,
        "planned_scenes": planned,
        "manuscript_scenes_present": present,
        "missing_manuscript_scenes": missing,
        "features": features,
        **({"notes": data["notes"]} if isinstance(data.get("notes"), str) else {}),
    }


def report(projects_root: Path = PROJECTS, project_ids: list[str] | None = None) -> dict:
    """Count exact repeated feature tags across structurally complete manuscripts only."""
    projects_root = Path(projects_root)
    if project_ids is None:
        ids = sorted(
            path.name for path in projects_root.iterdir()
            if path.is_dir() and not path.name.startswith("_") and (path / "brief" / "project.json").exists()
        ) if projects_root.exists() else []
    else:
        ids = []
        for project_id in project_ids:
            if not isinstance(project_id, str) or PROJECT_RE.fullmatch(project_id) is None:
                return {"error": f"invalid project id {project_id!r}"}
            if project_id not in ids:
                ids.append(project_id)

    rows: list[dict] = []
    errors: list[str] = []
    for project_id in ids:
        project = projects_root / project_id
        if not project.is_dir():
            errors.append(f"unknown project {project_id!r}")
            continue
        row = annotation(project)
        rows.append(row)
        if row["status"] != "valid":
            errors.extend(f"{project_id}: {message}" for message in row["errors"])

    complete = [row for row in rows if row["status"] == "valid" and row["complete_story"]]
    partial = [row for row in rows if row["status"] == "valid" and not row["complete_story"]]
    occurrences: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in complete:
        for field in FEATURE_FIELDS:
            for value in row["features"].get(field, []):
                occurrences[(field, value)].append(row["project_id"])

    denominator = len(complete)
    features = [
        {
            "dimension": dimension,
            "tag": tag,
            "count": len(projects),
            "projects": sorted(projects),
            "prevalence": (len(projects) / denominator) if denominator else None,
        }
        for (dimension, tag), projects in occurrences.items()
    ]
    features.sort(key=lambda item: (-item["count"], item["dimension"], item["tag"]))
    repeated = [item for item in features if item["count"] >= 2]
    return {
        "status": "valid" if not errors else "incomplete",
        "projects_requested": ids,
        "complete_projects_included": [row["project_id"] for row in complete],
        "partial_projects_excluded": [row["project_id"] for row in partial],
        "invalid_or_missing": [row["project_id"] for row in rows if row["status"] != "valid"],
        "errors": errors,
        "feature_counts": features,
        "repeated_features": repeated,
        "note": (
            "Counts describe exact project-owned tags among complete manuscripts. They are not an "
            "originality score, a quality ranking, or a requirement that a new story avoid repetition."
        ),
    }
