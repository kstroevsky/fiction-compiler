"""Deterministic tournament / selection engine (P2).

The design review's decisive point: the **code**, not the agent prompt, must own anonymization,
order randomization/reversal, candidate identity, multi-dimensional (Pareto) selection, and judge-
disagreement recording — otherwise "blind A/B" and "don't average away disagreement" are merely
requested, not guaranteed. The LLM judges stay agents; this module prepares the blinded comparison
and computes the selection math so isolation and fairness are structural.

Scores are multidimensional and never collapsed into one number (per the operating contract): a
winner is chosen only when one candidate Pareto-dominates all others; otherwise the non-dominated
set is surfaced for a human decision, with the tradeoff recorded rather than averaged.
"""
from __future__ import annotations

import random
from pathlib import Path

# Higher score == better. Findings are penalties, so a clean dimension scores 0 (the best).
_SEVERITY_PENALTY = {"minor": 1.0, "material": 4.0, "fatal": 16.0}


def _rng(seed: int) -> random.Random:
    return random.Random(seed)


def anonymize(candidate_ids: list[str], *, seed: int = 0) -> tuple[dict[str, str], dict[str, str]]:
    """Map true candidate ids -> blinded labels (A, B, C…) in a seeded-random assignment.

    Returns ``(label_by_id, id_by_label)``. Deterministic for a seed (reproducible tournament) but
    the assignment hides which file/strategy a judge is looking at.
    """
    shuffled = sorted(candidate_ids)
    _rng(seed).shuffle(shuffled)
    labels = [chr(ord("A") + i) for i in range(len(shuffled))]
    label_by_id = {cid: labels[i] for i, cid in enumerate(shuffled)}
    return label_by_id, {label: cid for cid, label in label_by_id.items()}


def presentation_orders(labels: list[str], *, seed: int = 0) -> list[list[str]]:
    """A forward and a reversed order (fight position bias), plus one shuffled order when >2."""
    base = sorted(labels)
    orders = [base, list(reversed(base))]
    if len(base) > 2:
        shuffled = base[:]
        _rng(seed + 1).shuffle(shuffled)
        if shuffled not in orders:
            orders.append(shuffled)
    return orders


def dominates(a: dict[str, float], b: dict[str, float]) -> bool:
    """True if score-vector ``a`` Pareto-dominates ``b`` (>= on every dim, > on at least one).

    A dimension absent from a vector counts as 0 (a clean, no-finding dimension — the best value).
    """
    dims = set(a) | set(b)
    ge_all = all(a.get(d, 0.0) >= b.get(d, 0.0) for d in dims)
    gt_any = any(a.get(d, 0.0) > b.get(d, 0.0) for d in dims)
    return ge_all and gt_any


def pareto_front(scores: dict[str, dict[str, float]]) -> set[str]:
    """The set of non-dominated candidate ids. ``scores`` maps id -> {dimension: value}."""
    return {cid for cid, sc in scores.items()
            if not any(dominates(other, sc) for oid, other in scores.items() if oid != cid)}


def dimension_winners(scores: dict[str, dict[str, float]]) -> dict[str, list[str]]:
    """Best candidate(s) per dimension (ties kept) — the tradeoffs the Pareto front encodes."""
    dims: set[str] = set()
    for vector in scores.values():
        dims |= set(vector)
    winners: dict[str, list[str]] = {}
    for dim in sorted(dims):
        best = max(vector.get(dim, 0.0) for vector in scores.values())
        winners[dim] = sorted(cid for cid, vector in scores.items() if vector.get(dim, 0.0) == best)
    return winners


def has_disagreement(scores: dict[str, dict[str, float]]) -> bool:
    """Disagreement == no single dominator, or the per-dimension winners are not all the same set."""
    if len(scores) < 2:
        return False
    distinct_winner_sets = {tuple(v) for v in dimension_winners(scores).values()}
    return len(pareto_front(scores)) > 1 or len(distinct_winner_sets) > 1


def scores_from_critiques(critiques: list[dict]) -> dict[str, dict[str, float]]:
    """Derive a per-candidate, per-dimension penalty score from critique findings (higher better)."""
    scores: dict[str, dict[str, float]] = {}
    for critique in critiques:
        candidate = Path(str(critique.get("candidate", ""))).name
        if not candidate:
            continue
        bucket = scores.setdefault(candidate, {})
        for finding in critique.get("findings", []):
            dimension = finding.get("dimension", "unknown")
            bucket[dimension] = bucket.get(dimension, 0.0) - _SEVERITY_PENALTY.get(finding.get("severity"), 0.0)
    return scores


def run_tournament(critiques: list[dict], *, seed: int = 0) -> dict:
    """Blind, ordered, Pareto-scored selection over a scene's candidates from their critiques."""
    scores = scores_from_critiques(critiques)
    candidate_ids = sorted(scores)
    if not candidate_ids:
        return {"decision": "no_candidates", "reason": "no critiques with a candidate were supplied"}

    label_by_id, id_by_label = anonymize(candidate_ids, seed=seed)
    front = pareto_front(scores)
    if len(front) == 1:
        recommendation = {"decision": "select", "candidate": next(iter(front))}
    else:
        recommendation = {
            "decision": "human_decision_required",
            "pareto_front": sorted(front),
            "reason": "multiple non-dominated candidates — a genuine tradeoff; do not average it away",
        }
    return {
        "candidates": candidate_ids,
        "blind_labels": label_by_id,          # id -> blinded label (what a judge may see)
        "reveal_map": id_by_label,            # label -> id (keep OUT of the judges' view)
        "presentation_orders": presentation_orders(list(label_by_id.values()), seed=seed),
        "scores": scores,
        "pareto_front": sorted(front),
        "dimension_winners": dimension_winners(scores),
        "disagreement": has_disagreement(scores),
        "recommendation": recommendation,
    }
