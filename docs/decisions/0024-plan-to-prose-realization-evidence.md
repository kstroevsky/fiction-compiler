# ADR 0024 — Add evidence-bound plan-to-prose realization states

## Context

The 2026-09-28 review found that the compiler checked whether a scene plan was internally valid and
whether extracted prose claims contradicted canon, but did not check whether the prose actually
realized the plan's required events. Treating a missing extraction as proof of omission would repeat
the audit's central epistemic error: incomplete model evidence is not deterministic truth.

## Decision

Extend `prose-claims` with two stages. `observed_events` is produced from the candidate without seeing
the plan and carries exact prose evidence. `event_alignment` is a separate plan-aware stage that maps
required canonical events to those observations and records one of `realized`, `omitted`, or
`unverified`.

`prose_audit` now compares the aligned result with `scene.spec.required_events`:

- an explicit `omitted` required event is a material realization finding;
- a missing or explicitly `unverified` alignment makes the audit verdict `uncertain` when no harder
  defect exists;
- a `realized` event must point to an actual plan-blind observation;
- a consequential observed event with no canonical alignment is advisory evidence to reconcile with
  the scene plan or state delta;
- free-text `turn` and `exit_state` remain `unverified` because the current representation has no
  deterministic semantic oracle for them.

This is translation-validation infrastructure, not evidence that the extractor/alignment model is
accurate. `require_prose_audit` remains opt-in until those stages are calibrated on planted omissions,
oblique realizations, and clean controls. ADR 0030 adds the calibration evidence workflow, while the
actual live/hidden-set calibration result remains open.

## Verification

Tests cover missing alignment → uncertainty, explicit omission → material revision, an oblique but
evidence-bound realization → pass, an unaligned consequential event → advisory evidence, and invalid
alignment to a nonexistent observation → error. Existing prose-audit, schema, and promotion tests stay
green.

## Consequences

The compiler can now represent the distinction between absence, omission, and unknown at the
plan-to-prose boundary. Literary questions about whether a turn *lands* or an affect is achieved stay
with calibrated critics/readers rather than being smuggled into a hard check.
