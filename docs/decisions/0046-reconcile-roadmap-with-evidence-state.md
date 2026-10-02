# ADR 0046 — Reconcile the roadmap with the implemented evidence state

## Status

Accepted and implemented, 2026-09-29.

## Context

The Sept. 28 audit and the implementation work through ADR 0045 changed the architecture faster than
the staged roadmap was updated. The roadmap's detailed status sections correctly described immutable
acceptance objects, fabula-ordered replay, plan search, frozen selection experiments, repertoire
diagnostics, reader probes, and evidence boundaries, but the older Stage 0–4 checklist still described
several of those mechanics as future work.

The most consequential drift was Stage 1's claim that promotion still needed to append accepted deltas
to mutable canon ledgers, and Stage 4's continued presentation of a continuation-prediction ensemble,
`Originality*` formula, and simulated reader-expectation tracker as required future architecture.
Those statements conflict with the implemented authority model and with ADRs 0041/0045.

## Decision

`docs/implementation-roadmap.md` now treats the repository's current code/evidence state as the
checkpoint rather than preserving obsolete implementation instructions.

- Stage 1 records immutable content-addressed acceptance objects plus the atomic canon index as the
  authority transaction. `reconstruct_state_before` replays frozen accepted deltas, preferring fabula
  order where defined. Superseded acceptances remain history during revision.
- Stage 4 records the implemented blind/order-balanced Pareto tournament, frozen selection-value
  experiments, scene-plan search, repertoire diagnostics, and measured prefix-reader probes.
  `Originality*` and simulated reader expectation are no longer listed as required gates.
- A §6 status table maps each audit proposal to implemented mechanics and the evidence that remains
  genuinely unrun. Infrastructure is never counted as a positive empirical result.
- Stages 0–4 distinguish completed baseline mechanics from open empirical studies and evidence-driven
  expansion.

## Evidence checked

The reconciliation was checked against current source rather than inferred from old ADR prose:

- `acceptance.py` defines immutable content-addressed objects and makes `canon/index.json` the active
  acceptance map/transaction boundary.
- `promote.py` updates active acceptance objects/head state atomically and preserves/rebases immutable
  revision history while scheduling deterministic and subjective rechecks.
- `state.py` reconstructs accepted deltas and exposes `reconstruct_state_before`, preferring fabula
  replay with explicit fallback.
- `tournament.py` owns anonymization, forward/reverse presentation orders, eligibility floors, Pareto
  selection, and disagreement preservation.
- ADRs 0027/0028/0041/0045 provide the plan-search, selection-measurement, repertoire, and prefix-reader
  evidence paths described by the updated Stage 4.

## Consequences

Future implementation work should start from the audit-status table and the explicit `Still`/unrun
evidence statements, not from superseded Stage 0–4 TODO text. The next remaining claims are primarily
empirical: live realization and critic calibration, independent selection-value measurement, actual
reader/owner evidence, matched-cost writer-family/edit-versus-regeneration experiments, more external
controls, and the bounded long-form diagnostic. Unknown evidence remains unknown rather than being
backfilled from repository history or model judgment.
