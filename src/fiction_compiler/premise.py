"""Premise-layer divergence + diagnosis (ADR 0017).

The highest-leverage decisions in a story — whose arc it is, whether the central conflict can be
settled by proof, how obliquely it approaches its feeling — are made at the premise layer, which
had no check. A single default premise sails through and sets the ceiling before any audit runs
(observed: 'Slack Water' passed every downstream audit yet lost to 'The Overnight' on premise-level
choices the pipeline could not see).

This module extends the pipeline's existing separation-of-powers to that layer WITHOUT installing a
new gatekeeper. The design constraint (user-directed): influence must stay decentralized — no single
LLM component may become the determinative selector at the most consequential layer. So it does two
things and no more:

- **Divergence floor (deterministic):** refuse to proceed unless the premise stage emitted at least
  ``MIN_DISTINCT_SIGNATURES`` *structurally distinct* candidates. This forces a wider search — the
  real lever for a creatively-constrained generator — and rejects a batch that collapsed toward one
  shape. It selects nothing and ranks nothing.
- **Diagnostic probes (a fixed, versioned rubric in ``premise-probes.json``):** structural questions
  applied to each candidate. The rubric is an inspectable, human-editable data artifact, not a
  model's live verdict; the LLM answers the questions, it does not invent them or pick a winner.

Selection stays exactly where it already is: the human ``premise`` gate, informed by preserved
disagreement. No LLM component gains veto or selection power here. The floor is code; the probes only
surface risks.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import schema
from .workspace import ROOT

PROBES_PATH = ROOT / "premise-probes.json"

# Minimum size and structural spread of a premise batch. A batch smaller than MIN_CANDIDATES, or one
# whose candidates collapse to fewer than MIN_DISTINCT_SIGNATURES architectures, is a search that
# never really diverged.
MIN_CANDIDATES = 3
MIN_DISTINCT_LOGLINES = 3


def load_probes(path: Path | None = None, *, profile: str = "core") -> list[dict]:
    """The fixed diagnostic rubric (data, not code). Returns [] if the file is absent."""
    path = path or PROBES_PATH
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if profile == "core":
        return data.get("probes", [])
    return data.get("profiles", {}).get(profile, [])


def architecture_signature(candidate: dict) -> tuple:
    """The structural fingerprint the floor diversifies on — NOT a quality score.

    The three axes where a batch most easily collapses to one default shape: whether the transforming
    character is the POV character (on-camera vs off-camera arc), the conflict type, and whether the
    story approaches its feeling directly or obliquely.
    """
    return (
        candidate.get("pov_character") == candidate.get("transforming_character")
        if candidate.get("transforming_character") is not None else None,
        candidate.get("conflict_type"),
        candidate.get("obliqueness"),
        candidate.get("resolution_type"),
    )


def _normalized_logline(candidate: dict) -> str:
    return " ".join(str(candidate.get("logline", "")).lower().split())


def diversity_floor(candidates: list[dict]) -> dict:
    """Deterministic gate on the premise BATCH. Forces a wide, structurally-varied search.

    Returns ``{ok, issues, distinct_architectures, candidates}``. It never ranks or selects a
    candidate — it only refuses a batch that is too small, malformed, or collapsed toward a single
    architecture. The decision of *which* premise to use is not made here.
    """
    issues: list[str] = []
    if len(candidates) < MIN_CANDIDATES:
        issues.append(f"need at least {MIN_CANDIDATES} premise candidates; got {len(candidates)}")
    for i, cand in enumerate(candidates):
        label = cand.get("id", i)
        errs = schema.validate_named(cand, "premise")
        if errs:
            issues.append(f"candidate {label!r}: invalid premise ({'; '.join(errs)})")
    signatures = {architecture_signature(c) for c in candidates}
    loglines = {_normalized_logline(c) for c in candidates if _normalized_logline(c)}
    if candidates and len(loglines) < MIN_DISTINCT_LOGLINES:
        issues.append(
            f"premise batch contains only {len(loglines)} distinct normalized logline(s) across "
            f"{len(candidates)} candidate(s) (need {MIN_DISTINCT_LOGLINES}); relabeling the same "
            "premise does not count as wider search"
        )
    return {
        "ok": not issues,
        "issues": issues,
        "distinct_architectures": len(signatures),
        "distinct_loglines": len(loglines),
        "candidates": len(candidates),
    }


def probe_report(candidates: list[dict], path: Path | None = None, *, profile: str = "core") -> dict:
    """Pair the fixed rubric with the batch for the human gate. Diagnoses; does not select.

    Returns the divergence-floor result plus the probe questions, so the human ``premise`` gate sees
    both 'is the search wide enough?' (deterministic) and 'what should I interrogate?' (the rubric),
    without any component having ranked the candidates.
    """
    return {
        "floor": diversity_floor(candidates),
        "probe_profile": profile,
        "probes": load_probes(path, profile=profile),
        "note": "The floor verifies search evidence only; declared tags and probes diagnose. "
                "They do not establish quality or select a premise.",
    }
