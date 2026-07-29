"""The tool surface the LLM author actually calls.

Thin, JSON-returning wrappers over the deterministic engine, plus a registry (name +
description + JSON-Schema + handler) that the MCP server exposes. These do not write fiction —
they hand the model reference (KB), continuity truth (state), guardrail findings (audits), and
a revision fitness signal, so the *model* can write and revise well.

Every handler returns a JSON-serialisable dict. Keep them pure and cheap.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import defaultness, hard_audit, kb, revision
from .context import compile_bundle
from .state import StoryState, accepted_scene_ids, reconstruct_state_before
from .workspace import project_dir


def _state_json(state: StoryState) -> dict:
    return {
        "time": state.time,
        "facts": state.facts,
        "knowledge": {c: sorted(v) for c, v in state.knowledge.items()},
        "relationships": [{"pair": sorted(p), "state": s} for p, s in state.relationships.items()],
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


def evaluate_revision(before_findings: list, after_findings: list, target: str | None = None) -> dict:
    outcome = revision.evaluate_revision(before_findings, after_findings, target_dimension=target)
    return {
        "decision": outcome.decision,
        "reason": outcome.reason,
        "target_dimension": outcome.target_dimension,
        "target_before": outcome.target_before,
        "target_after": outcome.target_after,
        "material_regressions": outcome.material_regressions,
        "fixed_dimensions": outcome.fixed_dimensions,
    }


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
          "Decide whether a revision should be accepted. Give the prior and revised versions' "
          "findings (arrays of critique objects) and the target dimension. Applies the contract's "
          "accept/regression/stop rules so revision converges instead of drifting to blandness.",
          {"before_findings": {"type": "array"}, "after_findings": {"type": "array"}, "target": {"type": "string"}},
          ["before_findings", "after_findings"], evaluate_revision),
]

_BY_NAME: dict[str, dict] = {t["name"]: t for t in TOOLS}


def list_tools() -> list[dict]:
    """Tool descriptors without the handler (MCP tools/list shape)."""
    return [{k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict:
    tool = _BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}"}
    return tool["handler"](**(arguments or {}))
