"""Event-sourced story state reconstruction.

The canonical story state at any point is ``initial canon + accepted state deltas``
(see ``docs/architecture.md``). Nothing keeps a single mutable "current world"; we
replay it. This module is the keystone the hard audits and the context compiler build
on: it answers "what is true, and who knows what, *before* scene X" — deterministically,
and without letting a fact a later scene introduces leak backward.

Discourse vs fabula
-------------------
Three identifiers are distinct: the **scene id** is repository identity and discourse (reading)
order; a state delta's **time** is its canonical fabula time; and a scene spec's **fabula_time** is
the planning-time timestamp used before the delta is accepted. ``narrative_mode`` marks deliberate
analepsis/prolepsis. When comparable timestamps are available, state replay follows fabula order so
a flashback sees historical truth rather than later-in-story state. Discourse order remains the
deterministic fallback for legacy artifacts whose time is absent or not comparable; that fallback is
reported through ``reconstruction_issues`` rather than being silently presented as historical proof.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import acceptance
from .ontology import typed_equal


# A scene id like "ch03-sc02" -> sort key (3, 2). Anything malformed sorts last.
def scene_sort_key(scene_id: str) -> tuple[int, int]:
    try:
        chapter, scene = scene_id.split("-")
        return (int(chapter[2:]), int(scene[2:]))
    except (ValueError, IndexError):
        return (10**9, 10**9)


def normalize_fabula_time(value: Any) -> tuple[str, Any] | None:
    """Normalize supported fabula timestamps without conflating numeric and datetime domains."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return ("number", float(value))
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return ("datetime-naive", parsed)
    return ("datetime-aware", parsed.astimezone(timezone.utc).timestamp())


def compare_fabula_time(left: Any, right: Any) -> int | None:
    """Compare supported fabula times; return None when their domains are incomparable."""
    a, b = normalize_fabula_time(left), normalize_fabula_time(right)
    if a is None or b is None or a[0] != b[0]:
        return None
    return (a[1] > b[1]) - (a[1] < b[1])


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
ResourceKey = tuple[str, str]
_MISSING = object()


def _compare_value(actual: Any, expected: Any, comparison: str) -> bool:
    if comparison == "eq":
        return typed_equal(actual, expected)
    if comparison == "ne":
        return not typed_equal(actual, expected)
    if (isinstance(actual, (int, float)) and not isinstance(actual, bool)
            and isinstance(expected, (int, float)) and not isinstance(expected, bool)):
        if comparison == "lt":
            return actual < expected
        if comparison == "lte":
            return actual <= expected
        if comparison == "gt":
            return actual > expected
        if comparison == "gte":
            return actual >= expected
    return False


@dataclass
class StoryState:
    """Reconstructed story state at one point in the fabula/discourse history."""

    time: Any = None
    facts: dict[str, str] = field(default_factory=dict)  # currently true proposition id -> text
    # Stable proposition identity survives truth changes, so an id cannot silently acquire new text.
    fact_definitions: dict[str, str] = field(default_factory=dict)
    # Epistemic state is split from world truth. Memory survives world changes; belief may be wrong.
    memory: dict[str, set[str]] = field(default_factory=dict)
    beliefs: dict[str, dict[str, bool]] = field(default_factory=dict)
    belief_sources: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # Directional: (subject, object) -> {dimension: value}. A legacy symmetric relationship is
    # stored in BOTH directions under the "state" dimension (see _apply_relationship_record).
    relationships: dict[RelKey, dict[str, Any]] = field(default_factory=dict)
    # Typed world/spatial/object predicates: (predicate, subject, object) -> value (default True).
    predicates: dict[PredKey, Any] = field(default_factory=dict)
    # Only declared load-bearing quantities live here. Keys are (resource, holder/location).
    resources: dict[ResourceKey, float | int] = field(default_factory=dict)
    resource_units: dict[str, str] = field(default_factory=dict)
    open_promises: dict[str, str] = field(default_factory=dict)  # promise id -> text
    # Full promise declarations survive closure so audits can retain trigger/payoff semantics while
    # ``open_promises`` stays backward-compatible as id -> display text.
    promise_definitions: dict[str, dict[str, Any]] = field(default_factory=dict)
    closed_promises: set[str] = field(default_factory=set)
    applied_scenes: list[str] = field(default_factory=list)
    reconstruction_order: str = "seed"
    reconstruction_issues: list[str] = field(default_factory=list)

    def fact_exists(self, fact_id: str) -> bool:
        return fact_id in self.facts

    @property
    def knowledge(self) -> dict[str, set[str]]:
        """Backward-compatible view of *current factive* knowledge.

        A proposition can stay remembered and believed after the world changes, but it is no
        longer knowledge once it is not currently true. Use ``remembers`` / ``believes`` when
        historical or possibly mistaken epistemic state is the intended query.
        """
        characters = set(self.memory) | set(self.beliefs)
        return {
            character: {
                fact_id
                for fact_id, stance in self.beliefs.get(character, {}).items()
                if stance is True and fact_id in self.facts
            }
            for character in characters
        }

    def remembers(self, character: str, fact_id: str) -> bool:
        return fact_id in self.memory.get(character, set())

    def belief(self, character: str, fact_id: str) -> bool | None:
        return self.beliefs.get(character, {}).get(fact_id)

    def believes(self, character: str, fact_id: str, value: bool = True) -> bool:
        return self.belief(character, fact_id) is value

    def knows(self, character: str, fact_id: str) -> bool:
        return self.fact_exists(fact_id) and self.believes(character, fact_id, True)

    def resource_quantity(self, resource: str, holder: str) -> float | int:
        return self.resources.get((resource, holder), 0)

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

    def holds(self, predicate: str, subject: str, object: str | None = None, *,
              value: Any = _MISSING, comparison: str = "eq") -> bool:
        """Whether a typed atom holds — the query event preconditions are evaluated against.

        ``knows`` is current factive knowledge, ``believes`` may be mistaken, and ``remembers``
        records retained proposition memory. Relationship verbs consult directional dimensions;
        everything else consults the typed predicate store. When ``value`` is supplied, comparison is
        explicit and type-aware (so boolean false is not numeric zero). Ordered comparisons are only
        defined for numbers. Omitting ``value`` preserves the legacy truthiness/presence query.
        """
        if value is _MISSING and comparison != "eq":
            return False
        if predicate == "knows":
            actual = object is not None and self.knows(subject, object)
            return actual if value is _MISSING else _compare_value(actual, value, comparison)
        if predicate == "remembers":
            actual = object is not None and self.remembers(subject, object)
            return actual if value is _MISSING else _compare_value(actual, value, comparison)
        if predicate == "believes":
            if object is None:
                return False
            actual = self.belief(subject, object)
            if actual is None:
                return False
            return bool(actual) if value is _MISSING else _compare_value(actual, value, comparison)
        if (predicate, subject, object) in self.predicates:
            actual = self.predicates[(predicate, subject, object)]
            return bool(actual) if value is _MISSING else _compare_value(actual, value, comparison)
        if object is not None:
            dims = self.relationships.get((subject, object))
            if dims is not None and predicate in dims:
                actual = dims[predicate]
                return bool(actual) if value is _MISSING else _compare_value(actual, value, comparison)
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


def _define_proposition(state: StoryState, proposition: dict) -> bool:
    """Define a stable proposition without asserting that it is currently true."""
    fact_id, text = proposition["id"], proposition["text"]
    previous = state.fact_definitions.get(fact_id)
    if previous is not None and previous != text:
        return False
    state.fact_definitions.setdefault(fact_id, text)
    return True


def _apply_fact_record(state: StoryState, fact: dict) -> bool:
    """Define/establish one fact without allowing its id to acquire a new meaning.

    Returns ``False`` for a conflicting redefinition. Replay preserves the original proposition;
    hard-audit reports the conflict as a material integrity error.
    """
    if not _define_proposition(state, fact):
        return False
    state.facts[fact["id"]] = fact["text"]
    return True


def _set_belief(state: StoryState, change: dict, *, legacy: bool = False) -> None:
    character, fact_id = change["character"], change["fact"]
    op = change.get("op", "add" if legacy else "set")
    if op in ("remove", "forget"):
        state.memory.setdefault(character, set()).discard(fact_id)
        state.beliefs.setdefault(character, {}).pop(fact_id, None)
        state.belief_sources.setdefault(character, {}).pop(fact_id, None)
        return

    value = True if legacy else bool(change.get("value", True))
    state.memory.setdefault(character, set()).add(fact_id)
    state.beliefs.setdefault(character, {})[fact_id] = value
    metadata = {
        key: change[key]
        for key in ("source", "event")
        if change.get(key) is not None
    }
    if legacy:
        metadata.setdefault("source", "legacy_knowledge")
    state.belief_sources.setdefault(character, {})[fact_id] = metadata


def _apply_resource_seed(state: StoryState, record: dict) -> None:
    resource, holder = record["id"], record["holder"]
    unit = record.get("unit")
    if unit:
        state.resource_units.setdefault(resource, unit)
    state.resources[(resource, holder)] = record["quantity"]


def apply_resource_change(state: StoryState, change: dict) -> str | None:
    """Apply one quantity operation, returning a semantic error without partial mutation."""
    resource = change.get("resource")
    quantity = change.get("quantity")
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool) or quantity <= 0:
        return f"resource {resource!r} quantity must be a positive number"

    unit = change.get("unit")
    known_unit = state.resource_units.get(resource)
    if unit and known_unit and unit != known_unit:
        return f"resource {resource!r} uses unit {unit!r}, expected {known_unit!r}"
    if unit and not known_unit:
        state.resource_units[resource] = unit

    op = change.get("op")
    if op == "acquire":
        holder = change.get("holder")
        key = (resource, holder)
        state.resources[key] = state.resources.get(key, 0) + quantity
        return None
    if op == "consume":
        holder = change.get("holder")
        key = (resource, holder)
        available = state.resources.get(key, 0)
        if available < quantity:
            return f"resource {resource!r} at {holder!r} underflows: {available} < {quantity}"
        state.resources[key] = available - quantity
        return None
    if op == "transfer":
        source, destination = change.get("from"), change.get("to")
        source_key, destination_key = (resource, source), (resource, destination)
        available = state.resources.get(source_key, 0)
        if available < quantity:
            return f"resource {resource!r} at {source!r} underflows: {available} < {quantity}"
        state.resources[source_key] = available - quantity
        state.resources[destination_key] = state.resources.get(destination_key, 0) + quantity
        return None
    return f"unknown resource operation {op!r}"


def resource_change_errors(state: StoryState, changes: list[dict]) -> list[str]:
    """Validate ordered resource operations against a copy of the supplied state."""
    working = deepcopy(state)
    errors: list[str] = []
    for index, change in enumerate(changes):
        error = apply_resource_change(working, change)
        if error:
            errors.append(f"resource_changes[{index}]: {error}")
    return errors


def _apply_delta(state: StoryState, delta: dict) -> None:
    for proposition in delta.get("propositions_defined", []):
        _define_proposition(state, proposition)
    for fact in delta.get("facts_added", []):
        _apply_fact_record(state, fact)
    for fact_id in delta.get("facts_removed", []):
        state.facts.pop(fact_id, None)
    for change in delta.get("knowledge_changes", []):
        _set_belief(state, change, legacy=True)
    for change in delta.get("belief_changes", []):
        _set_belief(state, change)
    for change in delta.get("relationship_changes", []):  # legacy symmetric {pair, state}
        _apply_relationship_record(state, change)
    for edge in delta.get("relationship_edges", []):  # directional {subject, object, dimension}
        _apply_relationship_record(state, edge)
    for predicate in delta.get("predicate_changes", []):  # typed world/spatial/object atoms
        _apply_predicate_record(state, predicate)
    for change in delta.get("resource_changes", []):
        apply_resource_change(state, change)
    for promise in delta.get("promises_opened", []):
        state.open_promises[promise["id"]] = promise["text"]
        state.promise_definitions.setdefault(promise["id"], dict(promise))
    for promise_id in delta.get("promises_closed", []):
        state.open_promises.pop(promise_id, None)
        state.closed_promises.add(promise_id)
    if delta.get("time") is not None:
        state.time = delta["time"]


def seed_state(project: Path) -> StoryState:
    """Story state at t0 — the initial canon, before any scene has run."""
    canon = project / "canon"
    state = StoryState()
    for proposition in _read_jsonl(canon / "propositions.jsonl"):
        _define_proposition(state, proposition)
    for fact in _read_jsonl(canon / "facts.jsonl"):
        _apply_fact_record(state, fact)
    for record in _read_jsonl(canon / "knowledge-state.jsonl"):
        _set_belief(state, record, legacy=True)
    for record in _read_jsonl(canon / "belief-state.jsonl"):
        _set_belief(state, record)
    for record in _read_jsonl(canon / "relationship-state.jsonl"):  # legacy or directional
        _apply_relationship_record(state, record)
    for record in _read_jsonl(canon / "world-state.jsonl"):  # typed predicates (optional ledger)
        _apply_predicate_record(state, record)
    for record in _read_jsonl(canon / "resources.jsonl"):
        _apply_resource_seed(state, record)
    for record in _read_jsonl(canon / "promises.jsonl"):
        state.open_promises[record["id"]] = record["text"]
        state.promise_definitions.setdefault(record["id"], dict(record))
    timeline = _read_jsonl(canon / "timeline.jsonl")
    if timeline:
        # The last seed record defines the story's opening time.
        state.time = timeline[-1].get("time")
    return state


def accepted_scene_ids(project: Path) -> list[str]:
    """Accepted (promoted) scene ids in discourse/repository order."""
    index = _read_json(project / "canon" / "index.json", {})
    ids = list(index.get("accepted_state_deltas", []))
    return sorted(ids, key=scene_sort_key)


def _load_delta(project: Path, scene_id: str) -> dict | None:
    frozen = acceptance.load_scene_snapshot(project, scene_id)
    if frozen is not None:
        _, snapshot = frozen
        return acceptance.frozen_json(snapshot, "state_delta")
    path = project / "scenes" / scene_id / "state-delta.json"
    return _read_json(path, None) if path.exists() else None


def _load_spec(project: Path, scene_id: str) -> dict:
    frozen = acceptance.load_scene_snapshot(project, scene_id)
    if frozen is not None:
        _, snapshot = frozen
        return acceptance.frozen_json(snapshot, "spec")
    path = project / "scenes" / scene_id / "spec.json"
    return _read_json(path, {}) if path.exists() else {}


def scene_fabula_time(project: Path, scene_id: str, *, prefer_live: bool = False) -> Any:
    """Return a scene's fabula time, optionally preferring mutable planning/revision inputs.

    Accepted history normally reads from immutable snapshots. While planning or validating a
    revision, however, the target scene's live spec/delta is the proposed history and must determine
    which accepted scenes precede it.
    """
    delta_path = project / "scenes" / scene_id / "state-delta.json"
    spec_path = project / "scenes" / scene_id / "spec.json"
    delta = (
        _read_json(delta_path, None)
        if prefer_live and delta_path.exists()
        else _load_delta(project, scene_id)
    )
    if isinstance(delta, dict) and delta.get("time") is not None:
        return delta.get("time")
    spec = (
        _read_json(spec_path, {})
        if prefer_live and spec_path.exists()
        else _load_spec(project, scene_id)
    )
    return spec.get("fabula_time")


def fabula_order(project: Path, scene_ids: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Order scenes by comparable fabula time, with an explicit discourse-order fallback."""
    ids = list(scene_ids) if scene_ids is not None else accepted_scene_ids(project)
    if not ids:
        return [], []
    normalized: dict[str, tuple[str, Any]] = {}
    issues: list[str] = []
    for scene_id in ids:
        raw = scene_fabula_time(project, scene_id)
        value = normalize_fabula_time(raw)
        if value is None:
            issues.append(f"{scene_id} has no orderable fabula time ({raw!r})")
        else:
            normalized[scene_id] = value
    domains = {value[0] for value in normalized.values()}
    if len(domains) > 1:
        issues.append(f"scenes mix incomparable fabula time domains: {sorted(domains)}")
    if issues:
        return sorted(ids, key=scene_sort_key), issues
    return sorted(ids, key=lambda scene_id: (normalized[scene_id][1], scene_sort_key(scene_id))), []


def accepted_scene_ids_before(project: Path, scene_id: str) -> tuple[list[str], list[str]]:
    """Accepted scenes earlier in fabula than a target; equal times use discourse order."""
    ids = accepted_scene_ids(project)
    target_time = scene_fabula_time(project, scene_id, prefer_live=True)
    target_norm = normalize_fabula_time(target_time)
    if target_norm is None:
        target_key = scene_sort_key(scene_id)
        return [sid for sid in ids if scene_sort_key(sid) < target_key], []

    selected: list[str] = []
    issues: list[str] = []
    for accepted_id in ids:
        if accepted_id == scene_id:
            continue
        accepted_time = scene_fabula_time(project, accepted_id)
        comparison = compare_fabula_time(accepted_time, target_time)
        if comparison is None:
            issues.append(
                f"cannot compare {accepted_id} fabula time {accepted_time!r} with "
                f"{scene_id} fabula time {target_time!r}"
            )
            continue
        if comparison < 0 or (
            comparison == 0 and scene_sort_key(accepted_id) < scene_sort_key(scene_id)
        ):
            selected.append(accepted_id)
    if issues:
        target_key = scene_sort_key(scene_id)
        return [sid for sid in ids if scene_sort_key(sid) < target_key], issues
    ordered, order_issues = fabula_order(project, selected)
    return ordered, order_issues


def reconstruct(project: Path, upto_scene: str | None = None, *, inclusive: bool = False) -> StoryState:
    """Reconstruct seed canon + accepted deltas, preferring fabula order when time is known."""
    state = seed_state(project)
    if upto_scene is None:
        replay_ids, issues = fabula_order(project)
        order_issues = list(issues)
        if state.time is not None:
            for scene_id in replay_ids:
                scene_time = scene_fabula_time(project, scene_id)
                if scene_time is None:
                    continue
                seed_comparison = compare_fabula_time(scene_time, state.time)
                if seed_comparison is None:
                    issues.append(
                        f"cannot compare {scene_id} fabula time {scene_time!r} with "
                        f"seed canon time {state.time!r}"
                    )
                elif seed_comparison < 0:
                    issues.append(
                        f"{scene_id} fabula time {scene_time!r} precedes seed canon time {state.time!r}"
                    )
        state.reconstruction_order = "fabula" if not order_issues else "discourse_fallback"
        state.reconstruction_issues.extend(issues)
    else:
        replay_ids, issues = accepted_scene_ids_before(project, upto_scene)
        order_issues = list(issues)
        if inclusive and upto_scene in accepted_scene_ids(project):
            replay_ids = [*replay_ids, upto_scene]
            replay_ids, extra = fabula_order(project, replay_ids)
            issues.extend(extra)
            order_issues.extend(extra)
        target_time = scene_fabula_time(project, upto_scene, prefer_live=True)
        normalized_target = normalize_fabula_time(target_time)
        if state.time is not None and target_time is not None:
            seed_comparison = compare_fabula_time(target_time, state.time)
            if seed_comparison is None:
                issues.append(
                    f"cannot compare {upto_scene} fabula time {target_time!r} with "
                    f"seed canon time {state.time!r}"
                )
            elif seed_comparison < 0:
                issues.append(
                    f"{upto_scene} fabula time {target_time!r} precedes seed canon time {state.time!r}"
                )
        if normalized_target is None:
            state.reconstruction_order = "discourse"
        elif order_issues:
            state.reconstruction_order = "discourse_fallback"
        else:
            state.reconstruction_order = "fabula"
        state.reconstruction_issues.extend(issues)
    for scene_id in replay_ids:
        delta = _load_delta(project, scene_id)
        if delta is not None:
            _apply_delta(state, delta)
            state.applied_scenes.append(scene_id)
    return state


def reconstruct_state_before(project: Path, scene_id: str) -> StoryState:
    """State as it stands immediately before ``scene_id`` (the brief's primitive)."""
    return reconstruct(project, upto_scene=scene_id, inclusive=False)
