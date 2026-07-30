# Focalization and Knowledge

**Concept:** focalization-and-knowledge · **Layer:** narratology
**Used by:** `src/fiction_compiler/hard_audit.py:audit_scene`, `continuity-auditor`

## Definition
*Focalization* is the perceptual/cognitive filter through which the narrative is presented —
whose eyes, whose knowledge, whose limits. Distinct from *voice* (who speaks) and from the
fabula. A focalized narrative can only convey what the focalizer perceives, knows, or infers.
Knowledge is per-character and, **in this system's v1 state model, monotonic** within a timeline: a
character cannot un-know, and cannot know a fact established only later (the *knowledge cutoff*).

**Limitation (honest scope).** Real minds are *not* monotonic — people forget, misremember, revise
beliefs, hold false beliefs, and learn a former "fact" was wrong. The current `state.py` cannot
represent forgetting, false belief, confidence, or the source of a belief, so it must not be relied
on for amnesia, unreliable-narrator, or belief-revision plots. Modelling non-monotonic knowledge
(belief vs. fact, confidence, source) is deferred (see the roadmap / review §"story state is too
shallow"). The `knowledge_required` cutoff the hard audit enforces is sound *within* that monotonic
assumption.

## Use when
Choosing a scene's pov and auditing whether the telling stays within its knowledge. The hard
audit enforces the cutoff: `knowledge_required` on a scene must be a subset of the state
reconstructed *before* it, or it is a fatal leak from the future.

## Diagnostic questions
- Does the narration report anything the focalizer could not perceive or know here?
- Are we told another character's private thoughts under a single focalizer? (Leak.)
- Does the reader know more than the focalizer? Is that dramatic irony — intended?

## Failure modes
- Head-hopping: interiority of non-focalized characters bleeds in.
- Future-knowledge leak: today's scene "knows" tomorrow's revelation.
- Omniscient convenience used to dump information the focalizer lacks.

## Conflicts with
Suspense sometimes wants the reader to know more than the character (dramatic irony); that is
a *discourse* choice, not a license to break the focalizer's knowledge.

## Related
[[narrative-distance]] · [[fabula-vs-discourse]] · [[suspense-surprise-curiosity]]

## Sources
- `lhn` — focalization (paraphrase).
- `wood-how-fiction-works` — free indirect style and knowledge (abstract).
