#!/usr/bin/env python3
"""Run the critic-calibration corpus and report recall/specificity.

Deterministic detectors are scored now; ``llm`` cases are marked needs_live (score them against a
live persona's findings via ``critic_eval.score_findings``). Exit non-zero if any deterministic case
is mis-scored, so a regression in a deterministic critic's recall is caught here too.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import critic_eval  # noqa: E402


def main() -> int:
    report = critic_eval.run_corpus()
    for r in report["results"]:
        mark = {True: "OK ", False: "MISS", None: "----"}[r["correct"]]
        caught = "-" if r["caught"] is None else ("caught" if r["caught"] else "missed")
        print(f"[{mark}] {r['id']:<22} critic={r['critic']:<18} {r['kind']:<8} {caught:<7} ({r['status']})")
    recall = report["recall"]
    spec = report["specificity"]
    print(f"\nscored {report['scored']}/{report['total']} "
          f"(needs_live={report['needs_live']}) | "
          f"recall={'n/a' if recall is None else f'{recall:.2f}'} "
          f"specificity={'n/a' if spec is None else f'{spec:.2f}'}")
    mis = [r["id"] for r in report["results"] if r["correct"] is False]
    if mis:
        print("MIS-SCORED (deterministic critic regression):", ", ".join(mis), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
