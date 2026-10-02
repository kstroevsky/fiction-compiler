#!/usr/bin/env python3
"""Run the evidence-bound framework improvement transaction (ADR 0033).

This CLI never edits the proposed framework files itself. Start freezes the clean baseline and
rollback bytes; the operator makes the declared edits; evaluate binds the edited state; prepare and
record collect blind before/after evidence; decide records human authority; rollback restores the
frozen declared paths when the evaluated state is still current.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import framework_change  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _dump(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value else 0


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Evidence-bound framework-change transactions.")
    sub = ap.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="freeze clean baseline and rollback bytes before editing")
    start.add_argument("--project", required=True)
    start.add_argument("--title", required=True)
    start.add_argument("--failure-observed", required=True)
    start.add_argument("--evidence", action="append", required=True)
    start.add_argument("--root-layer", required=True)
    start.add_argument("--minimal-change", required=True)
    start.add_argument("--regression-case", required=True)
    start.add_argument("--blind-comparison-plan", required=True)
    start.add_argument("--tradeoff", action="append", default=[])
    start.add_argument("--changed-path", action="append", required=True)
    start.add_argument("--proposed-by", required=True)
    start.add_argument("--proposer-kind", choices=["human", "agent"], required=True)
    start.add_argument("--minimum-observations", type=int, required=True)
    start.add_argument("--minimum-after-wins", type=int, required=True)
    start.add_argument("--maximum-before-wins", type=int, required=True)

    evaluate = sub.add_parser("evaluate", help="bind edited framework and rerun regression")
    evaluate.add_argument("--project", required=True)
    evaluate.add_argument("--change-id", required=True)

    prepare = sub.add_parser("prepare", help="freeze and blind one before/after output pair")
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--change-id", required=True)
    prepare.add_argument("--objective", required=True)
    prepare.add_argument("--before-file", required=True)
    prepare.add_argument("--after-file", required=True)
    prepare.add_argument("--prepared-by", required=True)

    packet = sub.add_parser("packet", help="show a frozen comparison without the reveal map")
    packet.add_argument("--project", required=True)
    packet.add_argument("--change-id", required=True)
    packet.add_argument("--comparison-id", required=True)

    record = sub.add_parser("record", help="record blind comparison evidence")
    record.add_argument("--project", required=True)
    record.add_argument("--change-id", required=True)
    record.add_argument("--comparison-id", required=True)
    record.add_argument("--evaluator-kind", choices=["human", "model"], required=True)
    record.add_argument("--evaluator-id", required=True)
    record.add_argument("--preferred", choices=["A", "B", "tie", "abstain"], required=True)
    record.add_argument("--rationale", required=True)

    status = sub.add_parser("status", help="show readiness, evidence, decision and rollback state")
    status.add_argument("--project", required=True)
    status.add_argument("--change-id", required=True)

    decide = sub.add_parser("decide", help="record explicit human approve/reject authority")
    decide.add_argument("--project", required=True)
    decide.add_argument("--change-id", required=True)
    decide.add_argument("--decision", choices=["approve", "reject"], required=True)
    decide.add_argument("--decided-by", required=True)
    decide.add_argument("--reason", required=True)
    decide.add_argument("--confirm", action="store_true", required=True)

    rollback = sub.add_parser("rollback", help="restore exact pre-change declared files")
    rollback.add_argument("--project", required=True)
    rollback.add_argument("--change-id", required=True)
    rollback.add_argument("--decided-by", required=True)
    rollback.add_argument("--reason", required=True)
    rollback.add_argument("--confirm", action="store_true", required=True)
    return ap


def main() -> int:
    args = parser().parse_args()
    project = project_dir(args.project)
    if args.command == "start":
        return _dump(framework_change.start(
            project,
            title=args.title,
            failure_observed=args.failure_observed,
            evidence=args.evidence,
            root_layer=args.root_layer,
            minimal_change=args.minimal_change,
            regression_case=args.regression_case,
            blind_comparison_plan=args.blind_comparison_plan,
            tradeoffs=args.tradeoff,
            changed_paths=args.changed_path,
            proposed_by=args.proposed_by,
            proposer_kind=args.proposer_kind,
            minimum_observations=args.minimum_observations,
            minimum_after_wins=args.minimum_after_wins,
            maximum_before_wins=args.maximum_before_wins,
        ))
    if args.command == "evaluate":
        return _dump(framework_change.evaluate(project, args.change_id))
    if args.command == "prepare":
        return _dump(framework_change.prepare_comparison(
            project, args.change_id, objective=args.objective,
            before_output=_read(args.before_file), after_output=_read(args.after_file),
            prepared_by=args.prepared_by,
        ))
    if args.command == "packet":
        return _dump(framework_change.comparison_packet(project, args.change_id, args.comparison_id))
    if args.command == "record":
        return _dump(framework_change.record_comparison(
            project, args.change_id, args.comparison_id, evaluator_kind=args.evaluator_kind,
            evaluator_id=args.evaluator_id, preferred=args.preferred, rationale=args.rationale,
        ))
    if args.command == "status":
        return _dump(framework_change.status(project, args.change_id))
    if args.command == "decide":
        if not args.confirm:
            return _dump({"error": "decision requires --confirm"})
        return _dump(framework_change.decide(
            project, args.change_id, decision=args.decision, decided_by=args.decided_by,
            decider_kind="human", reason=args.reason,
        ))
    if args.command == "rollback":
        return _dump(framework_change.rollback(
            project, args.change_id, decided_by=args.decided_by, decider_kind="human", reason=args.reason,
            confirm=args.confirm,
        ))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
