# ADR 0017 — Premise-layer divergence + diagnostic probes (decentralized, no upstream dictator)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Recorded here because the change is framework-global.

## 1. Failure observed
Two worked examples built through the same pipeline diverged sharply in quality. "The Overnight"
(single transforming consciousness, oblique approach, internal conflict) read as clearly stronger
than "Slack Water" (a fixed competent-truth-teller POV, an off-camera arc belonging to the other
character, a conflict settled by proof, a clever "third-thing" resolution, and a two-hander that
spoke its theme). Yet "Slack Water" **passed every downstream audit** — hard, literary, and
defaultness — at every scene. The quality gap was set entirely at the **premise layer**, which the
pipeline had no check on. The audits enforce a floor (no cliché, no leak, no told emotion); they do
not detect the *absence* of the highest-value structural choices. The ceiling was fixed before the
first audit ran, by whichever premise the generator happened to produce first — i.e. quality was
accidental, not reproducible.

## 2. Exact evidence
- `projects/slack-water` promoted three scenes, all with clean hard/literary/defaultness critiques,
  and still under-performs `projects/the-overnight` on: POV-holder-is-the-transformer (false vs
  true), conflict-settled-by-proof (true vs false), obliqueness (direct vs oblique).
- No module, schema, or fixture referenced the premise layer. `grep` for premise-level structure
  (whose arc / conflict type / obliqueness) across `src/fiction_compiler/` returned nothing before
  this change.

## 3. Root-layer diagnosis
Premise/architecture layer. The generative genericity that hurt "Slack Water" originates above the
scene layer, where the pipeline had no divergence pressure and no diagnostic. Per the defaultness
repair ladder, polishing lower layers (which every audit did) cannot fix a default premise.

## 4. Minimal proposed change
Extend the pipeline's **existing** separation-of-powers to the premise layer **without** installing
a new gatekeeper (the explicit design constraint: keep creative influence decentralized; do not let
one LLM component become the determinative selector at the most consequential layer). Two parts, and
no more:
- `schemas/premise.schema.json` — a premise/architecture candidate with structural tags
  (`pov_character`, `transforming_character`, `conflict_type`, `obliqueness`, `resolution_type`,
  `why_not_default`). Tags are for the floor, not a quality score.
- `src/fiction_compiler/premise.py` `diversity_floor(candidates)` — a **deterministic** gate on the
  *batch*: refuse to proceed unless ≥3 candidates present ≥3 distinct architecture signatures
  `(pov==transformer, conflict_type, obliqueness)`, each schema-valid and each stating a
  `why_not_default`. It forces a wider search and rejects a collapsed batch. **It ranks nothing and
  selects nothing.**
- `premise-probes.json` — a fixed, versioned, human-editable rubric of structural questions
  (tested-need, proof-resolvable, obliqueness, resolution-humility, enacted-vs-spoken,
  premise-defaultness). The LLM *answers* these per candidate; it does not invent them or pick a
  winner. Power lives in the artifact.

Selection remains the human `premise` gate (already listed in both projects' `human_gates`), informed
by preserved disagreement — identical in shape to the downstream tournament, moved upstream. No LLM
component gains veto or selection power; the floor is code, the probes only diagnose.

## 5. New regression case
`regression/fixtures.json`: `premise_diversity` check with two fixtures — a batch collapsed to one
architecture (three interpersonal/direct/off-camera candidates) must fail; three distinct
architectures (internal/oblique, character-vs-nature/direct, interpersonal/oblique) must pass.
`src/fiction_compiler/regression.py` gains the `premise_diversity` whitelist entry.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: the premise layer had no check; a single default premise proceeded to generation unopposed.
- After: a premise stage that emits one shape (or fewer than three) is refused deterministically;
  the batch used for the next story is confirmed to span three distinct architectures before a scene
  is drafted, and the fixed probe rubric is presented to the human gate for the pick. Framework
  regression 14/14 → 16/16; unit suite unchanged and green; `validate_workspace` passes.

## 7. Known trade-offs
- The floor guarantees *divergence and structural validity*, not *quality*; it cannot make a premise
  good, only refuse a collapsed search. It raises the ceiling by widening the search, not by taste.
- The structural tags are coarse (three axes). A batch could satisfy the floor with three shallowly
  different shapes; the probes + human gate are the backstop against that.
- The probe rubric is applied by an LLM (fallibly) and by the human reader; this ADR builds only the
  deterministic floor + the versioned rubric artifact, not an automated probe scorer — deliberately,
  to keep selection decentralized.
- `premise-probes.json` is not yet folded into `framework_manifest`; the deterministic floor logic
  in `premise.py` is (via package-source hashing).

## 8. Human approval status
Authorized as a user-directed change: "slightly improve the pipeline" under the explicit constraint
that upstream influence stay decentralized — "avoid too influential single LLM parts." The
constitution (`AGENTS.md`) is unchanged. Revert path: git history of `premise.py`,
`schemas/premise.schema.json`, `premise-probes.json`, `regression.py`, and `regression/fixtures.json`.
