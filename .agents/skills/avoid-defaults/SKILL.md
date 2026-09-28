---
name: avoid-defaults
description: Anti-obviousness technique — predict the model-default continuation, then design a motivated, retrospectively-legible alternative. Use before drafting a scene or choosing the next development.
---
Purpose: make the story non-obvious and non-boring **without resorting to randomness**. A strong
surprise is unexpected beforehand and inevitable in hindsight. This is a creative procedure — the
tools inform it; they do not perform it.

1. **Predict the default basin.** *Before* you draft, and without looking at what you intend to write,
   list the 3 most likely next developments given only the story so far. Better: get a second, fresh
   pass (a subagent or the `adversarial-reader`) to list its 3 independently. High overlap = the
   model-default basin — the obvious continuation everyone (including the reader) can feel coming.
2. **Leave the basin.** Your development must not be in the consensus list.
3. **Keep it caused.** It must follow from an existing character motive, belief (including a *false*
   belief), fear, or world affordance. Check `state_before` / the canon — if nothing there supports it,
   the surprise is arbitrary. Go *deeper* into character and world; do not reach for a twist.
4. **Plant the legibility.** After it lands, the reader should be able to point to earlier evidence.
   If that evidence isn't there yet, add or relocate a **setup** (open a promise) — a plant, not an
   explanation. Retrospective coherence is built before the surprise, not narrated after it.
5. **Score it.** `Originality* = Unexpectedness × Retrospective-coherence × Character-necessity`.
   A random meteor is high on unexpectedness and ~0 on necessity. A good reversal scores on all three.
   If any factor is ~0, it's the wrong move.
6. **Route defaults downward.** If the *prose* comes out generic, the real default may be a generic
   scene behavior → tactic → conflict → premise. Repair the lowest layer that is actually generic
   (see `kb/style/defaultness.md` and `kb/narratology/eventfulness.md`), then redraft — don't sand the
   sentence over a default scene.

Reference cards: `kb/narratology/suspense-surprise-curiosity.md`, `kb/narratology/eventfulness.md`,
`kb/style/defaultness.md`. Deterministic backstop: `defaultness_lint` catches the *surface* residue
this procedure is meant to prevent at the source.
