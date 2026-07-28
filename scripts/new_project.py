#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a fiction project from projects/_template")
    parser.add_argument("slug")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.slug):
        parser.error("slug must match [a-z0-9-]+")
    root = Path(__file__).resolve().parents[1]
    source = root / "projects" / "_template"
    target = root / "projects" / args.slug
    if target.exists():
        raise SystemExit(f"Project already exists: {target}")
    shutil.copytree(source, target)
    project_file = target / "brief" / "project.json"
    data = json.loads(project_file.read_text(encoding="utf-8"))
    data["id"] = args.slug
    project_file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
