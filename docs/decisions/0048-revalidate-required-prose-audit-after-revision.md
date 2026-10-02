# ADR 0048 — Revalidate policy-required prose audit after revision

## Context

Backward revision already rebases immutable acceptance history, reruns the deterministic scene hard
audit, and conservatively reopens literary, reader, voice, and whole-work review. A deeper check found
one missing invalidation boundary for projects whose review policy sets `require_prose_audit: true`.

Candidate-bound `prose-claims` are intentionally stronger than a candidate hash. They also bind the
scene spec, reconstructed state before the scene, state delta, and the complete deterministic audit
context. An upstream or retroactive fabula revision can therefore make a previously accepted prose
audit stale while leaving the downstream prose bytes unchanged. The frozen critique cannot prove
freshness by itself because it stores the candidate hash and findings, not the extractor's complete
binding set.

ADR 0030 remains controlling: extractor/alignment calibration is not strong enough to make prose audit
mandatory for every project. The fix must preserve the explicit project policy instead of silently
turning an experimental boundary into a universal gate.

## Decision

Post-revision invalidation now derives the deterministic prose-audit requirement from the **review
policy frozen inside each affected acceptance object**.

- If that policy did not require prose audit, backward revision behavior is unchanged.
- If it did, the affected scene gains a pending `prose_audit` scope alongside the existing hard and
  subjective scopes. The old candidate-bound critique remains historical evidence but cannot satisfy
  the new context.
- The prose scope is closed through `recheck_post_revision_prose_audit`, which accepts a newly extracted
  `prose-claims` artifact and reruns the existing deterministic verifier against the active acceptance.
  Candidate, spec, state-before, delta, and audit-context bindings must all be current. The accepted
  candidate source plus mutable spec/delta views must still match their frozen acceptance bytes.
- Every attempted valid rerun is written as content-addressed evidence under
  `.runs/post-revision/prose-audit/`. A clean deterministic `pass` removes only `prose_audit`; an
  `uncertain`, `revise`, or `reject` result remains visible as `needs_attention` and leaves the scope
  pending. Stale bindings are rejected before they can become evidence.

Subjective scopes keep ADR 0031's separate evidence-and-human-resolution path. This ADR does not let a
model verdict automatically resolve literary, reader, voice, or whole-work review.

## Why the old critique is insufficient

Reusing a prior `prose-audit` critique solely because its `candidate_sha256` still matches would defeat
the purpose of the stronger prose-claims binding. The exact defect is a state/context change with
unchanged prose bytes. Since the original extractor claims are not guaranteed to be retained in the
critique, the system records the scope as pending rather than fabricating a deterministic replay.

## Verification

Regression tests cover both policy branches: the default policy does not acquire a new requirement,
while an opted-in scene becomes pending after an upstream state revision. Pre-revision claims fail on
their stale `state_before_sha256`, changed mutable scene inputs cannot be used as substitute accepted
inputs, and newly rebound claims produce append-only evidence and clear only the prose-audit scope.
Existing hard and subjective post-revision behavior remains unchanged.
