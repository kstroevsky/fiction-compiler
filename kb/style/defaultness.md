# Defaultness

**Concept:** defaultness · **Layer:** style
**Used by:** `src/fiction_compiler/defaultness.py`, `kb/style/defaultness-catalog.json`, `adversarial-reader`

## Definition
*Defaultness* is the pull of the statistically obvious continuation — the phrasing, beat, or
resolution a language model (or an unrevised writer) reaches for first because it is the most
probable, not the most true. It appears at every layer: default sentences, default scene
behavior, default character tactics, default conflicts, default premises. The cure is almost
never a rarer adjective; it is to find the *lowest layer* where the genericity originates and
repair there.

## Use when
Any prose or plan review. The deterministic linter catches surface tics (clichés, told
emotion, filter words, adverb tags, opener runs); the `adversarial-reader` catches predictable
beats and unearned emotion; the architect catches default premises.

## The repair ladder (route downward)
```
generic sentence → generic scene behavior → generic character tactic
→ generic conflict → generic premise assumption
```
Fix the deepest layer that is actually generic. Polishing the sentence over a default scene
just hides the defect (a line editor must not bury a broken scene under prettier prose).

## Diagnostic questions
- Is this the first thing the model would produce? What are three less-obvious, still-motivated alternatives?
- Is an emotion shown *and then* explained? (Delete the explanation.)
- Does the ending resolve symmetrically into a tidy lesson? (Suspect uplift.)
- Is a surprise here merely improbable, or postdictable? ([[suspense-surprise-curiosity]])

## Failure modes
- Treating synonym-swapping as "style variation."
- Adding "don't be clichéd" to a prompt instead of fixing the generative layer.
- Morally sanitized conflict; premature therapeutic self-awareness; automatic hopeful uplift.

## Conflicts with
Genre contract — some defaults are *promises* the reader wants kept. Deviate deliberately,
and only where the contract allows (record it in the brief).

## Related
[[concrete-vs-abstract]] · [[suspense-surprise-curiosity]] · [[character-intentionality]]

## Sources
- `prose-reading` — noticing the unearned and the generic (abstract).
