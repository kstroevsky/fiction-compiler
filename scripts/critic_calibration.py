#!/usr/bin/env python3
"""Record and inspect B2 critic-calibration studies (ADR 0029)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import critic_calibration  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _emit(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value or value.get("evidence_status") == "invalid" else 0


def _json_object(raw: str, flag: str) -> dict:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {flag}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{flag} must decode to an object")
    return value


def _json_array(raw: str, flag: str) -> list:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {flag}: {exc}") from exc
    if not isinstance(value, list):
        raise ValueError(f"{flag} must decode to an array")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Record/read critic-calibration evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--project", required=True)
    start.add_argument("--name", required=True)
    start.add_argument("--case", action="append")
    start.add_argument("--criteria-json", default="{}")

    packet = sub.add_parser("packet")
    packet.add_argument("--project", required=True)
    packet.add_argument("--study", required=True)
    packet.add_argument("--case", required=True)

    observe = sub.add_parser("observe")
    observe.add_argument("--project", required=True)
    observe.add_argument("--study", required=True)
    observe.add_argument("--case", required=True)
    observe.add_argument("--judge-family", required=True)
    observe.add_argument("--judge-id", required=True)
    observe.add_argument("--writer-family", required=True)
    observe.add_argument("--trial", required=True, type=int)
    observe.add_argument("--variant", required=True)
    observe.add_argument("--transform", required=True,
                         choices=["identity", "metadata_relabel", "presentation_order", "formatting", "directional_defect", "other"])
    observe.add_argument("--expectation", required=True,
                         choices=["baseline", "invariant", "directional_worse"])
    observe.add_argument("--group")
    observe.add_argument("--verdict", required=True, choices=["pass", "revise", "reject", "uncertain"])
    observe.add_argument("--confidence", type=float, default=1.0)
    observe.add_argument("--findings-json", default="[]")

    label = sub.add_parser("human-label")
    label.add_argument("--project", required=True)
    label.add_argument("--study", required=True)
    label.add_argument("--case", required=True)
    label.add_argument("--annotator", required=True)
    label.add_argument("--role", required=True, choices=["expert", "target_reader", "owner", "other"])
    label.add_argument("--label", required=True, choices=["defect", "control", "abstain", "disputed"])
    label.add_argument("--severity", choices=["minor", "material", "fatal"])
    label.add_argument("--signal", action="append")
    label.add_argument("--notes")

    report = sub.add_parser("report")
    report.add_argument("--project", required=True)
    report.add_argument("--study", required=True)

    args = parser.parse_args()
    project = project_dir(args.project)
    try:
        if args.command == "start":
            return _emit(critic_calibration.start_study(
                project, args.name, case_ids=args.case, criteria=_json_object(args.criteria_json, "--criteria-json")
            ))
        if args.command == "packet":
            return _emit(critic_calibration.judge_packet(project, args.study, args.case))
        if args.command == "observe":
            return _emit(critic_calibration.record_observation(
                project, args.study, args.case, args.judge_family, args.judge_id, args.writer_family,
                args.trial, args.variant, args.transform, args.expectation, args.verdict,
                _json_array(args.findings_json, "--findings-json"), confidence=args.confidence,
                invariance_group=args.group,
            ))
        if args.command == "human-label":
            return _emit(critic_calibration.record_human_label(
                project, args.study, args.case, args.annotator, args.role, args.label,
                severity=args.severity, signals=args.signal, notes=args.notes,
            ))
        return _emit(critic_calibration.report(project, args.study))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
