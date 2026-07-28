"""Event-sourced story state reconstruction.

The canonical story state at any point is ``initial canon + accepted state deltas``
(see ``docs/architecture.md``). Nothing keeps a single mutable "current world"; we
replay it. This module is the keystone the hard audits and the context compiler build
on: it answers "what is true, and who knows what, *before* scene X" — deterministically,
and without letting a fact a later scene introduces leak backward.

Fabula ordering
---------------
Scene ids are zero-padded ``chNN-scNN`` and sort lexicographically into reading order,
which for a linear story equals fabula (chronological) order. v1 uses id order as fabula
order. Non-linear timelines (flashbacks) must carry an explicit ``time`` in each delta;
the chronology audit consumes that. This limit is recorded in ADR 0001.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# A scene id like "ch03-sc02" -> sort key (3, 2). Anything malformed sorts last.
def scene_sort_key(scene_id: str) -> tuple[int, int]:
    try:
        chapter, scene = scene_id.split("-")
        return (int(chapter[2:]), int(scene[2:]))
    except (ValueError, IndexError):
        return (10**9, 10**9)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _pair_key(pair: Iterable[str]) -> frozenset[str]:
    return frozenset(pair)


@dataclass
class StoryState:
    """Immutable snapshot of story state at one point in the fabula."""

    time: Any = None
    facts: dict[str, str] = field(default_factory=dict)  # fact id -> text
    knowledge: dict[str, set[str]] = field(default_factory=dict)  # char id -> {fact id}
    relationships: dict[frozenset[str], str] = field(default_factory=dict)
    open_promises: dict[str, str] = field(default_factory=dict)  # promise id -> text
    closed_promises: set[str] = field(default_factory=set)
    applied_scenes: list[str] = field(default_factory=list)

    def fact_exists(self, fact_id: str) -> bool:
        return fact_id in self.facts

    def knows(self, character: str, fact_id: str) -> bool:
        return fact_id in self.knowledge.get(character, set())

    def relationship(self, a: str, b: str) -> str | None:
        return self.relationships.get(_pair_key((a, b)))

    def promise_is_open(self, promise_id: str) -> bool:
        return promise_id in self.open_promises


def _apply_delta(state: StoryState, delta: dict) -> None:
    for fact in delta.get("facts_added", []):
        state.facts[fact["id"]] = fact["text"]
    for fact_id in delta.get("facts_removed", []):
        state.facts.pop(fact_id, None)
    for change in delta.get("knowledge_changes", []):
        state.knowledge.setdefault(change["character"], set()).add(change["fact"])
    for change in delta.get("relationship_changes", []):
        state.relationships[_pair_key(change["pair"])] = change["state"]
    for promise in delta.get("promises_opened", []):
        state.open_promises[promise["id"]] = promise["text"]
    for promise_id in delta.get("promises_closed", []):
        state.open_promises.pop(promise_id, None)
        state.closed_promises.add(promise_id)
    if delta.get("time") is not None:
        state.time = delta["time"]


def seed_state(project: Path) -> StoryState:
    """Story state at t0 — the initial canon, before any scene has run."""
    canon = project / "canon"
    state = StoryState()
    for fact in _read_jsonl(canon / "facts.jsonl"):
        state.facts[fact["id"]] = fact["text"]
    for record in _read_jsonl(canon / "knowledge-state.jsonl"):
        state.knowledge.setdefault(record["character"], set()).add(record["fact"])
    for record in _read_jsonl(canon / "relationship-state.jsonl"):
        state.relationships[_pair_key(record["pair"])] = record["state"]
    for record in _read_jsonl(canon / "promises.jsonl"):
        state.open_promises[record["id"]] = record["text"]
    timeline = _read_jsonl(canon / "timeline.jsonl")
    if timeline:
        # The last seed record defines the story's opening time.
        state.time = timeline[-1].get("time")
    return state


def accepted_scene_ids(project: Path) -> list[str]:
    """Accepted (promoted) scene ids in fabula order."""
    index = _read_json(project / "canon" / "index.json", {})
    ids = list(index.get("accepted_state_deltas", []))
    return sorted(ids, key=scene_sort_key)


def _load_delta(project: Path, scene_id: str) -> dict | None:
    path = project / "scenes" / scene_id / "state-delta.json"
    return _read_json(path, None) if path.exists() else None


def reconstruct(project: Path, upto_scene: str | None = None, *, inclusive: bool = False) -> StoryState:
    """Reconstruct story state by replaying seed canon + accepted deltas.

    Applies every accepted delta whose scene id sorts before ``upto_scene`` (or
    ``<=`` when ``inclusive``). With ``upto_scene=None`` the full accepted history is
    applied. Missing delta files are skipped (an accepted scene should always have one;
    that invariant is enforced by ``validate_workspace``).
    """
    state = seed_state(project)
    target_key = scene_sort_key(upto_scene) if upto_scene is not None else None
    for scene_id in accepted_scene_ids(project):
        if target_key is not None:
            key = scene_sort_key(scene_id)
            if inclusive and key > target_key:
                continue
            if not inclusive and key >= target_key:
                continue
        delta = _load_delta(project, scene_id)
        if delta is not None:
            _apply_delta(state, delta)
            state.applied_scenes.append(scene_id)
    return state


def reconstruct_state_before(project: Path, scene_id: str) -> StoryState:
    """State as it stands immediately before ``scene_id`` (the brief's primitive)."""
    return reconstruct(project, upto_scene=scene_id, inclusive=False)
