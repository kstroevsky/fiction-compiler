---
name: draft-scene
description: Drafts multiple strategically distinct prose candidates from an accepted scene specification and compiled context.
---
You are the author. The tools below are your reference and guardrails — they do not write for you.
Goal: 2–4 strategically distinct candidates the audits can compare.

1. **Ground the scene.** Get the leak-free bundle: MCP `compile_context(project, scene_id)` or
   `python3 scripts/compile_scene_context.py <project> <scene>`. Confirm the spec is accepted and
   schema-valid.
2. **Load craft.** `kb_search` the concepts this scene leans on (scene-dramaturgy, dialogue-subtext,
   narrative-distance, showing-and-telling, eventfulness); `kb_get` the ones you'll actually use.
   Honor `planning/style-profile.json`.
3. **Respect knowledge limits.** Nothing in a candidate may exceed `state_before.participant_knowledge`
   — the focalizer cannot know what they haven't learned. Check with the `state_before` tool.
4. **Diverge on strategy, not wording.** First run the `avoid-defaults` procedure: name the most
   predictable versions of this scene and make your candidates *not* those, while staying caused by
   character + world. Declare each candidate's distinct dramatic tactic / focal distance / information
   pattern before writing.
5. **Draft each candidate separately** under `scenes/<id>/candidates/`.
6. **Self-check the prose.** `defaultness_lint` each candidate. Treat hits as evidence, not verdicts —
   repair at the lowest responsible layer (see `kb/style/defaultness.md`), never by synonym-swapping.
7. **Touch nothing canonical.** Do not update canon or manuscript. Record any structural problem you
   discover instead of improvising around it (route it to the narrative architect).
