# ADR 0011 — Framework regression harness (P5)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. First slice of Priority 5 (framework self-improvement). Recorded
here because the change is framework-global.

## 1. Failure observed
The FRAMEWORK loop — the one that changes prompts, rubrics, schemas, and the compiler itself — was
procedural only: the `retrospective` skill and `constitution/change-policy.md` describe how a change
should be justified, but nothing *executed* a regression check. The review: "No framework rule should
be accepted merely because the same LLM that proposed it preferred its output," and it asks for fixed
regression fixtures, recorded versions/context hashes, and a runner. None existed, so a change to a
prompt/rubric/schema could silently break an invariant an ADR had established.

## 2. Exact evidence
- `docs/implementation-roadmap.md`: "The framework PDCA loop (Stage 5) still has only the
  `retrospective` skill + `change-policy`; its regression-fixture runner and run-manifest
  observability remain ⬜."
- No module ran fixtures; the only regression coverage was the unit suite (which tests code, not the
  invariants-as-fixtures the framework loop needs to gate a prompt/rubric/schema change).

## 3. Root-layer diagnosis
Framework self-improvement (meta) layer. The invariants the ADRs established were enforced only by
hand-written unit tests, with no fixture-driven, fingerprinted CHECK a framework change could be
gated on.

## 4. Minimal proposed change
- `src/fiction_compiler/regression.py`: a closed whitelist `CHECKS` of deterministic checks
  (`defaultness_verdict`, `revision_decision`, `tournament_decision`, `ontology_valid`) — a fixture
  names a check and asserts its output, so a fixture can never execute arbitrary code. `run_fixture`
  / `run_regressions` report pass/fail; `framework_manifest()` returns a content fingerprint of the
  deterministic framework (schemas + KB index + package source) so a run is anchored to *what* ran.
- `regression/fixtures.json`: fixed fixtures, each pinning an ADR invariant (defaultness detection,
  the ADR-0009/0010 revision traps incl. the waiver path, ADR-0007 tournament select/defer, ADR-0005
  ontology typo rejection).
- `scripts/run_regression.py`: CLI that prints per-fixture pass/fail + the fingerprint and exits
  non-zero on any failure (so it gates CI or an agent's framework change). MCP tool `run_regression`.

## 5. New regression case
`tests/test_regression.py`: the committed fixtures all pass; a deliberately wrong expectation is
detected as a failure; an unknown check and a broken fixture input are failures, not crashes; the
manifest yields a 64-hex framework fingerprint; the MCP tool runs the fixtures.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: changing a rubric or schema had no automated guard beyond the unit suite; the framework
  loop could "congratulate itself".
- After: `python3 scripts/run_regression.py` prints `9/9 passed. framework_fingerprint=…` and exits
  0; break an invariant (e.g. weaken the defaultness catalog) and the matching fixture fails and the
  command exits non-zero. Suite 111 → 117; `validate_workspace` passes.

## 7. Known trade-offs
- Only deterministic, inline-fixturable checks are covered. Prompt/rubric changes whose effect is on
  *LLM* output are not tested here (that needs the blind before/after human+model evaluation of P6);
  this harness pins the deterministic floor beneath them.
- The manifest fingerprints schemas + KB index + package source, not prompt/agent files or model
  parameters; extending it to those (and recording token/cost) is a later slice.
- The runner reports regressions; the *acceptance/rollback* workflow (thresholds, human approval,
  reverting the change) still lives in `change-policy.md` + the `retrospective` skill and is not
  automated end-to-end.

## 8. Human approval status
Authorized as the user-directed "do P5" step. The constitution (`AGENTS.md`) is unchanged. Revert
path: remove `src/fiction_compiler/regression.py`, `regression/fixtures.json`,
`scripts/run_regression.py`, the `run_regression` tool + import in `tools.py`, and
`tests/test_regression.py`.
