# ADR 0012 — Human gate and rubric in the acceptance manifest

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Completes Priority 0 (trustworthy promotion). Recorded here because
the change is framework-global.

## 1. Failure observed
ADR 0002/0003 made promotion enforce the triple audit, bind critiques to the candidate bytes, hash
the canon chain, write atomically, and confine paths. But the reviewer's headline invariant has one
more clause — canon may advance only when the exact candidate passed the required audits **"under a
recorded rubric and human gate."** The acceptance manifest recorded no approver identity and no
rubric version, so the human decision the operating contract requires left no trace and could not be
required.

## 2. Exact evidence
- `src/fiction_compiler/promote.py` decision dict (pre-change): `candidate_sha256`,
  `state_delta_sha256`, `parent_canon_hash`, `resulting_canon_hash`, `binding_critiques` — but no
  `approved_by`/`human_gate`/`rubric_version`.
- `brief/project.json` `human_gates` (e.g. `["premise","voice-profile","ending","final"]`) was
  declarative only; nothing consumed it at promotion.
- The reviewer's "next milestone": *"A candidate cannot become canon unless the code proves that the
  exact candidate passed the exact required audits under a recorded rubric and human gate."*

## 3. Root-layer diagnosis
Verification / governance layer. The audits and hashes were enforced; the human approval that the
contract puts above them was neither required nor recorded.

## 4. Minimal proposed change (additive; opt-in per project)
- `promote_candidate(..., approved_by=None, rubric_version=None)`: if the project's `brief/project.json`
  lists `"promotion"` in `human_gates`, `approved_by` is **required** — promotion refuses (before any
  write) without it. The acceptance manifest always records
  `human_gate: {required, approved, approver}` and `rubric_version`.
- The `promote` MCP tool gains `approved_by` / `rubric_version` and passes them through.
- Opt-in: a project that does not list `"promotion"` promotes exactly as before (backward-compatible;
  the committed examples and all prior tests are unaffected).

## 5. New regression case
`tests/test_promote.py` (`HumanGateTests`): a project that lists `"promotion"` in `human_gates`
refuses promotion without an approver (and writes nothing); with `approved_by`/`rubric_version` it
promotes and the manifest records `human_gate.approved=true`, the approver, and the rubric version; an
ungated project still promotes without an approver and records `human_gate.required=false`.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: a gated project could be promoted with no human approval and no record of who approved or
  under which rubric.
- After: `promote_candidate(gated_project, …)` raises `human gate required: this project lists
  'promotion' in human_gates; promote with approved_by=<approver> …`; with the approver, the manifest
  carries `{"human_gate": {"required": true, "approved": true, "approver": "…"}, "rubric_version": "…"}`.
  Suite 117 → 120; regression 10/10; `validate_workspace` passes.

## 7. Known trade-offs
- Enforcement is opt-in via the `"promotion"` gate token; a project that never adds it is never gated
  (chosen to avoid breaking existing projects). Making it default-on is a policy decision for later.
- `approved_by` and `rubric_version` are trusted strings; the engine records them but does not
  authenticate the approver or verify a rubric artifact exists (no signature, no rubric registry yet).
- The gate fires at scene promotion; a separate manuscript-level "final" human gate is still just a
  declared token, not enforced.

## 8. Human approval status
Authorized as the user-directed "continue finishing the initial plan" step — the closing clause of
Priority 0. The constitution (`AGENTS.md`) is unchanged. Revert path: git history of `promote.py`,
`tools.py`, and `tests/test_promote.py`.
