# ADR 0035 — Execute linear scene events in beat order

Engineering decision record for the event-graph execution defect identified in the September 27
audit. This is a deterministic causal-consistency improvement, not evidence about literary quality.

## 1. Failure observed

`hard_audit.audit_scene` previously checked every required event against one state reconstructed
before the scene. An earlier beat therefore could not establish a later beat's precondition. Event
`causes` only checked dictionary membership, fact causes were misread as missing events, graph edges
were not cycle-checked, and a canonical event could be listed again in a flashback scene with no
distinction between re-narrating it and executing its world effects twice.

## 2. Exact evidence

- `docs/audits/2026-09-27/audit.md` §“The event graph remains mostly descriptive” calls for a small
  ordered beat executor for linear scenes, precondition checks immediately before each beat, and
  event identity separate from discourse appearances.
- The audit specifically requires that flashback narration not apply the same world event twice.
- Existing project graphs use both `fact-*` and `evt-*` causal references; treating every `causes`
  item as an event reference was therefore semantically wrong.

## 3. Root-layer diagnosis

The defect belongs to the executable **fabula/event IR**. Aggregate scene deltas prove an end state;
they do not establish the causal order that produced it. The auditor needs a temporary beat-level
state while checking the ordered scene plan.

## 4. Minimal change

For a linear scene, `required_events` is now an execution order:

1. reconstruct the state before the scene;
2. check an event's fact/event/typed preconditions and causes against the state immediately before
   that event;
3. require every typed effect to have a matching scene-delta change;
4. apply only that event's matched effect to an audit-only shadow state; and
5. continue to the next required event.

Typed predicate and epistemic effects participate in the shadow execution. Event effects may now
also declare `{op, fact}` so a beat can establish/remove a stable fact that a later beat consumes.
The aggregate `state-delta.json` remains canonical persistence; the executor never mutates canon.

`causes` now distinguishes `fact-*` truth from `evt-*` predecessor execution. Canon audit validates
event identity, cause/edge endpoints, and directed cycles using the combined cause/edge graph.

`required_events` means **execute this canonical world event**. A scene that re-presents an event in
discourse without executing it uses `event_references`. Re-executing an event already executed by an
earlier accepted scene is material. Prose realization reports executable required events and
discourse-only references separately, so a flashback/recollection can still be checked for presence
without changing world state again.

Non-linear scenes continue to check their preconditions against the reconstructed pre-scene state;
they do not yet receive fabula-ordered reconstruction. This intentionally stops at the audit's
“linear scenes first” boundary.

## 5. New regression cases

Tests prove that:

- event A can establish a typed predicate required by event B, while reversing A/B fails both the
  cause and precondition checks;
- a fact effect can establish a later `fact-*` precondition;
- a knowledge effect cannot become factive merely because the aggregate scene delta adds the fact
  later; the event must establish truth before knowledge;
- a directed event cycle and unresolved graph edge are material;
- a previously executed event fails when listed for execution again but passes as an
  `event_reference`; and
- prose realization keeps discourse-only references separate from world-event execution.

## 6. Before/after interpretation

Before: the event graph constrained scene membership but not within-scene causal order. After: the
linear event list is an executable causal proof over declared effects, while repeated discourse
appearances no longer imply repeated world mutation.

This does not prove that the event decomposition is complete, that extracted prose caused the delta,
or that ordered beats improve reader experience.

## 7. Known limits

- The executor is intentionally total-order only. Partial-order/concurrent execution waits for a
  project that needs it.
- Resource operations remain ordered within `state-delta.resource_changes`; event-level resource
  effects are not yet part of `event.schema.json`.
- Non-linear scenes still lack fabula-ordered reconstruction. A newly introduced past event in an
  analepsis cannot yet be replayed into a historical snapshot safely.
- `event_references` records discourse identity, not how the prose frames that appearance; the
  plan-aware realization pass only records realized/omitted/unverified alignment.

## 8. Human approval status

Authorized as implementation of the user-requested September audit/plan. Revert path is the commit
containing the hard-audit/event-schema/prose-realization changes and their tests. Partial-order or
fabula reconstruction remains a separate future decision.
