#!/usr/bin/env python3
"""Record and inspect ADR 0030 prose-realization calibration evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import realization_calibration  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _emit(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value or value.get("evidence_status") == "invalid" else 0


def _json_value(raw: str, expected: type, flag: str):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {flag}: {exc}") from exc
    if not isinstance(value, expected):
        noun = "object" if expected is dict else "array"
        raise ValueError(f"{flag} must decode to an {noun}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Record/read plan-to-prose realization calibration.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--project", required=True)
    start.add_argument("--name", required=True)
    start.add_argument("--case", action="append")
    start.add_argument("--criteria-json", default="{}")

    extract_packet = sub.add_parser("extractor-packet")
    extract_packet.add_argument("--project", required=True)
    extract_packet.add_argument("--study", required=True)
    extract_packet.add_argument("--case", required=True)

    extraction = sub.add_parser("extraction")
    extraction.add_argument("--project", required=True)
    extraction.add_argument("--study", required=True)
    extraction.add_argument("--case", required=True)
    extraction.add_argument("--extractor-family", required=True)
    extraction.add_argument("--extractor-id", required=True)
    extraction.add_argument("--trial", required=True, type=int)
    extraction.add_argument("--observed-events-json", required=True)

    align_packet = sub.add_parser("aligner-packet")
    align_packet.add_argument("--project", required=True)
    align_packet.add_argument("--study", required=True)
    align_packet.add_argument("--extraction", required=True)

    alignment = sub.add_parser("alignment")
    alignment.add_argument("--project", required=True)
    alignment.add_argument("--study", required=True)
    alignment.add_argument("--extraction", required=True)
    alignment.add_argument("--aligner-family", required=True)
    alignment.add_argument("--aligner-id", required=True)
    alignment.add_argument("--event-alignment-json", required=True)

    report = sub.add_parser("report")
    report.add_argument("--project", required=True)
    report.add_argument("--study", required=True)

    args = parser.parse_args()
    project = project_dir(args.project)
    try:
        if args.command == "start":
            return _emit(realization_calibration.start_study(
                project, args.name, case_ids=args.case,
                criteria=_json_value(args.criteria_json, dict, "--criteria-json"),
            ))
        if args.command == "extractor-packet":
            return _emit(realization_calibration.extractor_packet(project, args.study, args.case))
        if args.command == "extraction":
            return _emit(realization_calibration.record_extraction(
                project, args.study, args.case, args.extractor_family, args.extractor_id, args.trial,
                _json_value(args.observed_events_json, list, "--observed-events-json"),
            ))
        if args.command == "aligner-packet":
            return _emit(realization_calibration.aligner_packet(project, args.study, args.extraction))
        if args.command == "alignment":
            return _emit(realization_calibration.record_alignment(
                project, args.study, args.extraction, args.aligner_family, args.aligner_id,
                _json_value(args.event_alignment_json, list, "--event-alignment-json"),
            ))
        return _emit(realization_calibration.report(project, args.study))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
