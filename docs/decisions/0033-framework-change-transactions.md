# ADR 0033 — Make framework changes evidence-bound, human-approved, and rollback-capable

Engineering decision record for the remaining Stage-5 governance gap identified by the September
27–28 audit/review. This implements the existing process policy; it does not change the constitution.

## 1. Failure observed

ADR 0011 made deterministic framework regressions executable, but adoption still depended on manual
discipline. There was no runtime object binding a proposed prompt/rubric/schema/process change to its
clean baseline, declared files, blind before/after evidence, approval criteria, human decision, or a
recoverable pre-change snapshot. A regression run could therefore be green while the evidence needed
by `constitution/change-policy.md` lived only in prose and rollback meant reconstructing edits by
hand.

## 2. Exact evidence

- `constitution/change-policy.md` requires eight fields for a process change: observed failure,
  exact evidence, root-layer diagnosis, minimal change, new regression case, blind before/after
  outputs, known trade-offs, and human approval status. Agents may propose; they may not approve their
  own constitutional changes.
- `docs/decisions/0011-framework-regression-harness.md` explicitly left thresholds, human approval,
  and rollback outside the executable harness.
- `docs/audits/2026-09-27/experiments.md` requires recorded before/after evidence, regression
  coverage, accepted trade-offs, and an authorized decision before adopting process interventions.

## 3. Root-layer diagnosis

The missing layer is **framework change governance**, above the regression checks themselves. A
deterministic regression pass can show that pinned invariants survived; it cannot establish that a
creative-process intervention helped, that the measured edit was the declared edit, or that a human
authorized adoption.

## 4. Minimal change

`src/fiction_compiler/framework_change.py` introduces an append-only transaction under
`<project>/.runs/framework-changes/<change-id>/`:

- `start` requires all eight policy fields, a declared repository-relative file scope, and
  predeclared comparison counts. It refuses a failing baseline, fingerprints the behavior-relevant
  framework, and snapshots exact bytes (including the fact that a declared future file did not yet
  exist).
- `evaluate` reruns regression after the operator edits the framework. It compares exact file
  manifests and marks the state mechanically ready only when the regression floor passes, at least
  one declared file actually changed, and no undeclared behavior-relevant file changed. For Python
  source edits it also verifies that the running interpreter imported the same source now on disk;
  a long-lived MCP server must be restarted rather than fingerprinting new files while executing old
  modules.
- `prepare_comparison` freezes supplied before/after outputs and stores the reveal map privately;
  evaluators receive only randomized A/B labels. `record_comparison` preserves ties/abstentions and
  records evaluator identity/kind. A model agent proposing the change may still judge a pair for
  diagnostic purposes, but that self-judgment is excluded from threshold evidence.
- `decide` separates evidence from authority. Approval requires a fresh mechanically-ready state and
  the predeclared blind-comparison threshold; only an explicit `decider_kind=human` record is
  accepted. The MCP wrapper additionally requires `confirm=true` so an authority record is not made
  accidentally.
- `rollback` requires an explicit human decider and restores only the declared pre-change paths. It first proves the current files still
  match the evaluated state, verifies every backup, then restores/deletes through `AtomicBatch` and
  reruns regression. Later edits are never silently overwritten. If rollback itself restores Python
  source, that in-process rerun is explicitly marked unverified/stale until a fresh process imports
  the restored code.
- `regression.framework_file_manifest` exposes the exact files behind the aggregate framework
  fingerprint, and `run_regressions(root=...)` makes the workflow independently testable.

The MCP surface mirrors the transaction, and `scripts/framework_change.py` provides the same path to
operators without MCP.

## 5. New regression cases

`tests/test_framework_change.py` proves that a clean declared edit can reach a human decision only
after blind independent evidence; agent self-judgment does not satisfy the threshold; undeclared
framework edits block readiness; rollback restores exact bytes and deletes declared newly-created
files; rollback refuses to clobber a later edit; and a dirty baseline or zero-observation policy
cannot start a transaction. Existing promotion tests continue to exercise `AtomicBatch` rollback.

## 6. Before/after interpretation

Before: framework regressions were fingerprinted, but the surrounding improvement transaction was a
manual checklist. After: the repository can show exactly what baseline was tested, which files were
declared and changed, what blinded evidence was collected, whether the predeclared evidence rule was
met, who made the human decision, and whether a rejected edit can still be restored safely.

This is a governance/correctness improvement. It is not evidence that any particular prompt, rubric,
or creative workflow improves fiction.

## 7. Known limits

- The local prototype records human identity as an assertion; it does not authenticate a person.
  Protection from an unrestricted local agent would require an external approval authority, as the
  audit threat model already notes.
- Before/after output text is supplied to the transaction and hash-bound when prepared. The system
  does not prove that a claimed `before` output was generated before the change; studies that need
  stronger provenance must freeze outputs at study start.
- The predeclared comparison rule is intentionally simple counts, not a significance test or a
  literary oracle. Underpowered, mixed, or missing evidence must remain inconclusive.
- `AtomicBatch` protects against ordinary exceptions and restores prior state on a failed commit; a
  hard process kill between filesystem operations is not a true cross-file transaction.
- Long-running MCP processes cannot evaluate newly edited Python source without restart. This is a
  deliberate refusal: file hashes are not evidence that the in-memory code actually executed.
- Provider/token/cost completeness is a separate measurement problem. ADR 0032 covers live role
  reviews; generation/revision accounting remains open before matched-cost claims.

## 8. Human approval status

Authorized as implementation of the user's requested audit/plan work. This ADR adds the mechanism
that future process changes must use; it does not approve any future framework proposal. Revert path:
the commit containing `framework_change.py`, its schemas/tests/CLI/tool entries, the small
`AtomicBatch` delete extension, and these documentation updates.
