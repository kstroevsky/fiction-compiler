# ADR 0042 — Record owner preference evidence

## Status

Accepted and implemented, 2026-09-29.

## Context

Review §6.6 identified a missing evidence stream: the project owner can choose premises, endings,
plans, candidates, or revisions, but those choices were not recorded in a form that could later test
whether a critic predicts this owner's taste. Reconstructing earlier choices from commits or accepted
stories would create hindsight labels because the exact alternatives shown, the stated reason, and the
decision context are no longer recoverable.

Owner preference is also a different target from the reader contract. Agreement with one owner's
choices cannot stand in for target-reader preference or general literary quality.

## Decision

Owner-taste calibration is prospective and append-only.

`record_owner_preference` stores one choice under
`decisions/preferences/records/pref-<uuid>.json`. Every shown alternative is frozen as exact UTF-8
bytes in `decisions/preferences/artifacts/<sha256>.txt`, whether it was supplied inline or read from a
project-local file. The record preserves the decision kind, chosen alternative, stated reason,
decision date, and optional metadata. At least two uniquely named alternatives are required, and file
inputs cannot escape the project.

`owner_preference_packet` returns those exact alternatives but withholds `chosen_id` and `reason`.
The packet hash binds a critic prediction to that choice-hidden input.
`record_owner_preference_prediction` stores one immutable pick or abstention per critic under
`.runs/owner-preference-calibration/`; stale packet hashes and duplicate predictions by the same critic
for one preference are rejected.

`owner_preference_report` validates the durable choice, snapshots, and prediction bindings, then reports
per-critic record count, picks, correct picks, abstentions, and descriptive agreement among picks.
Missing owner history remains explicitly `no_owner_preferences_recorded`; existing projects are not
backfilled from repository outcomes.

Durable owner-choice records are included in workspace validation. Calibration predictions remain run
evidence under `.runs` and are validated when the owner-preference report is requested.

## Authority boundary

These records measure only whether a critic predicts this owner's recorded choices. They do not prove
target-audience preference, literary quality, critic calibration in general, or a powered estimate.
They do not become a promotion gate or an automatic taste model.

Future premise or plan generation may use accumulated owner choices as one declared input, but the
compiler must keep that signal separate from audience evidence and must not silently infer owner taste
from accepted stories.

## Regression evidence

`tests/test_owner_preference.py` checks:

- exact alternative freezing, path confinement, unique IDs, and valid chosen alternatives;
- choice-hidden packets and hash-bound predictions;
- one prediction per critic, including explicit abstention;
- descriptive agreement accounting without audience-quality claims;
- tamper detection for frozen alternatives and durable workspace validation;
- the absence of fabricated historical owner records in existing projects; and
- MCP/schema contracts for the four owner-preference tools.

## Consequences

The audit's owner-taste gap now has a maintained prospective evidence path. The repository can collect
the data needed for a later critic-agreement study without contaminating general-reader evaluation or
pretending unavailable historical alternatives are known. Actual predictive performance remains an
empirical question until enough owner choices and critic predictions are recorded.
