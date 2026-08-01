# ADR 0018 — Agents-best-practices audit: agent-legible critique lifecycle + cache-prefix hygiene

Engineering decision record for repo-global changes, following the eight fields required by
`constitution/change-policy.md`. Prompted by a user-directed audit of this project *as an agent
harness* against the `agents-best-practices` skill.

## 1. Failure observed
The fiction compiler is itself an agent harness (an MCP tool surface + subagent critics + a gated
state change), and an audit against agent-harness best practices surfaced two mechanical defects that
this session's own dogfooding had already paid for by hand:
- **The critique seam is not agent-legible.** The promotion gate's evidence — `critiques/*.json`,
  each bound to the bytes it judged by `candidate_sha256` — was produced entirely by the model
  hand-writing JSON: copying the sha from lint output, setting `audit_class`, keeping the verdict
  consistent with finding severities, and picking a filename. Across the two stories built this
  session that was ~60 hand-authored files. A single wrong hex digit silently denies a critique at
  the gate; a `pass` that accidentally carries a `material` finding is a contradiction the gate
  rejects only at promote time. The best-practice rule — *"repeated failures should become tools;
  make validation signals legible without manual copy"* — was unmet.
- **Cache-prefix poisoning.** `context.compile_bundle` returned `generated_at` (a per-call UTC
  timestamp) as the **first** field of the drafting/audit bundle, violating the explicit gotcha
  *"do not put timestamps at the start of cacheable prompts"* — any cached prefix that embeds the
  bundle fragments on every compile.

## 2. Exact evidence
- `src/fiction_compiler/tools.py` (pre-change) had no critique-writing tool; `promote.py`
  `evaluate_audit_gate` credits a critique toward its class only when `candidate_sha256 ==` the
  promoted bytes — a value the model had to transcribe by hand into every file.
- `src/fiction_compiler/context.py` (pre-change) `return {"generated_at": datetime.now(...), ...}`
  as the leading key of the bundle.

## 3. Root-layer diagnosis
Harness/tooling layer (agent legibility + prompt-cache hygiene), not the story loop. The generative
work was fine; the *environment* forced an error-prone manual transcription and shipped a volatile
value in a cacheable prefix.

## 4. Minimal proposed change
- `src/fiction_compiler/critique.py`:
  - `record_critique(project, scene_id, candidate, critic, verdict, findings, …)` — stamps
    `candidate_sha256` from the candidate file's actual bytes, derives `audit_class` from the critic
    (reusing `promote.AUDIT_CLASS_BY_CRITIC`), validates against `critique.schema`, and **refuses a
    verdict/severity contradiction** (`consistency_problem`: a `pass` may not carry material/fatal)
    with a model-readable remediation message — so the bad artifact cannot be written. Path-confined
    to the project. The scene-level hard audit uses `candidate == scene_id` (no sha).
  - `scene_status(project, scene_id, candidate)` — read-only inspector that runs the *real* gate
    (`evaluate_audit_gate`) plus the structural preconditions (`spec`, schema-valid matching delta)
    and reports `audit_gate.ready` + `audit_gate.reasons` **without mutating** canon — the
    validator-with-remediation pattern, shifted left of `promote`.
  - Both exposed as MCP tools in `tools.py`.
- `src/fiction_compiler/context.py`: move `generated_at` to the **end** of the bundle; the stable,
  deterministic content now leads.

## 5. New regression case
`regression/fixtures.json`: `critique_consistency` check with three fixtures — a `pass` carrying a
`material` finding fails; a clean `pass` passes; a `revise` may carry a `material` finding.
`tests/test_critique.py` covers sha stamping, audit-class derivation, the pass/material refusal (and
that nothing is written), schema rejection of a malformed finding, `scene_status` gate reasons, and —
the correctness win — that **editing a candidate after it was judged makes `scene_status.ready` go
false** (the stale sha is no longer credited).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: the model transcribed shas and audit classes by hand into every critique; a wrong digit or
  an inconsistent verdict was caught only at promote time (or never); the bundle's first field was a
  timestamp.
- After: one call stamps the sha and class and refuses inconsistencies up front; `scene_status`
  answers "would promote succeed, and why not" before any state change; the bundle prefix is stable.
  Framework regression 16→19; suite 140→150 (new `test_critique.py`); `validate_workspace` passes.

## 7. Known trade-offs
- The live MCP server is a long-lived process and will not expose the two new tools until it is
  restarted (the same staleness noted for `run_regression` in earlier sessions); the library
  functions and CLI path work immediately.
- `record_critique` records whatever verdict/findings the caller supplies; it enforces *consistency*
  and *binding*, not *critical quality* — the independent subagent critics remain the source of the
  judgment. It does not itself run a critic.
- Deferred (surfaced by the same audit, not built here): (a) framing candidate prose as untrusted
  data to judge subagents (prompt-injection boundary); (b) a critic-calibration eval (planted-defect
  fixtures measuring critic recall); (c) an append-only scene-loop trace under `.runs/`; (d) routing
  the blind-boundary through `tournament.anonymize` in code rather than by hand in agent prompts.

## 8. Human approval status
Authorized as a user-directed change: "use the agents-best-practices skill to improve the project;
find deep, meaningful solutions." The constitution (`AGENTS.md`) is unchanged. Revert path: git
history of `critique.py`, `context.py`, `tools.py`, `regression.py`, `regression/fixtures.json`, and
`tests/test_critique.py`.
