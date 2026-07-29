"""Defaultness linter — deterministic detection of model-default prose.

This is the early, code-level slice of Audit 3 (adversarial defaultness). It cannot judge
whether a surprise is earned — that needs the reader model and the LLM critics — but it can
catch, cheaply and repeatably, the surface tics that mark unrevised model output: stock
clichés, emotions told-then-paraphrased, POV filter words, weak intensifiers, progressive
hedges, and adverb dialogue tags. Patterns live in ``kb/style/defaultness-catalog.json`` so
the catalog is data, not code.

A match is *evidence to inspect*, never a verdict. The diagnosis says so, and points repair
downward when the tic is a symptom of a deeper default. Output conforms to critique.schema.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .workspace import KB

_CAP_PER_CATEGORY = 8
_SEVERITY_RANK = {"minor": 0, "material": 1, "fatal": 2}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_OPENER_RUN = 3  # this many consecutive sentences sharing an opener == monotony


def load_catalog() -> dict:
    path = KB / "style" / "defaultness-catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _finding(severity: str, evidence: str, diagnosis: str, dimension: str = "defaultness") -> dict:
    return {
        "dimension": dimension,
        "severity": severity,
        "evidence": evidence,
        "diagnosis": diagnosis,
        "repair_layer": "prose",
    }


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _scan_lines(text: str, category: str, spec: dict, findings: list[dict]) -> None:
    severity = spec.get("severity", "minor")
    compiled = [re.compile(p, re.IGNORECASE) for p in spec.get("patterns", [])]
    hits: list[tuple[int, str, str]] = []  # (line_no, matched_text, line_text)
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in compiled:
            for match in pattern.finditer(line):
                hits.append((line_no, match.group(0), line.strip()))

    # Density-gated categories only fire when they exceed a per-1000-words rate.
    density_limit = spec.get("density_per_1000_words")
    if density_limit is not None:
        words = max(_word_count(text), 1)
        rate = len(hits) * 1000 / words
        if rate < density_limit:
            return
        findings.append(_finding(
            severity,
            f"{len(hits)} '{category}' hits ({rate:.1f} per 1000 words), e.g. "
            + "; ".join(sorted({h[1].lower() for h in hits}))[:160],
            f"Weak-word density exceeds {density_limit}/1000; prune or replace with specifics.",
        ))
        return

    for line_no, matched, line_text in hits[:_CAP_PER_CATEGORY]:
        findings.append(_finding(
            severity,
            f"L{line_no}: {matched!r} in “{line_text[:120]}”",
            _DIAGNOSIS.get(category, "Model-default phrasing; verify it earns its place or repair a lower layer."),
        ))
    extra = len(hits) - _CAP_PER_CATEGORY
    if extra > 0:
        findings.append(_finding(severity, f"+{extra} more '{category}' matches (truncated)",
                                 "Category recurs; likely a habit rather than a choice."))


_DIAGNOSIS = {
    "cliches": "Stock phrase; the image is inherited, not perceived. Replace with something only this character in this moment would notice.",
    "telling_emotion": "Emotion named then paraphrased instead of enacted. Cut the label; show the behavior that implies it.",
    "filter_perception": "POV filter word distances the reader from perception. Usually deletable ('she saw the door open' -> 'the door opened').",
    "progressive_hedge": "'began to / seemed to' softens action into approximation. Commit to the action.",
    "adverb_dialogue_tag": "Adverb props up a weak verb or redundant tag. Prefer the line itself carrying the tone.",
}


def _opener_repetition(text: str, findings: list[dict]) -> None:
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
    openers = [re.sub(r"^[\"'“‘(]+", "", s).split(" ")[0].lower().strip(".,;:!?") for s in sentences]
    run_word, run_len, run_start = None, 0, 0
    for i, word in enumerate(openers):
        if word and word == run_word:
            run_len += 1
        else:
            run_word, run_len, run_start = word, 1, i
        if run_len == _OPENER_RUN and run_word:
            findings.append(_finding(
                "minor",
                f"{_OPENER_RUN} consecutive sentences open with {run_word!r} (from sentence {run_start + 1})",
                "Repeated sentence openers flatten rhythm; vary syntax or subordinate.",
                dimension="rhythm",
            ))


def lint_text(text: str) -> list[dict]:
    catalog = load_catalog()
    findings: list[dict] = []
    for category, spec in catalog.items():
        if category.startswith("_") or not isinstance(spec, dict):
            continue
        _scan_lines(text, category, spec, findings)
    _opener_repetition(text, findings)
    return findings


def _verdict(findings: list[dict]) -> str:
    worst = max((_SEVERITY_RANK[f["severity"]] for f in findings), default=-1)
    if worst >= _SEVERITY_RANK["material"]:
        return "revise"
    return "pass"


def lint_file(path: Path) -> dict:
    raw = Path(path).read_bytes()
    findings = lint_text(raw.decode("utf-8"))
    return {
        "candidate": Path(path).name,
        # Bind the critique to the exact bytes linted, so the promotion gate can trust it as
        # candidate-bound evidence for the defaultness class (see promote.evaluate_audit_gate).
        "candidate_sha256": hashlib.sha256(raw).hexdigest(),
        "critic": "defaultness-lint",
        "audit_class": "defaultness",
        "verdict": _verdict(findings),
        "confidence": 0.7,
        "findings": findings,
    }
