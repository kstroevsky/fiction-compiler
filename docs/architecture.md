# Architecture

## Compiler analogy

| Fiction layer | Compiler analogue | Canonical artifact |
|---|---|---|
| Reader contract | Product specification | `brief/project.json` |
| Storyworld/fabula | Semantic model / IR | `canon/**`, `planning/event-graph.json` |
| Discourse | Scheduling / lowering | `planning/discourse-plan.json` |
| Scene plan | Function-level IR | `scenes/<id>/spec.json` |
| Prose | Generated code | candidate Markdown |
| Continuity checks | Type checking / static analysis | validator reports |
| Reader response | Integration / acceptance tests | critic reports and human gates |
| Revision | Debugging / optimization | decisions and regression cases |

## Why layers matter

A sentence can be excellent while the scene is unnecessary; a scene can be tense while the character action is unmotivated; a plot can be coherent while the telling is monotonous. Each defect must be repaired at its owning layer.

## Canon is event-sourced

Accepted scenes append state deltas. Current state is derived from the initial canon plus accepted deltas. This makes contradictions traceable and allows alternate branches without corrupting the main story.
