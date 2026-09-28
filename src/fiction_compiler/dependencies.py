"""Conservative state dependencies for accepted scenes.

The dependency ledger deliberately models only facts, typed predicates, and promises.  It is useful
for finding *known* downstream dependents after an earlier accepted scene changes, but it is not a
claim that literary dependencies are complete.  Callers must still conservatively recheck downstream
reader, voice, and whole-work effects after backward revision.
"""
from __future__ import annotations

import json
from typing import Any


def read_set_from_context(bundle: dict) -> dict:
    """Return the conservative state read set represented by a compiled scene context."""
    before = bundle.get("state_before", {}) if isinstance(bundle, dict) else {}
    facts = before.get("facts", {}) if isinstance(before, dict) else {}
    predicates = before.get("predicates", []) if isinstance(before, dict) else []
    promises = before.get("open_promises", {}) if isinstance(before, dict) else {}
    return {
        "mode": "conservative_context",
        "facts": sorted(str(fact_id) for fact_id in facts if fact_id),
        "predicates": sorted(
            [
                {
                    "predicate": str(item.get("predicate")),
                    "subject": str(item.get("subject")),
                    "object": str(item.get("object")),
                }
                for item in predicates
                if isinstance(item, dict)
                and item.get("predicate") is not None
                and item.get("subject") is not None
                and item.get("object") is not None
            ],
            key=lambda item: (item["predicate"], item["subject"], item["object"]),
        ),
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
    for fact_id in delta.get("facts_removed", []):
        if fact_id is not None:
            records.setdefault(str(fact_id), []).append("remove")
    for item in delta.get("knowledge_changes", []):
        if isinstance(item, dict) and item.get("fact") is not None:
            fact_id = str(item["fact"])
            records.setdefault(fact_id, []).append(
                "knowledge:" + json.dumps(item, sort_keys=True, ensure_ascii=False)
            )
    return {key: sorted(values) for key, values in records.items()}


def _promise_effects(delta: dict) -> dict[str, list[str]]:
    records = _records_by_id(delta, "promises_opened")
    for promise_id in delta.get("promises_closed", []):
        if promise_id is not None:
            records.setdefault(str(promise_id), []).append("close")
    return {key: sorted(values) for key, values in records.items()}


def _predicate_effects(delta: dict) -> dict[tuple[str, str, str], list[str]]:
    records: dict[tuple[str, str, str], list[str]] = {}
    for item in delta.get("predicate_changes", []):
        if not isinstance(item, dict):
            continue
        parts = (item.get("predicate"), item.get("subject"), item.get("object"))
        if any(value is None for value in parts):
            continue
        key = tuple(str(value) for value in parts)
        records.setdefault(key, []).append(json.dumps(item, sort_keys=True, ensure_ascii=False))
    return {key: sorted(values) for key, values in records.items()}


def _changed_keys(before: dict[Any, list[str]], after: dict[Any, list[str]]) -> set[Any]:
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def changed_state_refs(before_delta: dict, after_delta: dict) -> dict:
    """Return state identities whose declared effects changed between two scene deltas."""
    facts = sorted(_changed_keys(_fact_effects(before_delta), _fact_effects(after_delta)))
    promises = sorted(_changed_keys(_promise_effects(before_delta), _promise_effects(after_delta)))
    predicates = sorted(
        _changed_keys(_predicate_effects(before_delta), _predicate_effects(after_delta))
    )
    return {
        "facts": facts,
        "predicates": [
            {"predicate": predicate, "subject": subject, "object": obj}
            for predicate, subject, obj in predicates
        ],
        "promises": promises,
    }


def dependency_match(read_set: dict | None, changed: dict) -> bool | None:
    """True for a known state dependency, False for a known miss, None when no read set exists."""
    if not isinstance(read_set, dict):
        return None
    if set(map(str, read_set.get("facts", []))) & set(map(str, changed.get("facts", []))):
        return True
    if set(map(str, read_set.get("promises", []))) & set(map(str, changed.get("promises", []))):
        return True
    reads = {
        (str(item.get("predicate")), str(item.get("subject")), str(item.get("object")))
        for item in read_set.get("predicates", [])
        if isinstance(item, dict)
    }
    changed_predicates = {
        (str(item.get("predicate")), str(item.get("subject")), str(item.get("object")))
        for item in changed.get("predicates", [])
        if isinstance(item, dict)
    }
    return bool(reads & changed_predicates)
