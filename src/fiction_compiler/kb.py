"""Knowledge-base retrieval — put the right craft card in front of the LLM at the right time.

The KB is reference the *author* (the LLM) reaches for, not something the pipeline enforces.
This module makes it retrievable: search concept cards by keyword/layer, fetch a full card, and
list registered sources. Deterministic and fast — it is a lookup, not a judgment.
"""
from __future__ import annotations

import json
from functools import lru_cache

from .workspace import KB


@lru_cache(maxsize=1)
def _index() -> dict:
    return json.loads((KB / "index.json").read_text(encoding="utf-8"))


def concepts() -> list[dict]:
    return _index().get("concepts", [])


def sources(stream: str | None = None) -> list[dict]:
    data = json.loads((KB / "source-register.json").read_text(encoding="utf-8")).get("sources", [])
    return [s for s in data if not stream or s.get("stream") == stream]


def _card_text(concept: dict) -> str:
    path = KB / concept["card"]
    return path.read_text(encoding="utf-8") if path.exists() else ""


def get(concept_id: str) -> dict | None:
    """Return one concept's metadata plus its full card text."""
    for concept in concepts():
        if concept["id"] == concept_id:
            return {**concept, "card_text": _card_text(concept)}
    return None


def _summary(concept: dict) -> dict:
    keys = ("id", "layer", "claim", "evidence_strength", "use_when", "dangerous_when",
            "conflicts_with", "card", "related", "used_by", "sources")
    return {k: concept[k] for k in keys if k in concept}


def search(query: str = "", layer: str | None = None, limit: int = 10) -> list[dict]:
    """Rank concept cards against a keyword query (empty query lists everything).

    Scores id matches highest, then metadata, then card-body hits. Returns summaries; call
    ``get`` for the full card text.
    """
    terms = [t for t in query.lower().split() if t]
    scored: list[tuple[int, dict]] = []
    for concept in concepts():
        if layer and concept.get("layer") != layer:
            continue
        if not terms:
            scored.append((1, concept))
            continue
        meta = " ".join([
            concept.get("id", ""), concept.get("use_when", ""), concept.get("layer", ""),
            " ".join(concept.get("related", [])), " ".join(str(s) for s in concept.get("sources", [])),
        ]).lower()
        body = _card_text(concept).lower()
        score = 0
        for term in terms:
            if term in concept.get("id", "").lower():
                score += 3
            if term in meta:
                score += 2
            if term in body:
                score += 1
        if score:
            scored.append((score, concept))
    scored.sort(key=lambda pair: -pair[0])
    return [_summary(c) for _, c in scored[:limit]]
