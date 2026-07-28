# ADR 0001 — Structured state deltas and canon ledgers

Engineering decision record for an infrastructure schema change, following the eight
fields required by `constitution/change-policy.md`. Recorded here (not under a single
`projects/<slug>/decisions/`) because the change is repo-global, not story-specific.

## 1. Failure observed
The original `state-delta.schema.json` stored `knowledge_changes`,
`relationship_changes`, `promises_opened`, `facts_added`, etc. as arrays of free-text
**strings**. The quality contract lists "Character knowledge consistency", "Causal
preconditions", and "Canon and timeline consistency" as *hard* constraints — checks that
must be done in code, not by an LLM. Free-text strings cannot be checked deterministically:
there is no reliable way for code to decide from `"mara finally understood the signal"`
whether character `char-mara` now knows fact `fact-signal-cut`.

## 2. Exact evidence
- `schemas/state-delta.schema.json` (pre-change): `"knowledge_changes": {"type": "array", "items": {"type": "string"}}`.
- `scripts/compile_scene_context.py` performed no state reconstruction; nothing prevented
  future-knowledge leakage.
- `scripts/promote_candidate.py` never folded a delta into canon.
- The design brief's own example (`docs/original-design-brief.md`, §"Canon should be
  event-sourced") uses **structured** knowledge changes (`{character, learned, confidence,
  source}`); the repo had simplified that into unusable strings.

## 3. Root-layer diagnosis
Computational-operations layer (typed intermediate representation). The defect is that the
IR was too lossy to support the verification layer above it.

## 4. Minimal proposed change
Give the state delta typed, id-referencing records:
- `facts_added: [{id: fact-*, text}]`, `facts_removed: [fact-*]`
- `knowledge_changes: [{character: char-*, fact: fact-*}]`
- `relationship_changes: [{pair: [char-*, char-*], state, note?}]`
- `promises_opened: [{id: promise-*, text, owed_by?}]`, `promises_closed: [promise-*]`
- optional `time` (story-time reached after the scene) for chronology.

Top-level field names are unchanged; only item types are tightened. Parallel seed ledgers
(`canon/facts.jsonl`, `knowledge-state.jsonl`, `relationship-state.jsonl`, `promises.jsonl`,
`timeline.jsonl`) hold the story's initial condition in the same shapes.

## 5. New regression case
`tests/test_state.py` — a fixture project whose reconstructed state before a scene must (a)
contain only facts/knowledge established by earlier scenes and (b) **never** contain a fact a
later scene introduces (no future-knowledge leak). `tests/test_hard_audit.py` — a scene that
requires knowledge no earlier scene granted must fail the knowledge-cutoff check.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `reconstruct_state_before` did not exist; leakage was structurally possible.
- After: reconstruction is deterministic and the no-leak invariant is asserted by tests.

## 7. Known trade-offs
- Authoring a delta is now more verbose and must use stable ids.
- Id ordering (`chNN-scNN`) is treated as fabula order for v1; non-linear timelines must
  encode explicit `time` in deltas (chronology audit consumes it). Documented as a known limit.
- `character.json.knowledge` remains human-facing prose; machine seed knowledge lives in
  `knowledge-state.jsonl`. The two are not auto-reconciled yet.

## 8. Human approval status
Authorized as part of the user-requested roadmap implementation (the roadmap explicitly
called out event-sourcing and hard audits as unbuilt). Flagged here for review; revert path
is git history of `schemas/state-delta.schema.json` plus removal of `src/fiction_compiler/state.py`.
