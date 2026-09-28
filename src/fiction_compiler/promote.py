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

Accepted artifacts are frozen into content-addressed snapshots and the canon index is the authority
transaction. Explicit backward revision creates a new immutable chain while preserving superseded
objects; it never mutates the only copy of accepted history.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from . import (acceptance, defaultness, dependencies, hard_audit, integrity, issue_resolution,
               review_policy, schema)
from .context import compile_bundle
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


def _review_attempt_evidence(project: Path, scene_id: str, critique_data: dict) -> dict:
    """Freeze the exact role-runner attempt when provenance points to one we can verify."""
    provenance = critique_data.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("source") != "role_runner":
        return {"status": "not_applicable"}
    run_id = provenance.get("run_id")
    packet_sha256 = provenance.get("packet_sha256")
    if not isinstance(run_id, str) or not run_id or not isinstance(packet_sha256, str):
        return {"status": "unverified", "reason": "runtime provenance has no usable run id/digest"}
    attempt_path = project / ".runs" / "reviews" / scene_id / f"{run_id}.json"
    if not attempt_path.exists():
        return {
            "status": "unverified",
            "run_id": run_id,
            "reason": "role-runner attempt artifact is unavailable",
        }
    artifact = _freeze(attempt_path, project)
    try:
        attempt = json.loads(artifact["text"])
    except json.JSONDecodeError:
        return {"status": "unverified", "run_id": run_id, "reason": "attempt artifact is invalid JSON"}
    packet = attempt.get("packet")
    recorded_sha = attempt.get("packet_sha256")
    if not isinstance(packet, dict):
        return {"status": "unverified", "run_id": run_id, "reason": "attempt has no packet"}
    actual_sha = acceptance.sha256_bytes(acceptance.canonical_json_bytes(packet))
    if recorded_sha != packet_sha256 or actual_sha != packet_sha256:
        return {
            "status": "mismatch",
            "run_id": run_id,
            "expected_packet_sha256": packet_sha256,
            "recorded_packet_sha256": recorded_sha,
            "actual_packet_sha256": actual_sha,
        }
    return {"status": "verified", "run_id": run_id, "artifact": artifact}


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
        "supersedes_acceptance": snapshot.get("supersedes_acceptance"),
        "rebase_reason": snapshot.get("rebase_reason"),
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


def _append_history(index: dict, scene_id: str, object_id: str) -> None:
    history = index.setdefault("acceptance_history", {})
    if not isinstance(history, dict):
        history = {}
        index["acceptance_history"] = history
    scene_history = history.setdefault(scene_id, [])
    if not isinstance(scene_history, list):
        scene_history = []
        history[scene_id] = scene_history
    if object_id not in scene_history:
        scene_history.append(object_id)


def _revision_parent(project: Path, accepted: list[str], acceptance_objects: dict[str, str],
                     scene_id: str) -> tuple[str | None, str]:
    ordered = sorted(accepted, key=scene_sort_key)
    position = ordered.index(scene_id)
    if position == 0:
        return None, integrity.seed_hash(project)
    parent_scene = ordered[position - 1]
    parent_object = acceptance_objects.get(parent_scene)
    if not parent_object:
        raise ValueError(
            f"cannot revise {scene_id}: predecessor {parent_scene} is a legacy acceptance without "
            "an immutable acceptance object"
        )
    parent_snapshot = acceptance.load_object(project, parent_object)
    return parent_object, str(parent_snapshot["resulting_canon_hash"])


def _assert_downstream_views_match(project: Path, accepted: list[str],
                                   acceptance_objects: dict[str, str], scene_id: str) -> None:
    """Refuse to rebase over mutable downstream views that no longer match accepted authority."""
    ordered = sorted(accepted, key=scene_sort_key)
    position = ordered.index(scene_id)
    for downstream_scene in ordered[position + 1:]:
        object_id = acceptance_objects.get(downstream_scene)
        if not object_id:
            raise ValueError(
                f"cannot revise {scene_id}: downstream scene {downstream_scene} has no immutable "
                "acceptance object"
            )
        snapshot = acceptance.load_object(project, object_id)
        views = (
            ("spec", project / "scenes" / downstream_scene / "spec.json"),
            ("state_delta", project / "scenes" / downstream_scene / "state-delta.json"),
            ("candidate", project / "manuscript" / "chapters" / f"{downstream_scene}.md"),
        )
        for field, path in views:
            expected = acceptance.frozen_bytes(snapshot, field)
            if not path.exists() or path.read_bytes() != expected:
                relative = path.relative_to(project)
                raise ValueError(
                    f"cannot revise {scene_id}: downstream derived view {relative} differs from "
                    f"accepted {downstream_scene}; restore/resolve it before rebasing history"
                )


def _refresh_pending_hard_rechecks(project: Path, index: dict) -> dict:
    """Resume deterministic post-revision checks after a crash or interrupted materialization."""
    rechecks = index.get("rechecks_required", {})
    if not isinstance(rechecks, dict):
        return index
    changed = False
    for downstream_scene, entry in rechecks.items():
        if not isinstance(entry, dict):
            continue
        scopes = entry.get("required_scopes", [])
        if not isinstance(scopes, list) or "hard" not in scopes:
            continue
        result = hard_audit.audit_scene(project, downstream_scene)
        entry["hard_audit"] = {
            "status": "pass" if result.get("verdict") == "pass" else "needs_attention",
            "verdict": result.get("verdict"),
            "findings": result.get("findings", []),
        }
        if result.get("verdict") == "pass":
            entry["required_scopes"] = [scope for scope in scopes if scope != "hard"]
        changed = True
    if changed:
        acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))
    return index


def _commit_revision_chain(project: Path, index: dict, accepted: list[str],
                           acceptance_objects: dict[str, str], scene_id: str,
                           old_object: str, new_object: str, new_snapshot: dict,
                           old_delta: dict, new_delta: dict) -> tuple[dict, list[str]]:
    """Replace one accepted scene and rebase immutable downstream snapshots onto its new chain."""
    ordered = sorted(accepted, key=scene_sort_key)
    position = ordered.index(scene_id)
    downstream = ordered[position + 1:]
    changed = dependencies.changed_state_refs(old_delta, new_delta)
    _append_history(index, scene_id, old_object)
    acceptance_objects[scene_id] = new_object

    rechecks = index.get("rechecks_required", {})
    rechecks = dict(rechecks) if isinstance(rechecks, dict) else {}
    rechecks.pop(scene_id, None)
    current_object = new_object
    current_hash = str(new_snapshot["resulting_canon_hash"])
    rebased: dict[str, dict] = {}

    for downstream_scene in downstream:
        prior_object = acceptance_objects.get(downstream_scene)
        if not prior_object:
            raise ValueError(
                f"cannot revise {scene_id}: downstream scene {downstream_scene} is a legacy "
                "acceptance without an immutable acceptance object"
            )
        prior = acceptance.load_object(project, prior_object)
        replacement = deepcopy(prior)
        replacement["parent_acceptance"] = current_object
        replacement["parent_canon_hash"] = current_hash
        replacement["resulting_canon_hash"] = integrity.link_hash(
            current_hash, downstream_scene, str(replacement["state_delta"]["sha256"])
        )
        replacement["supersedes_acceptance"] = prior_object
        replacement["rebase_reason"] = {"upstream_revision": scene_id}
        replacement_object = acceptance.write_object(project, replacement)
        _append_history(index, downstream_scene, prior_object)
        acceptance_objects[downstream_scene] = replacement_object
        match = dependencies.dependency_match(prior.get("read_set"), changed)
        rechecks[downstream_scene] = {
            "caused_by_scene": scene_id,
            "acceptance_object": replacement_object,
            "known_state_dependency": match,
            "required_scopes": ["hard", "literary", "reader", "voice", "whole_work"],
            "hard_audit": {"status": "pending"},
        }
        rebased[downstream_scene] = {
            "from": prior_object,
            "to": replacement_object,
            "known_state_dependency": match,
        }
        current_object = replacement_object
        current_hash = str(replacement["resulting_canon_hash"])

    index["acceptance_objects"] = acceptance_objects
    index["head_acceptance"] = current_object
    index["rechecks_required"] = rechecks
    events = index.get("revision_events", [])
    events = list(events) if isinstance(events, list) else []
    event = {
        "scene_id": scene_id,
        "revised_at": datetime.now(timezone.utc).isoformat(),
        "from_acceptance": old_object,
        "to_acceptance": new_object,
        "changed_state_refs": changed,
        "rebased": rebased,
        "conservative_downstream_recheck": downstream,
    }
    event["id"] = acceptance.sha256_bytes(acceptance.canonical_json_bytes(event))
    events.append(event)
    index["revision_events"] = events

    # The index replacement is the authority transaction. New immutable objects already exist; if a
    # later derived-view or recheck write fails, retrying can repair it without losing canon history.
    acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))

    # Re-run the deterministic hard audit against the *new* active chain. Literary/reader/voice
    # effects remain explicitly pending because deterministic code cannot establish those outcomes.
    _refresh_pending_hard_rechecks(project, index)
    return index, downstream


def promote_candidate(project: Path, scene_id: str, candidate_file: str, *,
                      approved_by: str | None = None, rubric_version: str | None = None,
                      revision: bool = False) -> dict:
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
        revising = False
        existing = None
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
                if not revision:
                    raise ValueError(
                        f"{scene_id} is already accepted with different frozen inputs; "
                        "create an explicit revision branch/version instead of rewriting canon"
                    )
                revising = True
                ordered = sorted(accepted, key=scene_sort_key)
                for accepted_scene in ordered[ordered.index(scene_id):]:
                    if not acceptance_objects.get(accepted_scene):
                        raise ValueError(
                            f"cannot revise {scene_id}: {accepted_scene} has no immutable "
                            "acceptance object to preserve/rebase"
                        )
                _assert_downstream_views_match(project, accepted, acceptance_objects, scene_id)
            else:
                affected = []
                if revision:
                    index = _refresh_pending_hard_rechecks(project, index)
                    affected = [
                        sid for sid, entry in index.get("rechecks_required", {}).items()
                        if isinstance(entry, dict) and entry.get("caused_by_scene") == scene_id
                    ]
                    for affected_scene in affected:
                        active_object = acceptance_objects.get(affected_scene)
                        if active_object:
                            _materialize_snapshot(
                                project, active_object, acceptance.load_object(project, active_object)
                            )
                decision = _materialize_snapshot(project, existing_object, existing)
                result = {
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
                if revision:
                    result.update({
                        "revision": True,
                        "rebased_scenes": affected,
                        "rechecks_required": {
                            sid: index.get("rechecks_required", {}).get(sid) for sid in affected
                        },
                    })
                return result
        if not revising and accepted and scene_sort_key(scene_id) <= max(map(scene_sort_key, accepted)):
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
        issue_bindings: list[dict] = []
        if policy.get("require_issue_resolutions"):
            issue_reasons, issue_bindings = issue_resolution.evaluate_gate(
                scene_dir, candidate.name, candidate_artifact["sha256"], loaded
            )
            gate_reasons.extend(issue_reasons)

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

        if revising:
            parent_acceptance, parent_canon_hash = _revision_parent(
                project, accepted, acceptance_objects, scene_id
            )
        else:
            parent_acceptance = index.get("head_acceptance")
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
                    "review_attempt": _review_attempt_evidence(project, scene_id, critique_data),
                }
            )
            frozen_binding.append(artifact)
        frozen_issue_resolutions = [
            {
                "resolution": _freeze(item["resolution_path"], project),
                "source_critique": _freeze(item["source_critique_path"], project),
            }
            for item in issue_bindings
        ]

        compiled_context = compile_bundle(project, scene_id)
        context_basis = dict(compiled_context)
        context_basis.pop("generated_at", None)
        context_basis_bytes = acceptance.canonical_json_bytes(context_basis)

        snapshot = {
            "schema_version": 1,
            "scene_id": scene_id,
            "parent_acceptance": parent_acceptance,
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
            "issue_resolutions": frozen_issue_resolutions,
            "rubric_version": rubric_version,
            "human_gate": {
                "required": gate_required,
                "approved": bool(approved_by),
                "approver": approved_by,
            },
            "read_set": dependencies.read_set_from_context(compiled_context),
            "context_basis": {
                "status": "reconstructed_at_acceptance",
                "note": (
                    "Deterministic context basis reconstructed at acceptance; this does not prove "
                    "the same bytes were supplied during drafting unless separate run provenance exists."
                ),
                "sha256": acceptance.sha256_bytes(context_basis_bytes),
                "text": context_basis_bytes.decode("utf-8"),
            },
        }
        if revising and existing_object:
            snapshot["supersedes_acceptance"] = existing_object
            snapshot["rebase_reason"] = {"backward_revision": scene_id}

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
        for pair in frozen_issue_resolutions:
            for artifact in pair.values():
                path = project / artifact["path"]
                if path.read_bytes() != artifact["text"].encode("utf-8"):
                    raise ValueError(f"issue evidence changed during validation: {artifact['path']}")

        object_id = acceptance.write_object(project, snapshot)
        if revising:
            assert existing is not None and existing_object is not None
            old_delta = acceptance.frozen_json(existing, "state_delta")
            index, downstream = _commit_revision_chain(
                project, index, accepted, acceptance_objects, scene_id,
                existing_object, object_id, snapshot, old_delta, delta,
            )
            for affected_scene in [scene_id, *downstream]:
                active_object = index["acceptance_objects"][affected_scene]
                active_snapshot = acceptance.load_object(project, active_object)
                _materialize_snapshot(project, active_object, active_snapshot)
            return {
                "promoted_to": str((project / "manuscript" / "chapters" / f"{scene_id}.md").relative_to(project)),
                "accepted_state_deltas": index["accepted_state_deltas"],
                "decision_file": str(
                    (project / "decisions" / f"promote-{scene_id}.json").relative_to(project)
                ),
                "critique_files": [item["path"] for item in snapshot["binding_critiques"]],
                "resulting_canon_hash": snapshot["resulting_canon_hash"],
                "acceptance_object": object_id,
                "idempotent": False,
                "revision": True,
                "rebased_scenes": downstream,
                "rechecks_required": {
                    scene: index.get("rechecks_required", {}).get(scene) for scene in downstream
                },
            }
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
