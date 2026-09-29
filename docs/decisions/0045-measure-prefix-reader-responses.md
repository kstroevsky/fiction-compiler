# ADR 0045 — Measure prefix-reader responses without modeling reader state

## Status

Accepted and implemented, 2026-09-29.

## Context

Track G and review §§6.4–6.5 distinguish planned disclosure from observed reader experience. ADR 0040
made revelation/disclosure structure explicit, but it deliberately stopped short of claiming that a
reader noticed, understood, expected, or remained uncertain about anything. The only existing
reader-prefix packet was tied to post-revision rechecks, so it could not serve as a reusable measurement
workflow for ordinary project development.

The missing capability was evidence capture, not a more elaborate simulated “reader mind.”

## Decision

Projects may now declare `planning/reader-probes.json`. Each probe names an accepted scene boundary and
one or more predeclared questions of kind `comprehension`, `expectation`, `ambiguity`, `engagement`, or
`affect`. Response modes are `free_text`, `single_choice`, or `scale_1_5`. A question may bind to an
exact reader-contract clause, but no hidden “correct reader state” is required.

`reader_probe_packet` builds the current accepted manuscript prefix through the probe boundary and
hashes the complete reader-visible packet. It includes only prose, question wording, response mode, and
declared options. Contract-clause bindings, planning notes, later scenes, hidden canon, and intended
outcomes are omitted from the packet.

`record_reader_probe_response` stores one immutable response per respondent/probe under
`.runs/reader-probes/`. The response embeds the exact packet and packet hash, records whether the
respondent is human or model, and keeps target-audience/general-reader/expert cohorts separate from
`model-proxy`. Answer shape is validated against the question mode. If accepted prose or question
wording changes, the old packet hash becomes stale and cannot accept new responses.

`reader_probe_report` validates stored evidence and reports fresh versus stale responses, human/model
and cohort counts, single-choice distributions, and 1–5 scale distributions/means. Free-text answers
are counted but intentionally receive `semantic_summary: not_computed`; interpreting them remains a
separate human or explicitly evidenced analysis step. The report emits no literary-quality or
reader-contract pass/fail verdict.

Contract coverage now validates `reader-question` references against declared probe question IDs and,
when a question names a contract clause, verifies that it is mapped to that exact clause.

## Worked project

`forecourt` now declares two probe points:

- after `ch01-sc01`, asking for an unconstrained next-step expectation and current uncertainty about
  the man; and
- after `ch01-sc03`, asking readers to describe Jo's concrete ending action, rate certainty that the man
  was dangerous, and state any unresolved question.

The ending-action question is mapped to the “small, concrete decision” reader-contract clause; the
danger-certainty question is mapped to the “genuinely ambiguous to the end” clause. Coverage mapping
still has `verification: not_assessed`. No response files are fabricated, so Forecourt currently reports
`probe_plan_without_responses`.

## Regression evidence

`tests/test_reader_probe.py` verifies:

- later prose, contract bindings, and hidden planning notes do not leak into the prefix packet;
- free-text, single-choice, and scale answer modes are enforced;
- model proxies cannot masquerade as target-audience humans;
- target-audience and model-proxy distributions remain separate;
- free-text semantics are not auto-inferred;
- prose changes make recorded evidence stale and old packet hashes unusable;
- one respondent cannot submit multiple responses to one probe;
- reader-contract references resolve to real declared questions; and
- the real Forecourt plan is valid while honestly containing zero responses.

The template now includes an empty `reader-probes.json`, and workspace validation checks any declared
probe plan.

## Consequences

The compiler can now collect the evidence proposed by Track G without converting annotations into
cognition. Actual target-audience conclusions still require recruited readers and recorded responses;
model-proxy data remains a separate cohort. Statistical thresholds, semantic coding of free-text
answers, and larger audience studies are empirical decisions that this milestone does not invent.
