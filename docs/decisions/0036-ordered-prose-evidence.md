# ADR 0036 — Bind and order prose evidence

Engineering decision record for the prose-claim verification defect identified in the September 27
audit. This closes a deterministic consistency hole; it does not establish extractor recall or
literary quality.

## 1. Failure observed

`prose_audit` was candidate-hash aware but still accepted free-text evidence by substring and judged
epistemic changes at whole-scene granularity. If a scene eventually taught the focalizer a fact, a
claim near the beginning of the prose could use that later knowledge and pass. Repeated evidence text
also had no stable occurrence identity. The result mixed two different questions: whether extracted
claims are logically consistent, and whether the extractor found everything relevant in the prose.

## 2. Exact evidence

- `docs/audits/2026-09-27/audit.md` §“Claim verification is incomplete and has unsound rules” states
  that “A claim occurring early can use knowledge acquired later in the same scene.”
- The same finding calls for binding candidate/spec/state/claims, validating evidence spans, adding
  ordered observations, and returning coverage/uncertainty separately from logical consistency.
- The audit explicitly warns against treating an empty or incomplete extraction as proof that prose
  contains no relevant claim.

## 3. Root-layer diagnosis

The defect sits at the **prose extraction → executable scene IR** boundary. The state delta is an
end-of-scene aggregate; it cannot by itself prove when the prose makes a claim. Event alignment is
the existing bridge between plan-blind prose observations and canonical event identity, so temporal
claim verification should use that bridge rather than invent a second scene-order representation.

## 4. Decision

Candidate-bound `prose-claims` now attest the deterministic inputs used by the verifier:

- candidate bytes (`candidate_sha256`);
- scene spec (`spec_sha256`);
- canonical serialization of reconstructed pre-scene state (`state_before_sha256`); and
- scene state delta (`state_delta_sha256`).

They also carry `audit_context_sha256`, a canonical semantic digest over the spec, reconstructed
pre-scene state, scene delta, event graph, discourse plan, and current canonical character IDs. The
explicit hashes make the major inputs inspectable; the context digest prevents a changed event graph
or tense/character context from silently reinterpreting an old extraction.

Every candidate-bound claim and observed event carries an exact character span into the decoded
UTF-8 candidate. The verifier rejects missing, out-of-range, or text-mismatching spans, so repeated
phrases have an explicit occurrence rather than relying on substring membership.

`belief_changes.event` remains provenance for the event that informed a stance, as established by ADR
0034; it is not overloaded as execution timing. An epistemic state change can separately declare
`at_event`, meaning the canonical event during which that change becomes effective. Hard audit
requires `at_event` to be an event this scene executes and to carry the matching knowledge/belief
effect. Prose audit then uses the plan-blind observation's evidence span and separate plan-aware event
alignment as ordering evidence. Legacy changes without `at_event` remain valid state deltas, but they
cannot prove within-scene timing to the prose verifier.

Typed `predicate_changes` use the same optional `at_event` execution binding. Hard audit requires the
bound event to execute in the scene and carry the same typed effect, and a change bound to a later
event cannot satisfy an earlier event's effect. This lets prose verification replay load-bearing
predicate state such as `located_at` without treating the aggregate end-of-scene delta as if it were
already true at scene entry.

For an epistemic prose claim, the verifier replays aligned, event-bound truth and belief changes up to
the claim's exact span. A verified supporting event that occurs after the claim is a material temporal
leak. A fact removal or belief correction before the claim can likewise invalidate state that held at
scene entry. If a relevant state change lacks an execution binding/alignment, the result is
`uncertain`; uncertainty is not converted into either a pass or a contradiction. Factive knowledge
requires both true belief and current truth at the claim position.

World-fact claims use the same ordered event evidence. A fact added later in the scene cannot support
an earlier `states_fact` claim; a fact removed before a claim no longer supports it. When the delta
changes truth but no executed canonical event and aligned prose span establish when that change takes
effect, the result is uncertain rather than a fabricated pass/failure.

`located_at` claims replay event-bound predicate changes over the reconstructed pre-scene predicate
state. False-valued stored predicates are not treated as active locations. A claim before an aligned
move is material; the same claim after the aligned remove/add move can pass. Unbound or unaligned
movement remains explicit uncertainty.

The interiority rule now consults the project discourse plan's focalization mode. Fixed-internal (or
legacy unspecified) narration retains the single-focalizer constraint; an explicitly variable or
omniscient/non-fixed mode is not labeled head-hopping solely because another character's interiority
appears. This is a narrow policy read, not a universal narratology schema.

The result now reports two separate surfaces:

- `consistency`: deterministic status for the extracted claims plus explicit unresolved ordering; and
- `coverage`: always `unverified` in this deterministic pass, because claim extraction completeness is
  an empirical property of the extractor.

## 5. Compatibility boundary

Unbound claim objects used by deterministic regression fixtures can still be checked against scene
state without pretending they carry candidate provenance. Once a `candidate` is supplied, the
candidate/spec/pre-state/delta/context bindings and exact evidence spans are required at runtime. The
`prose_claim_bindings` tool returns the hashes an extraction workflow must copy into its artifact.

Legacy `knowledge_changes` gains optional source `event` provenance and `at_event`; `belief_changes`
gains `at_event` while retaining the existing source `event`. New belief work continues to prefer
`belief_changes`; the legacy field remains supported for backward compatibility.

## 6. Regression cases

Tests prove that:

- repeated evidence text can be pinned to one exact occurrence and a mismatching span is rejected;
- changing the scene spec after extraction makes the claims artifact stale;
- a knowledge claim before its aligned learning event is material;
- the same claim after its aligned learning event passes;
- pre-scene knowledge is no longer factive after an aligned fact-removal event, and a corrected prior
  belief no longer satisfies a later claim;
- a world-fact claim before its establishing event is material, while the same claim after that event
  passes; missing fact-order evidence is uncertain;
- false-valued locations are inactive, and event-bound remove/add movement changes which location can
  support a claim at each prose position;
- predicate changes bound to a later event cannot satisfy an earlier event effect;
- explicitly variable focalization does not trigger the fixed-internal head-hopping rule;
- missing event/span ordering produces explicit uncertainty while logical consistency remains
  separately reported;
- a false proposition cannot become factive knowledge merely because a belief update exists; and
- `at_event` is material when its event does not carry the corresponding effect, while source `event`
  remains provenance and only needs to resolve.

## 7. Known limits

- Deterministic verification still cannot establish extraction recall. The ADR 0030 live/hidden-set
  calibration remains required before prose audit gains broader gate authority.
- Free-text turn, exit-state, affect, subtext, and plan quality remain reader/model evaluation tasks.
- The discourse plan still has no dedicated schema for the full space of narration/focalization
  policies; this change only stops imposing fixed-internal access when a project explicitly declares
  a different mode.
- Non-linear scenes still lack fabula-ordered state reconstruction. Ordered prose spans describe
  discourse position, while historical world-state reconstruction remains future work.

## 8. Human approval status

Authorized as implementation of the user-requested September audit/plan. The change is intentionally
limited to provenance, evidence identity, temporal consistency, and uncertainty representation.
