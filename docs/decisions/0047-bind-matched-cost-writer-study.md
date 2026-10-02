# ADR 0047 — Bind matched-cost writer-family and revision-strategy studies

## Status

Accepted and implemented, 2026-09-29.

## Context

Review §6.11 proposes testing different writer-model families and edit-based revision against
regeneration at equal cost. ADR 0039 already records scene-level operation provenance, exact candidate
snapshots, provider/model identity, and known/unknown token and monetary cost. ADR 0028 already freezes
candidate bytes before selection and exposes them to independent readers under blind,
counterbalanced pair assignments.

Those evidence streams were separate. A later experiment could therefore label a frozen candidate as
“family A” or “edited” without proving which recorded run produced those exact bytes, declare a study
after seeing reader outcomes, or call arms equal-cost while one arm had missing usage.

## Decision

A writer study is a small binding artifact inside an existing selection experiment:
`.runs/selection-eval/<scene>/<selection-id>/writer-study.json`.

`freeze_writer_study` is allowed only before any reader preference has been recorded. It requires one
arm for every frozen selection candidate and binds the pool fingerprint plus each candidate SHA-256 to:

- one existing scene-run id;
- the successful generation or revision operation that produced those exact candidate bytes;
- exact provider and model strings;
- a declared writer-family label; and
- `independent-draft`, `regenerate`, or `edit` strategy.

An edit arm also names `source_candidate_sha256`. The source must occur in an earlier successful
operation in the same run and must differ from the output hash, preventing an edit label from being
attached to an unrelated or byte-identical output. One exact provider/model pair cannot be relabeled as
multiple writer families inside the same study; the family label remains declared metadata rather than
an inferred vendor genealogy.
`writer-family` studies require at least two declared families; `edit-vs-regeneration` studies require
an edit arm and at least one regeneration/independent-draft arm.

The study predeclares `total_tokens` or `cost_usd` as its matching metric, a maximum relative gap, and
which generation/critique/revision phases count. `writer_study_report` revalidates all source evidence,
keeps missing metered usage explicitly unknown, reports the observed relative gap only when every arm's
metric is complete, and reuses the selection experiment's already-blinded independent reader evidence.

At freeze time each arm also stores the exact ordered operation IDs and a hash of their canonical
records for the included phases. A later operation appended to one of those phases, or a modification
to previously frozen accounting/provenance evidence, invalidates the study instead of silently changing
its matched-cost condition after outcomes are known. Scene-run candidate snapshots are reverified as
part of the composition boundary.

The report states whether evidence is still missing, the cost condition failed, readers are still
needed, or the frozen pool has descriptively complete reader evidence. It does not rank writer
families, run a significance test, or infer population-level superiority.

## Evidence boundaries

The family label is declared experimental metadata; provider/model identity and candidate bytes are
the machine-verifiable provenance. The compiler does not infer vendor genealogy from model names.

Cost matching covers the predeclared phases in each arm's bound scene run. Human labor that has no
metered token/USD record is not silently converted into model cost. Study authors must choose a metric
and phase scope appropriate to the hypothesis before reader outcomes exist.

An equal-cost design is necessary evidence for the audit's comparison, not proof that the resulting
prose differs because of family or strategy alone. Crossed briefs/runs/raters and appropriate
uncertainty analysis remain requirements of the actual study.

## Regression evidence

`tests/test_writer_study.py` verifies:

- exact matched-cost cross-family arm binding;
- refusal to freeze the study after reader evidence exists;
- unknown usage remains unknown rather than zero;
- a cost gap outside the predeclared tolerance is reported rather than normalized away;
- edit arms require an earlier hash-bound source candidate in the same run;
- provider/model mismatches cannot be relabeled into a valid arm; and
- scene-run snapshot tampering and post-freeze writer operations invalidate the frozen study; and
- the two author-facing tools are registered.

Workspace validation rechecks every persisted writer-study artifact and its selection/run bindings.

## Consequences

The repository can now execute review §6.11 without inventing a second reader-preference workflow or
trusting post-hoc experiment labels. It still has no empirical result about writer-family diversity or
edit-versus-regeneration quality. Those conclusions require real generation/revision runs at the
predeclared cost condition followed by independent blind reader evidence.
