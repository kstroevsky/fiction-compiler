# Knowledge Base Design

## Tier 0: constitution
Small, always-loaded rules that define safety, architecture, quality, and process-change boundaries.

## Tier 1: indexes
Compact maps of concepts, aliases, source IDs, and when each module applies.

## Tier 2: operational notes
Concise, source-grounded patterns, counterexamples, checklists, and diagnostic questions.

## Tier 3: deep references
Longer summaries, citations, research notes, and genre-specific material loaded only when needed.

## Tier 4: corpora and analyses
Public-domain, licensed, or user-provided texts; extracted abstract features; scene annotations; narrative graphs. Raw copyrighted text must not be copied into the repository without permission.

## Retrieval rule
Retrieve by task and layer, not by generic semantic similarity alone. A scene drafting bundle should include the scene spec, directly participating characters, current relationship/knowledge state, relevant world rules, nearby promises, current discourse constraints, and the style profile—never the entire encyclopedia.

## Two source streams
Knowledge enters from two distinct streams, tagged by `stream` in `kb/source-register.json`:

- **craft-instruction** — the centuries-long body of writing tutorials, poetics, and craft manuals. This is the source of *heuristics*. Much of it is public-domain classic instruction (Aristotle's *Poetics*, Horace's *Ars Poetica*, Longinus, Freytag, Poe, Henry James, Lubbock, Forster, early Strunk) that can be ingested freely; the modern online body of tutorials and essays is in-copyright and mined for abstract features only, cited per heuristic.
- **fiction-corpus** — public-domain *stories* for pattern analysis and annotation (`kb/corpus-notes/`).

We extract abstract craft features; we never reproduce protected text. Learning is not copying. US public-domain status does not settle EU/DE status (EU term is life + 70), so each source records a `copyright_note` to verify before full-text ingestion in the EU.
