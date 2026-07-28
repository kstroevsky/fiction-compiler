# Suspense, Surprise, Curiosity

**Concept:** suspense-surprise-curiosity · **Layer:** narratology
**Used by:** `adversarial-reader` agent, `docs/evaluation.md`

## Definition
Three distinct engines of reader attention, all governed by *information control*:
- **Curiosity** — the reader wants to know something withheld about the past/hidden.
- **Suspense** — the reader anticipates an outcome and fears/hopes for it (often knows *more*
  than the character: dramatic irony).
- **Surprise** — an expectation is violated. Valuable only when *postdictable*: unexpected
  beforehand, yet retrospectively legible from evidence already present.

A surprise that is merely improbable (a random meteor) is cheap. A strong reversal scores on
three axes at once: **Unexpectedness × Retrospective coherence × Character necessity.**

## Use when
Scheduling reveals; judging whether a twist is earned. This is the anti-obviousness test the
`adversarial-reader` applies and the `Originality*` metric the roadmap's selection stage will
compute.

## Diagnostic questions
- What does the reader know vs. the character right now? Which engine am I running?
- After the surprise, can the reader point to earlier evidence that made it possible?
- Does the reversal arise from *this* character/world, or could it happen in any story?
- Is the most statistically obvious next beat the one I chose? (If so, mutate it.)

## Failure modes
- Twist without seeding (arbitrary, feels like a cheat).
- Seeding without twist (telegraphed; suspense collapses).
- Withholding by author fiat rather than by the focalizer's genuine limits.

## Conflicts with
Causal telegraphing (see [[causality-and-preconditions]]) — manage the tension with what is
*shown* vs. *withheld*, not by breaking cause.

## Related
[[promise-and-payoff]] · [[defaultness]] · [[focalization-and-knowledge]]

## Sources
- `lhn` — tellability and narrative surprise (paraphrase).
