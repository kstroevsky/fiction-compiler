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


def assign_orders(judges: list[str], orders: list[list[str]]) -> list[dict]:
    """Isolation ledger: give each judge a presentation order, cycling through the available orders.

    Records *which* judge saw *which* order so a later reader can see the blinding/ordering each
    judgment was made under — the "judge isolation metadata" the review asked the code to own.
    """
    return [{"judge": judge, "presentation_order": orders[i % len(orders)]}
            for i, judge in enumerate(judges)]


def disagreement_from_rankings(rankings: list[list[str]]) -> dict:
    """Given each judge's ranked candidate list (best first), report agreement on the winner.

    Disagreement is information (operating contract): we record the distinct top picks rather than
    averaging the judges into a single, unsupported verdict.
    """
    top_picks = [ranking[0] for ranking in rankings if ranking]
    return {
        "top_picks": top_picks,
        "distinct_top_picks": sorted(set(top_picks)),
        "agree_on_winner": len(set(top_picks)) <= 1,
    }


def scores_from_critiques(critiques: list[dict]) -> dict[str, dict[str, float]]:
    """Derive a per-candidate, per-dimension penalty score from critique findings (higher better)."""
    scores: dict[str, dict[str, float]] = {}
    for critique in critiques:
        candidate = Path(str(critique.get("candidate", ""))).name
        # Only prose candidates (``*.md``) are contestants. A candidate-independent critique — the
        # scene-level hard audit, whose ``candidate`` is the scene id — must not become a phantom
        # candidate that dominates the field.
        if not candidate.endswith(".md"):
            continue
        bucket = scores.setdefault(candidate, {})
        for finding in critique.get("findings", []):
            dimension = finding.get("dimension", "unknown")
            bucket[dimension] = bucket.get(dimension, 0.0) - _SEVERITY_PENALTY.get(finding.get("severity"), 0.0)
    return scores


# Code audits form the DETERMINISTIC FLOOR: a candidate with a material/fatal finding from one of
# these cannot be selected, however much a critic prefers it. This is the guard that lets us lean on
# the (strong) LLM critic for selection without it choosing fluent prose past a hard failure.
DETERMINISTIC_CRITICS = frozenset({"hard-audit", "defaultness-lint", "prose-audit"})


def floor_eligible(critiques: list[dict]) -> set[str]:
    """Candidates that clear the deterministic floor — no material/fatal finding from a code audit."""
    candidates: set[str] = set()
    disqualified: set[str] = set()
    for critique in critiques:
        name = Path(str(critique.get("candidate", ""))).name
        if not name.endswith(".md"):
            continue
        candidates.add(name)
        if critique.get("critic") in DETERMINISTIC_CRITICS and \
                any(f.get("severity") in ("material", "fatal") for f in critique.get("findings", [])):
            disqualified.add(name)
    return candidates - disqualified


def scores_from_judgments(judgments: list[dict], reveal_map: dict[str, str]) -> dict[str, dict[str, float]]:
    """Aggregate blind per-dimension judge scores into per-candidate scores (mean across judges).

    Each judgment scores anonymized labels; ``reveal_map`` (label -> candidate id) de-anonymizes.
    Higher = better. The mean is only the *point estimate*; disagreement is recorded separately and
    can still force a human decision, so nothing is averaged away silently.
    """
    accumulated: dict[str, dict[str, list[float]]] = {}
    for judgment in judgments:
        for label, dim_scores in (judgment.get("scores") or {}).items():
            candidate = reveal_map.get(label)
            if candidate is None or not isinstance(dim_scores, dict):
                continue
            bucket = accumulated.setdefault(candidate, {})
            for dimension, value in dim_scores.items():
                try:
                    bucket.setdefault(dimension, []).append(float(value))
                except (TypeError, ValueError):
                    continue
    return {c: {d: sum(vs) / len(vs) for d, vs in dims.items()} for c, dims in accumulated.items()}


def rankings_from_judgments(judgments: list[dict], reveal_map: dict[str, str]) -> list[list[str]]:
    """Each judge's candidate-id ranking (best first) by total score — for disagreement detection."""
    rankings: list[list[str]] = []
    for judgment in judgments:
        totals: dict[str, float] = {}
        for label, dim_scores in (judgment.get("scores") or {}).items():
            candidate = reveal_map.get(label)
            if candidate is None or not isinstance(dim_scores, dict):
                continue
            totals[candidate] = sum(float(v) for v in dim_scores.values() if isinstance(v, (int, float)))
        rankings.append([c for c, _ in sorted(totals.items(), key=lambda kv: -kv[1])])
    return rankings


def run_tournament(critiques: list[dict], *, seed: int = 0, judges: list[str] | None = None,
                   judgments: list[dict] | None = None, judge_rankings: list[list[str]] | None = None) -> dict:
    """Blind, ordered, Pareto selection over a scene's candidates, behind the deterministic floor.

    Selection basis: if ``judgments`` (blind per-dimension LLM-critic scores) are supplied, the strong
    critic drives the Pareto pick among floor-eligible candidates; otherwise deterministic critique
    penalties do. Either way, a candidate that fails the deterministic floor is never selected.
    ``judges`` add an isolation ledger; ``judge_rankings`` remain accepted for disagreement only.
    """
    penalty_scores = scores_from_critiques(critiques)
    candidate_ids = sorted(penalty_scores)
    if not candidate_ids:
        return {"decision": "no_candidates", "reason": "no critiques with a candidate were supplied"}

    label_by_id, id_by_label = anonymize(candidate_ids, seed=seed)
    orders = presentation_orders(list(label_by_id.values()), seed=seed)
    eligible = floor_eligible(critiques)

    if judgments:
        judged = scores_from_judgments(judgments, id_by_label)
        scores = {c: judged[c] for c in candidate_ids if c in eligible and c in judged}
        basis = "critic-judgments"
    else:
        scores = {c: penalty_scores[c] for c in candidate_ids if c in eligible}
        basis = "deterministic-findings"

    front = pareto_front(scores)
    if not scores:
        recommendation = {"decision": "no_eligible_candidates",
                          "reason": "no candidate cleared the deterministic floor (or was scored)"}
    elif len(front) == 1:
        recommendation = {"decision": "select", "candidate": next(iter(front))}
    else:
        recommendation = {"decision": "human_decision_required", "pareto_front": sorted(front),
                          "reason": "multiple non-dominated candidates — a genuine tradeoff; do not average it away"}

    disagreement = has_disagreement(scores)
    record = {
        "candidates": candidate_ids,
        "floor_eligible": sorted(eligible),
        "floor_failed": sorted(set(candidate_ids) - eligible),
        "selection_basis": basis,
        "blind_labels": label_by_id,          # id -> blinded label (what a judge may see)
        "reveal_map": id_by_label,            # label -> id (keep OUT of the judges' view)
        "presentation_orders": orders,
        "scores": scores,
        "pareto_front": sorted(front),
        "dimension_winners": dimension_winners(scores),
        "recommendation": recommendation,
    }
    if judges:
        record["judge_ledger"] = assign_orders(judges, orders)
    rankings = rankings_from_judgments(judgments, id_by_label) if judgments else judge_rankings
    if rankings:
        judge_disagreement = disagreement_from_rankings(rankings)
        record["judge_disagreement"] = judge_disagreement
        disagreement = disagreement or not judge_disagreement["agree_on_winner"]
    record["disagreement"] = disagreement
    return record
