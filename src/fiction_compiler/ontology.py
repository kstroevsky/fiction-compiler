"""Declared predicate domains for the executable story IR.

Projects may opt into a predicate ontology (``canon/ontology.json``) and an entity registry
(``canon/entity-registry.json``). Predicate names/arity remain the base guarantee; value domains,
closed entity types, and exclusivity are enforced only when explicitly declared.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_MISSING = object()
_ORDERED_COMPARISONS = {"lt", "lte", "gt", "gte"}


def load_ontology(project: Path) -> dict | None:
    path = project / "canon" / "ontology.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_entity_registry(project: Path) -> dict | None:
    path = project / "canon" / "entity-registry.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def predicate_specs(ontology: dict) -> dict[str, dict]:
    """Accept the schema document or the legacy {name: spec} map used by callers/tests."""
    predicates = ontology.get("predicates") if isinstance(ontology, dict) else None
    if isinstance(predicates, list):
        return {p["name"]: p for p in predicates if isinstance(p, dict) and p.get("name")}
    return ontology


def _prefix(entity: str) -> str:
    return entity.split("-", 1)[0] if entity else ""


def typed_equal(left: Any, right: Any) -> bool:
    """Compare JSON-like values without Python's bool/int coercion."""
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if (isinstance(left, (int, float)) and not isinstance(left, bool)
            and isinstance(right, (int, float)) and not isinstance(right, bool)):
        return left == right
    return type(left) is type(right) and left == right


def _value_type_ok(value: Any, value_type: str) -> bool:
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "string":
        return isinstance(value, str)
    return True


def ontology_definition_errors(ontology: dict) -> list[str]:
    """Semantic errors JSON Schema cannot express (duplicates/domain compatibility)."""
    errors: list[str] = []
    raw = ontology.get("predicates", []) if isinstance(ontology, dict) else []
    if not isinstance(raw, list):
        return errors
    names = [p.get("name") for p in raw if isinstance(p, dict) and p.get("name")]
    for name in sorted({name for name in names if names.count(name) > 1}):
        errors.append(f"duplicate predicate declaration {name!r}")
    for spec in raw:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name", "<unnamed>")
        value_type = spec.get("value_type")
        allowed = spec.get("allowed_values")
        if isinstance(allowed, list) and value_type:
            for value in allowed:
                if not _value_type_ok(value, value_type):
                    errors.append(f"predicate {name!r} allowed value {value!r} is not {value_type}")
        minimum, maximum = spec.get("minimum"), spec.get("maximum")
        if (minimum is not None or maximum is not None) and value_type not in {"number", "integer"}:
            errors.append(f"predicate {name!r} numeric bounds require value_type number/integer")
        if minimum is not None and maximum is not None and minimum > maximum:
            errors.append(f"predicate {name!r} minimum exceeds maximum")
        if spec.get("exclusive_object_per_subject"):
            if spec.get("arity") != "binary":
                errors.append(f"predicate {name!r} exclusivity requires binary arity")
            if value_type not in {None, "boolean"}:
                errors.append(f"predicate {name!r} exclusivity requires boolean/presence semantics")
    return errors


def entity_registry_errors(registry: dict) -> list[str]:
    """Semantic registry errors, especially duplicate ids with ambiguous declared types."""
    rows = registry.get("entities", []) if isinstance(registry, dict) else []
    ids = [row.get("id") for row in rows if isinstance(row, dict) and row.get("id")]
    return [
        f"duplicate entity id {entity_id!r}"
        for entity_id in sorted({entity_id for entity_id in ids if ids.count(entity_id) > 1})
    ]


def _registry_maps(registry: dict | None) -> tuple[dict[str, str], set[str]]:
    if not registry:
        return {}, set()
    entities = {
        row["id"]: row["type"]
        for row in registry.get("entities", [])
        if isinstance(row, dict) and row.get("id") and row.get("type")
    }
    return entities, set(registry.get("closed_types", []))


def _entity_errors(entity: str | None, role: str, allowed_types: list[str] | None,
                   registry: dict | None) -> list[str]:
    if not entity:
        return []
    entities, closed_types = _registry_maps(registry)
    actual_type = entities.get(entity) or _prefix(entity)
    errors: list[str] = []
    if allowed_types and actual_type not in allowed_types:
        errors.append(f"{role} {entity!r} has type {actual_type!r}, expected one of {allowed_types}")
    if entity not in entities and closed_types:
        expected = set(allowed_types or [])
        if _prefix(entity) in closed_types or (expected and expected.issubset(closed_types)):
            errors.append(f"{role} {entity!r} is not declared in the closed entity registry")
    return errors


def check_atom(ontology: dict, predicate: str | None, subject: str | None, object: str | None,
               *, value: Any = _MISSING, comparison: str = "eq", op: str | None = None,
               registry: dict | None = None) -> list[str]:
    """Return violations of one typed atom under explicitly declared domain constraints."""
    spec = predicate_specs(ontology).get(predicate)
    if spec is None:
        return [f"predicate {predicate!r} is not declared in the ontology"]
    errors: list[str] = []
    arity = spec.get("arity")
    if arity == "binary" and not object:
        errors.append(f"predicate {predicate!r} is binary but used without an object")
    if arity == "unary" and object:
        errors.append(f"predicate {predicate!r} is unary but used with object {object!r}")
    errors.extend(_entity_errors(subject, "subject", spec.get("subject_types"), registry))
    errors.extend(_entity_errors(object, "object", spec.get("object_types"), registry))

    value_type = spec.get("value_type")
    allowed = spec.get("allowed_values")
    minimum, maximum = spec.get("minimum"), spec.get("maximum")
    if comparison not in {"eq", "ne", "lt", "lte", "gt", "gte"}:
        errors.append(f"predicate {predicate!r} uses unsupported comparison {comparison!r}")
    if value is _MISSING:
        needs_value = value_type not in {None, "boolean"} or minimum is not None or maximum is not None
        if isinstance(allowed, list) and not any(typed_equal(True, candidate) for candidate in allowed):
            needs_value = True
        if op != "remove" and needs_value:
            errors.append(f"predicate {predicate!r} requires an explicit typed value")
        if comparison != "eq":
            errors.append(f"predicate {predicate!r} comparison {comparison!r} requires a value")
        return errors

    if value_type and not _value_type_ok(value, value_type):
        errors.append(f"predicate {predicate!r} value {value!r} is not {value_type}")
    if isinstance(allowed, list) and not any(typed_equal(value, candidate) for candidate in allowed):
        errors.append(f"predicate {predicate!r} value {value!r} is outside allowed_values {allowed}")
    if minimum is not None and (not _value_type_ok(value, "number") or value < minimum):
        errors.append(f"predicate {predicate!r} value {value!r} is below minimum {minimum}")
    if maximum is not None and (not _value_type_ok(value, "number") or value > maximum):
        errors.append(f"predicate {predicate!r} value {value!r} is above maximum {maximum}")
    if comparison in _ORDERED_COMPARISONS and value_type not in {"number", "integer"}:
        errors.append(f"predicate {predicate!r} ordered comparison requires a numeric value domain")
    return errors


def exclusive_predicate_errors(ontology: dict,
                               predicates: dict[tuple[str, str, str | None], Any]) -> list[str]:
    """Check declared one-object-per-subject constraints against one state snapshot."""
    exclusive = {
        name for name, spec in predicate_specs(ontology).items()
        if spec.get("exclusive_object_per_subject")
    }
    active: dict[tuple[str, str], list[str]] = {}
    for (predicate, subject, obj), value in predicates.items():
        if predicate not in exclusive or obj is None or not bool(value):
            continue
        active.setdefault((predicate, subject), []).append(obj)
    return [
        f"predicate {predicate!r} subject {subject!r} has multiple active objects {sorted(objects)}"
        for (predicate, subject), objects in sorted(active.items()) if len(set(objects)) > 1
    ]
