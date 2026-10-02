#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import authoring  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fiction project from projects/_template")
    parser.add_argument("slug")
    args = parser.parse_args()
    try:
        authoring.create_project(args.slug)
    except ValueError as exc:
        parser.error(str(exc))
    print(ROOT / "projects" / args.slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
