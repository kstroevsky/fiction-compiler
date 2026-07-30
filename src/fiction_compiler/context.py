"""Minimal, leak-free scene-context assembly.

Shared by the CLI (`scripts/compile_scene_context.py`) and the tools/MCP layer so the LLM gets
the exact same bundle whether it runs the script or calls the tool. The bundle is derived from
the reconstructed state *before* the scene, so it can never contain what a later scene reveals.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .state import reconstruct_state_before
from .workspace import RUNS

_PROJECT_KEEP = ["id", "title", "form", "audience", "reader_contract", "theme_question", "constraints", "desired_affect"]


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def compile_bundle(project: Path, scene_id: str) -> dict:
    scene_dir = project / "scenes" / scene_id
    spec = _load(scene_dir / "spec.json", {})
    pov = spec.get("pov")
    participants = list(dict.fromkeys([pov] + spec.get("participants", []))) if pov else spec.get("participants", [])
    participant_set = {p for p in participants if p}

    character_sheets = []
    for path in sorted((project / "canon" / "characters").glob("*.json")):
        data = _load(path, {})
        if data.get("id") in participant_set:
            character_sheets.append(data)

    before = reconstruct_state_before(project, scene_id)
    knowledge = {c: sorted(before.knowledge.get(c, set())) for c in participant_set if c in before.knowledge}
    relationships = [
        {"subject": subject, "object": obj, "dimensions": dims}
        for (subject, obj), dims in before.relationships.items()
        if {subject, obj} & participant_set
    ]
    predicates = [
        {"predicate": predicate, "subject": subject, "object": obj, "value": value}
        for (predicate, subject, obj), value in before.predicates.items()
        if subject in participant_set or obj in participant_set
    ]
    canon_index = _load(project / "canon" / "index.json", {})

    # Inclusion manifest: why each item is in the bundle, and how load-bearing it is. Facts the scene
    # explicitly requires are "required"; the rest are "background". Makes context packing testable
    # (and is the first step toward true relevance pruning + token budgets — see the roadmap).
    required_facts = {r.get("fact") for r in spec.get("knowledge_required", []) if r.get("fact")}
    context_manifest: list[dict] = []
    for sheet in character_sheets:
        context_manifest.append({"kind": "character", "ref": sheet.get("id"),
                                 "reason": "scene participant", "priority": "required", "source": "canon/characters"})
    for fact_id in before.facts:
        needed = fact_id in required_facts
        context_manifest.append({"kind": "fact", "ref": fact_id,
                                 "reason": "required knowledge for the scene" if needed else "established before the scene",
                                 "priority": "required" if needed else "background", "source": "canon"})
    for promise_id in before.open_promises:
        context_manifest.append({"kind": "promise", "ref": promise_id, "reason": "open obligation",
                                 "priority": "reference", "source": "canon"})
    for rule in canon_index.get("world_rules", []):
        context_manifest.append({"kind": "world_rule", "ref": rule, "reason": "world constraint",
                                 "priority": "reference", "source": "canon/index"})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scene_id": scene_id,
        "project": {k: v for k, v in _load(project / "brief" / "project.json", {}).items() if k in _PROJECT_KEEP},
        "scene_spec": spec,
        "participants": character_sheets,
        "state_before": {
            "time": before.time,
            "facts": before.facts,
            "participant_knowledge": knowledge,
            "relationships": relationships,
            "predicates": predicates,
            "open_promises": before.open_promises,
        },
        "world_rules": canon_index.get("world_rules", []),
        "context_manifest": context_manifest,
        "discourse_plan": _load(project / "planning" / "discourse-plan.json", {}),
        "style_profile": _load(project / "planning" / "style-profile.json", {}),
        "note": (
            "state_before is reconstructed from seed canon + accepted deltas only; it cannot "
            "contain anything a later scene introduces. Add targeted missing canon if needed; "
            "never paste the whole project."
        ),
    }


def write_bundle(bundle: dict, scene_id: str) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = RUNS / run_id / scene_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "context-bundle.json"
    out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
