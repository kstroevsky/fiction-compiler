# ADR 0016 — Critic-driven selection (utilizing the generator–discriminator gap)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Recorded here because the change is framework-global.

## 1. Failure observed
The project's premise is that an LLM is a far stronger **critic** of fiction than **generator** of it
(the generator–discriminator gap). The right architecture is therefore search under a strong
discriminator: generate wide/cheap, then let the critic *select* and specify narrow repairs. But the
tournament's actual selection was driven by `scores_from_critiques` — deterministic finding-*counts*.
The strong faculty (the LLM critic's comparative judgment) only flipped a `disagreement` flag via
`judge_rankings`; **it never drove the pick.** The one strength worth exploiting was scaffolded but
unwired.

## 2. Exact evidence
- `src/fiction_compiler/tournament.py` `run_tournament`: `scores = scores_from_critiques(critiques)`
  → `pareto_front(scores)` → recommendation. `judge_rankings` only fed `disagreement_from_rankings`.
- No schema existed for an LLM critic's comparative judgment, and nothing converted judge input into
  the Pareto score vectors that decide the winner.

## 3. Root-layer diagnosis
Selection/evaluation layer. The deterministic scaffolding (anonymization, order reversal, Pareto,
disagreement) was correct; it simply wasn't being fed by the strong discriminator.

## 4. Minimal proposed change
- `schemas/judgment.schema.json`: a **blind** judgment an LLM critic produces over anonymized
  candidates — `scores` keyed by blind label → per-dimension number (higher = better), plus judge id,
  presentation order, confidence, rationale. The judge sees labels only; the tournament owns the
  reveal map.
- `tournament.py`: `scores_from_judgments(judgments, reveal_map)` (mean per candidate/dimension, with
  disagreement preserved separately), `rankings_from_judgments`, and a **deterministic floor** —
  `floor_eligible(critiques)` excludes any candidate with a material/fatal finding from a code audit
  (`hard-audit`/`defaultness-lint`/`prose-audit`). `run_tournament(..., judgments=…)` selects with the
  **critic's** scores among floor-eligible candidates (`selection_basis: "critic-judgments"`);
  without judgments it falls back to deterministic penalties. A candidate that fails the floor is
  never selected, however much a critic prefers it; if none clear the floor the decision is
  `no_eligible_candidates`. The `tournament` MCP tool gains `judgments`.

The floor is the essential guard on the asymmetry: an LLM critic asked "which is better?" drifts
toward fluent, on-distribution prose — the very defaultness the project fights — so the code audits
it cannot override are what make it safe to let the critic choose.

## 5. New regression case
`tests/test_tournament.py`: judge scores drive the pick; a candidate the critic prefers is still
excluded when it fails the floor; all-fail → `no_eligible_candidates`; split judges force a human
decision; `scores_from_judgments` means across judges. `regression/fixtures.json` pins the floor
(a material code-audit finding excludes a candidate; all-fail yields `no_eligible_candidates`).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: selection was a function of finding-counts; the LLM critic's comparative verdict changed
  nothing but a flag.
- After (demo, `the-overnight/ch01-sc01`): the tournament anonymizes to A/B/C, the critic scores the
  blind candidates per dimension, and `selection_basis: "critic-judgments"` drives the Pareto pick
  (de-anonymized to `candidate-a-r1`). A blind judge that scores a floor-failed candidate highest
  cannot select it. Suite 135 → 140; regression 12/12 → 14/14; `validate_workspace` passes.

## 7. Known trade-offs
- The judging itself is an LLM call (agent-side); this ADR builds only the deterministic plumbing that
  makes the judgment *authoritative for selection*. Judge honesty/quality is not verified here.
- Judge scores are mean-aggregated for the Pareto vector; the mean is a point estimate and disagreement
  is preserved separately (and can force `human_decision_required`), so nothing is silently averaged —
  but a more faithful per-judge-Pareto is left for later.
- The floor uses a fixed set of deterministic critics; a new code audit must be added to it.
- This is the *selection* half of "critic drives, generator serves." The complements — a critic-first
  target spec (taste upstream) and wider/cheaper generation (best-of-N volume) — remain to build.

## 8. Human approval status
Authorized as the user-directed slice: "LLM is a great critic and a poor writer — utilize the
difference," choosing critic-driven selection first. The constitution (`AGENTS.md`) is unchanged.
Revert path: git history of `tournament.py`, `tools.py`, `regression.py`,
`schemas/judgment.schema.json`, `regression/fixtures.json`, and `tests/test_tournament.py`.
