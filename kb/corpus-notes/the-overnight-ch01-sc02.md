# Annotated scene: "The Overnight," ch01-sc02 (the decision)

**Concept:** annotated-overnight-decision · **Layer:** corpus
**Used by:** `draft-scene` skill, `character-simulator` agent
**Evidence strength:** structural (analysis of an in-repo artifact; the prose can be re-read exactly at
`projects/the-overnight/manuscript/chapters/ch01-sc02.md`)
**Source:** `the-overnight-example` (generated in-repo; no external rights)

This is the first seeded corpus annotation. It extracts *abstract craft features* from a scene the
repository owns, so nothing here depends on copyrighted text. It is **one sample** — a model to study,
not a rule to induce (AGENTS.md forbids learning a style rule from a single success).

## What the scene is
Nadia, alone on the overnight shift, has found the wake-order dough ruined (sc01). This scene is the
decision: whether to wake her hospitalized grandmother for the recipe, or make her own bread. Nothing
external happens — one character, one room. Yet the scene **turns**, on a *status/agency* shift rather
than an event: she moves from deferring to Esther to trusting her own hands.

## How the turn is enacted (not stated)
The value shift is carried entirely by action and object, never by a named feeling:
- **The near-call → the phone set down.** Desire (rescue) meets the cost (admitting she cannot hold
  the shop). The turn is a single physical act: "She set the phone face down on the bench."
- **The watched second scald.** Competence claimed through correction of a past failure — she stands
  over the pan this time. Backstory arrives as *procedure*, not exposition.
- **The kneading rhythm.** "Push, fold, quarter turn" — the one deliberately repeated device; the
  arithmetic of the deadline "stops running" inside the bodily rhythm. Interiority rendered as labor.

## Craft features to extract (transferable)
- A scene can turn on **status/agency** with zero external event — the counter to a naive
  "something must happen" reading ([[static-scene]], [[scene-dramaturgy]]).
- **Enact the decision in the hands**: the strongest beat is an object moved (the phone), not a
  thought reported ([[showing-and-telling]], [[character-intentionality]]).
- **Backstory as procedure**: the spoiled-milk memory teaches competence without pausing the scene.
- The state delta records the abstract turn deterministically: `relationship_edges` moves
  `defers_to` from `total` → `loosening`, so the arc is machine-visible, not merely asserted.

## Caution
The scene works under *this* reader contract (quiet realism, feeling via the hands). The same
techniques would misfire under a contract that promised propulsive external drama. Do not generalize
the mode; generalize the *principle* (turn = a legible change; enact it concretely).

## Related
[[scene-dramaturgy]] · [[character-intentionality]] · [[showing-and-telling]] · [[static-scene]]
