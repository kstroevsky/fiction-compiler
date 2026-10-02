"""Conservative state dependencies for accepted scenes.

The dependency ledger models declared facts/epistemic state, typed predicates, resources, and
promises. It is useful for finding *known* downstream dependents after an earlier accepted scene
changes, but it is not a claim that literary dependencies are complete. Callers must still conservatively recheck downstream
reader, voice, and whole-work effects after backward revision.
"""
from __future__ import annotations

import json
from typing import Any


def read_set_from_context(bundle: dict) -> dict:
    """Return the conservative state read set represented by a compiled scene context."""
    before = bundle.get("state_before", {}) if isinstance(bundle, dict) else {}
    facts = before.get("facts", {}) if isinstance(before, dict) else {}
    memory = before.get("participant_memory", {}) if isinstance(before, dict) else {}
    beliefs = before.get("participant_beliefs", {}) if isinstance(before, dict) else {}
    relationships = before.get("relationships", []) if isinstance(before, dict) else []
    predicates = before.get("predicates", []) if isinstance(before, dict) else []
    resources = before.get("resources", []) if isinstance(before, dict) else []
    promises = before.get("open_promises", {}) if isinstance(before, dict) else {}
    epistemic_facts = {
        str(fact_id)
        for values in memory.values() if isinstance(values, list)
        for fact_id in values if fact_id
    } | {
        str(item.get("fact"))
        for values in beliefs.values() if isinstance(values, list)
        for item in values if isinstance(item, dict) and item.get("fact")
    }
    return {
        "mode": "conservative_context",
        "facts": sorted({str(fact_id) for fact_id in facts if fact_id} | epistemic_facts),
        "predicates": sorted(
            [
                {
                    "predicate": str(item.get("predicate")),
                    "subject": str(item.get("subject")),
                    "object": None if item.get("object") is None else str(item.get("object")),
                }
                for item in predicates
                if isinstance(item, dict)
                and item.get("predicate") is not None
                and item.get("subject") is not None
            ],
            key=lambda item: (item["predicate"], item["subject"], item["object"] or ""),
        ),
        "relationships": sorted(
            [
                {"subject": str(item.get("subject")), "object": str(item.get("object")),
                 "dimension": str(dimension)}
                for item in relationships if isinstance(item, dict)
                and item.get("subject") is not None and item.get("object") is not None
                for dimension in (item.get("dimensions") or {})
            ],
            key=lambda item: (item["subject"], item["object"], item["dimension"]),
        ),
        "resources": sorted({
            str(item.get("resource")) for item in resources
            if isinstance(item, dict) and item.get("resource")
        }),
        "promises": sorted(str(promise_id) for promise_id in promises if promise_id),
    }


def _records_by_id(delta: dict, collection: str, id_key: str = "id") -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    for item in delta.get(collection, []):
        if not isinstance(item, dict) or item.get(id_key) is None:
            continue
        key = str(item[id_key])
        records.setdefault(key, []).append(json.dumps(item, sort_keys=True, ensure_ascii=False))
    return {key: sorted(values) for key, values in records.items()}


def _fact_effects(delta: dict) -> dict[str, list[str]]:
    records = _records_by_id(delta, "facts_added")
    for fact_id, values in _records_by_id(delta, "propositions_defined").items():
        records.setdefault(fact_id, []).extend("define:" + value for value in values)
    for fact_id in delta.get("facts_removed", []):
        if fact_id is not None:
            records.setdefault(str(fact_id), []).append("remove")
    for collection, prefix in (("knowledge_changes", "knowledge"), ("belief_changes", "belief")):
        for item in delta.get(collection, []):
            if isinstance(item, dict) and item.get("fact") is not None:
                fact_id = str(item["fact"])
                records.setdefault(fact_id, []).append(
                    prefix + ":" + json.dumps(item, sort_keys=True, ensure_ascii=False)
                )
    return {key: sorted(values) for key, values in records.items()}


def _promise_effects(delta: dict) -> dict[str, list[str]]:
    records = _records_by_id(delta, "promises_opened")
    for promise_id in delta.get("promises_closed", []):
        if promise_id is not None:
            records.setdefault(str(promise_id), []).append("close")
    return {key: sorted(values) for key, values in records.items()}


def _predicate_effects(delta: dict) -> dict[tuple[str, str, str | None], list[str]]:
    records: dict[tuple[str, str, str | None], list[str]] = {}
    for item in delta.get("predicate_changes", []):
        if not isinstance(item, dict):
            continue
        if item.get("predicate") is None or item.get("subject") is None:
            continue
        key = (
            str(item["predicate"]), str(item["subject"]),
            None if item.get("object") is None else str(item.get("object")),
        )
        records.setdefault(key, []).append(json.dumps(item, sort_keys=True, ensure_ascii=False))
    return {key: sorted(values) for key, values in records.items()}


def _relationship_effects(delta: dict) -> dict[tuple[str, str, str], list[str]]:
    records: dict[tuple[str, str, str], list[str]] = {}
    for item in delta.get("relationship_edges", []):
        if not isinstance(item, dict) or any(item.get(key) is None for key in ("subject", "object", "dimension")):
            continue
        key = (str(item["subject"]), str(item["object"]), str(item["dimension"]))
        records.setdefault(key, []).append(json.dumps(item, sort_keys=True, ensure_ascii=False))
    for item in delta.get("relationship_changes", []):
        if not isinstance(item, dict) or not isinstance(item.get("pair"), list) or len(item["pair"]) != 2:
            continue
        left, right = map(str, item["pair"])
        rendered = json.dumps(item, sort_keys=True, ensure_ascii=False)
        records.setdefault((left, right, "state"), []).append(rendered)
        records.setdefault((right, left, "state"), []).append(rendered)
    return {key: sorted(values) for key, values in records.items()}


def _resource_effects(delta: dict) -> dict[str, list[str]]:
    records: dict[str, list[str]] = {}
    for item in delta.get("resource_changes", []):
        if not isinstance(item, dict) or item.get("resource") is None:
            continue
        key = str(item["resource"])
        records.setdefault(key, []).append(json.dumps(item, sort_keys=True, ensure_ascii=False))
    return {key: sorted(values) for key, values in records.items()}


def _changed_keys(before: dict[Any, list[str]], after: dict[Any, list[str]]) -> set[Any]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def changed_state_refs(before_delta: dict, after_delta: dict) -> dict:
    """Return state identities whose declared effects changed between two scene deltas."""
    facts = sorted(_changed_keys(_fact_effects(before_delta), _fact_effects(after_delta)))
    promises = sorted(_changed_keys(_promise_effects(before_delta), _promise_effects(after_delta)))
    resources = sorted(_changed_keys(_resource_effects(before_delta), _resource_effects(after_delta)))
    predicates = sorted(
        _changed_keys(_predicate_effects(before_delta), _predicate_effects(after_delta))
    )
    relationships = sorted(
        _changed_keys(_relationship_effects(before_delta), _relationship_effects(after_delta))
    )
    return {
        "facts": facts,
        "predicates": [
            {"predicate": predicate, "subject": subject, "object": obj}
            for predicate, subject, obj in predicates
        ],
        "relationships": [
            {"subject": subject, "object": obj, "dimension": dimension}
            for subject, obj, dimension in relationships
        ],
        "resources": resources,
        "promises": promises,
    }


def dependency_match(read_set: dict | None, changed: dict) -> bool | None:
    """True for a known state dependency, False for a known miss, None when no read set exists."""
    if not isinstance(read_set, dict):
        return None
    if set(map(str, read_set.get("facts", []))) & set(map(str, changed.get("facts", []))):
        return True
    if set(map(str, read_set.get("resources", []))) & set(map(str, changed.get("resources", []))):
        return True
    if set(map(str, read_set.get("promises", []))) & set(map(str, changed.get("promises", []))):
        return True
    reads = {
        (str(item.get("predicate")), str(item.get("subject")),
         None if item.get("object") is None else str(item.get("object")))
        for item in read_set.get("predicates", [])
        if isinstance(item, dict)
    }
    changed_predicates = {
        (str(item.get("predicate")), str(item.get("subject")),
         None if item.get("object") is None else str(item.get("object")))
        for item in changed.get("predicates", [])
        if isinstance(item, dict)
    }
    if reads & changed_predicates:
        return True
    relationship_reads = {
        (str(item.get("subject")), str(item.get("object")), str(item.get("dimension")))
        for item in read_set.get("relationships", []) if isinstance(item, dict)
    }
    relationship_changes = {
        (str(item.get("subject")), str(item.get("object")), str(item.get("dimension")))
        for item in changed.get("relationships", []) if isinstance(item, dict)
    }
    return bool(relationship_reads & relationship_changes)
