# ADR 0041 — Cross-project repertoire diagnostic

## Status

Accepted and implemented, 2026-09-29.

## Context

The audit identified a possible house-style problem that cannot be diagnosed reliably by sentence
linting alone: several completed stories may converge on the same discourse architecture, focalization,
turn shape, ending action, or recurring object repertoire. The review specifically recommended typed
per-story features and a cross-project recurrence report while warning against turning difference into
a universal quality rule.

The repository previously had only one-off audit notes for this comparison. There was no maintained
project annotation, no explicit distinction between completed and partial manuscripts, and no tool an
author could use before planning the next story.

## Decision

Each project may declare `planning/story-repertoire.json` with project-owned slug tags for:

- ending form;
- turn form;
- resolution form;
- object motifs; and
- focalization.

The tags are descriptive local vocabulary, not a claim that these five facets form a universal theory
of fiction. A project also declares whether the evidence is a complete manuscript, partial manuscript,
or plan only. Completeness is checked against the scenes in the discourse plan and the materialized
manuscript chapters; a project cannot label a prefix as a complete story.

`fiction_compiler.repertoire.report` and the read-only `repertoire_report` MCP tool count exact tag
recurrence only among complete manuscripts. Partial projects remain visible but are excluded from
observed-story frequency claims. The report exposes per-tag counts, project membership, and descriptive
prevalence. It deliberately does not compute an aggregate originality or homogeneity score.

The five currently complete worked stories are annotated from their assembled manuscripts. The report
therefore makes one audit observation reproducible: all five end with a `small-physical-act` tag and all
five use `close-third` / `fixed-internal` focalization. `salt-in-the-wire` is identified as a partial
manuscript and its unknown ending/resolution are not guessed.

## Authority boundary

Recurrence is a prompt for inspection, not a defect by itself. A repeated ending or focalization may be
exactly right for a story. The report must not block promotion, rank stories, reward novelty for its own
sake, or optimize prose to evade AI/style detectors.

When recurrence is relevant during planning, the creative author may use it as input to divergent plan
generation or the `avoid-defaults` skill and propose alternatives. Deterministic code does not invent or
select those alternatives.

## Regression evidence

`tests/test_repertoire.py` checks:

- complete manuscripts are counted and partial prefixes are excluded;
- false completeness claims are invalid;
- the current repository reproduces the five-story small-physical-act and fixed-internal recurrence;
  and
- the report is exposed through the MCP registry.

Workspace validation checks every repertoire annotation against its schema.

## Consequences

The framework can now notice repeated project-level choices using maintained evidence rather than
retrospective prose impressions. This addresses the audit's local repertoire diagnostic proposal, but
does not validate a general originality metric, establish causal framework influence, or replace the
recommended controlled writer/reader studies.
