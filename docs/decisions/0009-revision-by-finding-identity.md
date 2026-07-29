# ADR 0009 — Revision acceptance by finding identity, not counts

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. First slice of Priority 3. Recorded here because the change is
framework-global.

## 1. Failure observed
`evaluate_revision` judged a revision by **counting** findings per severity and dimension. The
review's motivating example defeats a count: two `minor` findings replaced by one *new* `material`
finding makes the count fall (2 → 1), so a count-only check reads a regression as an improvement and
**accepts** it. Counts also cannot tell a *persisted* finding from a *newly introduced* one, nor
notice the same finding escalating in severity.

## 2. Exact evidence
- `src/fiction_compiler/revision.py` `evaluate_revision`: `target_before/target_after` and
  `regressions` were computed from `Counter`s over dimensions/severities; the accept branch fired on
  `target_after < target_before`, and the regression branch only compared serious *counts* per
  dimension.
- The review: "Revision compares counts, not actual defects … Give findings stable fingerprints and
  compare resolved / unchanged / newly introduced / severity increases."

## 3. Root-layer diagnosis
Revision-evaluation (story PDCA CHECK/ACT) layer. The evidence — each finding's dimension and exact
evidence span — was present; the evaluator simply reduced it to counts before deciding.

## 4. Minimal proposed change (additive to the existing decision)
- `revision.py`: `finding_fingerprint(finding)` = `(dimension, normalized evidence)` — deliberately
  severity-independent, so a defect can be tracked across a revision. `diff_findings(before, after)`
  classifies every finding as **fixed / persisted / worsened / newly_introduced** (keeping the worst
  severity per fingerprint).
- `evaluate_revision` now also rejects on **identity** regression: any *new* serious
  (material/fatal) finding, or the same finding *worsened* to a serious severity, blocks acceptance —
  in addition to the existing count-based and fatal-count checks. The escalate/stop/continue logic is
  unchanged. The outcome carries `fixed_findings / persisted_findings / worsened_findings /
  new_findings`.
- `tools.evaluate_revision` returns those four lists; `record_revision` logs a compact
  `finding_diff` (counts of each) to `revision-log.jsonl`.

## 5. New regression case
`tests/test_revision.py`: `diff_findings` classifies fixed/persisted/worsened/new correctly;
`finding_fingerprint` ignores severity and whitespace; the review's example (2 minor → 1 new
material, count falls) is **rejected**; a same-identity finding escalated minor→material is rejected;
a cleanly fixed target is accepted and reported in `fixed_findings`. The eight pre-existing
count-based decision tests still pass (evidence-less findings collapse to one fingerprint per
dimension, so no spurious new/worsened arises).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `evaluate_revision(before=2×minor cliche, after=1×material cliche, target=cliche)` →
  `accept` (count 2 → 1).
- After: same input → `reject_regression` citing `new material cliche`, and the outcome lists the
  new finding. Suite 103 → 108; `validate_workspace` passes.

## 7. Known trade-offs
- Identity is `(dimension, normalized evidence)`; a revision that rewords the evidence for the *same*
  underlying defect reads as fixed + new rather than persisted. This is conservative (it will not
  silently accept), but it is not semantic matching.
- "Rerun **all** relevant audits after a revision" is only partly delivered: the deterministic
  prose-dependent audit is the defaultness linter (which `record_revision` already runs). The hard
  audit is spec/delta-level and prose-independent, so rerunning it on a prose revision is a no-op
  until the hard audit reads prose (review §4, deferred). Literary critiques remain agent-supplied.
- Acceptance still *triggers* on the count-based target improvement; identity is used to *block*
  regressions and to report the diff. Making the accept trigger itself fingerprint-based (target
  finding id resolved) is a further refinement.

## 8. Human approval status
Authorized as part of the user-directed "continue both" step. The constitution (`AGENTS.md`) is
unchanged. Revert path: git history of `revision.py`, `tools.py`, and `tests/test_revision.py`.
