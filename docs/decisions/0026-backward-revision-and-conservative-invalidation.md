# ADR 0026 — Backward revision preserves history and invalidates downstream evidence

## Context

The accepted-scene chain was intentionally immutable: promoting different bytes for an already
accepted scene was refused. That protected authority, but it made a normal long-form operation
impossible: discovering a later payoff can require planting setup in an earlier scene. The
2026-09-28 review §6.2 therefore called for backward revision, preserved history, scene read sets,
dependency invalidation, and conservative downstream rechecks.

The difficult boundary is epistemic. A fact/predicate/promise read set can identify some concrete
state dependencies, but it cannot enumerate thematic, voice, pacing, or reader-expectation effects.
Those must not be silently treated as unchanged merely because no typed state dependency matches.

## Decision

Accepted scenes remain immutable objects. A backward revision creates a new acceptance object for the
revised scene and new rebased acceptance objects for every downstream scene. The old objects remain in
`canon/index.json.acceptance_history`; the active `acceptance_objects` map moves to the new chain. The
integrity verifier treats historical objects as referenced evidence and verifies their content hashes,
so preserving history does not create false orphan failures.

Every newly promoted snapshot also records a conservative `read_set` derived from the scene's
reconstructed pre-scene context: fact ids, typed predicate identities, and open-promise ids. When an
earlier delta changes, the revision code compares typed state effects and labels downstream scenes as
known dependents (`true`), known non-matches (`false`), or unknown (`null` for older snapshots without
a read set).

All downstream scenes are invalidated for literary/reader/voice/whole-work review regardless of that
typed match. Deterministic hard audit is rerun immediately against the new active chain and is removed
from the pending scopes only when it passes. This intentionally treats the read set as useful evidence,
not a proof of dependency completeness.

The acceptance snapshot freezes the exact candidate and review-policy bytes as before. It now also
freezes a deterministic `context_basis` reconstructed at acceptance and labels it explicitly as such;
that basis is not claimed to be the exact drafting prompt. When a binding literary critique points to
a persisted role-runner attempt, promotion additionally freezes and verifies that exact attempt packet.
Missing run evidence remains `unverified` rather than being invented.

Two tools expose the workflow: `revise_acceptance` performs the confirm-gated rewrite/rebase, and
`revision_status` reports pending rechecks plus the append-only revision-event ledger.

## Verification

Regression fixtures cover both important cases:

- changing a scene-1 fact that scene 2 read marks scene 2 as a known dependent, rebases its immutable
  acceptance object, reruns hard audit, preserves both superseded objects, and leaves canon integrity
  `verified` with no orphan artifacts;
- changing only scene-1 prose still invalidates downstream literary/reader/voice/whole-work evidence,
  even though the typed state dependency match is false.

Focused promotion/tool tests also verify that the new operation is explicitly confirm-gated and that
normal in-place re-promotion remains refused unless revision mode is selected.

## Consequences

The compiler can now revise backwards without silently mutating accepted history or breaking the hash
chain. It can identify concrete state dependents while conservatively exposing the larger literary
blast radius.

This does **not** complete whole-work literary review. Pending reader/voice/whole-work scopes are
deliberately left open until fresh evidence is produced, and exact drafting-context provenance remains
unverified unless a future drafting runner records it directly.
