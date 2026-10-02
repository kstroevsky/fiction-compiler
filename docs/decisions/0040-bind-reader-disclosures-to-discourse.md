# ADR 0040 — Bind reader disclosures to discourse

## Status

Accepted and implemented, 2026-09-29.

## Context

The audit's Track G separates intended disclosure from observed reader comprehension. The repository
already had a structural `reader-disclosure.json` format, but a disclosure could name a fact and scene
without proving that it corresponded to any declared revelation in `planning/discourse-plan.json`.
Conversely, a discourse revelation could remain free text with no machine-visible declaration saying
whether it exposed a canonical fact or represented a choice, recognition, ambiguity, or other
non-factual move.

That gap made the two discourse artifacts independently plausible rather than mutually accountable.
It also left all six worked projects without project-level disclosure ledgers.

## Decision

Every fact disclosure now names its `source_revelation`. The report verifies that the revelation
exists and occurs in the same scene. A single planned revelation may bind several canonical facts.

Every planned revelation must be accounted for in exactly one of two ways:

- one or more fact disclosures bind it to canonical fact ids; or
- `non_fact_revelations` gives an explicit reason why the revelation is not a canonical fact
  disclosure.

A revelation cannot be both fact-bound and declared non-factual. Missing declarations, unknown
revelation ids, and scene mismatches make the ledger structurally invalid.

Curiosity gaps and surprise/setup checks retain their existing discourse-order semantics. The six
worked projects now carry disclosure ledgers grounded in their accepted prose and existing discourse
plans. Where the plan describes an enacted choice, recognition, or unresolved ambiguity rather than a
new fact, the ledger says so instead of inventing a fact solely to satisfy the format.

## Authority boundary

This is a discourse-layer consistency check. `verification` remains `structural_only`.

`stated` and `implied` record the annotation's intended disclosure mode. They do not establish that a
reader noticed, understood, believed, remembered, or correctly inferred the information. Curiosity
gap closure records planned structural availability, not measured suspense or satisfaction.

No disclosure annotation becomes a literary promotion gate, and no reader-contract clause becomes
verified merely because it points at this ledger. Actual reader probes and independent audience
measurement remain empirical Track G work.

## Regression evidence

`tests/test_reader.py` now checks:

- complete fact/non-fact accounting for every discourse revelation;
- source-revelation scene consistency;
- the existing fair-play/setup and curiosity-order rules; and
- valid structural ledgers for all six worked projects.

The workspace validator continues to validate the JSON schema. The broader unit and regression suites
must stay green before this change is committed.

## Consequences

The repository can now distinguish "this planned revelation exposes these canonical facts" from
"this planned revelation is a non-factual discourse move" without claiming a reader model. Future
reader experiments can sample prefixes from this declared structure and compare predictions or
questions against reader responses while keeping observed comprehension separate from annotations.
