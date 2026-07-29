"""Predicate ontology — declares the legal typed predicates so the executable checks (ADR 0004)
cannot be fooled by a typo.

Optional per project (``canon/ontology.json``). When absent, predicate atoms are unconstrained
(back-compat). When present, the hard audit checks every typed atom a scene touches — event
preconditions/effects and the scene's own ``predicate_changes`` / ``relationship_edges`` — for a
declared name, the right arity, and allowed subject/object entity types. Without this, ADR 0004 left
the vocabulary open: ``located_att`` was a silently different predicate that could never be
satisfied.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_ontology(project: Path) -> dict | None:
    """Return {predicate_name: spec} for the project, or None if it declares no ontology."""
    path = project / "canon" / "ontology.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {p["name"]: p for p in data.get("predicates", []) if p.get("name")}


def _prefix(entity: str) -> str:
    return entity.split("-", 1)[0] if entity else ""


def check_atom(ontology: dict, predicate: str | None, subject: str | None, object: str | None) -> list[str]:
    """Return the ways one typed atom violates the ontology (empty == valid)."""
    spec = ontology.get(predicate)
    if spec is None:
        return [f"predicate {predicate!r} is not declared in the ontology"]
    errors: list[str] = []
    arity = spec.get("arity")
    if arity == "binary" and not object:
        errors.append(f"predicate {predicate!r} is binary but used without an object")
    if arity == "unary" and object:
        errors.append(f"predicate {predicate!r} is unary but used with object {object!r}")
    subject_types = spec.get("subject_types")
    if subject_types and subject and _prefix(subject) not in subject_types:
        errors.append(f"predicate {predicate!r} subject {subject!r} is not a {subject_types} entity")
    object_types = spec.get("object_types")
    if object_types and object and _prefix(object) not in object_types:
        errors.append(f"predicate {predicate!r} object {object!r} is not a {object_types} entity")
    return errors
