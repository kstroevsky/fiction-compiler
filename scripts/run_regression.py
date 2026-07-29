#!/usr/bin/env python3
"""Run the framework regression fixtures and exit non-zero on any failure.

This is the FRAMEWORK loop's gate: run it before and after a change to a prompt, rubric, schema, or
the deterministic code. A failure means an established invariant regressed — reject or roll back the
change rather than accept it because an evaluator preferred the new output.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import regression  # noqa: E402


def main() -> int:
    report = regression.run_regressions()
    for result in report["results"]:
        if result["passed"]:
            print(f"[PASS] {result['name']}")
        else:
            detail = result.get("error") or f"expected={result.get('expected')!r} actual={result.get('actual')!r}"
            print(f"[FAIL] {result['name']}  ({detail})")
    fingerprint = report["manifest"]["framework_fingerprint"][:12]
    print(f"\n{report['passed']}/{report['total']} passed. framework_fingerprint={fingerprint}…")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
