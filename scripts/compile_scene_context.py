#!/usr/bin/env python3
"""Compile a minimal, leak-free context bundle for drafting or auditing one scene.

The previous version statically dumped whole planning files, which let a fact a later
scene introduces sit in the drafting context of an earlier one. This version derives
``state_before`` from the event-sourced reconstruction, so the bundle can only contain
what is true — and what each participant knows — *before* the scene. That is the whole
point of separating fabula from discourse: you draft with the past, never the future.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.state import reconstruct_state_before  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def optional_load(path: Path, default):
    return load(path) if path.exists() else default


def trim_project(project_brief: dict) -> dict:
    keep = ["id", "title", "form", "audience", "reader_contract", "theme_question", "constraints", "desired_affect"]
    return {k: project_brief[k] for k in keep if k in project_brief}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile minimal scene context")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    args = parser.parse_args()
    project = (ROOT / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    scene_dir = project / "scenes" / args.scene_id
    spec = load(scene_dir / "spec.json")

    pov = spec.get("pov")
    participants = list(dict.fromkeys([pov] + spec.get("participants", []))) if pov else spec.get("participants", [])
    participant_set = {p for p in participants if p}

    character_sheets = []
    for path in sorted((project / "canon" / "characters").glob("*.json")):
        data = load(path)
        if data.get("id") in participant_set:
            character_sheets.append(data)

    before = reconstruct_state_before(project, args.scene_id)
    # Only the participants' knowledge is relevant to how this scene can be told.
    knowledge = {c: sorted(before.knowledge.get(c, set())) for c in participant_set if c in before.knowledge}
    relationships = [
        {"pair": sorted(pair), "state": state}
        for pair, state in before.relationships.items()
        if pair & participant_set  # relationships touching someone in the scene
    ]

    canon_index = optional_load(project / "canon" / "index.json", {})
    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scene_id": args.scene_id,
        "project": trim_project(optional_load(project / "brief" / "project.json", {})),
        "scene_spec": spec,
        "participants": character_sheets,
        "state_before": {
            "time": before.time,
            "facts": before.facts,
            "participant_knowledge": knowledge,
            "relationships": relationships,
            "open_promises": before.open_promises,
        },
        "world_rules": canon_index.get("world_rules", []),
        "discourse_plan": optional_load(project / "planning" / "discourse-plan.json", {}),
        "style_profile": optional_load(project / "planning" / "style-profile.json", {}),
        "note": (
            "state_before is reconstructed from seed canon + accepted deltas only; it cannot "
            "contain anything a later scene introduces. Add targeted missing canon if needed; "
            "never paste the whole project."
        ),
    }
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = ROOT / ".runs" / run_id / args.scene_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "context-bundle.json"
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
