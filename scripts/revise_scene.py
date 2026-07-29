#!/usr/bin/env python3
"""Drive one turn of the STORY's PDCA revision loop over a scene.

    python3 scripts/revise_scene.py PROJECT SCENE --before old.md --after new.md \
            [--target defaultness] [--record] \
            [--before-critiques 'critiques/*.json'] [--after-critiques ...]

CHECK is deterministic here: the two prose candidates are linted for defaultness, and any
extra critique JSONs (e.g. from the LLM literary critics) are merged in. ACT applies the
operating contract's accept/stop rules. `--record` appends the iteration to the scene's
revision-log.jsonl so the loop's own stop conditions (iterations, attempts) are grounded in
history rather than vibes. Exit code 0 only on ACCEPT.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import defaultness, revision  # noqa: E402


def resolve_project(arg: str) -> Path:
    return (ROOT / arg).resolve() if not Path(arg).is_absolute() else Path(arg)


def resolve_candidate(project: Path, scene: str, arg: str) -> Path:
    candidate = Path(arg)
    if candidate.exists():
        return candidate
    in_scene = project / "scenes" / scene / "candidates" / arg
    if in_scene.exists():
        return in_scene
    raise SystemExit(f"Candidate not found: {arg}")


def load_critiques(patterns: list[str] | None) -> list[dict]:
    critiques: list[dict] = []
    for pattern in patterns or []:
        for path in sorted(glob.glob(pattern)):
            critiques.append(json.loads(Path(path).read_text(encoding="utf-8")))
    return critiques


def main() -> int:
    parser = argparse.ArgumentParser(description="Story-level PDCA revision check")
    parser.add_argument("project_dir")
    parser.add_argument("scene_id")
    parser.add_argument("--before", required=True, help="prior candidate (file or candidates/<name>)")
    parser.add_argument("--after", required=True, help="revised candidate")
    parser.add_argument("--target", help="dimension the revision targets, e.g. defaultness, knowledge")
    parser.add_argument("--before-critiques", nargs="*", help="extra critique JSON globs for the prior version")
    parser.add_argument("--after-critiques", nargs="*", help="extra critique JSON globs for the revised version")
    parser.add_argument("--max-iter", type=int, default=3)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--record", action="store_true", help="append this iteration to revision-log.jsonl")
    args = parser.parse_args()

    project = resolve_project(args.project_dir)
    scene_dir = project / "scenes" / args.scene_id
    before_path = resolve_candidate(project, args.scene_id, args.before)
    after_path = resolve_candidate(project, args.scene_id, args.after)

    before = [defaultness.lint_file(before_path), *load_critiques(args.before_critiques)]
    after = [defaultness.lint_file(after_path), *load_critiques(args.after_critiques)]

    history = revision.revision_history(scene_dir)
    iteration = len(history) + 1
    attempts_at_layer = 1 + sum(1 for h in history if h.get("target_dimension") == args.target)

    outcome = revision.evaluate_revision(
        before, after,
        target_dimension=args.target,
        iteration=iteration,
        max_iterations=args.max_iter,
        max_attempts_per_layer=args.max_attempts,
        attempts_at_current_layer=attempts_at_layer,
    )
    b, a = revision.tally(before), revision.tally(after)

    print(f"iteration {iteration} | target: {args.target or '(serious findings)'}")
    print(f"  before  fatal={b['fatal']} material={b['material']} minor={b['minor']}")
    print(f"  after   fatal={a['fatal']} material={a['material']} minor={a['minor']}")
    print(f"  target  {outcome.target_before} -> {outcome.target_after}"
          f"   fixed={outcome.fixed_dimensions or '-'}   regressions={outcome.material_regressions or '-'}")
    print(f"  DECISION: {outcome.decision.upper()} — {outcome.reason}")

    if args.record:
        path = revision.log_revision(scene_dir, {
            "iteration": iteration,
            "before": str(before_path.name),
            "after": str(after_path.name),
            "target_dimension": args.target,
            "counts": outcome.counts(b, a),
            "decision": outcome.decision,
            "reason": outcome.reason,
        })
        print(f"  recorded -> {path.relative_to(project)}")

    return 0 if outcome.decision == revision.ACCEPT else 1


if __name__ == "__main__":
    raise SystemExit(main())
