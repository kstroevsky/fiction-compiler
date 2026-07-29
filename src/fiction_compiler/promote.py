"""Promotion as a library function, shared by the CLI and the MCP tool.

Promotion is the one state-changing step in the story loop: it copies a reviewed candidate
into the manuscript and folds its accepted delta into the event-sourced canon. It refuses
unless the preconditions hold, so canon can only ever advance through reviewed work.

Two classes of precondition are enforced here:

- **Structural:** a spec exists, and a schema-valid ``state-delta.json`` whose ``scene_id`` matches.
- **Audit gate:** the triple-audit protocol from ``AGENTS.md`` is *enforced*, not just documented.
  The candidate being promoted must be backed by a clean **hard**, **literary**, and
  **defaultness** critique that actually judges *this* candidate. A critique whose ``verdict`` is
  not ``pass``, or that carries a ``material``/``fatal`` finding, blocks promotion; a critique that
  judges a *different* candidate is not counted as evidence for this one. This closes the gap the
  old gate left open — where any JSON file in ``critiques/`` (even one judging a different
  candidate, or reporting ``revise``) satisfied "at least one critique exists".

This slice deliberately does **not** yet hash artifacts or make the write atomic (see the roadmap /
ADR for the immutable-manifest slice). It closes the *enforcement* hole first.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import schema
from .state import scene_sort_key

# --- Audit gate ------------------------------------------------------------------------------
# Maps each critic to the triple-audit class it satisfies. Sourced from the triple-audit skill:
# hard = deterministic hard audit; defaultness = deterministic linter; literary = the LLM personas.
AUDIT_CLASS_BY_CRITIC: dict[str, str] = {
    "hard-audit": "hard",
    "defaultness-lint": "defaultness",
    "continuity-auditor": "literary",
    "character-simulator": "literary",
    "style-editor": "literary",
    "adversarial-reader": "literary",
}
REQUIRED_AUDIT_CLASSES: tuple[str, ...] = ("hard", "literary", "defaultness")
BLOCKING_SEVERITIES: frozenset[str] = frozenset({"material", "fatal"})


def audit_class_of(critique: dict) -> str | None:
    """The triple-audit class a critique belongs to.

    Prefers an explicit ``audit_class`` field (forward-looking); falls back to the critic map so
    the legacy critiques already on disk still classify.
    """
    explicit = critique.get("audit_class")
    if explicit in REQUIRED_AUDIT_CLASSES:
        return explicit
    return AUDIT_CLASS_BY_CRITIC.get(critique.get("critic"))


def _blocking_findings(critique: dict) -> set[str]:
    return {f.get("severity") for f in critique.get("findings", [])} & BLOCKING_SEVERITIES


def critique_is_clean(critique: dict) -> bool:
    """A critique clears its gate only when it passed *and* carries no blocking finding."""
    return critique.get("verdict") == "pass" and not _blocking_findings(critique)


def _consistency_problems(critique: dict, label: str) -> list[str]:
    """Verdict/findings problems that must block promotion, with the critic named for evidence."""
    problems: list[str] = []
    verdict = critique.get("verdict")
    if verdict is None:
        return [f"{label}: critique has no verdict"]
    blocking = _blocking_findings(critique)
    if verdict == "pass" and blocking:
        problems.append(
            f"{label}: verdict 'pass' contradicts {sorted(blocking)} finding(s) "
            "— a pass may not carry a material/fatal finding"
        )
    if verdict != "pass":
        problems.append(f"{label}: verdict {verdict!r} is unresolved (not 'pass')")
    return problems


def _collect_binding(loaded: list[tuple[str, dict | None, str | None]],
                     candidate_name: str, scene_id: str) -> tuple[list[tuple[str, dict, str | None]], list[str]]:
    """Split loaded critiques into those that bind to this candidate, plus any parse errors.

    A critique binds to the candidate when it judges that exact candidate file. The hard audit is
    candidate-independent (it audits the scene spec + delta), so its ``candidate`` is the scene id;
    it binds to every candidate of the scene. Critiques judging a *different* candidate are ignored.
    """
    binding: list[tuple[str, dict, str | None]] = []
    parse_errors: list[str] = []
    for label, critique, err in loaded:
        if err is not None:
            parse_errors.append(f"{label}: not valid JSON ({err})")
            continue
        cls = audit_class_of(critique)
        cand = str(critique.get("candidate", ""))
        is_scene_level_hard = cls == "hard" and cand == scene_id
        if is_scene_level_hard or Path(cand).name == candidate_name:
            binding.append((label, critique, cls))
    return binding, parse_errors


def evaluate_audit_gate(loaded: list[tuple[str, dict | None, str | None]],
                        candidate_name: str, scene_id: str) -> list[str]:
    """Return blocking reasons (empty == the candidate may be promoted).

    Enforces, over the critiques that actually judge this candidate: schema validity, verdict/
    findings consistency, and full triple-audit coverage by *clean* critiques.
    """
    binding, reasons = _collect_binding(loaded, candidate_name, scene_id)
    covered: set[str] = set()
    for label, critique, cls in binding:
        errs = schema.validate_named(critique, "critique")
        if errs:
            reasons.append(f"{label}: invalid critique ({'; '.join(errs)})")
        reasons.extend(_consistency_problems(critique, label))
        if cls and critique_is_clean(critique):
            covered.add(cls)
    for required in REQUIRED_AUDIT_CLASSES:
        if required not in covered:
            reasons.append(f"no clean {required} audit found for candidate {candidate_name!r}")
    return reasons


def promote_candidate(project: Path, scene_id: str, candidate_file: str) -> dict:
    scene_dir = project / "scenes" / scene_id
    candidate = Path(candidate_file)
    if not candidate.is_absolute():
        candidate = scene_dir / "candidates" / candidate
    if not candidate.exists():
        raise ValueError(f"Candidate not found: {candidate}")
    if not (scene_dir / "spec.json").exists():
        raise ValueError("Scene spec is missing")

    critiques = sorted((scene_dir / "critiques").glob("*.json")) if (scene_dir / "critiques").exists() else []
    if not critiques:
        raise ValueError("No critique JSON files found; run the triple audit first")

    delta_path = scene_dir / "state-delta.json"
    if not delta_path.exists():
        raise ValueError("state-delta.json is required before promotion")
    delta = json.loads(delta_path.read_text(encoding="utf-8"))
    errors = schema.validate_named(delta, "state-delta")
    if errors:
        raise ValueError("state-delta.json is invalid: " + "; ".join(errors))
    if delta.get("scene_id") != scene_id:
        raise ValueError(f"state-delta scene_id {delta.get('scene_id')!r} != {scene_id!r}")

    # Audit gate: the reviewed critiques must actually clear the candidate. Load them once, run the
    # gate, and refuse *before* touching the manuscript or canon so a failed gate leaves no trace.
    loaded: list[tuple[str, dict | None, str | None]] = []
    for path in critiques:
        try:
            loaded.append((path.name, json.loads(path.read_text(encoding="utf-8")), None))
        except json.JSONDecodeError as exc:
            loaded.append((path.name, None, str(exc)))
    gate_reasons = evaluate_audit_gate(loaded, candidate.name, scene_id)
    if gate_reasons:
        raise ValueError(
            f"Audit gate failed for {scene_id} candidate {candidate.name}:\n  - "
            + "\n  - ".join(gate_reasons)
        )
    binding, _ = _collect_binding(loaded, candidate.name, scene_id)

    target = project / "manuscript" / "chapters" / f"{scene_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidate, target)

    index_path = project / "canon" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    accepted = list(index.get("accepted_state_deltas", []))
    if scene_id not in accepted:
        accepted.append(scene_id)
    index["accepted_state_deltas"] = sorted(set(accepted), key=scene_sort_key)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    decision = {
        "scene_id": scene_id,
        "candidate": str(candidate.relative_to(project)) if candidate.is_relative_to(project) else str(candidate),
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "critique_files": [str(p.relative_to(project)) for p in critiques],
        # The subset the gate actually credited as evidence for *this* candidate, so the decision
        # record shows which audits cleared it rather than every file that happened to be present.
        "binding_critiques": [
            {"file": label, "critic": c.get("critic"), "audit_class": audit_class_of(c), "verdict": c.get("verdict")}
            for label, c, _ in binding
        ],
    }
    decision_file = project / "decisions" / f"promote-{scene_id}.json"
    decision_file.parent.mkdir(parents=True, exist_ok=True)
    decision_file.write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")

    return {
        "promoted_to": decision["promoted_to"],
        "accepted_state_deltas": index["accepted_state_deltas"],
        "decision_file": str(decision_file.relative_to(project)),
        "critique_files": decision["critique_files"],
    }
