# ADR 0007 — Deterministic tournament / selection engine (P2)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. First slice of Priority 2 (the missing "search / selection system").
Recorded here because the change is framework-global.

## 1. Failure observed
The operating contract requires blind A/B comparison, reversed order, multidimensional scoring, a
preserved Pareto view, and recorded judge disagreement. None of this existed as code — it lived only
as instructions in skills and agent prompts, so isolation and fairness were *requested*, not
guaranteed. No code anonymized candidates, reversed order, computed a non-dominated set, or detected
disagreement, and there was no way to turn a scene's critiques into a selection decision.

## 2. Exact evidence
- `.claude/skills/triple-audit/SKILL.md` step 5: "Anonymize candidates and reverse order …" — an
  instruction to the agent, with no enforcing code.
- The repository had no module computing dominance, a Pareto front, or disagreement; `revision.py`
  compares one before/after pair, not a field of candidates.
- The review: "Build a tournament orchestrator before adding more critic personas … the code — not
  the agent prompt — must own anonymization, ordering, candidate identity, tournament recording, and
  disagreement detection."

## 3. Root-layer diagnosis
Selection/evaluation layer. The judging is legitimately an LLM task, but the *fairness machinery*
around it (blinding, ordering, multidimensional selection, disagreement) is deterministic and must be
owned by code so it cannot be skipped or gamed by a prompt.

## 4. Minimal proposed change
New `src/fiction_compiler/tournament.py`:
- `anonymize(ids, seed)` → seeded, reproducible id↔blinded-label maps (judges never see the id or
  strategy); `presentation_orders(labels)` → a forward **and** a reversed order (position bias),
  plus a shuffled order when >2.
- `dominates` / `pareto_front` → multidimensional selection with "higher = better"; a dimension
  absent from a vector counts as 0 (clean). `dimension_winners` and `has_disagreement` surface the
  tradeoffs rather than averaging them.
- `scores_from_critiques` → per-candidate, per-dimension penalty scores from critique findings
  (minor 1 / material 4 / fatal 16).
- `run_tournament(critiques, seed)` → blinded labels + reveal map, presentation orders, scores, the
  Pareto front, per-dimension winners, a disagreement flag, and a recommendation: **select** only
  when one candidate dominates all others, otherwise **human_decision_required** over the
  non-dominated set (never a collapsed single number).

Exposed as the MCP `tournament(project, scene_id, seed)` tool, which reads the scene's committed
critiques. The tool returns the reveal map for the *orchestrator*; judge agents must not be shown it.

## 5. New regression case
`tests/test_tournament.py`: anonymization is deterministic per seed and reversible; presentation
orders include a reversed order; `dominates`/`pareto_front` select a single dominator and keep a
genuine tradeoff (both candidates on the front, `disagreement` True); `scores_from_critiques`
accumulates penalties; `run_tournament` recommends `select` for a dominator and
`human_decision_required` for a tradeoff; the tool reads a scene's critiques end-to-end.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: "blind, reversed, multidimensional, preserve disagreement" was prose an agent was trusted
  to honour; there was no selection artifact.
- After: `run_tournament` returns a structured record whose blinding/order/Pareto/disagreement are
  computed deterministically; a clean candidate vs one with a material finding yields
  `{"decision": "select", …}`, while a style-vs-cliché tradeoff yields `{"decision":
  "human_decision_required", "pareto_front": [a, b]}` with `disagreement: true`. Suite 90 → 99;
  `validate_workspace` passes.

## 7. Known trade-offs
- Scores are derived from deterministic critique findings (severity penalties). Richer LLM judge
  scores / pairwise rankings are not yet ingested — the engine is ready for them (it takes score
  vectors) but the wiring and a judge-isolation ledger are a later slice.
- Anonymization hides ids from a judge only if the caller actually withholds `reveal_map`; the engine
  guarantees the blinding *exists*, not that every caller respects it. Writing blinded candidate
  copies to `.runs/` and recording which judge saw which order is deferred.
- Severity weights (1/4/16) are a fixed heuristic, not a human-calibrated weighting; the Pareto view
  deliberately avoids committing to one, but `scores_from_critiques` still encodes that ranking.
- Disagreement is inferred from score-vector tradeoffs, not yet from independent judges ranking the
  same blinded pair.

## 8. Human approval status
Authorized as the "do both" step (finish P1 + start P2). The constitution (`AGENTS.md`) is unchanged.
Revert path: remove `src/fiction_compiler/tournament.py`, the `tournament` tool + import in
`tools.py`, and `tests/test_tournament.py`.
