# ADR 0031 — Bind post-revision subjective rechecks to exact accepted prose

## Context

ADR 0026 made backward revision safe for canon history and conservatively invalidated every downstream
scene for `literary`, `reader`, `voice`, and `whole_work` review. Deterministic hard checks rerun
immediately, but the remaining scopes stayed pending because there was no provenance-bearing way to
show what fresh reviewer or reader actually saw, and no explicit transaction for closing the scope.

The 2026-09-28 review §6.2 requires the larger literary blast radius to remain visible until fresh
post-revision evidence exists. It also requires a first-class whole-work pass that can identify an
earlier scene for another backward revision.

## Decision

Add a post-revision evidence workflow with three separate operations.

1. A **recheck packet** is built from the current immutable acceptance objects and canon head. Literary
   and voice packets carry the active accepted work with a target scene. Reader packets contain only
   the accepted prefix through the target scene, so later prose and planned outcomes cannot leak into
   the reader observation. A `whole_work` packet is global and binds every active accepted scene plus
   the exact set of scenes currently pending whole-work recheck.
2. **Evidence recording** persists the exact packet, packet hash, evaluator kind/id/cohort, verdict,
   findings and provenance under `.runs/post-revision/`. Recording never clears a scope. A stale packet
   is refused, and `pass` cannot carry material or fatal findings.
3. **Resolution** is a separate explicit decision that names the passing evidence artifact, records
   `decided_by` and a reason, rechecks that the evidence still matches the current acceptance head, and
   only then removes the bound scope from `rechecks_required`. Whole-work resolution clears that scope
   only for the pending scenes frozen in the evidence packet.

Resolved entries remain in the canon index with an empty `required_scopes` list and immutable
resolution references, so `revision_status` can distinguish pending from completed rechecks instead of
erasing the audit trail.

## Why resolution is separate from evidence

An LLM review, model reader probe, or human response is evidence, not authority by itself. Keeping the
resolution transaction separate prevents a clean-looking model verdict from silently closing a
subjective recheck. It also lets a human adjudicator use model evidence without rewriting its source.

## Whole-work findings

Whole-work evidence may carry `target_scene` on individual findings. A non-pass therefore identifies a
repair location without mutating canon automatically; the existing backward-revision operation remains
the only way to replace accepted history.

## Verification

Tests cover prefix-only reader packets, evidence that does not auto-close, scope-specific explicit
resolution, global whole-work resolution, refusal of non-pass/contradictory evidence, stale packet
rejection, and the pending/completed status split. Existing backward-revision and promotion tests stay
green.
