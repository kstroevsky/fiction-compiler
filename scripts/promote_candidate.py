#!/usr/bin/env python3
"""Promote a reviewed scene candidate into the manuscript and canon.

Thin CLI over ``fiction_compiler.promote.promote_candidate`` (shared with the MCP `promote`
tool). Preconditions (spec, at least one critique, a schema-valid matching state delta) are
enforced in the library; failures surface as a non-zero exit.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.promote import promote_candidate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote an accepted scene candidate")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    parser.add_argument("candidate_file")
    args = parser.parse_args()
    project = (ROOT / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    try:
        result = promote_candidate(project, args.scene_id, args.candidate_file)
    except ValueError as exc:
        raise SystemExit(str(exc))
    print(result["promoted_to"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
