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


_SEV_RANK = {"minor": 0, "material": 1, "fatal": 2}


def _normalize_evidence(text: object) -> str:
    return " ".join(str(text).lower().split())


def finding_fingerprint(finding: dict) -> tuple[str, str]:
    """Stable identity of a finding: dimension + normalized evidence span.

    Deliberately independent of severity, so the *same* defect can be tracked as it is fixed,
    persists, or worsens across a revision — the review's requirement that acceptance operate on
    issue identity, not raw counts.
    """
    return (finding.get("dimension", "?"), _normalize_evidence(finding.get("evidence", "")))


def diff_findings(before: list[dict], after: list[dict]) -> dict:
    """Classify findings by identity: fixed / persisted / worsened / newly_introduced."""
    def index(items: list[dict]) -> dict[tuple[str, str], dict]:
        idx: dict[tuple[str, str], dict] = {}
        for finding in _flatten(items):
            fp = finding_fingerprint(finding)
            if fp not in idx or _SEV_RANK.get(finding.get("severity"), 0) > _SEV_RANK.get(idx[fp].get("severity"), 0):
                idx[fp] = finding  # keep the worst severity seen for a fingerprint
        return idx

    before_idx, after_idx = index(before), index(after)
    fixed = [before_idx[fp] for fp in before_idx if fp not in after_idx]
    newly_introduced = [after_idx[fp] for fp in after_idx if fp not in before_idx]
    persisted, worsened = [], []
    for fp, finding in after_idx.items():
        if fp in before_idx:
            if _SEV_RANK.get(finding.get("severity"), 0) > _SEV_RANK.get(before_idx[fp].get("severity"), 0):
                worsened.append(finding)
            else:
                persisted.append(finding)
    return {"fixed": fixed, "persisted": persisted, "worsened": worsened, "newly_introduced": newly_introduced}


def _compact(findings: list[dict]) -> list[dict]:
    return [{"dimension": f.get("dimension"), "severity": f.get("severity"), "evidence": f.get("evidence")}
            for f in findings]


def _waiver_index(waivers: list[dict] | None) -> dict[tuple[str, str], dict]:
    """Index waivers by the finding fingerprint they excuse. Each waiver should carry a reason."""
    return {(w.get("dimension", "?"), _normalize_evidence(w.get("evidence", ""))): w
            for w in (waivers or [])}


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
    # Identity-based diff (fingerprint = dimension + normalized evidence), not just counts.
    fixed_findings: list[dict] = field(default_factory=list)
    persisted_findings: list[dict] = field(default_factory=list)
    worsened_findings: list[dict] = field(default_factory=list)
    new_findings: list[dict] = field(default_factory=list)
    waived_findings: list[dict] = field(default_factory=list)

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
    waivers: list[dict] | None = None,
) -> RevisionOutcome:
    """Decide the fate of one revision against the previous version's critiques.

    ``target_dimension`` is the defect the revision was meant to fix (e.g. "defaultness",
    "knowledge"). If omitted, the target is the total count of serious (material+fatal) findings.
    ``waivers`` are findings (by dimension + evidence) deliberately accepted with a reason; a waived
    finding neither blocks acceptance nor counts as a regression.
    """
    b, a = tally(before), tally(after)

    if target_dimension:
        target_before = b["all_by_dimension"].get(target_dimension, 0)
        target_after = a["all_by_dimension"].get(target_dimension, 0)
    else:
        target_before = b["fatal"] + b["material"]
        target_after = a["fatal"] + a["material"]

    fatal_regressed = a["fatal"] > b["fatal"]

    # Regression and acceptance are judged by finding IDENTITY, not raw counts. A finding whose
    # fingerprint matches a waiver is deliberately accepted (reason recorded) and neither blocks nor
    # counts as a regression; everything else is judged by identity, so e.g. two minors replaced by
    # one *new* material finding is a regression even though the raw count fell.
    diff = diff_findings(before, after)
    waiver_index = _waiver_index(waivers)

    def _waived(finding: dict) -> bool:
        return finding_fingerprint(finding) in waiver_index

    new_serious = [f for f in diff["newly_introduced"] if f.get("severity") in _SERIOUS and not _waived(f)]
    worsened_serious = [f for f in diff["worsened"] if f.get("severity") in _SERIOUS and not _waived(f)]
    waived = [f for f in diff["newly_introduced"] + diff["worsened"] if _waived(f)]
    regression_dims = sorted({f.get("dimension") for f in new_serious + worsened_serious})
    fixed = sorted({f.get("dimension") for f in diff["fixed"] if f.get("severity") in _SERIOUS})

    # Acceptance operates on issue IDENTITY: the target defect must have a finding actually resolved
    # (by fingerprint) with no unwaived serious regression in that dimension.
    if target_dimension:
        target_fixed = [f for f in diff["fixed"] if f.get("dimension") == target_dimension]
        target_regressed = [f for f in new_serious + worsened_serious if f.get("dimension") == target_dimension]
        target_resolved = bool(target_fixed) and not target_regressed
    else:
        target_resolved = any(f.get("severity") in _SERIOUS for f in diff["fixed"]) \
            and not new_serious and not worsened_serious

    if fatal_regressed or new_serious or worsened_serious:
        decision = REJECT_REGRESSION
        where = [f"new {f.get('severity')} {f.get('dimension')}" for f in new_serious]
        where += [f"worsened {f.get('dimension')}" for f in worsened_serious]
        if fatal_regressed and not where:
            where = ["fatal count"]
        reason = f"revision caused a material/fatal regression by identity in {where}; do not accept"
    elif a["fatal"] == 0 and target_resolved:
        label = target_dimension or "serious findings"
        waived_note = f" ({len(waived)} waived)" if waived else ""
        reason = f"target '{label}' resolved by identity ({target_before}->{target_after} count), no unwaived regressions{waived_note}"
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
        material_regressions=regression_dims,
        fixed_dimensions=fixed,
        fixed_findings=_compact(diff["fixed"]),
        persisted_findings=_compact(diff["persisted"]),
        worsened_findings=_compact(diff["worsened"]),
        new_findings=_compact(diff["newly_introduced"]),
        waived_findings=[{**_compact([f])[0], "reason": waiver_index[finding_fingerprint(f)].get("reason")}
                         for f in waived],
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
