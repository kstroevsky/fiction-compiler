# Scene Dramaturgy

**Concept:** scene-dramaturgy · **Layer:** craft
**Used by:** `schemas/scene.schema.json`, `draft-scene` skill

## Definition
A scene is a unit of change under pressure. Minimum viable structure: a focal character with a
*desire* active *now*, an *obstacle/conflict* resisting it, escalating *tactics*, a *turn*
where the situation shifts irreversibly, and an *exit state* different from the entry. If
nothing changes — in value, knowledge, status, or relationship — it is not a scene; it is an
errand. The scene schema encodes this: `desire`, `conflict`, `turn`, `exit_state` are required.

## Use when
Writing a scene spec and testing scene necessity. Necessity test: delete the scene — what
promise, causal link, or value-shift is lost? If nothing, cut or merge it.

## Diagnostic questions
- Whose scene is this, and what do they want in the next few minutes?
- What is in the way, and does the opposition push back with its own logic?
- What is the turn — the moment after which they cannot go back?
- What has changed by the exit (emotion / knowledge / status / relationship)?

## Failure modes
- Pleasant conversation to word-count; no turn.
- "Errand" scenes that convey info but change no value.
- The obstacle folds too easily (tension resolved the moment it gets uncomfortable).
- Turn announced ("she realized everything was different") instead of enacted.

## Conflicts with
Sequel/reflection beats — not every unit is high-conflict; some are reaction/decision. Keep
those short and let them *decide*, not merely muse.

## Related
[[character-intentionality]] · [[dialogue-subtext]] · [[promise-and-payoff]]

## Sources
- `swain-techniques` — scene (goal/conflict/disaster) and sequel (abstract).
- `mckee-dialogue` — the turn as the unit of change (abstract).
