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
import platform
from datetime import datetime, timezone
from pathlib import Path

from . import (critic_eval, critique, defaultness, integrity, ontology, premise, prose_audit,
               revision, tournament)
from .workspace import ROOT

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


def _critic_case(inp: dict) -> bool:
    """Critic-recall invariant: a deterministic detector must catch (or not) a gold planted defect."""
    return critic_eval.run_deterministic_case(inp)


def _vendor_output(inp: dict) -> str:
    """Untrusted multi-vendor-output boundary (ADR 0020): raw text -> 'malformed' or verdict:consistency.

    Pins that an external vendor's reply is only allowed toward the gate when it is well-formed JSON
    with a valid verdict, and that a 'pass' carrying a material/fatal finding is flagged inconsistent
    (record_critique would refuse it) — the same rule the gate enforces, at the vendor seam.
    """
    from . import role_runner  # lazy: tools <-> regression <-> role_runner would cycle at import
    try:
        parsed = role_runner.parse_vendor_critique(inp["raw"])
    except role_runner.MalformedVendorOutput:
        return "malformed"
    ok = critique.consistency_problem(parsed["verdict"], parsed["findings"]) is None
    return f"{parsed['verdict']}:{'consistent' if ok else 'inconsistent'}"


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
    "critic_case": _critic_case,
    "vendor_output": _vendor_output,
}


# --- provenance -------------------------------------------------------------------------------

def _hash_paths(root: Path, paths) -> str:
    combined = []
    for path in sorted(paths, key=lambda p: p.relative_to(root).as_posix()):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            combined.append(f"{rel}:{integrity.sha256_file(path)}")
    return integrity.sha256_bytes("\n".join(combined).encode("utf-8"))


def _framework_groups(root: Path) -> dict[str, list[Path]]:
    return {
        "schemas": list((root / "schemas").glob("*.json")),
        "knowledge_base": [
            path for path in (root / "kb").rglob("*") if path.suffix in {".json", ".md"}
        ],
        "source": list((root / "src" / "fiction_compiler").rglob("*.py")),
        "scripts": list((root / "scripts").rglob("*.py")),
        "configuration": [
            *list((root / "config").rglob("*.json")),
            root / "premise-probes.json",
        ],
        "evaluation_data": [
            *list((root / "evals").rglob("*.json")),
            *list((root / "regression").rglob("*.json")),
        ],
        "agent_instructions": [
            *list((root / ".claude" / "agents").rglob("*.md")),
            *list((root / ".agents" / "skills").glob("*/SKILL.md")),
            root / "AGENTS.md",
            root / "CLAUDE.md",
            *list((root / "constitution").rglob("*.md")),
        ],
        "runtime_config": [root / "pyproject.toml"],
    }


def is_framework_path(relative_path: str) -> bool:
    """Whether a repository-relative path belongs to the behavior-relevant framework surface.

    This mirrors ``_framework_groups`` lexically so a transaction can declare a file that does not
    exist yet without allowing unrelated documentation or arbitrary workspace files into scope.
    """
    path = Path(relative_path)
    parts = path.parts
    if not parts or path.is_absolute() or ".." in parts:
        return False
    posix = path.as_posix()
    if len(parts) == 2 and parts[0] == "schemas" and path.suffix == ".json":
        return True
    if parts[0] == "kb" and path.suffix in {".json", ".md"}:
        return True
    if len(parts) >= 3 and parts[:2] == ("src", "fiction_compiler") and path.suffix == ".py":
        return True
    if parts[0] == "scripts" and path.suffix == ".py":
        return True
    if parts[0] == "config" and path.suffix == ".json":
        return True
    if posix == "premise-probes.json":
        return True
    if parts[0] in {"evals", "regression"} and path.suffix == ".json":
        return True
    if len(parts) >= 3 and parts[:2] == (".claude", "agents") and path.suffix == ".md":
        return True
    if len(parts) == 4 and parts[:2] == (".agents", "skills") and parts[-1] == "SKILL.md":
        return True
    if posix in {"AGENTS.md", "CLAUDE.md", "pyproject.toml"}:
        return True
    if parts[0] == "constitution" and path.suffix == ".md":
        return True
    return False


def framework_file_manifest(root: Path | None = None) -> dict[str, str]:
    """Return the exact behavior-relevant files behind the aggregate framework fingerprint."""
    root = (root or ROOT).resolve()
    files: dict[str, str] = {}
    for paths in _framework_groups(root).values():
        for path in paths:
            if path.is_file():
                files[path.relative_to(root).as_posix()] = integrity.sha256_file(path)
    return dict(sorted(files.items()))


# Captured once when this Python process imports the regression module. A long-lived MCP server may
# otherwise read a new source fingerprint from disk while still executing old imported functions.
_RUNTIME_SOURCE_SHA256 = _hash_paths(
    ROOT.resolve(), _framework_groups(ROOT.resolve())["source"]
)


def runtime_source_status(root: Path | None = None) -> dict:
    root = (root or ROOT).resolve()
    if root != ROOT.resolve():
        return {
            "checked": False,
            "fresh": None,
            "reason": "alternate test root does not correspond to this interpreter's imported package",
        }
    disk_sha256 = _hash_paths(root, _framework_groups(root)["source"])
    return {
        "checked": True,
        "fresh": disk_sha256 == _RUNTIME_SOURCE_SHA256,
        "imported_source_sha256": _RUNTIME_SOURCE_SHA256,
        "disk_source_sha256": disk_sha256,
    }


def framework_manifest(root: Path | None = None) -> dict:
    """Fingerprint every repository artifact that can change framework behavior.

    The fingerprint includes deterministic code plus the external policy/prompt/configuration files
    that steer generation and evaluation. ``root`` is injectable so tests can prove that each class
    of external artifact participates without mutating the checked-out repository.
    """
    root = (root or ROOT).resolve()
    groups = _framework_groups(root)
    hashes = {name: _hash_paths(root, paths) for name, paths in groups.items()}
    runtime = f"{platform.python_implementation()} {platform.python_version()}"
    combined_input = "\n".join([*(f"{name}:{hashes[name]}" for name in sorted(hashes)),
                                  f"python_runtime:{runtime}"])
    combined = integrity.sha256_bytes(combined_input.encode("utf-8"))
    return {
        "framework_fingerprint": combined,
        **{f"{name}_sha256": digest for name, digest in hashes.items()},
        "python_runtime": runtime,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# --- runner -----------------------------------------------------------------------------------

def load_fixtures(path: Path | None = None, root: Path | None = None) -> list[dict]:
    path = path or ((root or ROOT) / "regression" / "fixtures.json")
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


def run_regressions(fixtures: list[dict] | None = None, root: Path | None = None) -> dict:
    """Run every fixture and report pass/fail against the current framework fingerprint."""
    fixtures = load_fixtures(root=root) if fixtures is None else fixtures
    results = [run_fixture(f) for f in fixtures]
    passed = sum(1 for r in results if r["passed"])
    return {
        "manifest": framework_manifest(root),
        "runtime_source": runtime_source_status(root),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "ok": passed == len(results),
        "results": results,
    }
