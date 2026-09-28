# ADR 0025 — Type promise triggers and payoff events

## Context

The promise ledger previously represented only `{id, text, owed_by?}` plus a later closed id. That
could detect “closed without opening” and “still open at manuscript end,” but it could not tell an
intentional unresolved setup from an obligation whose planned trigger/payoff had already occurred.
The 2026-09-28 review identified this as part of the backward-revision/global-coherence gap.

## Decision

Promise declarations may now optionally name `trigger_event` and `payoff_event`, both canonical
`evt-*` ids. Legacy declarations remain valid. State replay preserves full promise definitions while
keeping the existing `open_promises: id -> text` view for compatibility.

Canon audit adds plan-level structural checks:

- trigger/payoff event ids must resolve in the event graph;
- a promise cannot be closed before its declared trigger;
- when a promise declares a payoff event, closure must occur in a scene that declares that event;
- if the payoff event occurs and the promise remains open, that is material;
- an open promise whose trigger has occurred is material at manuscript end; an untriggered/legacy
  open promise remains advisory (`minor`).

These checks establish consistency between the event plan and promise ledger. They do not prove that
the prose makes a payoff legible; that remains part of prose realization/reader evaluation.

## Verification

Focused state, hard-audit, context, and schema tests cover legacy compatibility, preserved promise
metadata, triggered unpaid promises, missing closure at payoff, and unresolved event references.

## Consequences

Projects can opt into stronger setup/payoff semantics where the narrative contract needs them without
forcing every open question into a rigid event model. This also gives later whole-work invalidation a
typed dependency to reason about.
