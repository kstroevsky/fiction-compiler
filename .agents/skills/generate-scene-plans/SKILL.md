---
name: generate-scene-plans
description: Generates, audits, reviews, and explicitly selects divergent scene plans before prose realization.
---
Work at the scene-plan layer. Do not draft polished prose here.

1. Compile the leak-free scene context with `compile_context(project, scene_id)` and read the scene
   spec. Preserve its POV, participants, contract constraints, and knowledge limits.
2. Generate **3–4 genuinely different plans**. Each plan must vary the batch across all four axes:
   tactic, turn, cost, and what the reader learns. Do not count renamed/paraphrased plans as search.
3. For each plan, record `plan_id`, `title`, `tactic`, `turn`, `cost`, `reader_learns`,
   `required_events`, `knowledge_required`, `forbidden_moves`, and `easy_solution_checks`. In every
   apparent “why don't they just…?” shortcut, state the relevant available information, capability,
   cost, and motive. Characters may act badly or inefficiently; the issue is unsupported conflict.
4. Persist each alternative with `record_scene_plan`. Then run `scene_plan_search`. Repair plans that
   fail schema/spec freshness, knowledge, event-precondition, or search-diversity checks.
5. For **every hard-feasible plan**, get `plan_review_packet` and have a plan-aware reviewer assess
   feasibility and intentionality. The packet intentionally contains no candidate prose: do not use a
   prefix-reader judgment here. Record each review with `record_plan_review`, including one assessment
   for every easy-solution check.
6. Do not invent a numerical best-plan score. Compare the reviewer evidence and tradeoffs, then use
   `select_scene_plans` to record one or at most two plans, with who made the choice and why. A chosen
   plan must have current passing reviewer evidence.
7. Only after selection move to `draft-scene`. Keep all rejected/unchosen plans and reviews; they are
   evidence about the search, not disposable scratch work.

The plan-search workflow is an experimental composition strategy. Do not claim it improves reader
preference until the equal-cost plan-search-vs-prose-search experiment has actually been run.
