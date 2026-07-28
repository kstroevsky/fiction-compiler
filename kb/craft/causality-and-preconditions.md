# Causality and Preconditions

**Concept:** causality-and-preconditions · **Layer:** craft
**Used by:** `src/fiction_compiler/hard_audit.py:audit_scene`, `narrative-architect`

## Definition
An event is legitimate only when its preconditions hold: the actors are present and capable,
they possess the required knowledge, the world permits the action, and prior events have made
it possible. Plot is a chain of *because*, not a list of *and then*. "Because" carries;
"and then" merely continues.

## Use when
Planning an event graph, or auditing whether a scene can occur at its position. The hard
audit checks the machine-checkable subset: referenced events exist; required knowledge was
established before the scene (`knowledge_required`); pov/participants are defined.

## Diagnostic questions
- What must already be true for this to happen? Is each precondition established *earlier*?
- Does any character act on information they could not have?
- Remove the prior scene: does this one still stand? If yes, the causal link was decorative.

## Failure modes
- Convenient knowledge: a character suddenly knows what the plot needs.
- Coincidence doing causal work (acceptable to *cause* trouble, suspect when it *solves* it).
- Capability appearing on demand (a skill/tool never set up).

## Conflicts with
Surprise — over-tight causal telegraphing kills it. Resolve via information control, not by
breaking causality (see [[suspense-surprise-curiosity]]).

## Related
[[character-intentionality]] · [[eventfulness]] · [[promise-and-payoff]]

## Sources
- `egri-dramatic-writing` — orchestration of forces (abstract).
- `swain-techniques` — motivation→reaction as a causal unit (abstract).
