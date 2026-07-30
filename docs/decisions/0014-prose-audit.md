# ADR 0014 — Prose audit: the hard audit reads the prose (review §4)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Addresses the review's §4 — the largest remaining verification gap.
Recorded here because the change is framework-global.

## 1. Failure observed
The hard audit (`hard_audit.py`) proves the scene *spec*, state delta, and event graph, but it never
reads the candidate **prose**. So it cannot catch the prose revealing something the focalizer does
not know, introducing an unplanned character, head-hopping into another mind, breaking the requested
tense, contradicting an object's location, or resolving a promise the state delta never records.
Those are all facts about the text, invisible to a spec-only audit. The "POV audit" only checked that
`spec.json` named a defined character.

## 2. Exact evidence
- `src/fiction_compiler/hard_audit.py` reads `spec.json`, `state-delta.json`, and
  `planning/event-graph.json`; it never opens `candidates/*.md` or `manuscript/chapters/*.md`.
- The review §4 enumerates the prose-level defects a spec audit misses and prescribes a two-stage
  process: "an extraction agent derives factual and epistemic claims from the prose; deterministic
  code compares those structured claims against state and scene constraints."

## 3. Root-layer diagnosis
Hard-verification layer, prose half. Reading prose reliably needs an LLM (extraction), but *judging*
the extracted claims against state is deterministic and belongs in code — the same split as the
tournament (code owns the fairness math; the LLM judges).

## 4. Minimal proposed change
- `schemas/prose-claims.schema.json`: the artifact an extraction agent derives from ONE candidate's
  prose — `pov`, `tense`, `word_count`, and typed `claims` (`character_present`, `focalizer_knows`,
  `interiority_of`, `located_at`, `closes_promise`, `states_fact`) each with `evidence`.
- `src/fiction_compiler/prose_audit.py` `audit_prose(project, scene_id, claims)`: reconstructs
  state-before + reads the spec/discourse plan and **proves** the claims — a focalizer knowing an
  ungranted fact (leak), an unplanned character, head-hopping, a tense break, a spatial contradiction,
  a promise closed in prose but not in the delta, or a stated fact not in canon are material findings;
  a canon character who acts but isn't a declared participant is a minor. Output is a `critique.schema`
  critique (critic `prose-audit`, `audit_class: hard`) so it flows through the same gate/tournament.
  The epistemic rule is factored into a pure `is_knowledge_leak(pov_knows_before, granted_this_scene)`.
- `scripts/prose_audit.py` CLI (`--write`) + MCP `prose_audit` tool.

## 5. New regression case
`tests/test_prose_audit.py`: consistent claims pass; a knowledge leak, unplanned character,
head-hopping, tense break, spatial contradiction, and an unrecorded promise closure are each material;
a canon character who is not a declared participant is a minor. `regression/fixtures.json` pins the
leak rule (leak when neither known-before nor granted-this-scene; not a leak when the scene grants it).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: the hard audit passed prose that had the focalizer narrate a fact from a future scene.
- After, on the committed `the-overnight/ch01-sc01`: the honest extracted claims audit **pass** (0
  findings); injecting `focalizer_knows(char-nadia, fact-loaves-delivered)` — a fact scene three
  introduces — yields `revise` with `knowledge: the focalizer knows/reveals 'fact-loaves-delivered',
  which they have not learned by this scene`. Suite 125 → 133; regression 10/10 → 12/12;
  `validate_workspace` passes.

## 7. Known trade-offs
- Correctness depends on honest extraction: a claim the agent omits is a defect the audit cannot see.
  The audit proves the claims it is *given*; it does not guarantee the claim set is complete. Pairing
  it with the deterministic `defaultness_lint` (which reads raw text) and requiring evidence spans
  mitigates but does not eliminate this.
- `prose_audit` is not yet a **required** promotion-gate class; making it required would force every
  promotion to carry a prose-claims artifact (a workflow change). It is available and produces a
  hard-class critique that the gate credits when present.
- Checks are conservative (they fire only on a positive claim that conflicts with state); subtler
  focalization drift without an explicit `interiority_of` claim is not caught.

## 8. Human approval status
Authorized as the user-directed "do B" step — the review's §4. The constitution (`AGENTS.md`) is
unchanged. Revert path: remove `prose_audit.py`, `schemas/prose-claims.schema.json`,
`scripts/prose_audit.py`, the `prose_audit` tool + import in `tools.py`, the regression check/fixtures,
and `tests/test_prose_audit.py`.
