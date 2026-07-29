# ADR 0005 — Predicate ontology for the executable story IR

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Second slice of Priority 1, hardening ADR 0004. Recorded here
because the change is framework-global.

## 1. Failure observed
ADR 0004 made event preconditions/effects checkable but left the predicate **vocabulary open**: any
string was a legal predicate. A typo (`located_att` for `located_at`) was silently a *different*
predicate — `holds()` returned False, so a precondition became permanently unsatisfiable and an
effect recorded under the typo never matched the event's declared effect. The executable checks could
be quietly defeated by a spelling mistake, and nothing constrained arity (`offline` used with an
object) or entity types (`located_at(char, char)`).

## 2. Exact evidence
- `src/fiction_compiler/state.py` `holds()` and `_apply_predicate_record`: key on the raw
  `predicate` string with no validation.
- `schemas/state-delta.schema.json` `predicate_changes` / `relationship_edges`, and
  `schemas/event.schema.json` typed atoms: `predicate` is `{"type": "string"}` with no enumeration.
- `src/fiction_compiler/hard_audit.py` (post-ADR-0004): evaluated `before.holds(predicate, …)` but
  never checked that `predicate` was a real predicate.

## 3. Root-layer diagnosis
Typed-IR / world-rules layer. The IR had predicate *atoms* but no *schema for predicates* — no
declaration of which predicates exist, their arity, or their argument types.

## 4. Minimal proposed change (additive; opt-in per project)
- `schemas/ontology.schema.json` + optional `projects/<slug>/canon/ontology.json`: a list of
  `{name, arity: unary|binary, subject_types?, object_types?, relationship?, description?}`.
- `src/fiction_compiler/ontology.py`: `load_ontology(project)` and `check_atom(ontology, predicate,
  subject, object)` returning violation strings (undeclared name, arity mismatch, subject/object
  entity-type mismatch by id prefix).
- `hard_audit.audit_scene`: when an ontology is present, every typed atom the scene touches — each
  required event's typed preconditions/effects, and the scene's own `predicate_changes` /
  `relationship_edges` — is checked; a violation is a **material** `"ontology"` finding. When no
  ontology file exists, the check is skipped (back-compat).
- `validate_workspace`: schema-validates `canon/ontology.json` when present. `_template` ships a
  starter ontology (knows, located_at, has_object, available, trusts, owes, injured).

## 5. New regression case
`tests/test_ontology.py`: `check_atom` flags an undeclared/typo predicate, a binary used without an
object, a unary used with one, and subject/object type mismatches; a valid atom yields no errors.
`tests/test_hard_audit.py` (`HardAuditOntologyTests`): with an ontology, a typo predicate is a
material `"ontology"` finding (`revise`) even when world-state would satisfy the intended predicate;
a declared predicate passes; **without** an ontology the same custom predicate is tolerated (`pass`).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: an event precondition `located_att(char-jonas, loc-station)` produced only a confusing
  "precondition does not hold" (or silently mismatched an effect) — the typo itself was invisible.
- After (ontology present): it yields `evt-relay-cut precondition: predicate 'located_att' is not
  declared in the ontology`. Suite 79 → 88; `validate_workspace` passes (committed examples declare
  no ontology, so enforcement is skipped for them).

## 7. Known trade-offs
- Enforcement is opt-in: a project without `canon/ontology.json` keeps the open vocabulary. The
  guarantee only covers projects that declare one.
- Entity typing is by id **prefix** (`char-`, `loc-`, …), not a real type system; it will not catch
  a well-formed id that names the wrong entity.
- The ontology is a flat list — no inheritance, no predicate composition, no cardinality beyond
  unary/binary, and no cross-predicate constraints (e.g. an entity being in two locations at once).

## 8. Human approval status
Authorized as the "continue" step after ADR 0004, per the recommended next slice (a predicate
ontology to harden the executable checks). The constitution (`AGENTS.md`) is unchanged. Revert path:
remove `src/fiction_compiler/ontology.py`, `schemas/ontology.schema.json`, the `_template` ontology,
and the ontology block/import in `hard_audit.py` and `validate_workspace.py`, plus the added tests.
