# ADR 0050 — Complete Codex MCP execution

**Status:** accepted
**Date:** 2026-09-29

## Problem

ADR 0049 made repository-owned authoring operations MCP-visible, but visibility was not sufficient
for a real Codex authoring loop. Ordinary Codex runs still lacked enough MCP safety metadata/trust to
call the server without one-off approval overrides. A later signature audit also found handler
parameters that existed in Python but were absent from MCP schemas.

One workflow gap remained after those fixes: promotion policy can require a literary critique with
runtime provenance from `role_runner`, while MCP exposed only `role_prompt`. Codex could construct
the blind packet over MCP but had to leave MCP and invoke `scripts/run_role.py` to produce the
provider attempt and trusted critique.

## Decision

Make Codex execution and the live review path first-class MCP behavior:

- every tool descriptor carries MCP annotations for read-only, destructive, idempotent, and
  open-world behavior;
- the project-local Codex MCP registration uses `default_tools_approval_mode = "approve"` for this
  bounded repository-owned server while compiler confirmation and human gates remain in force;
- a registry invariant requires every public handler parameter and required parameter to match its
  MCP schema, preventing Python-only arguments;
- authoring tools embed the canonical project/character/scene/state-delta schemas instead of opaque
  `type: object` placeholders, including canonical id patterns and cross-field usage guidance so
  Codex can construct valid writes from `tools/list` without probing validation errors first;
- `run_role_review` exposes one live configured role and `run_review_panel` exposes several;
- both load only the human-owned roster, expose no transport/persona injection, persist the existing
  immutable provider attempt artifacts, and record critiques by default;
- the live tools are annotated `openWorldHint=true`, `readOnlyHint=false`,
  `idempotentHint=false`; deterministic `role_prompt` remains read-only and closed-world.

No new review semantics are introduced. The MCP bridge delegates to `role_runner.run_role` and
`run_panel`, so parsing, provider metadata, candidate binding, provenance, disagreement handling,
and promotion-gate rules stay centralized.

## Evidence

The focused tool/MCP/role-runner suite covers registry shape, annotation behavior, full
signature/schema parity, canonical nested authoring schemas, live-wrapper delegation, model-provider
failure conversion, and existing role-runner provenance behavior. The MCP protocol tests verify that
the new networked tools are advertised with open-world annotations.

Acceptance is also exercised with real Codex against the configured project-local MCP server:
read-only compiler calls, authoring mutations, candidate retrieval, context compilation, audits,
revision evidence, and confirmation guards must all be reachable without one-off tool overrides.
Live vendor acceptance depends on the configured API credentials/model ids; provider failures are
reported as tool errors and leave their attempt evidence according to the existing role-runner rules.

## Consequences

A Codex author can now remain on the MCP surface from project bootstrap and prose branching through
the policy-valid live literary-review path, scene readiness checks, confirmation-gated promotion, and
manuscript assembly. The configured vendor roster and external credentials remain human/environment
owned, and no arbitrary network target is exposed through MCP.
