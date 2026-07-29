"""The STORY's own PDCA revision loop (distinct from the framework's).

There are two self-improvement loops in this system and they must never be conflated:

  * FRAMEWORK loop  — improves prompts/rubrics/schemas (the `retrospective` skill +
                      `constitution/change-policy.md`). It changes the *compiler*.
  * STORY loop      — improves the *manuscript*: plan a target defect, draft a revision,
                      CHECK against the audits, ACT (accept / route lower / stop). This module.

The drafting (DO) is the LLM's job. What must be deterministic is the CHECK and the ACT: a
revision is accepted **only when it improves the target defect without a material regression
elsewhere**, and the loop must **stop** rather than drift toward the evaluator's preferred
blandness. Both rules come straight from the operating contract; here they are code, so the
loop cannot congratulate itself.

`evaluate_revision` takes the critiques (deterministic and/or LLM) of the previous version and
the revised version and returns a decision plus its evidence. `log_revision` records each
iteration to `scenes/<id>/revision-log.jsonl` for observability and for the stop conditions.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Decisions
ACCEPT = "accept"
REJECT_REGRESSION = "reject_regression"
CONTINUE = "continue"
ESCALATE_LAYER = "escalate_layer"
STOP_NO_PROGRESS = "stop_no_progress"

_SERIOUS = {"material", "fatal"}


def _flatten(items: list[dict]) -> list[dict]:
    """Accept a list of critique dicts (each with 'findings') or a flat list of findings."""
    findings: list[dict] = []
    for item in items:
        if isinstance(item, dict) and "findings" in item:
            findings.extend(item["findings"])
        elif isinstance(item, dict):
            findings.append(item)
    return findings


def tally(items: list[dict]) -> dict:
    findings = _flatten(items)
    by_severity = Counter(f.get("severity", "minor") for f in findings)
    serious_by_dimension = Counter(
        f.get("dimension", "?") for f in findings if f.get("severity") in _SERIOUS
    )
    all_by_dimension = Counter(f.get("dimension", "?") for f in findings)
    return {
        "by_severity": by_severity,
        "serious_by_dimension": serious_by_dimension,
        "all_by_dimension": all_by_dimension,
        "fatal": by_severity.get("fatal", 0),
        "material": by_severity.get("material", 0),
        "minor": by_severity.get("minor", 0),
        "total": len(findings),
    }


@dataclass
class RevisionOutcome:
    decision: str
    reason: str
    target_dimension: str | None
    fatals_before: int
    fatals_after: int
    target_before: int
    target_after: int
    material_regressions: list[str] = field(default_factory=list)
    fixed_dimensions: list[str] = field(default_factory=list)

    def counts(self, before: dict, after: dict) -> dict:
        return {
            "before": {"fatal": before["fatal"], "material": before["material"], "minor": before["minor"]},
            "after": {"fatal": after["fatal"], "material": after["material"], "minor": after["minor"]},
        }


def evaluate_revision(
    before: list[dict],
    after: list[dict],
    *,
    target_dimension: str | None = None,
    iteration: int = 1,
    max_iterations: int = 3,
    max_attempts_per_layer: int = 2,
    attempts_at_current_layer: int = 1,
) -> RevisionOutcome:
    """Decide the fate of one revision against the previous version's critiques.

    ``target_dimension`` is the defect the revision was meant to fix (e.g. "defaultness",
    "knowledge"). If omitted, the target is the total count of serious (material+fatal) findings.
    """
    b, a = tally(before), tally(after)

    if target_dimension:
        target_before = b["all_by_dimension"].get(target_dimension, 0)
        target_after = a["all_by_dimension"].get(target_dimension, 0)
    else:
        target_before = b["fatal"] + b["material"]
        target_after = a["fatal"] + a["material"]
    target_improved = target_after < target_before

    dimensions = set(b["serious_by_dimension"]) | set(a["serious_by_dimension"])
    regressions = sorted(
        d for d in dimensions
        if d != target_dimension and a["serious_by_dimension"].get(d, 0) > b["serious_by_dimension"].get(d, 0)
    )
    fixed = sorted(
        d for d in dimensions
        if a["serious_by_dimension"].get(d, 0) < b["serious_by_dimension"].get(d, 0)
    )
    fatal_regressed = a["fatal"] > b["fatal"]

    if fatal_regressed or regressions:
        decision = REJECT_REGRESSION
        where = regressions or ["fatal count"]
        reason = f"revision caused a material/fatal regression in {where}; do not accept"
    elif a["fatal"] == 0 and target_improved:
        label = target_dimension or "serious findings"
        reason = f"target '{label}' improved {target_before}->{target_after}, no regressions, no fatals"
        decision = ACCEPT
    elif iteration >= max_iterations:
        decision = STOP_NO_PROGRESS
        reason = f"no acceptable improvement after {iteration} iteration(s); escalate to a human"
    elif attempts_at_current_layer >= max_attempts_per_layer:
        decision = ESCALATE_LAYER
        reason = (f"{attempts_at_current_layer} attempts at this layer without acceptance; "
                  f"route the defect one layer lower (see the defaultness repair ladder)")
    else:
        decision = CONTINUE
        reason = ("fatal findings remain; keep repairing" if a["fatal"] > 0
                  else "no regression, but the target did not improve yet; iterate")

    return RevisionOutcome(
        decision=decision,
        reason=reason,
        target_dimension=target_dimension,
        fatals_before=b["fatal"],
        fatals_after=a["fatal"],
        target_before=target_before,
        target_after=target_after,
        material_regressions=regressions,
        fixed_dimensions=fixed,
    )


def revision_history(scene_dir: Path) -> list[dict]:
    path = scene_dir / "revision-log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def log_revision(scene_dir: Path, record: dict) -> Path:
    scene_dir.mkdir(parents=True, exist_ok=True)
    path = scene_dir / "revision-log.jsonl"
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
