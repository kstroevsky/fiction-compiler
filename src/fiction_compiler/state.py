"""Event-sourced story state reconstruction.

The canonical story state at any point is ``initial canon + accepted state deltas``
(see ``docs/architecture.md``). Nothing keeps a single mutable "current world"; we
replay it. This module is the keystone the hard audits and the context compiler build
on: it answers "what is true, and who knows what, *before* scene X" — deterministically,
and without letting a fact a later scene introduces leak backward.

Discourse vs fabula
-------------------
Three identifiers are distinct (per the design review): the **scene id** is repository identity
*and* discourse (reading) order; each delta's **time** is fabula (event) time — when it happens in
the story; and a scene spec's **narrative_mode** (linear / analepsis / prolepsis) marks a deliberate
divergence between the two. Reconstruction still *replays* in scene-id (discourse) order; the
chronology audit checks fabula time along the linear thread only, so a flashback (analepsis) does not
read as "time running backward" (ADR 0006). Fabula-ordered state reconstruction — showing a flashback
only what was true at its earlier fabula time — remains a deferred refinement (see ADR 0001).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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


# A relationship key is an ORDERED (subject, object) pair; a predicate key is
# (predicate, subject, object) with object optional (None for unary state like offline(obj)).
RelKey = tuple[str, str]
PredKey = tuple[str, str, str | None]


@dataclass
class StoryState:
    """Immutable snapshot of story state at one point in the fabula."""

    time: Any = None
    facts: dict[str, str] = field(default_factory=dict)  # fact id -> text
    knowledge: dict[str, set[str]] = field(default_factory=dict)  # char id -> {fact id}
    # Directional: (subject, object) -> {dimension: value}. A legacy symmetric relationship is
    # stored in BOTH directions under the "state" dimension (see _apply_relationship_record).
    relationships: dict[RelKey, dict[str, Any]] = field(default_factory=dict)
    # Typed world/spatial/object predicates: (predicate, subject, object) -> value (default True).
    predicates: dict[PredKey, Any] = field(default_factory=dict)
    open_promises: dict[str, str] = field(default_factory=dict)  # promise id -> text
    closed_promises: set[str] = field(default_factory=set)
    applied_scenes: list[str] = field(default_factory=list)

    def fact_exists(self, fact_id: str) -> bool:
        return fact_id in self.facts

    def knows(self, character: str, fact_id: str) -> bool:
        return fact_id in self.knowledge.get(character, set())

    def relationship(self, a: str, b: str) -> str | None:
        """The descriptive 'state' of the a/b relationship, order-independent (back-compat)."""
        for key in ((a, b), (b, a)):
            dims = self.relationships.get(key)
            if dims and "state" in dims:
                return dims["state"]
        return None

    def relationship_directed(self, subject: str, object: str, dimension: str = "state") -> Any:
        """A directional relationship dimension (e.g. trusts/fears/owes) from subject to object."""
        return self.relationships.get((subject, object), {}).get(dimension)

    def holds(self, predicate: str, subject: str, object: str | None = None) -> bool:
        """Whether a typed atom holds — the query event preconditions are evaluated against.

        Bridges the existing stores: ``knows`` consults per-character knowledge, a relationship
        verb consults the directional relationship dimensions, and everything else consults the
        typed predicate store.
        """
        if predicate == "knows":
            return object is not None and self.knows(subject, object)
        if (predicate, subject, object) in self.predicates:
            return bool(self.predicates[(predicate, subject, object)])
        if object is not None:
            dims = self.relationships.get((subject, object))
            if dims is not None and predicate in dims:
                return bool(dims[predicate])
        return False

    def promise_is_open(self, promise_id: str) -> bool:
        return promise_id in self.open_promises


def _apply_relationship_record(state: StoryState, record: dict) -> None:
    """Apply one relationship record (legacy symmetric ``{pair, state}`` or directional edge)."""
    if "pair" in record:  # legacy symmetric descriptive relationship -> both directions
        a, b = record["pair"]
        state.relationships.setdefault((a, b), {})["state"] = record["state"]
        state.relationships.setdefault((b, a), {})["state"] = record["state"]
    else:  # directional: {subject, object, dimension, value?}
        key = (record["subject"], record["object"])
        state.relationships.setdefault(key, {})[record["dimension"]] = record.get("value", True)


def _apply_predicate_record(state: StoryState, record: dict) -> None:
    """Apply one typed predicate record. Seed records omit ``op`` (treated as add)."""
    key = (record["predicate"], record["subject"], record.get("object"))
    if record.get("op") == "remove":
        state.predicates.pop(key, None)
    else:
        state.predicates[key] = record.get("value", True)


def _apply_delta(state: StoryState, delta: dict) -> None:
    for fact in delta.get("facts_added", []):
        state.facts[fact["id"]] = fact["text"]
    for fact_id in delta.get("facts_removed", []):
        state.facts.pop(fact_id, None)
    for change in delta.get("knowledge_changes", []):
        state.knowledge.setdefault(change["character"], set()).add(change["fact"])
    for change in delta.get("relationship_changes", []):  # legacy symmetric {pair, state}
        _apply_relationship_record(state, change)
    for edge in delta.get("relationship_edges", []):  # directional {subject, object, dimension}
        _apply_relationship_record(state, edge)
    for predicate in delta.get("predicate_changes", []):  # typed world/spatial/object atoms
        _apply_predicate_record(state, predicate)
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
    for record in _read_jsonl(canon / "relationship-state.jsonl"):  # legacy or directional
        _apply_relationship_record(state, record)
    for record in _read_jsonl(canon / "world-state.jsonl"):  # typed predicates (optional ledger)
        _apply_predicate_record(state, record)
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
