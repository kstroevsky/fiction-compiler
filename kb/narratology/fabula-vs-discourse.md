# Fabula vs. Discourse

**Concept:** fabula-vs-discourse · **Layer:** narratology
**Used by:** `src/fiction_compiler/state.py`, `docs/architecture.md`

## Definition
*Fabula* is the events in causal-chronological order — what happened. *Discourse* (sjuzhet)
is the particular telling — the order, pace, and selection through which a reader receives
them. The same fabula can yield radically different works depending on discourse.

## Use when
Before repairing any defect. Ask which layer owns it: a confusing scene may have sound
fabula but broken discourse (told out of order, wrong focalizer), or vice versa. The
compiler enforces this split: canon/state is fabula; `planning/discourse-plan.json` is
discourse; prose is realization.

## Diagnostic questions
- If I re-ordered the telling, would the *events* still be coherent? (Tests fabula.)
- Is the reader confused because of what happened, or because of how it was shown?
- Does a "fix" secretly rewrite causality when only presentation needed changing?

## Failure modes
- Patching a causal hole with a line of pretty prose (repairing the wrong layer).
- Flashbacks that silently mutate the event record instead of only re-ordering the telling.
- Treating scene id order as fabula order when the discourse is non-linear (encode explicit
  `time` in state deltas — the chronology audit relies on it).

## Conflicts with
Nothing inherently; it is the organizing distinction. It constrains order-duration-frequency.

## Related
[[order-duration-frequency]] · [[focalization-and-knowledge]]

## Sources
- `lhn` — fabula/sjuzhet and computational narratology (paraphrase only).
