#!/usr/bin/env python3
"""Run the deterministic hard audit (Audit 1) over a project or a single scene.

    python3 scripts/hard_audit.py <project> <scene-id>   # audit one scene, write critique
    python3 scripts/hard_audit.py <project>              # audit canon + every accepted scene

Exit code is non-zero when any fatal finding exists, so this can gate promotion.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import hard_audit, schema  # noqa: E402
from fiction_compiler.state import accepted_scene_ids  # noqa: E402


def resolve_project(arg: str) -> Path:
    return (ROOT / arg).resolve() if not Path(arg).is_absolute() else Path(arg)


def print_critique(critique: dict) -> None:
    label = critique["candidate"]
    print(f"[{critique['verdict'].upper()}] {label} ({len(critique['findings'])} findings)")
    for finding in critique["findings"]:
        print(f"  - {finding['severity']:8} {finding['dimension']:10} {finding['diagnosis']}")
        print(f"    evidence: {finding['evidence']}  -> repair @ {finding['repair_layer']}")


def self_check(critique: dict) -> None:
    errors = schema.validate_named(critique, "critique")
    if errors:  # a bug in the auditor, not the story — fail loudly
        raise SystemExit("INTERNAL: hard-audit produced invalid critique:\n" + "\n".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic hard audit")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id", nargs="?")
    parser.add_argument("--write", action="store_true", help="write critique JSON under the scene's critiques/")
    args = parser.parse_args()
    project = resolve_project(args.project_dir)

    critiques: list[dict] = []
    if args.scene_id:
        critique = hard_audit.audit_scene(project, args.scene_id)
        self_check(critique)
        critiques.append(critique)
        if args.write:
            out = project / "scenes" / args.scene_id / "critiques" / "hard-audit.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(critique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"wrote {out.relative_to(project)}")
    else:
        canon = hard_audit.audit_canon(project)
        self_check(canon)
        critiques.append(canon)
        for scene_id in accepted_scene_ids(project):
            scene_critique = hard_audit.audit_scene(project, scene_id)
            self_check(scene_critique)
            critiques.append(scene_critique)

    for critique in critiques:
        print_critique(critique)

    fatal = any(hard_audit.has_fatal(c) for c in critiques)
    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
