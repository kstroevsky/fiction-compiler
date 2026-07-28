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
make validate                         # structural and continuity checks
make test                             # regression tests
python3 scripts/compile_scene_context.py projects/my-novel ch01-sc01
python3 scripts/promote_candidate.py projects/my-novel ch01-sc01 candidate-a.md
```

## Important rule

Generated branches live in `.runs/` or a scene's `candidates/` directory. Only a reviewed candidate may be promoted into `manuscript/` or canonical state.
