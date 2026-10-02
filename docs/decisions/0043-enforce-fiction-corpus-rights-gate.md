# ADR 0043 — Enforce fiction-corpus rights gate

## Status

Accepted and implemented, 2026-09-29.

## Context

The implementation roadmap requires a German/EU copyright-verification field before external fiction
is ingested, and review §6.9 repeats that requirement before public-domain literature is used as a
control. The source register previously carried only prose `copyright_note` fields. Those notes warned
that a US-public-domain corpus does not establish EU/DE clearance for a particular work, translation,
or edition, but code could not distinguish a cleared title from a corpus that still needed checking.

## Decision

Every `fiction-corpus` source now carries a structured `rights` object with:

- `eu_de_status`: `cleared`, `repository-owned`, `per-title-verification-required`, or `not-cleared`;
- `full_text_policy`: `allowed`, `blocked-pending-title-check`, or `blocked`;
- a non-empty `basis`; and
- `verified_on` when the source is actually cleared or repository-owned.

Workspace validation enforces consistent combinations. Corpus aggregators such as Standard Ebooks and
Project Gutenberg are deliberately `per-title-verification-required` and block full-text ingestion.
They cannot be treated as blanket EU/DE clearance merely because their texts are public domain in the
US. A future external literary control must therefore get its own source entry with title/edition-level
evidence before `full_text_policy: allowed` is valid.

Repository-owned fiction is marked separately because no external literary rights determination is
needed.

## Regression evidence

`tests/test_kb.py` requires every fiction-corpus entry to expose structured rights state and checks the
allowed policy/status combinations. `scripts/validate_workspace.py` enforces the same invariant for the
real repository data.

## Consequences

The project now has a machine-checkable prerequisite for review §6.9 rather than a prose reminder.
This does not itself establish that any external masterwork is EU/DE-cleared, nor does it run the
literature-control experiment. Those remain separate title-level research and empirical work.
