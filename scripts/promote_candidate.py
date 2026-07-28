#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote an accepted scene candidate")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    parser.add_argument("candidate_file")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = (root / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    scene_dir = project / "scenes" / args.scene_id
    candidate = Path(args.candidate_file)
    if not candidate.is_absolute():
        candidate = scene_dir / "candidates" / candidate
    if not candidate.exists():
        raise SystemExit(f"Candidate not found: {candidate}")
    if not (scene_dir / "spec.json").exists():
        raise SystemExit("Scene spec is missing")
    critiques = list((scene_dir / "critiques").glob("*.json")) if (scene_dir / "critiques").exists() else []
    if not critiques:
        raise SystemExit("No critique JSON files found; run triple audit first")
    state_delta = scene_dir / "state-delta.json"
    if not state_delta.exists():
        raise SystemExit("state-delta.json is required before promotion")

    target = project / "manuscript" / "chapters" / f"{args.scene_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, target)
    decision = {
        "scene_id": args.scene_id,
        "candidate": str(candidate.relative_to(project)),
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "critique_files": [str(p.relative_to(project)) for p in critiques]
    }
    decision_file = project / "decisions" / f"promote-{args.scene_id}.json"
    decision_file.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
