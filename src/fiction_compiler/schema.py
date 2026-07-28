"""A small, dependency-free JSON Schema validator.

The repository deliberately has no runtime dependencies, so rather than pull in
``jsonschema`` we implement the subset of draft 2020-12 that our own schemas in
``schemas/`` actually use:

    type (incl. union types), required, properties, items,
    enum, pattern, minLength, minimum, maximum

This is intentionally NOT a general-purpose validator. It rejects the malformed
artifacts our pipeline can produce, and nothing more. ``validate`` returns a
list of human-readable error strings (empty == valid) so callers can aggregate
findings; ``validate_named`` loads a schema from ``schemas/`` by its stem.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from .workspace import SCHEMAS


def _type_ok(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    # Unknown type keyword: do not fail on something we cannot check.
    return True


def _validate(instance: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, opt) for opt in options):
            errors.append(f"{path}: expected type {expected}, got {type(instance).__name__}")
            # A wrong type makes every downstream check noise; stop here.
            return

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(instance) < min_length:
            errors.append(f"{path}: string length {len(instance)} < minLength {min_length}")
        pattern = schema.get("pattern")
        # JSON Schema `pattern` is a search, not a full match; our schemas anchor
        # with ^...$ where they mean a full match, so re.search is correct.
        if pattern is not None and re.search(pattern, instance) is None:
            errors.append(f"{path}: {instance!r} does not match pattern {pattern!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if minimum is not None and instance < minimum:
            errors.append(f"{path}: {instance} < minimum {minimum}")
        maximum = schema.get("maximum")
        if maximum is not None and instance > maximum:
            errors.append(f"{path}: {instance} > maximum {maximum}")

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required property '{req}'")
        for key, subschema in schema.get("properties", {}).items():
            if key in instance:
                _validate(instance[key], subschema, f"{path}.{key}", errors)

    if isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(instance):
                _validate(item, items, f"{path}[{index}]", errors)


def validate(instance: Any, schema: dict, path: str = "$") -> list[str]:
    """Return a list of validation error messages; empty means valid."""
    errors: list[str] = []
    _validate(instance, schema, path, errors)
    return errors


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    """Load ``schemas/<name>.schema.json`` (name is the bare stem, e.g. 'scene')."""
    path = SCHEMAS / f"{name}.schema.json"
    if not path.exists():
        raise FileNotFoundError(f"No such schema: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_named(instance: Any, name: str, path: str | None = None) -> list[str]:
    """Validate an instance against a named schema from ``schemas/``."""
    return validate(instance, load_schema(name), path or f"${name}")
