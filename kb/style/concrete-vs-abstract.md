# Concrete vs. Abstract

**Concept:** concrete-vs-abstract · **Layer:** style
**Used by:** `src/fiction_compiler/defaultness.py`, `style-editor` agent

## Definition
Fiction persuades through the specific and perceptible, not the summarized and general.
Abstraction ("she was overwhelmed by a sense of loss") tells the reader a category; concretion
("she kept setting two cups on the tray") lets them infer it and feel the inference. The rule
is not "never abstract" — it is *earn* abstraction with prior specifics, and prefer the detail
only this character, in this world, at this moment, would register.

## Use when
Diagnosing generic, ornamental, or emotionally inert prose; deciding whether a sentence
*alters perception* or merely decorates.

## Diagnostic questions
- Could this sentence appear in a thousand other stories? (Generic → suspect.)
- Is an emotion named and then paraphrased instead of enacted? (Cut the label.)
- Does each image change how the reader perceives, or just ornament?
- Is the selected detail *characterizing* (chosen by this focalizer) or inventory?

## Failure modes
- Generic sensory inventory (the "sights, sounds, and smells" sweep).
- Abstract emotion words doing the work behavior should ([[dialogue-subtext]]).
- Ornamental metaphor that restates the literal meaning.
- Filter words and weak intensifiers padding perception (the defaultness linter flags these).

## Conflicts with
Compression — total concretion bloats. Summary is a legitimate *duration* choice; use it for
transition, not for the moments that matter.

## Related
[[defaultness]] · [[narrative-distance]]

## Sources
- `prose-reading` — close reading for specificity (abstract).
- `gardner-art-fiction` — vivid, continuous detail (abstract).
