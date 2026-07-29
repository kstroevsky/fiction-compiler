#!/usr/bin/env python3
"""Compile a minimal, leak-free context bundle for drafting or auditing one scene.

Thin CLI over ``fiction_compiler.context.compile_bundle`` (shared with the tools/MCP layer).
The bundle is derived from the state reconstructed *before* the scene, so it can only contain
what is true — and what each participant knows — before the scene. Drafting uses the past,
never the future.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.context import compile_bundle, write_bundle  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile minimal scene context")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    args = parser.parse_args()
    project = (ROOT / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    bundle = compile_bundle(project, args.scene_id)
    print(write_bundle(bundle, args.scene_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
