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

from . import acceptance, defaultness, hard_audit, integrity, review_policy, schema
from .state import scene_sort_key
from .workspace import resolve_scene_candidate, validate_scene_id

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
    "prose-audit": "hard",
}
REQUIRED_AUDIT_CLASSES: tuple[str, ...] = ("hard", "literary", "defaultness")
BLOCKING_SEVERITIES: frozenset[str] = frozenset({"material", "fatal"})


def audit_class_of(critique: dict) -> str | None:
    """The triple-audit class a critique belongs to.

    Authority comes only from the runtime-owned critic map. ``audit_class`` in an artifact is
    descriptive metadata and cannot grant a caller review authority.
    """
    # Authorization comes from the runtime-owned critic identity map, never a caller-provided
    # `audit_class`.  The explicit field remains useful descriptive metadata for legacy records.
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


def _freeze(path: Path, project: Path) -> dict:
    raw = path.read_bytes()
    return {
        "path": str(path.relative_to(project)),
        "sha256": integrity.sha256_bytes(raw),
        "text": raw.decode("utf-8"),
    }


def _policy_gate(
    loaded: list[tuple[str, dict | None, str | None]],
    candidate_name: str,
    candidate_sha256: str,
    scene_id: str,
    policy: dict,
) -> tuple[list[str], list[tuple[str, dict, str | None]]]:
    """Evaluate only review evidence that the declared policy actually requires."""
    binding, reasons = _collect_binding(loaded, candidate_name, scene_id)
    literary: list[dict] = []
    prose_audits: list[dict] = []
    for label, critique, cls in binding:
        errors = schema.validate_named(critique, "critique")
        if errors:
            reasons.append(f"{label}: invalid critique ({'; '.join(errors)})")
            continue
        recorded_hash = critique.get("candidate_sha256")
        if cls != "hard" and recorded_hash != candidate_sha256:
            reasons.append(f"{label}: critique is not bound to the frozen candidate bytes")
            continue
        if critique.get("critic") == "prose-audit":
            if critique_is_clean(critique) and recorded_hash == candidate_sha256:
                prose_audits.append(critique)
            continue
        if cls == "literary":
            reasons.extend(_consistency_problems(critique, label))
            provenance_ok = True
            if policy.get("require_runtime_provenance"):
                provenance = critique.get("provenance")
                provenance_ok = bool(
                    isinstance(provenance, dict)
                    and provenance.get("source") == "role_runner"
                    and provenance.get("role") == critique.get("critic")
                    and provenance.get("candidate_sha256") == candidate_sha256
                    and isinstance(provenance.get("packet_sha256"), str)
                )
                if not provenance_ok:
                    reasons.append(
                        f"{label}: literary review lacks matching runtime role-runner provenance"
                    )
            if critique_is_clean(critique) and recorded_hash == candidate_sha256 and provenance_ok:
                literary.append(critique)

    minimum = int(policy.get("minimum_literary_reviews", 0))
    if len(literary) < minimum:
        reasons.append(
            f"review policy requires {minimum} clean candidate-bound literary review(s); "
            f"found {len(literary)}"
        )
    seen_roles = {str(item.get("critic")) for item in literary}
    for role in policy.get("required_literary_roles", []):
        if role not in seen_roles:
            reasons.append(f"review policy requires a clean {role!r} review on these candidate bytes")
    if policy.get("require_prose_audit") and not prose_audits:
        reasons.append("review policy requires a clean candidate-bound prose-audit")
    return reasons, binding


def _materialize_snapshot(project: Path, object_id: str, snapshot: dict) -> dict:
    """Regenerate non-authoritative manuscript/decision views from one accepted object."""
    scene_id = str(snapshot["scene_id"])
    candidate_bytes = acceptance.frozen_bytes(snapshot, "candidate")
    target = project / "manuscript" / "chapters" / f"{scene_id}.md"
    acceptance.atomic_write(target, candidate_bytes)

    decision_file = project / "decisions" / f"promote-{scene_id}.json"
    previous = {}
    if decision_file.exists():
        try:
            previous = json.loads(decision_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    binding = snapshot.get("binding_critiques", [])
    decision = {
        "scene_id": scene_id,
        "candidate": snapshot["candidate"]["path"],
        "candidate_sha256": snapshot["candidate"]["sha256"],
        "promoted_to": str(target.relative_to(project)),
        "promoted_at": previous.get("promoted_at") or datetime.now(timezone.utc).isoformat(),
        "state_delta_sha256": snapshot["state_delta"]["sha256"],
        "parent_canon_hash": snapshot["parent_canon_hash"],
        "resulting_canon_hash": snapshot["resulting_canon_hash"],
        "acceptance_object": object_id,
        "review_policy": {
            "id": snapshot["review_policy"]["id"],
            "sha256": snapshot["review_policy"]["artifact"]["sha256"],
        },
        "rubric_version": snapshot.get("rubric_version"),
        "human_gate": snapshot.get("human_gate", {}),
        "critique_files": [item["path"] for item in binding],
        "binding_critiques": [
            {
                "file": item["path"],
                "critic": item.get("critic"),
                "audit_class": item.get("audit_class"),
                "verdict": item.get("verdict"),
                "sha256": item["sha256"],
            }
            for item in binding
        ],
    }
    acceptance.atomic_write(
        decision_file, (json.dumps(decision, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    return decision


def promote_candidate(project: Path, scene_id: str, candidate_file: str, *,
                      approved_by: str | None = None, rubric_version: str | None = None) -> dict:
    project = Path(project).resolve()
    validate_scene_id(scene_id)
    scene_dir = project / "scenes" / scene_id
    candidate = resolve_scene_candidate(project, scene_id, candidate_file)

    # The lock begins before any mutable promotion input is read. A competing promotion therefore
    # cannot validate against one canon head and commit against another.
    with integrity.PromotionLock(project):
        if not candidate.exists():
            raise ValueError(f"Candidate not found: {candidate}")
        spec_path = scene_dir / "spec.json"
        delta_path = scene_dir / "state-delta.json"
        if not spec_path.exists():
            raise ValueError("Scene spec is missing")
        if not delta_path.exists():
            raise ValueError("state-delta.json is required before promotion")

        candidate_artifact = _freeze(candidate, project)
        spec_artifact = _freeze(spec_path, project)
        delta_artifact = _freeze(delta_path, project)
        try:
            spec = json.loads(spec_artifact["text"])
            delta = json.loads(delta_artifact["text"])
        except json.JSONDecodeError as exc:
            raise ValueError(f"promotion input is not valid JSON: {exc}") from exc
        spec_errors = schema.validate_named(spec, "scene")
        if spec_errors:
            raise ValueError("spec.json is invalid: " + "; ".join(spec_errors))
        if spec.get("id") != scene_id:
            raise ValueError(f"spec scene id {spec.get('id')!r} != {scene_id!r}")
        delta_errors = schema.validate_named(delta, "state-delta")
        if delta_errors:
            raise ValueError("state-delta.json is invalid: " + "; ".join(delta_errors))
        if delta.get("scene_id") != scene_id:
            raise ValueError(f"state-delta scene_id {delta.get('scene_id')!r} != {scene_id!r}")

        index = acceptance.load_index(project)
        accepted = list(index.get("accepted_state_deltas", []))
        acceptance_objects = dict(index.get("acceptance_objects", {}))
        existing_object = acceptance_objects.get(scene_id)
        if scene_id in accepted:
            if not existing_object:
                raise ValueError(
                    f"{scene_id} is a legacy accepted scene; in-place re-promotion is forbidden. "
                    "Create an explicit revision branch/version instead."
                )
            existing = acceptance.load_object(project, existing_object)
            same = (
                existing.get("candidate", {}).get("sha256") == candidate_artifact["sha256"]
                and existing.get("spec", {}).get("sha256") == spec_artifact["sha256"]
                and existing.get("state_delta", {}).get("sha256") == delta_artifact["sha256"]
            )
            if not same:
                raise ValueError(
                    f"{scene_id} is already accepted with different frozen inputs; "
                    "create an explicit revision branch/version instead of rewriting canon"
                )
            decision = _materialize_snapshot(project, existing_object, existing)
            return {
                "promoted_to": decision["promoted_to"],
                "accepted_state_deltas": accepted,
                "decision_file": str(
                    (project / "decisions" / f"promote-{scene_id}.json").relative_to(project)
                ),
                "critique_files": decision["critique_files"],
                "resulting_canon_hash": existing["resulting_canon_hash"],
                "acceptance_object": existing_object,
                "idempotent": True,
            }
        if accepted and scene_sort_key(scene_id) <= max(map(scene_sort_key, accepted)):
            raise ValueError(
                f"{scene_id} would insert before or duplicate existing accepted history; "
                "branch/revision semantics are required"
            )

        policy, policy_artifact = review_policy.load(project)
        critiques = (
            sorted((scene_dir / "critiques").glob("*.json"))
            if (scene_dir / "critiques").exists()
            else []
        )
        loaded: list[tuple[str, dict | None, str | None]] = []
        raw_critiques: dict[str, dict] = {}
        for path in critiques:
            artifact = _freeze(path, project)
            raw_critiques[path.name] = artifact
            try:
                loaded.append((path.name, json.loads(artifact["text"]), None))
            except json.JSONDecodeError as exc:
                loaded.append((path.name, None, str(exc)))

        gate_reasons, binding = _policy_gate(
            loaded, candidate.name, candidate_artifact["sha256"], scene_id, policy
        )

        # Cheap deterministic checks are produced by the runtime itself. Stored JSON cannot spoof
        # them by claiming an audit_class.
        runtime_hard = hard_audit.audit_scene(project, scene_id)
        if runtime_hard.get("verdict") != "pass":
            gate_reasons.append(
                f"runtime hard audit returned {runtime_hard.get('verdict')!r}"
            )
        lint_findings = defaultness.lint_text(candidate_artifact["text"])
        lint_blocking = [
            finding for finding in lint_findings
            if finding.get("severity") in BLOCKING_SEVERITIES
        ]
        runtime_defaultness = {
            "candidate": candidate.name,
            "candidate_sha256": candidate_artifact["sha256"],
            "critic": "defaultness-lint",
            "audit_class": "defaultness",
            "verdict": "revise" if lint_blocking else "pass",
            "confidence": 0.7,
            "findings": lint_findings,
        }
        if policy.get("defaultness_mode") == "blocking" and lint_blocking:
            gate_reasons.append(
                f"runtime defaultness check found {len(lint_blocking)} blocking finding(s)"
            )
        if gate_reasons:
            raise ValueError(
                f"Audit gate failed for {scene_id} candidate {candidate.name}:\n  - "
                + "\n  - ".join(gate_reasons)
            )

        brief_path = project / "brief" / "project.json"
        if brief_path.exists():
            brief_artifact = _freeze(brief_path, project)
            project_meta = json.loads(brief_artifact["text"])
        else:
            project_meta = {}
            brief_artifact = {
                "path": "builtin:empty-project-brief",
                "sha256": acceptance.sha256_bytes(b"{}\n"),
                "text": "{}\n",
            }
        gate_required = "promotion" in project_meta.get("human_gates", [])
        if gate_required and not approved_by:
            raise ValueError(
                "human gate required: this project lists 'promotion' in human_gates; "
                "promote with approved_by=<approver> to record the approval"
            )

        parent_canon_hash = integrity.canon_head(project)
        resulting_canon_hash = integrity.link_hash(
            parent_canon_hash, scene_id, delta_artifact["sha256"]
        )
        frozen_binding = []
        for label, critique_data, cls in binding:
            artifact = dict(raw_critiques[label])
            artifact.update(
                {
                    "critic": critique_data.get("critic"),
                    "audit_class": cls,
                    "verdict": critique_data.get("verdict"),
                }
            )
            frozen_binding.append(artifact)

        snapshot = {
            "schema_version": 1,
            "scene_id": scene_id,
            "parent_acceptance": index.get("head_acceptance"),
            "parent_canon_hash": parent_canon_hash,
            "resulting_canon_hash": resulting_canon_hash,
            "candidate": candidate_artifact,
            "spec": spec_artifact,
            "state_delta": delta_artifact,
            "project_brief": brief_artifact,
            "review_policy": {"id": policy["id"], "artifact": policy_artifact},
            "runtime_checks": {
                "spec_hard": runtime_hard,
                "defaultness": runtime_defaultness,
            },
            "binding_critiques": frozen_binding,
            "rubric_version": rubric_version,
            "human_gate": {
                "required": gate_required,
                "approved": bool(approved_by),
                "approver": approved_by,
            },
        }

        # Detect an editor/agent changing a validated input while the checks were running. The
        # promotion lock serializes promotions; this second read also closes unrelated writer TOCTOU.
        for artifact in (candidate_artifact, spec_artifact, delta_artifact):
            path = project / artifact["path"]
            if path.read_bytes() != artifact["text"].encode("utf-8"):
                raise ValueError(f"promotion input changed during validation: {artifact['path']}")
        for artifact in frozen_binding:
            path = project / artifact["path"]
            if path.read_bytes() != artifact["text"].encode("utf-8"):
                raise ValueError(f"review evidence changed during validation: {artifact['path']}")

        object_id = acceptance.write_object(project, snapshot)
        accepted.append(scene_id)
        index["accepted_state_deltas"] = sorted(set(accepted), key=scene_sort_key)
        acceptance_objects[scene_id] = object_id
        index["acceptance_objects"] = acceptance_objects
        index["head_acceptance"] = object_id
        acceptance.atomic_write(
            acceptance.index_path(project),
            (json.dumps(index, indent=2, ensure_ascii=False) + "\n").encode("utf-8"),
        )

        # These writes are views. If this process dies after the index replacement, the immutable
        # snapshot still contains the accepted state and a retry of the same promotion repairs them.
        decision = _materialize_snapshot(project, object_id, snapshot)
        return {
            "promoted_to": decision["promoted_to"],
            "accepted_state_deltas": index["accepted_state_deltas"],
            "decision_file": str(
                (project / "decisions" / f"promote-{scene_id}.json").relative_to(project)
            ),
            "critique_files": decision["critique_files"],
            "resulting_canon_hash": resulting_canon_hash,
            "acceptance_object": object_id,
            "idempotent": False,
        }
