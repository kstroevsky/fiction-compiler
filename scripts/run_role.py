#!/usr/bin/env python3
"""External multi-vendor role runner CLI (ADR 0020).

Route one blind candidate to the model family the roster assigns a judge role, or run a whole panel
and report their (dis)agreement. This is the LIVE path: it calls real vendor APIs (keys from the
environment) and, with --record, writes the findings back through the deterministic record_critique.
The MCP server itself still makes no LLM calls; this process is an external client of judge_bundle +
record_critique.

Examples:
  # one role, dry (no write), using the roster's vendor+model for adversarial-reader
  python3 scripts/run_role.py --project forecourt --scene ch01-sc01 \
      --candidate candidate-a.md --role adversarial-reader

  # a heterogeneous panel, recording each vendor's critique and reporting disagreement
  python3 scripts/run_role.py --project forecourt --scene ch01-sc01 \
      --candidate candidate-a.md --panel adversarial-reader,character-simulator,style-editor --record
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import role_runner  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Route a blind candidate to a vendor-assigned judge role.")
    ap.add_argument("--project", required=True)
    ap.add_argument("--scene", required=True)
    ap.add_argument("--candidate", required=True, help="candidate filename under the scene's candidates/")
    ap.add_argument("--role", help="a single judge role from the roster")
    ap.add_argument("--panel", help="comma-separated roles to run as a panel")
    ap.add_argument("--roster", help="path to a roster JSON (default: config/model-roster.json)")
    ap.add_argument("--record", action="store_true",
                    help="write each critique back through record_critique (gate-bound)")
    args = ap.parse_args()

    if not args.role and not args.panel:
        ap.error("give --role ROLE or --panel ROLE1,ROLE2,...")

    try:
        roster = role_runner.load_roster(args.roster)
    except (FileNotFoundError, ValueError) as exc:
        print(f"roster error: {exc}", file=sys.stderr)
        return 2

    try:
        if args.panel:
            roles = [r.strip() for r in args.panel.split(",") if r.strip()]
            result = role_runner.run_panel(args.project, args.scene, args.candidate, roles,
                                           roster=roster, record=args.record)
        else:
            result = role_runner.run_role(args.project, args.scene, args.candidate, args.role,
                                          roster=roster, record=args.record)
    except role_runner.VendorUnavailable as exc:
        print(f"vendor unavailable: {exc}", file=sys.stderr)
        return 2
    except role_runner.MalformedVendorOutput as exc:
        print(f"malformed vendor output (rejected before the gate): {exc}", file=sys.stderr)
        return 3

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if "error" in result:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
