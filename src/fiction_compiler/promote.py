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
from datetime import datetime, timezone
from pathlib import Path

from . import integrity, schema
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


def _is_scene_level_hard(critique: dict, cls: str | None, scene_id: str) -> bool:
    """The hard audit is candidate-independent: its `candidate` is the scene id, not a prose file."""
    return cls == "hard" and str(critique.get("candidate")) == scene_id


def evaluate_audit_gate(loaded: list[tuple[str, dict | None, str | None]],
                        candidate_name: str, candidate_sha256: str, scene_id: str) -> list[str]:
    """Return blocking reasons (empty == the candidate may be promoted).

    Enforces, over the critiques that actually judge this candidate: schema validity, verdict/
    findings consistency, content-hash binding, and full triple-audit coverage by *clean* critiques.
    A candidate-specific critique counts toward its class only if it carries a ``candidate_sha256``
    equal to the promoted candidate's hash, so a critique cannot be credited for prose it never saw.
    The scene-level hard audit is candidate-independent and is exempt from the hash check.
    """
    binding, reasons = _collect_binding(loaded, candidate_name, scene_id)
    covered: set[str] = set()
    for label, critique, cls in binding:
        errs = schema.validate_named(critique, "critique")
        if errs:
            reasons.append(f"{label}: invalid critique ({'; '.join(errs)})")
        reasons.extend(_consistency_problems(critique, label))

        scene_level_hard = _is_scene_level_hard(critique, cls, scene_id)
        recorded_hash = critique.get("candidate_sha256")
        if not scene_level_hard and recorded_hash is not None and recorded_hash != candidate_sha256:
            reasons.append(
                f"{label}: candidate_sha256 {recorded_hash[:12]}… does not match the promoted "
                f"candidate {candidate_sha256[:12]}… — this critique judged different bytes"
            )
        hash_ok = scene_level_hard or recorded_hash == candidate_sha256
        if cls and critique_is_clean(critique) and hash_ok:
            covered.add(cls)
    for required in REQUIRED_AUDIT_CLASSES:
        if required not in covered:
            reasons.append(f"no clean, candidate-bound {required} audit found for {candidate_name!r}")
    return reasons


def promote_candidate(project: Path, scene_id: str, candidate_file: str, *,
                      approved_by: str | None = None, rubric_version: str | None = None) -> dict:
    scene_dir = project / "scenes" / scene_id
    candidate = Path(candidate_file)
    if not candidate.is_absolute():
        candidate = scene_dir / "candidates" / candidate
    if not candidate.exists():
        raise ValueError(f"Candidate not found: {candidate}")
    # Confinement: a candidate must live inside the project (an absolute path from an agent may not
    # reach outside it). Defence in depth alongside the MCP-boundary path checks.
    if not candidate.resolve().is_relative_to(project.resolve()):
        raise ValueError("candidate must live inside the project directory")
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

    # Audit gate: the reviewed critiques must actually clear *these* candidate bytes. Load them once,
    # run the gate against the candidate's hash, and refuse *before* any write so a failure is inert.
    candidate_sha256 = integrity.sha256_file(candidate)
    loaded: list[tuple[str, dict | None, str | None]] = []
    for path in critiques:
        try:
            loaded.append((path.name, json.loads(path.read_text(encoding="utf-8")), None))
        except json.JSONDecodeError as exc:
            loaded.append((path.name, None, str(exc)))
    gate_reasons = evaluate_audit_gate(loaded, candidate.name, candidate_sha256, scene_id)
    if gate_reasons:
        raise ValueError(
            f"Audit gate failed for {scene_id} candidate {candidate.name}:\n  - "
            + "\n  - ".join(gate_reasons)
        )
    binding, _ = _collect_binding(loaded, candidate.name, scene_id)

    # Human gate: if the project lists "promotion" in its human_gates, canon may not advance without a
    # recorded approver. Completes the reviewer's invariant — the exact candidate passed the exact
    # audits *under a recorded rubric and human gate* — and, like the audit gate, refuses before any write.
    brief_path = project / "brief" / "project.json"
    project_meta = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {}
    gate_required = "promotion" in project_meta.get("human_gates", [])
    if gate_required and not approved_by:
        raise ValueError(
            "human gate required: this project lists 'promotion' in human_gates; "
            "promote with approved_by=<approver> to record the approval"
        )

    # Canon hash chain: bind this delta to the exact prior canon state (see integrity.verify_canon).
    parent_canon_hash = integrity.canon_head(project)
    delta_sha256 = integrity.sha256_file(delta_path)
    resulting_canon_hash = integrity.link_hash(parent_canon_hash, scene_id, delta_sha256)

    target = project / "manuscript" / "chapters" / f"{scene_id}.md"
    index_path = project / "canon" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    accepted = list(index.get("accepted_state_deltas", []))
    if scene_id not in accepted:
        accepted.append(scene_id)
    index["accepted_state_deltas"] = sorted(set(accepted), key=scene_sort_key)

    decision = {
        "scene_id": scene_id,
        "candidate": str(candidate.relative_to(project)) if candidate.is_relative_to(project) else str(candidate),
        "candidate_sha256": candidate_sha256,
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "state_delta_sha256": delta_sha256,
        "parent_canon_hash": parent_canon_hash,
        "resulting_canon_hash": resulting_canon_hash,
        "rubric_version": rubric_version,
        "human_gate": {"required": gate_required, "approved": bool(approved_by), "approver": approved_by},
        "critique_files": [str(p.relative_to(project)) for p in critiques],
        # The subset the gate actually credited as evidence for *this* candidate — with each
        # critique's own hash — so the manifest shows exactly which audits cleared these bytes.
        "binding_critiques": [
            {"file": label, "critic": c.get("critic"), "audit_class": audit_class_of(c),
             "verdict": c.get("verdict"), "sha256": integrity.sha256_file(scene_dir / "critiques" / label)}
            for label, c, _ in binding
        ],
    }
    decision_file = project / "decisions" / f"promote-{scene_id}.json"

    # Atomic: hold a project lock and commit all three writes with rollback, so a crash or a
    # concurrent promotion cannot leave canon half-updated.
    with integrity.PromotionLock(project):
        batch = integrity.AtomicBatch()
        try:
            batch.write(target, candidate.read_bytes())
            batch.write(index_path, (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
            batch.write(decision_file, (json.dumps(decision, indent=2) + "\n").encode("utf-8"))
            batch.commit()
        except Exception:
            batch.rollback()
            raise

    return {
        "promoted_to": decision["promoted_to"],
        "accepted_state_deltas": index["accepted_state_deltas"],
        "decision_file": str(decision_file.relative_to(project)),
        "critique_files": decision["critique_files"],
        "resulting_canon_hash": resulting_canon_hash,
    }
