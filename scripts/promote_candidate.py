#!/usr/bin/env python3
"""Promote a reviewed scene candidate into the manuscript and canon.

Preconditions (all required by the operating contract): the scene has a spec, at
least one critique, and a schema-valid ``state-delta.json`` whose ``scene_id`` matches.
On success this copies the prose into the manuscript, records the decision, and — the
step the previous version was missing — appends the scene to
``canon/index.json.accepted_state_deltas`` so the event-sourced state includes it.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import schema  # noqa: E402
from fiction_compiler.state import scene_sort_key  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote an accepted scene candidate")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    parser.add_argument("candidate_file")
    args = parser.parse_args()
    project = (ROOT / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    scene_dir = project / "scenes" / args.scene_id
    candidate = Path(args.candidate_file)
    if not candidate.is_absolute():
        candidate = scene_dir / "candidates" / candidate
    if not candidate.exists():
        raise SystemExit(f"Candidate not found: {candidate}")
    if not (scene_dir / "spec.json").exists():
        raise SystemExit("Scene spec is missing")

    critiques = sorted((scene_dir / "critiques").glob("*.json")) if (scene_dir / "critiques").exists() else []
    if not critiques:
        raise SystemExit("No critique JSON files found; run triple audit first")

    state_delta_path = scene_dir / "state-delta.json"
    if not state_delta_path.exists():
        raise SystemExit("state-delta.json is required before promotion")
    delta = load(state_delta_path)
    delta_errors = schema.validate_named(delta, "state-delta", path=str(state_delta_path.relative_to(ROOT)))
    if delta_errors:
        raise SystemExit("state-delta.json is invalid:\n" + "\n".join(f"  - {e}" for e in delta_errors))
    if delta.get("scene_id") != args.scene_id:
        raise SystemExit(f"state-delta scene_id {delta.get('scene_id')!r} != {args.scene_id!r}")

    # Copy prose into the manuscript.
    target = project / "manuscript" / "chapters" / f"{args.scene_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, target)

    # Fold the accepted scene into the event-sourced canon log (idempotent, ordered).
    index_path = project / "canon" / "index.json"
    index = load(index_path) if index_path.exists() else {}
    accepted = list(index.get("accepted_state_deltas", []))
    if args.scene_id not in accepted:
        accepted.append(args.scene_id)
    index["accepted_state_deltas"] = sorted(set(accepted), key=scene_sort_key)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    decision = {
        "scene_id": args.scene_id,
        "candidate": str(candidate.relative_to(project)),
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "critique_files": [str(p.relative_to(project)) for p in critiques],
    }
    decision_file = project / "decisions" / f"promote-{args.scene_id}.json"
    decision_file.parent.mkdir(parents=True, exist_ok=True)
    decision_file.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
