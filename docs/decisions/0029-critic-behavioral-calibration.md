# ADR 0029 — Keep critic calibration as evidence, not authority

## Context

The 2026-09-28 review B2 and §5.1 identify several claims that the existing critic corpus cannot
establish from one run: repeatability, robustness to meaning-preserving presentation changes,
writer-family × judge-family sensitivity, correlated errors, and agreement with qualified humans.
The existing `critic_eval` correctly provides planted-defect screening, but its labels are repository
fixtures rather than a substitute for independent human calibration.

## Decision

Add a separate, immutable critic-calibration study under project-local `.runs/critic-calibration/`.
A study freezes the exact diagnostic cases and provisional labels before evidence arrives. Judge
packets withhold case identity, labels, target signals, and expected outcomes. Every live observation
records the exact judge family/id, writer family, repeat index, transform, and declared behavioral
expectation. Human labels are separate immutable records; expert disagreement stays disagreement.

Reports keep distinct:

- provisional fixture localization/false-positive evidence;
- run-to-run repeatability, which is not correctness;
- matched conditional invariance and directional tests;
- crossed writer/judge-family cells and direct joint-error counts, without assuming independence;
- agreement with expert labels only when at least two usable expert labels agree.

Malformed, stale-hash, duplicate, or tampered derived evidence invalidates the report. A changed
repository corpus does not rewrite a frozen study; the report records the frozen and current hashes.

## Why this shape

The audit explicitly warns that a benchmark score, a different vendor, or a fixed repeat count does
not grant review authority. Keeping calibration outside promotion prevents a small or disputed pilot
from silently becoming a creative veto. It also permits future public screening, hidden local controls,
and task-specific criteria without changing production policy.

## Evidence status

The infrastructure is testable and implemented. The empirical claim is still open: no qualified human
calibration cohort, public benchmark run, crossed-family live study, or repair-benefit experiment has
been completed. Priority/severity and repair benefit therefore remain explicit open evidence in the
report, and `authority` is always `not_a_promotion_gate`.

## Regression cases

Tests cover repeatability disagreement, matched invariance failure, crossed-family bookkeeping,
missing human labels, expert disagreement, agreed-label comparison, label-hidden judge packets, and
corrupt evidence invalidation.
