# Knowledge Base

Abstract craft knowledge for the pipeline. **We extract abstract features — heuristics, failure
modes, diagnostic questions — and never reproduce protected text.** Learning from a source is not
copying it.

## Two ingestion streams
Sources in `source-register.json` carry a `stream`:

- **craft-instruction** — the centuries-long body of writing tutorials, poetics, and craft
  manuals. This is where *heuristics* come from. Much of it is public-domain classic instruction
  (Aristotle, Horace, Longinus, Freytag, Poe, Henry James, Lubbock, Forster, early Strunk) which
  can be ingested freely; the modern online body (blogs, workshop lore, author essays) is
  in-copyright and mined for abstract features only, cited per heuristic.
- **fiction-corpus** — public-domain *stories* (Standard Ebooks, Project Gutenberg) for pattern
  analysis and annotation. See `corpus-notes/README.md`.
- **reference** — narratology handbooks and the like.

> Copyright discipline: US public-domain status does **not** settle EU/DE status (EU term is life
> + 70 years). Every source records a `copyright_note`; verify before ingesting full text in the EU.

## Layout (tiers)
- `index.json` — Level-0 concept map. Every concept names a `used_by` consumer, so no card is inert.
- `narratology/`, `craft/`, `style/` — Level-1 concept cards (this is where the cards live).
- `genre/`, `research/` — reserved for genre-specific and project research notes.
- `corpus-notes/` — Level-2/3 annotations from the fiction corpus.
- `style/defaultness-catalog.json` — machine-readable patterns for the defaultness linter.

`validate_workspace.py` fails if an indexed card is missing, a cited source is unregistered, or a
card is orphaned (present but unindexed). "The folder exists" is never "the KB is populated."
