---
name: draft-scene
description: Drafts multiple strategically distinct prose candidates from an accepted scene specification and compiled context.
---
You are the author. The tools below are your reference and guardrails — they do not write for you.
Goal: 2–4 strategically distinct candidates the audits can compare.

1. **Ground the scene.** Get the leak-free bundle: MCP `compile_context(project, scene_id)` or
   `python3 scripts/compile_scene_context.py <project> <scene>`. Confirm the spec is accepted and
   schema-valid. If the bundle contains `selected_scene_plans`, use those reviewed plans as the
   realization targets. If plan candidates exist but no current plan selection exists, return to the
   `generate-scene-plans` workflow before drafting. Legacy scenes with no plan artifacts may still
   draft directly from their spec.
2. **Load craft.** `kb_search` the concepts this scene leans on (scene-dramaturgy, dialogue-subtext,
   narrative-distance, showing-and-telling, eventfulness); `kb_get` the ones you'll actually use.
   Honor `planning/style-profile.json`.
3. **Respect knowledge limits.** Nothing in a candidate may exceed `state_before.participant_knowledge`
   — the focalizer cannot know what they haven't learned. Check with the `state_before` tool.
4. **Diverge at the correct layer.** First run the `avoid-defaults` procedure: name the most
   predictable realization of the selected plan and make candidates *not* that, while staying caused
   by character + world. When two scene plans were explicitly selected, prose candidates may realize
   either plan; when one plan was selected, vary prose realization rather than silently substituting a
   new structural plan. Declare each candidate's focal distance / information texture before writing.
5. **Draft each candidate separately** under `scenes/<id>/candidates/`.
6. **Self-check the prose.** `defaultness_lint` each candidate. Treat hits as evidence, not verdicts —
   repair at the lowest responsible layer (see `kb/style/defaultness.md`), never by synonym-swapping.
7. **Touch nothing canonical.** Do not update canon or manuscript. Record any structural problem you
   discover instead of improvising around it (route it to the narrative architect).
