# ADR 0004 — Executable story IR: typed predicates and directional relationships

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. This is the first slice of the reviewer's Priority 1 ("make the
story IR genuinely executable"). Recorded here because the change is framework-global.

## 1. Failure observed
The event graph looked structured but was not *executable*, and story state was too shallow to make
it so:
- `event.schema` `preconditions`/`effects` were `array of string`; real events mixed ids and prose
  (`"jonas is the station operator"`). The hard audit only checked that a scene's `required_events`
  **existed** — it never evaluated a precondition or effect against anything. The causal graph could
  not prove actors were present, capabilities held, or that an event's effects matched the delta.
- `StoryState.relationships` was keyed by an unordered `frozenset`, so it could not represent
  directional state ("A trusts B" vs "B trusts A", "A owes B"). There was no place for spatial,
  object, or world-rule state at all.

## 2. Exact evidence
- `schemas/event.schema.json` (pre-change): `"preconditions": {"type": "array", "items": {"type":
  "string"}}`; same for `effects`.
- `projects/salt-in-the-wire/planning/event-graph.json` `evt-relay-cut`: `preconditions:
  ["fact-chart-mis-surveyed", "jonas is the station operator"]` — an id and a prose sentence.
- `src/fiction_compiler/hard_audit.py` (pre-change) lines 131–134: the only event check was
  existence in the graph.
- `src/fiction_compiler/state.py`: `relationships: dict[frozenset[str], str]`, keyed unordered.

## 3. Root-layer diagnosis
Computational-operations layer (typed intermediate representation) and the verification layer above
it. The IR lacked the typed atoms a deterministic causal check needs; the relationship rep discarded
direction. No prose or narrative change is implicated.

## 4. Minimal proposed change (additive; backward-compatible)
- **Typed predicates.** `StoryState.predicates: (predicate, subject, object?) -> value`, seeded from
  an optional `canon/world-state.jsonl` and mutated by a new optional delta field
  `predicate_changes: [{op: add|remove, predicate, subject, object?, value?}]`. A unified
  `StoryState.holds(predicate, subject, object?)` query bridges the stores: `knows` consults
  per-character knowledge, a relationship verb consults relationship dimensions, everything else the
  predicate store.
- **Directional relationships.** `relationships` is now keyed by an ordered `(subject, object)` pair
  mapping `dimension -> value`. A legacy `{pair, state}` record (seed or `relationship_changes`) is
  stored symmetrically under the `state` dimension, so `relationship(a, b)` is unchanged; a new
  optional delta field `relationship_edges: [{subject, object, dimension, value?}]` and
  `relationship_directed(subject, object, dimension)` express direction (trusts/fears/owes).
- **Executable event graph.** `event.schema` preconditions/effects accept a legacy string **or** a
  typed atom. `hard_audit.audit_scene` now evaluates each required event's typed preconditions
  against `reconstruct_state_before` (unmet → material), checks each typed effect appears in the
  scene's `predicate_changes` (missing → material), and flags a prose precondition with a
  migrate-to-typed advisory (minor). `world-state.jsonl` is added to the hashed seed ledgers (ADR
  0003) so it is tamper-covered.

## 5. New regression case
`tests/test_state.py` (`TypedIRStateTests`): seed predicate + directional relationship reconstruct;
delta predicate add/remove; directionality (trust one way ≠ the other); `holds` bridges knowledge.
`tests/test_hard_audit.py` (`HardAuditExecutableEventTests`): an unmet typed precondition and a
missing typed effect are each material; a satisfied precondition with a recorded effect passes; a
prose precondition earns a minor advisory without blocking.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `audit_scene` on a scene requiring `evt-relay-cut` passed regardless of whether the actor
  was present or the effect recorded — the graph was descriptive.
- After: an unmet precondition yields `revise` with `evt-relay-cut precondition
  located_at(char-jonas, loc-station)`; recording the state (`world-state.jsonl`) and the effect
  (`predicate_changes`) yields `pass`. Suite 72 → 79; `validate_workspace` still passes (committed
  examples use only legacy string preconditions/relationships, all still valid).

## 7. Known trade-offs
- The predicate vocabulary is open (any `predicate` string). No ontology yet constrains which
  predicates/arities are legal, so a typo in a predicate name is silently a different predicate.
- Effect/precondition checking is opt-in per event: legacy string preconditions are tolerated (minor
  advisory), so the executable guarantee only covers events an author has migrated to typed atoms.
- Directional relationships and predicates are additive stores; the seed `relationship-state.jsonl`
  and `relationship_changes` keep their symmetric form, so a project is not *forced* to model
  direction.
- Fabula-time vs discourse-order separation (a later P1 slice) is **not** in this change; id order is
  still treated as fabula order (ADR 0001).

## 8. Human approval status
Authorized as the user-selected "keystone + directional relationships" first slice of Priority 1. The
constitution (`AGENTS.md`) is unchanged. Revert path: git history of `state.py`, `hard_audit.py`,
`context.py`, `tools.py`, `integrity.py`, `schemas/event.schema.json`, `schemas/state-delta.schema.json`,
and the added tests / `world-state.jsonl` ledgers.
