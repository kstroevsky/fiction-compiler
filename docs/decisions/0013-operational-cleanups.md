# ADR 0013 — Operational cleanups from the review

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Batches four small, deterministic items the review's "operational
and security" / "schema" / "§6" sections listed. Recorded here because the changes are framework-global.

## 1. Failure observed
Four independent papercuts the review named, none large, all real:
1. **Assembly hid corruption.** `assemble()` silently skipped an accepted scene whose manuscript was
   missing, so canon could claim a scene was promoted while the assembled story quietly dropped it.
2. **Schema validator too weak.** It lacked `minItems`/`maxItems`/`uniqueItems`/`additionalProperties`,
   so a state-delta relationship `pair` could be length 1, length 3, or a self-pair `[a, a]`.
3. **Context compiler was a blind dump.** `compile_context` injected all facts / world rules with no
   per-item inclusion reason or priority, so context packing could not be tested or budgeted.
4. **Permissions lagged the tooling.** `.claude/settings.json` allowed the older commands but not
   `hard_audit` / `defaultness_lint` / `revise_scene` / `assemble` / `run_regression` / the MCP server.

## 2. Exact evidence
- `src/fiction_compiler/assemble.py`: `if not md.exists(): continue`, and `test_assemble.py`
  asserted the skip as correct.
- `src/fiction_compiler/schema.py` docstring enumerated only type/required/properties/items/enum/
  pattern/minLength/minimum/maximum.
- `src/fiction_compiler/context.py`: `state_before.facts` = the full dict; `world_rules` = all of them;
  no manifest.
- `.claude/settings.json` `permissions.allow` (pre-change) listed validate/tests/new_project/
  compile_context/promote only.

## 3. Root-layer diagnosis
Operational / verification-plumbing layer. Each is a local correctness or ergonomics gap, not an
architectural one.

## 4. Minimal proposed change
1. `assemble()` collects accepted scenes with no manuscript and **raises** a fatal integrity error
   before writing, naming the missing scenes.
2. `schema.py` gains `minItems`, `maxItems`, `uniqueItems` (tolerant of unhashable members), and
   `additionalProperties:false`. Applied in `state-delta.schema`: the relationship `pair` is now
   `minItems:2, maxItems:2, uniqueItems:true`, and the typed `predicate_changes` / `relationship_edges`
   / `relationship_changes` items are `additionalProperties:false`.
3. `compile_bundle()` adds a `context_manifest`: one `{kind, ref, reason, priority, source}` row per
   included item — facts named in the scene's `knowledge_required` are `required`, the rest
   `background`; world rules `reference`. First step toward relevance pruning + token budgets.
4. `.claude/settings.json` allows the newer scripts + the MCP server.

## 5. New regression case
`tests/test_assemble.py`: a manuscript missing for an accepted scene is now a fatal error naming it.
`tests/test_schema.py` (`ValidatorKeywordTests`): min/max items, uniqueItems over dicts,
additionalProperties, and the concrete relationship-pair constraints. `tests/test_context.py`: the
manifest marks required vs background facts and carries a reason + source on every entry.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `assemble` on a project with an accepted-but-missing scene returned a short manuscript
  silently; a `pair: ["char-a"]` validated; the context bundle had no provenance.
- After: `assemble` raises `accepted scene(s) missing a manuscript file: ['ch01-sc09'] …`; the bad
  pair fails validation with `minItems`/`unique`; the bundle carries a `context_manifest`. Suite 120
  → 125; regression 10/10; `validate_workspace` still passes (the tightened schema keywords only
  constrain shapes the committed projects already satisfy).

## 7. Known trade-offs
- `additionalProperties:false` is applied only to the tightly-defined newer items, not broadly, to
  avoid rejecting older artifacts with incidental extra keys; the validator supports it everywhere now.
- The `context_manifest` explains inclusion and priority but does **not** yet prune or enforce a token
  budget — the full §6 relevance-sensitive compiler remains open.
- The custom validator still omits `oneOf`/`anyOf`/`$ref`/conditionals; adopting `jsonschema` is a
  separate, larger decision left open.

## 8. Human approval status
Authorized as the user-directed "do A" cleanup step. The constitution (`AGENTS.md`) is unchanged.
Revert path: git history of `assemble.py`, `schema.py`, `context.py`, `schemas/state-delta.schema.json`,
`.claude/settings.json`, and the touched tests.
