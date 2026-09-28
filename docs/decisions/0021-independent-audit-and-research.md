# ADR 0021 — Record a rechecked audit without adopting its proposals

## Request and scope

The user requested a deep repository and literature review, independent checking of an existing audit, improved criticism, and proposed solutions. The reviewed source commit is `310e50cfe9b8087c8a2af64e6e74f098548e6824`.

## What changed and why

Added an audit, research synthesis, experiment/implementation proposals, reproducible isolated probes, baseline logs and a pre-change tracked-file digest manifest under `docs/audits/2026-09-27/`. Registered 32 primary/guidance references in `kb/source-register.json`, preserving existing entries and distinguishing access depth and evidential limits.

The report confirms the major acceptance/provenance failures, adds typed-value and proposition-identity defects and contextual-lint false positives, and qualifies unsupported causal or universal literary claims. It recommends running independent literary evaluation alongside trust repairs.

## Verification

The pre-change workspace validator passed, 193 unit tests passed, and 28 framework fixtures passed. Seven of nine critic cases ran; two require live LLM findings. Twenty-four additional observations were recorded from isolated probes using temporary projects and offline vendor responses. Final checks are recorded in the audit evidence directory.

## Decision and approval status

This records research and proposals only. Production source, maintained tests, story artifacts, schemas, prompts, rubric, model roster, skills and constitution were not changed. No literary process proposal is approved by this ADR. Blind before/after prose comparisons and live/human evaluations remain proposed work, with explicit exit conditions and tradeoffs in the experiment plan. No provider calls, commits, pushes or external publication were performed.

The audit is framework-wide, so this decision is recorded here following the existing repository-wide ADR convention rather than attached to an arbitrary fiction project. The pre-existing untracked `.agents/` and `.codegraph/` directories were left intact.
