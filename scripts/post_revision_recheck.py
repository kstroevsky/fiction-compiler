#!/usr/bin/env python3
"""Inspect and close subjective or policy-required prose rechecks after backward revision."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import post_revision  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _emit(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value else 0


def _json(raw: str, expected: type, flag: str):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {flag}: {exc}") from exc
    if not isinstance(value, expected):
        raise ValueError(f"{flag} must decode to {'an object' if expected is dict else 'an array'}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-revision subjective recheck evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--project", required=True)

    packet = sub.add_parser("packet")
    packet.add_argument("--project", required=True)
    packet.add_argument("--scope", required=True, choices=sorted(post_revision.SCOPES))
    packet.add_argument("--scene")

    evidence = sub.add_parser("evidence")
    evidence.add_argument("--project", required=True)
    evidence.add_argument("--scope", required=True, choices=sorted(post_revision.SCOPES))
    evidence.add_argument("--scene")
    evidence.add_argument("--packet-sha256", required=True)
    evidence.add_argument("--evaluator-kind", required=True, choices=["human", "role_runner", "model_probe"])
    evidence.add_argument("--evaluator-id", required=True)
    evidence.add_argument("--cohort", required=True, choices=["target_reader", "expert_reader", "owner", "other"])
    evidence.add_argument("--verdict", required=True, choices=["pass", "revise", "reject", "uncertain"])
    evidence.add_argument("--findings-json", default="[]")
    evidence.add_argument("--provenance-json", default="{}")

    resolve = sub.add_parser("resolve")
    resolve.add_argument("--project", required=True)
    resolve.add_argument("--evidence", required=True)
    resolve.add_argument("--decided-by", required=True)
    resolve.add_argument("--reason", required=True)

    prose = sub.add_parser("prose-audit")
    prose.add_argument("--project", required=True)
    prose.add_argument("--scene", required=True)
    prose.add_argument("--claims-json", required=True)

    args = parser.parse_args()
    project = project_dir(args.project)
    try:
        if args.command == "status":
            return _emit(post_revision.status(project))
        if args.command == "packet":
            return _emit(post_revision.packet(project, args.scope, args.scene))
        if args.command == "evidence":
            return _emit(post_revision.record_evidence(
                project, args.scope, args.packet_sha256, args.evaluator_kind, args.evaluator_id,
                args.cohort, args.verdict, _json(args.findings_json, list, "--findings-json"),
                provenance=_json(args.provenance_json, dict, "--provenance-json"), scene_id=args.scene,
            ))
        if args.command == "prose-audit":
            return _emit(post_revision.recheck_prose_audit(
                project, args.scene, _json(args.claims_json, dict, "--claims-json")
            ))
        return _emit(post_revision.resolve_scope(project, args.evidence, args.decided_by, args.reason))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
