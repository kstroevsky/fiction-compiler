#!/usr/bin/env python3
"""Assemble accepted scenes into projects/<slug>/manuscript/manuscript.md."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.assemble import assemble  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Assemble the manuscript from accepted scenes")
    parser.add_argument("project_dir")
    args = parser.parse_args()
    project = (ROOT / args.project_dir).resolve() if not Path(args.project_dir).is_absolute() else Path(args.project_dir)
    result = assemble(project)
    print(f"{result['manuscript']}  ({len(result['scenes'])} scenes, {result['word_count']} words)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
