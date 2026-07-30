#!/usr/bin/env python3
"""Prove a candidate's extracted prose-claims against state + spec (the hard audit's prose half).

    python3 scripts/prose_audit.py <project> <scene-id> <claims.json> [--write]

``claims.json`` is the prose-claims artifact an extraction agent derives from ONE candidate's prose
(schemas/prose-claims.schema.json). Exit code is non-zero if the audit returns a blocking verdict.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import prose_audit, schema  # noqa: E402


def resolve_project(arg: str) -> Path:
    return (ROOT / arg).resolve() if not Path(arg).is_absolute() else Path(arg)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prove extracted prose-claims against state + spec")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    parser.add_argument("claims", help="path to the prose-claims JSON artifact")
    parser.add_argument("--write", action="store_true", help="write critiques/prose-audit.json")
    args = parser.parse_args()

    project = resolve_project(args.project_dir)
    claims = json.loads(Path(args.claims).read_text(encoding="utf-8"))
    errors = schema.validate_named(claims, "prose-claims")
    if errors:
        raise SystemExit("prose-claims artifact is invalid:\n" + "\n".join(errors))

    critique = prose_audit.audit_prose(project, args.scene_id, claims)
    print(f"[{critique['verdict'].upper()}] {args.scene_id} prose-audit ({len(critique['findings'])} findings)")
    for finding in critique["findings"]:
        print(f"  - {finding['severity']:8} {finding['dimension']:11} {finding['evidence']}")

    if args.write:
        out = project / "scenes" / args.scene_id / "critiques" / "prose-audit.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(critique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  wrote {out.relative_to(project)}")

    return 1 if critique["verdict"] in ("revise", "reject") else 0


if __name__ == "__main__":
    raise SystemExit(main())
