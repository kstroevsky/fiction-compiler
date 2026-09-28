---
name: compile-scene-context
description: Builds a minimal, task-specific context bundle for drafting or auditing one scene.
---
Run `python3 scripts/compile_scene_context.py <project-dir> <scene-id>`. Inspect the generated bundle under
`<project>/.runs/context/<scene-id>/<run-id>/context-bundle.json`. Add only missing relevant canon. Do
not paste the whole project into context. The bundle must include scene spec, participating characters,
current known facts, relevant world rules, nearby promises, discourse constraints, and style profile.
When a scene uses the plan-search workflow, the bundle also includes only the latest current,
hash-bound selected scene plan(s); stale selections are omitted rather than silently reused.
