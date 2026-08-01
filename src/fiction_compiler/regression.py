"""Framework regression harness (P5) — the FRAMEWORK loop's deterministic CHECK.

The story loop (``revision.py``) improves one manuscript; this improves the *compiler*. The review's
requirement: "No framework rule should be accepted merely because the same LLM that proposed it
preferred its output." So a change to a prompt, rubric, schema, or the deterministic code is only
safe if the pinned invariants still hold. This module runs **fixed fixtures** — input + expected
output for a whitelisted deterministic check — and reports pass/fail, plus a content fingerprint of
the framework so a change is observable.

Fixtures name a check from ``CHECKS`` (a closed whitelist — a fixture cannot execute arbitrary code)
and assert its output. Each fixture encodes an invariant an ADR established; if a future edit breaks
defaultness detection, the revision-regression trap, tournament selection, or ontology enforcement,
the runner fails and the framework change must be rejected or rolled back.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import critique, defaultness, integrity, ontology, premise, prose_audit, revision, tournament
from .workspace import KB, ROOT, SCHEMAS

FIXTURES = ROOT / "regression" / "fixtures.json"


# --- whitelisted checks -----------------------------------------------------------------------

def _defaultness_verdict(inp: dict) -> str:
    findings = defaultness.lint_text(inp["text"])
    return "revise" if any(f["severity"] in ("material", "fatal") for f in findings) else "pass"


def _revision_decision(inp: dict) -> str:
    return revision.evaluate_revision(
        inp["before"], inp["after"], target_dimension=inp.get("target"),
        iteration=inp.get("iteration", 1), attempts_at_current_layer=inp.get("attempts", 1),
        max_iterations=inp.get("max_iterations", 3), max_attempts_per_layer=inp.get("max_attempts_per_layer", 2),
        waivers=inp.get("waivers"),
    ).decision


def _tournament_decision(inp: dict) -> str:
    return tournament.run_tournament(inp["critiques"], seed=inp.get("seed", 0))["recommendation"]["decision"]


def _ontology_valid(inp: dict) -> bool:
    ont = {p["name"]: p for p in inp["ontology"].get("predicates", [])}
    atom = inp["atom"]
    return not ontology.check_atom(ont, atom.get("predicate"), atom.get("subject"), atom.get("object"))


def _prose_knowledge_leak(inp: dict) -> bool:
    return prose_audit.is_knowledge_leak(inp["pov_knows_before"], inp["granted_this_scene"])


def _premise_diversity(inp: dict) -> bool:
    return premise.diversity_floor(inp["candidates"])["ok"]


def _critique_consistency(inp: dict) -> bool:
    return critique.consistency_problem(inp["verdict"], inp["findings"]) is None


def _tournament_selected(inp: dict) -> str:
    result = tournament.run_tournament(inp["critiques"], seed=inp.get("seed", 0), judgments=inp.get("judgments"))
    rec = result["recommendation"]
    return rec.get("candidate", rec["decision"])


CHECKS = {
    "defaultness_verdict": _defaultness_verdict,
    "revision_decision": _revision_decision,
    "tournament_decision": _tournament_decision,
    "tournament_selected": _tournament_selected,
    "ontology_valid": _ontology_valid,
    "prose_knowledge_leak": _prose_knowledge_leak,
    "premise_diversity": _premise_diversity,
    "critique_consistency": _critique_consistency,
}


# --- provenance -------------------------------------------------------------------------------

def _hash_dir(paths) -> str:
    combined = []
    for path in sorted(paths, key=lambda p: p.name):
        if path.is_file():
            combined.append(f"{path.name}:{integrity.sha256_file(path)}")
    return integrity.sha256_bytes("\n".join(combined).encode("utf-8"))


def framework_manifest() -> dict:
    """A content fingerprint of the deterministic framework (schemas + KB index + package source).

    Changes whenever any pinned component changes, so a regression run is anchored to *what* was
    running. This is the "record versions / context hashes" the review asked for, deterministically.
    """
    schemas = _hash_dir(SCHEMAS.glob("*.json"))
    kb_index_path = KB / "index.json"
    kb_index = integrity.sha256_file(kb_index_path) if kb_index_path.exists() else ""
    source = _hash_dir((ROOT / "src" / "fiction_compiler").glob("*.py"))
    combined = integrity.sha256_bytes(f"{schemas}:{kb_index}:{source}".encode("utf-8"))
    return {
        "framework_fingerprint": combined,
        "schemas_sha256": schemas,
        "kb_index_sha256": kb_index,
        "source_sha256": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- runner -----------------------------------------------------------------------------------

def load_fixtures(path: Path | None = None) -> list[dict]:
    path = path or FIXTURES
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("fixtures", [])


def run_fixture(fixture: dict) -> dict:
    name, check = fixture.get("name"), fixture.get("check")
    handler = CHECKS.get(check)
    if handler is None:
        return {"name": name, "check": check, "passed": False, "error": f"unknown check {check!r}"}
    try:
        actual = handler(fixture.get("input", {}))
    except Exception as exc:  # noqa: BLE001 — a broken fixture is a failure, not a crash
        return {"name": name, "check": check, "passed": False, "error": f"{type(exc).__name__}: {exc}"}
    expected = fixture.get("expect")
    return {"name": name, "check": check, "expected": expected, "actual": actual, "passed": actual == expected}


def run_regressions(fixtures: list[dict] | None = None) -> dict:
    """Run every fixture and report pass/fail against the current framework fingerprint."""
    fixtures = load_fixtures() if fixtures is None else fixtures
    results = [run_fixture(f) for f in fixtures]
    passed = sum(1 for r in results if r["passed"])
    return {
        "manifest": framework_manifest(),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "ok": passed == len(results),
        "results": results,
    }
