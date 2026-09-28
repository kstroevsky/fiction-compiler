# ADR 0027 — Search over versioned scene plans before prose

## Context

The 2026-09-28 review §6.1 found that the repository could generate multiple prose candidates but
stored only one scene spec. `candidate_strategies` allowed informal variation, yet there was no
versioned artifact proving that consequential scene alternatives had been explored before expensive
prose realization. The audit proposed three or four plans varying tactic, turn, cost and reader
disclosure, followed by hard feasibility and plan-aware intentionality review.

This is a search protocol, not a validated quality metric. The audit's equal-cost comparison between
plan search and prose search has not been run, so the compiler must not encode a deterministic
"best plan" score.

## Decision

Scene-plan search is now a first-class, optional workflow:

- `scene-plan.schema.json` defines short alternatives bound to the exact scene-spec hash. Each plan
  states tactic, turn, cost, what the reader learns, required events/knowledge, forbidden moves, and
  explicit easy-solution analyses.
- `record_scene_plan` writes immutable plan candidates under
  `scenes/<scene>/plans/candidates/`. Reusing an id with different bytes is refused.
- `scene_plan_search` hard-audits plan freshness, knowledge availability, event references and typed
  event preconditions. Its divergence floor requires 3–4 hard-feasible plans, at least three distinct
  joint signatures, and variation across tactic, turn, cost and reader disclosure. It diagnoses search
  collapse; it never ranks the alternatives.
- `plan_review_packet` supplies one exact plan plus leak-free state/context and explicit feasibility,
  intentionality and "why don't they just…?" questions. It contains no candidate prose and does not
  ask for prefix-reader cognition. `record_plan_review` binds the resulting judgment to the exact plan
  hash. Every declared easy-solution check must be assessed; a `pass` cannot carry a material/fatal
  finding or an unsupported/uncertain easy-solution assessment.
- `select_scene_plans` records an explicit choice of one or two plans, who chose them, why, the exact
  plan hashes and the current batch fingerprint. Selection is permitted only after every hard-feasible
  plan has current plan-aware review evidence and every chosen plan has a current passing review.
- `compile_context` includes only a current selected plan set. If the scene spec changes, old plans,
  reviews and selections become visibly stale and are omitted from drafting context rather than
  silently reused.

Workspace validation checks all stored plan/review/selection schemas and semantically rejects stale or
invalid selection artifacts. The `generate-scene-plans` skill defines the creative workflow; the
`draft-scene` skill consumes reviewed selections when they exist while preserving legacy scenes with
no plan-search artifacts.

## Verification

Tests cover a valid three-plan batch, relabeled/collapsed search, an unresolved required event,
plan-review packet boundaries, mandatory easy-solution review, review-gated selection, hash-bound
selection flowing into compiled drafting context, and stale spec/review/selection invalidation.

## Consequences

The repository can now preserve evidence that a scene was searched structurally before prose, and can
prevent stale or unreviewed plans from becoming drafting instructions. The hard layer still proves
only modeled feasibility. Intentionality remains reviewer judgment, and reader response remains a
prose-level empirical question.

The central empirical claim remains open: this implementation does **not** establish that plan-level
search produces better fiction per unit cost than spending the same budget on more prose realizations.
That requires the audit's blind equal-cost reader-preference experiment.
