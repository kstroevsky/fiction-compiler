"""The tool surface the LLM author actually calls.

Thin, JSON-returning wrappers over the deterministic engine, plus a registry (name +
description + JSON-Schema + handler) that the MCP server exposes. These do not write fiction —
they hand the model reference (KB), continuity truth (state), guardrail findings (audits), and
a revision fitness signal, so the *model* can write and revise well.

Every handler returns a JSON-serialisable dict. Keep them pure and cheap.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import defaultness, hard_audit, kb, revision
from .assemble import assemble as _assemble
from .context import compile_bundle
from .promote import promote_candidate
from .state import StoryState, accepted_scene_ids, reconstruct_state_before
from .tournament import run_tournament
from .workspace import confine_file, confine_project, project_dir


def _state_json(state: StoryState) -> dict:
    return {
        "time": state.time,
        "facts": state.facts,
        "knowledge": {c: sorted(v) for c, v in state.knowledge.items()},
        "relationships": [{"subject": s, "object": o, "dimensions": dims}
                          for (s, o), dims in state.relationships.items()],
        "predicates": [{"predicate": p, "subject": s, "object": o, "value": v}
                       for (p, s, o), v in state.predicates.items()],
        "open_promises": state.open_promises,
        "closed_promises": sorted(state.closed_promises),
        "applied_scenes": state.applied_scenes,
    }


# --- handlers ---------------------------------------------------------------

def kb_search(query: str = "", layer: str | None = None) -> dict:
    return {"results": kb.search(query, layer)}


def kb_get(concept_id: str) -> dict:
    card = kb.get(concept_id)
    return card if card else {"error": f"no concept card with id {concept_id!r}"}


def kb_sources(stream: str | None = None) -> dict:
    return {"sources": kb.sources(stream)}


def state_before(project: str, scene_id: str) -> dict:
    return _state_json(reconstruct_state_before(project_dir(project), scene_id))


def compile_context(project: str, scene_id: str) -> dict:
    return compile_bundle(project_dir(project), scene_id)


def audit(project: str, scene_id: str | None = None) -> dict:
    root = project_dir(project)
    if scene_id:
        return hard_audit.audit_scene(root, scene_id)
    critiques = [hard_audit.audit_canon(root)]
    critiques += [hard_audit.audit_scene(root, s) for s in accepted_scene_ids(root)]
    return {"critiques": critiques}


def defaultness_lint(text: str | None = None, path: str | None = None) -> dict:
    if text is not None:
        findings = defaultness.lint_text(text)
        verdict = "revise" if any(f["severity"] in ("material", "fatal") for f in findings) else "pass"
        return {"verdict": verdict, "findings": findings}
    if path:
        return defaultness.lint_file(Path(path))
    return {"error": "provide either 'text' or 'path'"}


def evaluate_revision(
    before_findings: list,
    after_findings: list,
    target: str | None = None,
    iteration: int = 1,
    attempts_at_current_layer: int = 1,
    max_iterations: int = 3,
    max_attempts_per_layer: int = 2,
) -> dict:
    outcome = revision.evaluate_revision(
        before_findings, after_findings, target_dimension=target,
        iteration=iteration, attempts_at_current_layer=attempts_at_current_layer,
        max_iterations=max_iterations, max_attempts_per_layer=max_attempts_per_layer,
    )
    return {
        "decision": outcome.decision,
        "reason": outcome.reason,
        "target_dimension": outcome.target_dimension,
        "target_before": outcome.target_before,
        "target_after": outcome.target_after,
        "material_regressions": outcome.material_regressions,
        "fixed_dimensions": outcome.fixed_dimensions,
        "fixed": outcome.fixed_findings,
        "persisted": outcome.persisted_findings,
        "worsened": outcome.worsened_findings,
        "newly_introduced": outcome.new_findings,
    }


def _resolve_candidate(scene_dir, name: str):
    candidate = Path(name)
    return candidate if candidate.exists() else scene_dir / "candidates" / name


def record_revision(project: str, scene_id: str, before: str, after: str, target: str | None = None,
                    max_iterations: int = 3, max_attempts_per_layer: int = 2) -> dict:
    """Lint before/after, derive iteration+attempts from the persisted revision-log, decide, and log.

    Unlike ``evaluate_revision`` this reads and writes history, so the loop's stop conditions
    (ESCALATE_LAYER, STOP_NO_PROGRESS) become reachable and each iteration leaves a durable trace.
    """
    scene_dir = project_dir(project) / "scenes" / scene_id
    before_path = _resolve_candidate(scene_dir, before)
    after_path = _resolve_candidate(scene_dir, after)
    if not before_path.exists() or not after_path.exists():
        return {"error": "before/after candidate not found"}
    before_findings = [defaultness.lint_file(before_path)]
    after_findings = [defaultness.lint_file(after_path)]
    history = revision.revision_history(scene_dir)
    iteration = len(history) + 1
    attempts = 1 + sum(1 for h in history if h.get("target_dimension") == target)
    outcome = revision.evaluate_revision(
        before_findings, after_findings, target_dimension=target,
        iteration=iteration, attempts_at_current_layer=attempts,
        max_iterations=max_iterations, max_attempts_per_layer=max_attempts_per_layer,
    )
    b, a = revision.tally(before_findings), revision.tally(after_findings)
    revision.log_revision(scene_dir, {
        "iteration": iteration, "before": before_path.name, "after": after_path.name,
        "target_dimension": target, "counts": outcome.counts(b, a),
        "finding_diff": {"fixed": len(outcome.fixed_findings), "persisted": len(outcome.persisted_findings),
                         "worsened": len(outcome.worsened_findings), "new": len(outcome.new_findings)},
        "decision": outcome.decision, "reason": outcome.reason,
    })
    return {
        "iteration": iteration, "attempts_at_layer": attempts,
        "decision": outcome.decision, "reason": outcome.reason,
        "target_before": outcome.target_before, "target_after": outcome.target_after, "logged": True,
    }


def promote(project: str, scene_id: str, candidate_file: str, confirm: bool = False) -> dict:
    """Promote a candidate into manuscript + canon. State-changing, so it is gated on ``confirm``."""
    if not confirm:
        return {"error": "promotion changes canon and the manuscript; call again with confirm=true to proceed"}
    try:
        return promote_candidate(project_dir(project), scene_id, candidate_file)
    except ValueError as exc:
        return {"error": str(exc)}


def tournament(project: str, scene_id: str, seed: int = 0, persist: bool = False,
               judges: list | None = None, judge_rankings: list | None = None) -> dict:
    """Blind, Pareto-scored selection over a scene's candidates from their committed critiques.

    Reads ``scenes/<scene_id>/critiques/*.json`` and returns blinded labels, presentation orders
    (forward + reversed), per-candidate multidimensional scores, the non-dominated (Pareto) set,
    per-dimension winners, whether the judges disagree, and a recommendation. The code owns
    anonymization/ordering/selection so blind A/B is guaranteed, not merely requested. With
    ``persist=true`` it writes blinded candidate copies (``.runs/.../blind/<label>.md`` — the only
    thing a judge should see) and the full record to ``.runs/`` so the evidence is preserved.
    """
    proj = project_dir(project)
    scene_dir = proj / "scenes" / scene_id
    crit_dir = scene_dir / "critiques"
    critiques: list[dict] = []
    if crit_dir.exists():
        for path in sorted(crit_dir.glob("*.json")):
            try:
                critiques.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
    record = run_tournament(critiques, seed=seed, judges=judges, judge_rankings=judge_rankings)
    if persist and record.get("candidates"):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = proj / ".runs" / "tournament" / scene_id / stamp
        blind = run_dir / "blind"
        blind.mkdir(parents=True, exist_ok=True)
        for candidate_id, label in record["blind_labels"].items():
            src = scene_dir / "candidates" / candidate_id
            if src.exists():
                (blind / f"{label}.md").write_bytes(src.read_bytes())
        (run_dir / "record.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
        record["persisted_to"] = str(run_dir.relative_to(proj))
    return record


def assemble(project: str) -> dict:
    """Stitch the accepted scenes into one manuscript.md and return its path + word count."""
    return _assemble(project_dir(project))


# --- registry ---------------------------------------------------------------

def _tool(name: str, description: str, properties: dict, required: list[str], handler: Callable) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "properties": properties, "required": required},
        "handler": handler,
    }


TOOLS: list[dict] = [
    _tool("kb_search",
          "Search the craft knowledge base for relevant concept cards (focalization, scene "
          "dramaturgy, defaultness, dramatic structure, etc.). Returns card summaries; use kb_get "
          "for full text. Call this before drafting or diagnosing to pull the right craft into context.",
          {"query": {"type": "string"}, "layer": {"type": "string", "enum": ["narratology", "craft", "style"]}},
          [], kb_search),
    _tool("kb_get",
          "Fetch the full text of one craft concept card by id (e.g. 'scene-dramaturgy').",
          {"concept_id": {"type": "string"}}, ["concept_id"], kb_get),
    _tool("kb_sources",
          "List registered craft/reference sources (optionally by stream: craft-instruction, "
          "fiction-corpus, reference), with copyright/EU notes.",
          {"stream": {"type": "string"}}, [], kb_sources),
    _tool("state_before",
          "Reconstruct the event-sourced story state immediately BEFORE a scene: facts, "
          "per-character knowledge, relationships, open promises, time. Use this so you never "
          "write a character knowing something they haven't learned yet.",
          {"project": {"type": "string"}, "scene_id": {"type": "string"}}, ["project", "scene_id"], state_before),
    _tool("compile_context",
          "Assemble the minimal, leak-free drafting bundle for a scene (spec, participating "
          "characters, state_before, relevant world rules, discourse + style constraints).",
          {"project": {"type": "string"}, "scene_id": {"type": "string"}}, ["project", "scene_id"], compile_context),
    _tool("hard_audit",
          "Run the deterministic hard audit (Audit 1). With scene_id: audit one scene (knowledge "
          "cutoff, causal refs, POV). Without: audit canon + accepted scenes (chronology, promise "
          "ledger). Returns critique.schema findings with evidence.",
          {"project": {"type": "string"}, "scene_id": {"type": "string"}}, ["project"], audit),
    _tool("defaultness_lint",
          "Lint prose for model-default tics (clichés, told emotion, filter words, weak-word "
          "density, adverb tags, opener runs). Provide 'text' or a file 'path'. A hit is evidence "
          "to inspect, not proof — the fix may belong to a lower layer.",
          {"text": {"type": "string"}, "path": {"type": "string"}}, [], defaultness_lint),
    _tool("evaluate_revision",
          "Decide whether a revision should be accepted (stateless). Give the prior and revised "
          "versions' findings (arrays of critique objects) and the target dimension. Pass iteration "
          "/ attempts_at_current_layer to reach the ESCALATE_LAYER and STOP_NO_PROGRESS decisions.",
          {"before_findings": {"type": "array"}, "after_findings": {"type": "array"}, "target": {"type": "string"},
           "iteration": {"type": "integer"}, "attempts_at_current_layer": {"type": "integer"},
           "max_iterations": {"type": "integer"}, "max_attempts_per_layer": {"type": "integer"}},
          ["before_findings", "after_findings"], evaluate_revision),
    _tool("record_revision",
          "Run one revision iteration for a scene: lint the before/after candidates, derive iteration "
          "and attempts from the scene's revision-log, decide, and append the log. Use this (not the "
          "stateless evaluate_revision) to drive the loop with real history — it can ESCALATE/STOP and "
          "leaves a durable trace.",
          {"project": {"type": "string"}, "scene_id": {"type": "string"},
           "before": {"type": "string"}, "after": {"type": "string"}, "target": {"type": "string"}},
          ["project", "scene_id", "before", "after"], record_revision),
    _tool("promote",
          "Promote a reviewed candidate into the manuscript and fold its state delta into canon. "
          "STATE-CHANGING and gated: requires confirm=true, a spec, a schema-valid matching "
          "state-delta.json, and a passing triple audit — clean hard, literary, and defaultness "
          "critiques that each judge THIS candidate (a non-pass verdict or material finding blocks).",
          {"project": {"type": "string"}, "scene_id": {"type": "string"},
           "candidate_file": {"type": "string"}, "confirm": {"type": "boolean"}},
          ["project", "scene_id", "candidate_file"], promote),
    _tool("tournament",
          "Run a blind, Pareto-scored tournament over a scene's candidates from their critiques. "
          "Returns blinded labels + reveal map, forward/reversed presentation orders, per-candidate "
          "multidimensional scores, the non-dominated (Pareto) set, per-dimension winners, a "
          "disagreement flag, and a recommendation (select when one candidate dominates, else "
          "human_decision_required). Optional judges[] add an isolation ledger and judge_rankings[] "
          "(each judge's ranked candidate ids) fold into disagreement. persist=true writes blinded "
          "copies + the record to .runs/. Do NOT show the reveal_map to judge agents.",
          {"project": {"type": "string"}, "scene_id": {"type": "string"}, "seed": {"type": "integer"},
           "persist": {"type": "boolean"}, "judges": {"type": "array"}, "judge_rankings": {"type": "array"}},
          ["project", "scene_id"], tournament),
    _tool("assemble",
          "Stitch the accepted (promoted) scenes into a single manuscript.md, in fabula order, "
          "with title and chapter/scene breaks. Returns the path and word count.",
          {"project": {"type": "string"}}, ["project"], assemble),
]

_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOLS}


def list_tools() -> list[dict]:
    """Tool descriptors without the handler (MCP tools/list shape)."""
    return [{k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict:
    tool = _BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}"}
    args = dict(arguments or {})
    # MCP boundary: confine agent-supplied paths to approved roots before dispatch. In-process
    # callers (tests, CLI) call the handlers directly and are trusted; only the wire goes here.
    try:
        if isinstance(args.get("project"), str):
            confine_project(args["project"])
        if isinstance(args.get("path"), str):
            confine_file(args["path"])
    except ValueError as exc:
        return {"error": str(exc)}
    return tool["handler"](**args)
