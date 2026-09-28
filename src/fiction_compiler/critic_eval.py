"""Critic screening: measure whether critics catch planted diagnostic defects.

A diagnostic corpus (``evals/critic-cases.json``) pins planted defects and clean controls. Deterministic
detectors (defaultness, prose knowledge-leak, ontology, injection) are scored here and pinned in the
regression harness as recall/specificity invariants. LLM-persona cases carry provisional fixture
expectations and are scored with ``score_findings`` when live findings are supplied. They are useful
for screening but do not substitute for qualified human calibration; ADR 0029 owns that evidence.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import defaultness, ontology, prose_audit, safety
from .workspace import ROOT

CORPUS = ROOT / "evals" / "critic-cases.json"
DETERMINISTIC = {"defaultness", "prose_knowledge_leak", "ontology", "injection"}


def load_corpus(path: Path | None = None) -> list[dict]:
    path = path or CORPUS
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("cases", [])


def _blocking(findings: list[dict]) -> list[dict]:
    return [f for f in findings if f.get("severity") in ("material", "fatal")]


def _asserts_signal(text: str, signal: str) -> bool:
    """Whether free-form text asserts a signal rather than clearly negating it."""
    hay = text.lower()
    needle = signal.lower().strip()
    if not needle:
        return False
    pattern = re.compile(rf"(?<!\w){re.escape(needle)}(?!\w)")
    for match in pattern.finditer(hay):
        prefix = hay[max(0, match.start() - 48):match.start()]
        if re.search(
            r"(?:\bno\b|\bnot\b|\bnever\b|\bwithout\b|\blacks?\b|"
            r"\blacking\b|\babsence\s+of\b)(?:\W+\w+){0,3}\W*$",
            prefix,
        ):
            continue
        return True
    return False


def matching_signals(case: dict, findings: list[dict]) -> list[str]:
    """Return planted-defect signals positively localized by blocking findings."""
    signals = [str(s).lower() for s in case.get("signals", []) if str(s).strip()]
    matched: set[str] = set()
    for finding in _blocking(findings):
        dimension = str(finding.get("dimension", "")).lower()
        prose = " ".join(str(finding.get(k, "")) for k in ("diagnosis", "evidence"))
        for signal in signals:
            if _asserts_signal(dimension, signal) or _asserts_signal(prose, signal):
                matched.add(signal)
    return sorted(matched)


def score_findings(case: dict, findings: list[dict]) -> bool:
    """Did a critic's findings catch this case's planted defect?

    A blocking (material/fatal) finding counts if its dimension/diagnosis/evidence contains any of
    the case's signal keywords; with no signals, any blocking finding counts. This tolerates the
    free-form dimension slugs the LLM personas use while still requiring the defect to be named.
    """
    blocking = _blocking(findings)
    signals = [s.lower() for s in case.get("signals", [])]
    if not signals:
        return bool(blocking)
    return bool(matching_signals(case, blocking))


def run_deterministic_case(case: dict) -> bool:
    """Run a whitelisted deterministic detector and return whether it CAUGHT the defect."""
    detector = case.get("detector")
    inp = case.get("input", {})
    if detector == "defaultness":
        return score_findings(case, defaultness.lint_text(inp.get("text", "")))
    if detector == "prose_knowledge_leak":
        return prose_audit.is_knowledge_leak(inp.get("pov_knows_before"), inp.get("granted_this_scene"))
    if detector == "injection":
        return len(safety.scan_injection(inp.get("text", ""))) > 0
    if detector == "ontology":
        ont = {p["name"]: p for p in inp.get("ontology", {}).get("predicates", [])}
        atom = inp.get("atom", {})
        return bool(ontology.check_atom(ont, atom.get("predicate"), atom.get("subject"), atom.get("object")))
    raise ValueError(f"non-deterministic or unknown detector {detector!r}")


def run_corpus(cases: list[dict] | None = None, live_findings: dict | None = None) -> dict:
    """Score the corpus and report recall (defects caught) + specificity (controls not flagged).

    Deterministic cases run now; ``llm`` cases score against ``live_findings`` keyed by case id, or
    are marked ``needs_live``. Per-critic breakdown included.
    """
    cases = load_corpus() if cases is None else cases
    live_findings = live_findings or {}
    results: list[dict] = []
    for case in cases:
        detector = case.get("detector")
        matched_signals: list[str] = []
        if detector == "llm":
            if case["id"] in live_findings:
                supplied = live_findings[case["id"]]
                caught, status = score_findings(case, supplied), "scored"
                matched_signals = matching_signals(case, supplied)
            else:
                caught, status = None, "needs_live"
        else:
            caught, status = run_deterministic_case(case), "scored"
        expect = case.get("expect_caught", True)
        results.append({"id": case["id"], "critic": case.get("critic"), "kind": case.get("kind", "defect"),
                        "caught": caught, "status": status, "matched_signals": matched_signals,
                        "label_source": case.get("label_source", "mechanical_fixture"),
                        "correct": None if caught is None else (caught == expect)})

    scored = [r for r in results if r["status"] == "scored"]
    defects = [r for r in scored if r["kind"] == "defect"]
    controls = [r for r in scored if r["kind"] == "control"]
    by_critic: dict[str, dict] = {}
    for r in scored:
        b = by_critic.setdefault(r["critic"], {"scored": 0, "correct": 0})
        b["scored"] += 1
        b["correct"] += 1 if r["correct"] else 0
    return {
        "total": len(cases),
        "scored": len(scored),
        "needs_live": len(cases) - len(scored),
        "recall": (sum(1 for r in defects if r["caught"]) / len(defects)) if defects else None,
        "specificity": (sum(1 for r in controls if not r["caught"]) / len(controls)) if controls else None,
        "by_critic": by_critic,
        "results": results,
    }
