#!/usr/bin/env python3
"""Run the deterministic defaultness linter over scene candidates or arbitrary files.

    python3 scripts/defaultness_lint.py <project> <scene-id> [--write]
    python3 scripts/defaultness_lint.py --files draft-a.md draft-b.md

Exit code is non-zero if any candidate earns a 'revise' verdict (a material tic).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import defaultness, schema  # noqa: E402


def resolve_project(arg: str) -> Path:
    return (ROOT / arg).resolve() if not Path(arg).is_absolute() else Path(arg)


def report(critique: dict) -> None:
    print(f"[{critique['verdict'].upper()}] {critique['candidate']} ({len(critique['findings'])} findings)")
    for finding in critique["findings"]:
        print(f"  - {finding['severity']:8} {finding['dimension']:11} {finding['evidence']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic defaultness linter")
    parser.add_argument("project_dir", nargs="?")
    parser.add_argument("scene_id", nargs="?")
    parser.add_argument("--files", nargs="+", help="lint these files directly")
    parser.add_argument("--write", action="store_true", help="write critique JSON under the scene's critiques/")
    args = parser.parse_args()

    targets: list[tuple[Path, Path | None]] = []  # (candidate path, critique out dir)
    if args.files:
        targets = [(Path(f), None) for f in args.files]
    elif args.project_dir and args.scene_id:
        project = resolve_project(args.project_dir)
        candidates_dir = project / "scenes" / args.scene_id / "candidates"
        out_dir = project / "scenes" / args.scene_id / "critiques"
        for candidate in sorted(candidates_dir.glob("*.md")):
            targets.append((candidate, out_dir if args.write else None))
        if not targets:
            raise SystemExit(f"No candidates in {candidates_dir}")
    else:
        parser.error("provide <project> <scene-id> or --files ...")

    worst_revise = False
    for candidate, out_dir in targets:
        critique = defaultness.lint_file(candidate)
        errors = schema.validate_named(critique, "critique")
        if errors:
            raise SystemExit("INTERNAL: defaultness lint produced invalid critique:\n" + "\n".join(errors))
        report(critique)
        if critique["verdict"] == "revise":
            worst_revise = True
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"defaultness-{candidate.stem}.json"
            out.write_text(json.dumps(critique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  wrote {out.name}")

    return 1 if worst_revise else 0


if __name__ == "__main__":
    raise SystemExit(main())
