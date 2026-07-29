# Revision as Craft (the story's own improvement loop)

**Concept:** revision-as-craft · **Layer:** craft
**Used by:** `src/fiction_compiler/revision.py`, `triple-audit` skill, `promote-candidate` skill

## Definition
Writing is rewriting. The craft tradition is unanimous that the first rendering is raw material,
and the work happens in disciplined revision — Horace's *limae labor*, "the labor of the file."
But undirected revision drifts: it polishes sentences over broken scenes, or sands away the very
strangeness that made a draft alive. Disciplined revision is a **PDCA loop on the manuscript
itself**, distinct from improving the *framework*:

```
PLAN   name the target defect and the lowest layer that owns it
DO     produce a revision that changes THAT layer (not just the prose)
CHECK  re-run the audits; did the target clear WITHOUT a material regression elsewhere?
ACT    accept, or route the defect lower, or stop
```

## Use when
After any critique, before promotion, and whenever a candidate is "almost there."

## Stop conditions (so the loop converges, not drifts)
- all *fatal/hard* failures resolved, **and**
- the *target* dimension improved **without** a material regression elsewhere → accept;
- two repair attempts at a layer fail → escalate to the layer below;
- N iterations produce no improvement, or the budget is spent → stop and escalate to a human;
- judges remain materially divided → stop and escalate (do not average the disagreement away).

Infinite self-revision is not improvement — it converges on the evaluator's preferred blandness.
Route defects *downward* ([[defaultness]] ladder), never bury them under nicer sentences.

## Failure modes
- Line-editing a scene whose *structure* is the defect (wrong layer).
- "Revising" by synonym-swapping (motion without state-change — low [[eventfulness]]).
- Revising past the point of improvement until the text goes safe and generic.

## Related
[[defaultness]] · [[scene-dramaturgy]] · [[unity-of-effect]]
> Distinct from the FRAMEWORK improvement loop (`retrospective` skill + `constitution/change-policy.md`),
> which improves prompts/rubrics/schemas — not the story. See `docs/self-improvement-loops.md`.

## Sources
- `horace-ars-poetica` — the labor of the file; revise, revise (PD).
- `swain-techniques` — repair at the responsible structural unit (abstract).
