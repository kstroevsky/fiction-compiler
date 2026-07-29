# ADR 0006 — Fabula time vs discourse order (flashbacks)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Third slice of Priority 1. Recorded here because the change is
framework-global.

## 1. Failure observed
The system conflated three identifiers the design review asked to separate: scene id, discourse
(reading) order, and fabula (event) time. `accepted_scene_ids` sorts by `chNN-scNN` (discourse
order) and the chronology audit compared each accepted scene's `time` against the previous one,
flagging **any** backward movement as a material "temporal" finding. A legitimate flashback — a scene
that appears later in discourse but is set earlier in fabula time — was therefore reported as a
timeline contradiction, so the system could not model analepsis, prolepsis, framed narratives, or
overlapping timelines at all.

## 2. Exact evidence
- `src/fiction_compiler/hard_audit.py` `audit_canon`: `comparison = _compare_time(prev_time,
  current_time); if comparison > 0: _finding("temporal", "material", … "Story time runs backward …")`
  — applied unconditionally to consecutive discourse-ordered scenes.
- `src/fiction_compiler/state.py` docstring: "v1 uses id order as fabula order."
- `schemas/scene.schema.json`: no field distinguishing a scene's discourse position from its fabula
  time or marking a deliberate non-linear scene.

## 3. Root-layer diagnosis
Discourse/structure layer. The IR had a fabula clock (`delta.time`) and a discourse identity
(`scene_id`) but no marker for when the two deliberately diverge, so the chronology check could not
tell an authored flashback from an accidental contradiction.

## 4. Minimal proposed change
- `schemas/scene.schema.json`: optional `narrative_mode ∈ {linear, analepsis, prolepsis}` (absent =
  linear), documented as the discourse/fabula relation.
- `hard_audit.audit_canon`: check chronology along the **linear thread only**. A `linear` scene still
  trips the backward-time rule and advances the linear clock; an `analepsis`/`prolepsis` scene is a
  deliberate divergence — it is exempt from the rule and does **not** advance the clock (so a
  flashback between two present scenes does not make the next present scene look backward).
- `state.py` docstring: state the three-identifier model explicitly (scene id = discourse, delta.time
  = fabula, narrative_mode = the marked divergence).

## 5. New regression case
`tests/test_hard_audit.py`: a scene with an earlier `time` marked `analepsis` produces **no**
temporal finding; the same backward `time` **without** a mode (i.e. linear) is still flagged
material.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: a flashback (`sc02` at time 1 after `sc01` at time 5) was a material "time runs backward"
  finding — the audit forbade non-linear storytelling.
- After: with `narrative_mode: analepsis` it passes; an unmarked backward jump is still caught. Suite
  88 → 90; `validate_workspace` passes (existing scenes omit `narrative_mode` → linear, unchanged).

## 7. Known trade-offs
- **Reconstruction is still discourse-ordered.** A flashback is not yet shown only what was true at
  its earlier fabula time — `reconstruct_state_before` still replays in scene-id order. Fabula-ordered
  reconstruction (so a flashback cannot "see" facts from its future-in-fabula) remains deferred.
- `narrative_mode` marks divergence but does not verify it (an `analepsis` whose time is *not* earlier
  than its neighbours is not flagged); nor are overlapping/simultaneous timelines modelled.
- Chronology is checked along a single linear thread; multiple concurrent linear threads (parallel POV
  timelines) are not distinguished.

## 8. Human approval status
Authorized as part of the user-directed "do both" step (finish P1 + start P2). The constitution
(`AGENTS.md`) is unchanged. Revert path: git history of `hard_audit.py`, `state.py`,
`schemas/scene.schema.json`, and the added tests.
