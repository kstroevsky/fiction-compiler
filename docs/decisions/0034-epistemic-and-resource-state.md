# ADR 0034 — Separate world truth, belief, memory, and load-bearing resources

Engineering decision record for the remaining Track-E state-semantics defects in the September
27–28 audit/review. This extends the executable story IR; it does not claim that richer state makes
fiction better.

## 1. Failure observed

`StoryState.knowledge` previously stored only fact IDs. If a true fact was later removed, the
character still "knew" that ID, so current factive knowledge, retained memory, and stale belief were
indistinguishable. The same IR had no executable representation for a load-bearing quantity such as
twelve baked loaves, so acquire/use and conservation mistakes could survive structured planning.

## 2. Exact evidence

- The review's N2 probe removes a fact after a character learned it: `fact_exists=false` while the
  old `knows` query remained true.
- The review's Track E exit conditions explicitly require false-belief, learning-effect,
  negative-knowledge, acquire/use, and quantity cases.
- The *Overnight* close reading identifies a structured twelve-loaf contradiction that natural
  language fields alone cannot verify.
- The audit recommends stable propositions plus holder/source/revision information, while also
  warning against encoding a complete psychology or universal resource ontology before a story
  needs it.

## 3. Root-layer diagnosis

The defect belongs to the **story-state IR**. Current world truth and an agent's epistemic state are
different kinds of state; countable props that a causal turn depends on are another explicit state
dimension. Prose lint cannot reliably repair either distinction after generation.

## 4. Minimal change

`StoryState` now keeps:

- `facts`: propositions currently true in the world;
- `fact_definitions`: stable proposition IDs and immutable text, including propositions that are
  currently false;
- `memory`: propositions a character retains;
- `beliefs`: that character's current true/false stance, with optional source/event provenance;
- `knowledge`: a backward-compatible computed view that is true only when the character believes a
  proposition and the proposition is currently true;
- `resources`: explicitly declared `(resource, holder/location) -> quantity` balances plus units.

Legacy `knowledge_changes` remains a compact learn/forget operation for propositions that are true at
that point. New `belief_changes` supports `set` and `forget`, with typed sources (`perception`,
`testimony`, `inference`, `correction`, `forgetting`, or `unknown`). `propositions_defined` allows a
stable proposition to exist without asserting it as world truth, which is required to represent a
false belief without inventing a true fact.

Load-bearing resources are opt-in. Seed `resources.jsonl` records a balance; scene
`resource_changes` applies ordered `acquire`, `consume`, or quantity-preserving `transfer`
operations. Underflow and unit changes are material hard-audit findings. A scene may declare
`resource_requirements` when its action depends on a minimum or exact quantity.

Context bundles, state/tool serialization, character-simulator packets, prose claims, and backward
revision dependencies expose the same distinctions. `focalizer_knows` is factive; a new
`focalizer_believes` claim can represent a mistaken stance. Merely adding a world fact no longer
grants the focalizer knowledge of it.

The local schema validator now enforces the composition/conditional keywords used by these shapes
(`const`, `allOf`, `oneOf`, `not`, `if/then/else`) and exclusive numeric bounds rather than silently
accepting unenforced schema text.

## 5. New regression cases

Maintained tests prove that:

- removing truth preserves memory/belief while `knows` becomes false;
- a false belief can be corrected and later forgotten without changing proposition identity;
- `believes(..., value=False)` remains distinct from absence of belief and negative knowledge;
- an explicit belief update can satisfy a factive knowledge effect only when its proposition is
  true;
- an added world fact does not automatically become POV knowledge;
- acquire-then-use succeeds, unavailable consumption fails, and transfer conserves quantity;
- resource requirements fail on the wrong pre-scene quantity;
- compiled context and backward-revision read/change sets include epistemic/resource state; and
- malformed belief/resource records are rejected by the actual runtime schema validator.

## 6. Before/after interpretation

Before: one set answered both "what does this character retain?" and "what does this character know
to be currently true?", and quantity continuity lived in prose. After: those deterministic questions
have separate typed representations and hard checks.

This closes demonstrated consistency semantics. It does **not** establish that the extra state pays
for its authoring/context cost, improves reader outcomes, or captures every belief/resource needed by
future stories. Those are empirical questions.

## 7. Known limits

- Belief is one level per character. There is no nested theory of mind, probabilistic confidence,
  or general inference engine.
- Source metadata records how a stance entered the ledger; deterministic code does not prove that a
  testimony or inference was psychologically justified.
- Resources are explicit balances only. The compiler does not infer quantities from prose or model
  complete physics/inventory state.
- Event preconditions are still evaluated against the state before the whole scene. Ordered
  within-scene beat execution is the next independent Track-E slice.
- Nonlinear/fabula-ordered reconstruction and a fuller entity registry remain separate work.

## 8. Human approval status

Authorized as implementation of the user-requested September audit/plan. Revert path is the commit
containing the state/schema/audit/context/dependency changes and their regressions. This ADR records
the implemented representation; it does not authorize a broader psychology/resource simulator.
