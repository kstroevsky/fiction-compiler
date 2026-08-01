"""Agent-legible critique lifecycle: record a gate-bound critique, and inspect gate-readiness.

The promotion gate's evidence — the ``scenes/<scene>/critiques/*.json`` files, each bound to the
candidate it judged by ``candidate_sha256`` — was, until now, produced entirely by the model
hand-writing JSON: copying the sha from lint output, setting the right ``audit_class``, keeping the
verdict consistent with the finding severities, and choosing a filename. That is the harness's most
error-prone manual seam: a single wrong hex digit silently denies the critique at the gate, and a
``pass`` accidentally carrying a ``material`` finding is a contradiction the gate rejects only much
later. Per the agents-best-practices rule *"repeated failures should become tools; make validation
signals legible without manual copy"*, this module turns that toil into two mechanical tools:

- ``record_critique`` stamps the sha from the *actual* candidate bytes, derives ``audit_class`` from
  the critic, validates against ``critique.schema``, and refuses a verdict/severity contradiction
  with a model-readable remediation message — so the bad artifact cannot be written in the first place.
- ``scene_status`` is a read-only inspector that answers *"would ``promote`` succeed for this
  candidate, and if not, exactly why?"* by running the real gate logic without mutating anything —
  the validator-with-remediation pattern, shifted left of the state change.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import integrity, schema
from .promote import (AUDIT_CLASS_BY_CRITIC, BLOCKING_SEVERITIES, _collect_binding,
                      audit_class_of, evaluate_audit_gate)


def consistency_problem(verdict: str, findings: list[dict]) -> str | None:
    """The one rule the promotion gate also enforces, surfaced at write time.

    A ``pass`` may not carry a ``material``/``fatal`` finding. Returns a model-readable remediation
    string, or ``None`` when the verdict and severities are consistent.
    """
    blocking = sorted({f.get("severity") for f in findings} & BLOCKING_SEVERITIES)
    if verdict == "pass" and blocking:
        return (f"verdict 'pass' contradicts {blocking} finding(s): a pass may not carry a "
                "material/fatal finding. Fix: set verdict to 'revise', or downgrade the finding to "
                "'minor' if it is genuinely non-blocking.")
    return None


def _load_critiques(scene_dir: Path) -> list[tuple[str, dict | None, str | None]]:
    crit_dir = scene_dir / "critiques"
    loaded: list[tuple[str, dict | None, str | None]] = []
    if crit_dir.exists():
        for path in sorted(crit_dir.glob("*.json")):
            try:
                loaded.append((path.name, json.loads(path.read_text(encoding="utf-8")), None))
            except json.JSONDecodeError as exc:
                loaded.append((path.name, None, str(exc)))
    return loaded


def record_critique(project: Path, scene_id: str, candidate: str, critic: str, verdict: str,
                    findings: list[dict] | None = None, confidence: float = 1.0,
                    audit_class: str | None = None, filename: str | None = None) -> dict:
    """Write a schema-valid, candidate-bound critique. Stamps the sha; refuses inconsistencies.

    ``candidate`` is a candidate filename under ``scenes/<scene_id>/candidates/`` (its sha is stamped
    from the bytes on disk), or the scene id itself for the candidate-independent hard audit (no sha).
    ``audit_class`` defaults to the critic's class from the triple-audit map.
    """
    findings = findings or []
    scene_dir = project / "scenes" / scene_id
    is_scene_level = candidate == scene_id
    candidate_name, candidate_sha256 = candidate, None
    if not is_scene_level:
        cand_path = Path(candidate)
        if not cand_path.is_absolute() and not cand_path.exists():
            cand_path = scene_dir / "candidates" / candidate
        if not cand_path.exists():
            return {"error": f"candidate not found: {candidate}"}
        if not cand_path.resolve().is_relative_to(project.resolve()):
            return {"error": "candidate must live inside the project directory"}
        candidate_name = cand_path.name
        candidate_sha256 = integrity.sha256_file(cand_path)

    problem = consistency_problem(verdict, findings)
    if problem:
        return {"error": problem}

    cls = audit_class or AUDIT_CLASS_BY_CRITIC.get(critic)
    critique: dict = {"candidate": candidate_name, "critic": critic, "verdict": verdict,
                      "confidence": confidence, "findings": findings}
    if cls:
        critique["audit_class"] = cls
    if candidate_sha256:
        critique["candidate_sha256"] = candidate_sha256

    errors = schema.validate_named(critique, "critique")
    if errors:
        return {"error": "invalid critique (fix and re-record): " + "; ".join(errors)}

    stem = filename or f"{critic}-{(scene_id if is_scene_level else Path(candidate_name).stem)}"
    if not stem.endswith(".json"):
        stem += ".json"
    crit_dir = scene_dir / "critiques"
    crit_dir.mkdir(parents=True, exist_ok=True)
    out = crit_dir / stem
    out.write_text(json.dumps(critique, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "written": str(out.relative_to(project)),
        "candidate": candidate_name,
        "candidate_sha256": candidate_sha256,
        "audit_class": cls,
        "verdict": verdict,
        "findings": len(findings),
    }


def scene_status(project: Path, scene_id: str, candidate: str) -> dict:
    """Read-only: would ``promote`` accept this candidate, and if not, exactly why?

    Runs the real audit-gate logic (candidate-bound, per triple-audit class) plus the structural
    preconditions promotion checks, without touching canon or the manuscript. The ``audit_gate.reasons``
    are the same blocking messages ``promote`` would raise — surfaced before the state change.
    """
    scene_dir = project / "scenes" / scene_id
    spec_path = scene_dir / "spec.json"
    delta_path = scene_dir / "state-delta.json"

    cand_path = Path(candidate)
    if not cand_path.is_absolute() and not cand_path.exists():
        cand_path = scene_dir / "candidates" / candidate
    if not cand_path.exists():
        return {"error": f"candidate not found: {candidate}"}
    if not cand_path.resolve().is_relative_to(project.resolve()):
        return {"error": "candidate must live inside the project directory"}
    candidate_name = cand_path.name
    candidate_sha256 = integrity.sha256_file(cand_path)

    loaded = _load_critiques(scene_dir)
    binding, _ = _collect_binding(loaded, candidate_name, scene_id)
    reasons = evaluate_audit_gate(loaded, candidate_name, candidate_sha256, scene_id)

    structural: list[str] = []
    if not spec_path.exists():
        structural.append("spec.json is missing")
    if not delta_path.exists():
        structural.append("state-delta.json is required before promotion")
    else:
        delta = json.loads(delta_path.read_text(encoding="utf-8"))
        d_errs = schema.validate_named(delta, "state-delta")
        if d_errs:
            structural.append("state-delta.json is invalid: " + "; ".join(d_errs))
        elif delta.get("scene_id") != scene_id:
            structural.append(f"state-delta scene_id {delta.get('scene_id')!r} != {scene_id!r}")

    all_reasons = structural + reasons
    return {
        "scene_id": scene_id,
        "candidate": candidate_name,
        "candidate_sha256": candidate_sha256,
        "has_spec": spec_path.exists(),
        "has_state_delta": delta_path.exists(),
        "critiques": [
            {"file": label, "critic": (c or {}).get("critic"), "audit_class": audit_class_of(c or {}),
             "verdict": (c or {}).get("verdict")}
            for label, c, _ in loaded
        ],
        "binding_critiques": [
            {"file": label, "critic": c.get("critic"), "audit_class": cls, "verdict": c.get("verdict")}
            for label, c, cls in binding
        ],
        "audit_gate": {"ready": not all_reasons, "reasons": all_reasons},
        "promoted": (project / "manuscript" / "chapters" / f"{scene_id}.md").exists(),
    }
