# Fiction Compiler Starter

A model-agnostic, repository-first architecture for long-form fiction with Codex or Claude Code.

The system separates:

1. **Intent** — what the work promises the reader.
2. **Fabula** — characters, world state, causes, events, knowledge, and chronology.
3. **Discourse** — narrator, focalization, ordering, pacing, revelation, and scene selection.
4. **Realization** — prose, dialogue, imagery, rhythm, and formatting.
5. **Verification** — deterministic validators, adversarial critics, blind comparisons, and human gates.
6. **Learning** — versioned retrospectives and evaluation cases, never uncontrolled self-modification.

## Quick start

```bash
python3 scripts/new_project.py my-novel
make validate
make test
```

Then start either tool at the repository root:

```bash
codex
# or
claude
```

Suggested first instruction:

> Run the bootstrap-story skill for `projects/my-novel`. Interview me until the project brief has no material ambiguities. Do not draft prose yet.

## Core commands

```bash
make validate                         # schema + KB + continuity checks (see below)
make test                             # regression tests
make audit  PROJECT=projects/my-novel # deterministic hard audit (Audit 1)
make lint   PROJECT=projects/my-novel SCENE=ch01-sc01   # defaultness linter
make pipeline                         # validate -> audit -> test

python3 scripts/compile_scene_context.py projects/my-novel ch01-sc01   # leak-free context
python3 scripts/promote_candidate.py    projects/my-novel ch01-sc01 candidate-a.md
```

## Deterministic engine (`src/fiction_compiler/`)

The pipeline shifts as much judgment as possible off the LLM and onto code:

- **`schema.py`** — dependency-free JSON-Schema validation; `validate_workspace.py` enforces
  every typed artifact against `schemas/` (schemas are no longer decorative).
- **`state.py`** — event-sourced `reconstruct_state_before(scene)`: story state is
  `seed canon + accepted deltas`, replayed. This is what stops a fact a later scene introduces
  from leaking into an earlier one.
- **`hard_audit.py`** — Audit 1 in code: knowledge cutoff, causal references, POV, promise
  ledger, chronology. Emits `critique.schema`-valid findings with exact evidence.
- **`defaultness.py`** — deterministic slice of Audit 3: clichés, told emotion, filter words,
  weak-word density, adverb tags, opener runs — patterns in `kb/style/defaultness-catalog.json`.
- **`revision.py`** — the **story's** PDCA revision loop (deterministic CHECK/ACT): accept a
  revision only if it improves the target defect without a material regression; stop instead of
  drifting toward blandness. Driver: `scripts/revise_scene.py`; per-scene `revision-log.jsonl`.

Two self-improvement loops — the **story** loop (above) and the **framework** loop
(`retrospective` skill + `constitution/change-policy.md`) — are kept strictly separate; see
`docs/self-improvement-loops.md`. For what is built vs. deferred see `docs/implementation-roadmap.md`,
and `projects/salt-in-the-wire/` for a worked end-to-end example.

## Important rule

Generated branches live in `.runs/` or a scene's `candidates/` directory. Only a reviewed candidate may be promoted into `manuscript/` or canonical state.
