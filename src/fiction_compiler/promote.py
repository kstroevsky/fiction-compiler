"""Promotion as a library function, shared by the CLI and the MCP tool.

Promotion is the one state-changing step in the story loop: it copies a reviewed candidate
into the manuscript and folds its accepted delta into the event-sourced canon. It refuses
unless the preconditions hold — a spec, at least one critique, and a schema-valid state delta
whose scene_id matches — so canon can only ever advance through reviewed work.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import schema
from .state import scene_sort_key


def promote_candidate(project: Path, scene_id: str, candidate_file: str) -> dict:
    scene_dir = project / "scenes" / scene_id
    candidate = Path(candidate_file)
    if not candidate.is_absolute():
        candidate = scene_dir / "candidates" / candidate
    if not candidate.exists():
        raise ValueError(f"Candidate not found: {candidate}")
    if not (scene_dir / "spec.json").exists():
        raise ValueError("Scene spec is missing")

    critiques = sorted((scene_dir / "critiques").glob("*.json")) if (scene_dir / "critiques").exists() else []
    if not critiques:
        raise ValueError("No critique JSON files found; run the triple audit first")

    delta_path = scene_dir / "state-delta.json"
    if not delta_path.exists():
        raise ValueError("state-delta.json is required before promotion")
    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    errors = schema.validate_named(delta, "state-delta")
    if errors:
        raise ValueError("state-delta.json is invalid: " + "; ".join(errors))
    if delta.get("scene_id") != scene_id:
        raise ValueError(f"state-delta scene_id {delta.get('scene_id')!r} != {scene_id!r}")

    target = project / "manuscript" / "chapters" / f"{scene_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, target)

    index_path = project / "canon" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    accepted = list(index.get("accepted_state_deltas", []))
    if scene_id not in accepted:
        accepted.append(scene_id)
    index["accepted_state_deltas"] = sorted(set(accepted), key=scene_sort_key)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    decision = {
        "scene_id": scene_id,
        "candidate": str(candidate.relative_to(project)) if candidate.is_relative_to(project) else str(candidate),
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "critique_files": [str(p.relative_to(project)) for p in critiques],
    }
    decision_file = project / "decisions" / f"promote-{scene_id}.json"
    decision_file.parent.mkdir(parents=True, exist_ok=True)
    decision_file.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")

    return {
        "promoted_to": decision["promoted_to"],
        "accepted_state_deltas": index["accepted_state_deltas"],
        "decision_file": str(decision_file.relative_to(project)),
        "critique_files": decision["critique_files"],
    }
