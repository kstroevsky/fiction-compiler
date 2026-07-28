#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def optional_load(path: Path, default):
    return load(path) if path.exists() else default


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile minimal scene context")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    project = (root / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    scene_dir = project / "scenes" / args.scene_id
    spec = load(scene_dir / "spec.json")
    participants = set(spec.get("participants", []))

    characters = []
    for path in (project / "canon" / "characters").glob("*.json"):
        data = load(path)
        if data.get("id") in participants:
            characters.append(data)

    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": optional_load(project / "brief" / "project.json", {}),
        "scene": spec,
        "characters": characters,
        "canon_index": optional_load(project / "canon" / "index.json", {}),
        "event_graph": optional_load(project / "planning" / "event-graph.json", {}),
        "discourse_plan": optional_load(project / "planning" / "discourse-plan.json", {}),
        "style_profile": optional_load(project / "planning" / "style-profile.json", {}),
        "note": "Manually verify that every included item is relevant; add targeted missing context instead of the whole project."
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / ".runs" / run_id / args.scene_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "context-bundle.json"
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
