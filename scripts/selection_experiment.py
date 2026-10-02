#!/usr/bin/env python3
"""Freeze and inspect selector-value experiments (ADR 0028).

This CLI records evidence only.  It never calls a writer, critic, or reader model itself; generation,
selection and reader recruitment remain explicit external steps whose outputs are bound here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import selection_eval  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _emit(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value or value.get("status") == "invalid" else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Record/read frozen candidate-selection experiments.")
    sub = parser.add_subparsers(dest="command", required=True)

    freeze = sub.add_parser("freeze", help="freeze an ordered candidate pool")
    freeze.add_argument("--project", required=True)
    freeze.add_argument("--scene", required=True)
    freeze.add_argument("--candidate", action="append", required=True,
                        help="candidate filename in generation order; repeat for each candidate")
    freeze.add_argument("--seed", type=int, default=0)

    packet = sub.add_parser("packet", help="print the blinded reader packet")
    packet.add_argument("--project", required=True)
    packet.add_argument("--scene", required=True)
    packet.add_argument("--experiment", required=True)

    preference = sub.add_parser("preference", help="record one scheduled pairwise judgment")
    preference.add_argument("--project", required=True)
    preference.add_argument("--scene", required=True)
    preference.add_argument("--experiment", required=True)
    preference.add_argument("--rater", required=True)
    preference.add_argument("--cohort", required=True,
                            choices=["target_reader", "expert_reader", "owner", "other"])
    preference.add_argument("--rater-kind", required=True, choices=["human", "model_probe"])
    preference.add_argument("--pair", required=True)
    preference.add_argument("--choice", required=True, choices=["left", "right", "tie", "abstain"])
    preference.add_argument("--confidence", type=float)
    preference.add_argument("--reason")

    selector = sub.add_parser("selector", help="record a selector choice before reader judgments")
    selector.add_argument("--project", required=True)
    selector.add_argument("--scene", required=True)
    selector.add_argument("--experiment", required=True)
    selector.add_argument("--selector", required=True)
    selector.add_argument("--candidate", required=True)
    selector.add_argument("--provenance-json", default="{}",
                          help="JSON object describing the selector/run that produced the choice")

    operation = sub.add_parser("operation", help="record cost/failure evidence")
    operation.add_argument("--project", required=True)
    operation.add_argument("--scene", required=True)
    operation.add_argument("--experiment", required=True)
    operation.add_argument("--phase", required=True,
                           choices=["generation", "critique", "selection", "reader", "revision", "other"])
    operation.add_argument("--status", required=True, choices=["success", "failure"])
    operation.add_argument("--candidate")
    operation.add_argument("--provider")
    operation.add_argument("--model")
    operation.add_argument("--input-tokens", type=int)
    operation.add_argument("--output-tokens", type=int)
    operation.add_argument("--cost-usd", type=float)
    operation.add_argument("--failure-reason")

    report = sub.add_parser("report", help="report descriptive selector performance")
    report.add_argument("--project", required=True)
    report.add_argument("--scene", required=True)
    report.add_argument("--experiment", required=True)

    args = parser.parse_args()
    project = project_dir(args.project)
    if args.command == "freeze":
        return _emit(selection_eval.freeze_pool(project, args.scene, args.candidate, seed=args.seed))
    if args.command == "packet":
        return _emit(selection_eval.reader_packet(project, args.scene, args.experiment))
    if args.command == "preference":
        return _emit(selection_eval.record_preference(
            project, args.scene, args.experiment, args.rater, args.cohort, args.rater_kind,
            args.pair, args.choice, confidence=args.confidence, reason=args.reason,
        ))
    if args.command == "selector":
        try:
            provenance = json.loads(args.provenance_json)
        except json.JSONDecodeError as exc:
            print(f"invalid --provenance-json: {exc}", file=sys.stderr)
            return 2
        if not isinstance(provenance, dict):
            print("--provenance-json must decode to an object", file=sys.stderr)
            return 2
        return _emit(selection_eval.record_selector(
            project, args.scene, args.experiment, args.selector, args.candidate, provenance=provenance
        ))
    if args.command == "operation":
        return _emit(selection_eval.record_operation(
            project, args.scene, args.experiment, args.phase, args.status, candidate=args.candidate,
            provider=args.provider, model=args.model, input_tokens=args.input_tokens,
            output_tokens=args.output_tokens, cost_usd=args.cost_usd,
            failure_reason=args.failure_reason,
        ))
    return _emit(selection_eval.report(project, args.scene, args.experiment))


if __name__ == "__main__":
    raise SystemExit(main())
