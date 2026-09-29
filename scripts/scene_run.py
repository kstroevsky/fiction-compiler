#!/usr/bin/env python3
"""Create, resume, inspect, and append evidence to scene operational runs (ADR 0039)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import run_manifest  # noqa: E402
from fiction_compiler.workspace import project_dir  # noqa: E402


def _emit(value: dict) -> int:
    print(json.dumps(value, indent=2, ensure_ascii=False))
    return 1 if "error" in value or value.get("status") == "invalid" else 0


def _step(value: str) -> dict:
    parts = value.split(":", 2)
    if len(parts) < 2:
        raise argparse.ArgumentTypeError("step must be STEP_ID:PHASE[:DESCRIPTION]")
    result = {"step_id": parts[0], "phase": parts[1]}
    if len(parts) == 3 and parts[2]:
        result["description"] = parts[2]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record/resume a scene's operational evidence.")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--project", required=True)
    start.add_argument("--scene", required=True)
    start.add_argument("--step", action="append", type=_step, required=True,
                       help="STEP_ID:PHASE[:DESCRIPTION], repeat in planned order")
    start.add_argument("--run-id", help="reuse only to idempotently resume the same manifest")
    start.add_argument("--max-operations", type=int)
    start.add_argument("--max-total-tokens", type=int)
    start.add_argument("--max-cost-usd", type=float)

    status = sub.add_parser("status")
    status.add_argument("--project", required=True)
    status.add_argument("--scene", required=True)
    status.add_argument("--run", required=True)

    budget = sub.add_parser("budget")
    budget.add_argument("--project", required=True)
    budget.add_argument("--scene", required=True)
    budget.add_argument("--run", required=True)
    budget.add_argument("--estimated-total-tokens", type=int)
    budget.add_argument("--estimated-cost-usd", type=float)

    record = sub.add_parser("record")
    record.add_argument("--project", required=True)
    record.add_argument("--scene", required=True)
    record.add_argument("--run", required=True)
    record.add_argument("--step", required=True)
    record.add_argument("--status", required=True, choices=["success", "failure"])
    record.add_argument("--candidate")
    record.add_argument("--executor-kind", choices=["compiler", "human", "external_model", "role_runner", "unknown"])
    record.add_argument("--provider")
    record.add_argument("--model")
    record.add_argument("--provider-request-id")
    record.add_argument("--response-model")
    record.add_argument("--finish-reason")
    record.add_argument("--input-tokens", type=int)
    record.add_argument("--output-tokens", type=int)
    record.add_argument("--total-tokens", type=int)
    record.add_argument("--cost-usd", type=float)
    record.add_argument("--latency-ms", type=float)
    record.add_argument("--failure-reason")
    record.add_argument("--idempotency-key")
    record.add_argument("--metadata-json", default="{}")

    link = sub.add_parser("link-review")
    link.add_argument("--project", required=True)
    link.add_argument("--scene", required=True)
    link.add_argument("--run", required=True)
    link.add_argument("--step", required=True)
    link.add_argument("--review-run", required=True)
    link.add_argument("--cost-usd", type=float)
    link.add_argument("--candidate", help="needed only if the blinded review hash is ambiguous/stale")

    args = parser.parse_args()
    project = project_dir(args.project)
    if args.command == "start":
        budgets = {
            key: value for key, value in {
                "max_operations": args.max_operations,
                "max_total_tokens": args.max_total_tokens,
                "max_cost_usd": args.max_cost_usd,
            }.items() if value is not None
        }
        return _emit(run_manifest.start(project, args.scene, args.step, budgets, args.run_id))
    if args.command == "status":
        return _emit(run_manifest.status(project, args.scene, args.run))
    if args.command == "budget":
        return _emit(run_manifest.check_budget(
            project, args.scene, args.run,
            estimated_total_tokens=args.estimated_total_tokens,
            estimated_cost_usd=args.estimated_cost_usd,
        ))
    if args.command == "link-review":
        return _emit(run_manifest.link_review_attempt(
            project, args.scene, args.run, args.step, args.review_run,
            cost_usd=args.cost_usd, candidate=args.candidate,
        ))
    try:
        metadata = json.loads(args.metadata_json)
    except json.JSONDecodeError as exc:
        print(f"invalid --metadata-json: {exc}", file=sys.stderr)
        return 2
    if not isinstance(metadata, dict):
        print("--metadata-json must decode to an object", file=sys.stderr)
        return 2
    return _emit(run_manifest.record_operation(
        project, args.scene, args.run, args.step, args.status, candidate=args.candidate,
        executor_kind=args.executor_kind, provider=args.provider, model=args.model,
        provider_request_id=args.provider_request_id, response_model=args.response_model,
        finish_reason=args.finish_reason, input_tokens=args.input_tokens,
        output_tokens=args.output_tokens, total_tokens=args.total_tokens,
        cost_usd=args.cost_usd, latency_ms=args.latency_ms, failure_reason=args.failure_reason,
        idempotency_key=args.idempotency_key, metadata=metadata or None,
    ))


if __name__ == "__main__":
    raise SystemExit(main())
