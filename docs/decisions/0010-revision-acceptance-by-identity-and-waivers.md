# ADR 0010 — Revision acceptance by identity, and waivers

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Completes Priority 3 (revision by finding identity), building on
ADR 0009. Recorded here because the change is framework-global.

## 1. Failure observed
ADR 0009 made *regression detection* identity-based but left two gaps: (a) the **acceptance** trigger
still fired on a count improvement (`target_after < target_before`), so a revision could be accepted
because a target count fell even if no specific target finding was actually resolved; and (b) there
was no way to **waive** a finding — a deliberate, human-approved regression (e.g. a genre obligation)
would block acceptance forever, with no recorded justification. The operating contract's
`pass_with_waiver` idea had no implementation.

## 2. Exact evidence
- `src/fiction_compiler/revision.py` `evaluate_revision`: `target_improved = target_after <
  target_before` (count) gated the ACCEPT branch; and the reject trigger used a count-based
  `regressions` list that could not be waived.
- The review: "Revision acceptance should operate on issue identity, not only counts," and lists
  `waived` / `disputed` among the states a revision diff should track.

## 3. Root-layer diagnosis
Revision-evaluation (story PDCA ACT) layer. The identity diff existed (ADR 0009) but the accept
decision and the regression list were still count-shaped, and waivers were absent.

## 4. Minimal proposed change
- **Identity-based acceptance.** The target defect is "resolved" only when a target-dimension finding
  is *fixed by fingerprint* and there is no unwaived serious regression in that dimension
  (`target_resolved`); the ACCEPT branch now fires on `a.fatal == 0 and target_resolved`. The
  count-based `regressions` list is replaced by `regression_dims` derived from the (waiver-filtered)
  identity `new_serious`/`worsened_serious`, so `material_regressions` reports the same shape without
  a separate count path.
- **Waivers.** `evaluate_revision(..., waivers)` accepts findings (by dimension + normalized
  evidence, each carrying a `reason`) that are deliberately accepted: a waived finding is excluded
  from `new_serious`/`worsened_serious` (so it neither blocks nor counts as a regression) and is
  reported in `waived_findings` with its reason. Exposed through the `evaluate_revision` MCP tool.

## 5. New regression case
`tests/test_revision.py`: a target finding that merely *persists* (no identity fix) does not accept
even absent a regression; a waived new material finding accepts and is reported with its reason, while
the same revision *without* the waiver is rejected. `regression/fixtures.json` pins the waiver
invariant for the framework harness (ADR 0011). All prior revision tests still pass.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `evaluate_revision(before=1 material cliche, after=1 material style, target=cliche)` with a
  human waiver on the style finding → `reject_regression` (no waiver path); a count drop with no
  identity fix → `accept`.
- After: the waived case → `accept` (waived finding recorded with `reason: genre obligation`); a
  persisted-only target → not accepted. Suite 111 → 111 pass (this slice's 3 new tests replace a
  flawed one). `validate_workspace` passes.

## 7. Known trade-offs
- A waiver is trusted as supplied (like judge rankings); the engine records `reason`/`approved_by`
  but does not itself verify human approval — that gate lives in the workflow, not the function.
- Waiver identity is `(dimension, normalized evidence)`; reword the evidence and the waiver no longer
  matches (conservative — it will re-block rather than silently pass).
- Acceptance still requires a count-independent *fix* of the target; a revision that only downgrades a
  finding's severity (material→minor, same fingerprint) is treated as persisted, not resolved, so it
  will not auto-accept. That is defensible but stricter than a human might be.

## 8. Human approval status
Authorized as the user-directed "finish P3" step. The constitution (`AGENTS.md`) is unchanged. Revert
path: git history of `revision.py`, `tools.py`, and `tests/test_revision.py`.
