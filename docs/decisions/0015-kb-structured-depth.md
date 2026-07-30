# ADR 0015 — KB structured depth (P4 slice 1)

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. First slice of Priority 4 (the real literary knowledge base).
Recorded here because the change is framework-global.

## 1. Failure observed
The KB was a "starter": 16 concept cards with prose sections but no *machine-readable, enforced
depth*. The review asked that **every note carry** a claim, evidence strength, conditions of
applicability, counterexamples, known conflicts, and which audit/skill consumes it — and it flagged
specific cards as **over-absolute**: `eventfulness` equated boredom with low eventfulness;
`scene-dramaturgy` asserted "if nothing changes it is not a scene" as law; `focalization` described
knowledge as monotonic without noting that real minds forget, misremember, and hold false beliefs.
There were also no conflicting-theory cards and no annotated fiction analyses. The review is explicit
that P4 must add **depth and structure, not volume** ("do not simply add hundreds of generic cards").

## 2. Exact evidence
- `kb/index.json` concepts had `id/layer/card/use_when/used_by/related/sources` — no `claim`,
  `evidence_strength`, `dangerous_when`, `counterexamples`, or `conflicts_with`.
- `kb/narratology/eventfulness.md`: "boredom is low eventfulness." `kb/craft/scene-dramaturgy.md`:
  "if nothing changes … it is not a scene." `kb/narratology/focalization-and-knowledge.md`:
  "Knowledge is … monotonic," unqualified.
- `kb/corpus-notes/README.md`: "no annotations are seeded yet."

## 3. Root-layer diagnosis
Knowledge-base layer. The cards held craft prose but the *structure that forces conditionality* —
grading, counterexamples, explicit conflicts, consumers — was absent, so cards read as universal
rules and nothing could enforce otherwise.

## 4. Minimal proposed change (structure + enforcement + a small, honest seed)
- **Depth on every concept** (`kb/index.json`): `claim`, `evidence_strength`
  (structural | craft-heuristic | theoretical | contested | empirical), `dangerous_when`,
  `counterexamples`, `conflicts_with` — filled honestly for all 16 existing concepts.
- **Enforcement** (`validate_workspace.validate_kb`): every concept must carry those fields, the
  grade must be from the enum, `used_by` must be non-empty (an unconsumed concept is inert), and every
  `conflicts_with` must resolve to a real concept id. `kb.py` retrieval now surfaces the depth.
- **Fix the flagged cards**: `eventfulness`, `scene-dramaturgy`, and `focalization-and-knowledge` are
  edited to state their conditions and limits (the monotonic-knowledge scope is now explicit).
- **Two new cards demonstrating the missing types, honestly**: `static-scene` — a *conflicting
  theory* (the lyric/static mode) that `conflicts_with` eventfulness + scene-dramaturgy; and
  `annotated-overnight-decision` — the first **annotated scene**, analysing the repo's OWN worked
  example (`the-overnight/ch01-sc02`) so nothing depends on copyrighted text. A `the-overnight-example`
  source is registered for provenance.

## 5. New regression case
`tests/test_tools.py`: every concept carries the structured depth with a valid grade and resolvable
conflicts; the conflicting pair eventfulness ↔ static-scene is bidirectional. `validate_workspace`
now fails a KB without the depth (exercised by `test_workspace_validates`).

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `kb.get("eventfulness")` had no `evidence_strength`, no counterexamples, no conflicts; the
  card read as "boredom = low eventfulness."
- After: it is graded `contested`, lists counterexamples (lyric/ritual/observational), and
  `conflicts_with: ["static-scene"]`; the new `static-scene` card carries the opposing view.
  Concepts 16 → 18; suite 133 → 135; `validate_workspace` passes with depth enforced.

## 7. Known trade-offs
- This is depth-and-structure, not corpus breadth: two seed cards, not genre/period modules or a
  large annotated corpus. Those remain P4 work, gated by the copyright/extract-not-copy discipline.
- `evidence_strength` grades are the author's honest judgement, not a measured meta-analysis; most
  cards are `craft-heuristic`/`theoretical`, a few `structural` (the code enforces them).
- Retrieval is still substring scoring; a semantic index / task→concept classifier is not built.
- The single annotated card is one in-repo sample; AGENTS.md's "never learn a rule from one sample"
  is stated in the card itself.

## 8. Human approval status
Authorized as the user-directed "do P4" step. The constitution (`AGENTS.md`) is unchanged; the
extract-not-copy and provenance rules are honored (the only analysed fiction is the repo's own).
Revert path: git history of `kb/index.json`, the three edited cards, the two new cards,
`kb/source-register.json`, `scripts/validate_workspace.py`, `src/fiction_compiler/kb.py`, and the tests.
