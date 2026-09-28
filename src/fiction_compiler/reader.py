"""Reader-facing structural evidence without pretending to model comprehension.

The project can declare where each reader-contract clause is checked (or explicitly untested) and
annotate which canonical facts are available to the reader in discourse order.  These reports only
verify the annotation structure and its references.  They do not infer what a real reader noticed,
believed, remembered, or preferred; those remain measured reader/critic questions.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import schema
from .state import scene_sort_key


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def contract_coverage(project: Path) -> dict:
    """Check that every reader-contract clause is mapped or explicitly marked untested."""
    project = Path(project)
    brief = _load(project / "brief" / "project.json", {})
    clauses = list(brief.get("reader_contract", []))
    path = project / "brief" / "contract-coverage.json"
    if not path.exists():
        return {
            "project_id": brief.get("id"),
            "status": "missing",
            "mapped": 0,
            "untested": len(clauses),
            "clauses": [{"text": text, "state": "untested", "coverage": []} for text in clauses],
            "errors": ["brief/contract-coverage.json is missing"],
            "verification": "not_assessed",
        }

    artifact = _load(path, {})
    errors = schema.validate_named(artifact, "contract-coverage")
    if errors:
        return {"project_id": brief.get("id"), "status": "invalid", "errors": errors,
                "verification": "not_assessed"}
    if artifact.get("project_id") != brief.get("id"):
        errors.append("contract coverage project_id does not match brief/project.json")

    entries = artifact.get("clauses", [])
    by_text: dict[str, list[dict]] = {}
    for entry in entries:
        by_text.setdefault(entry.get("text", ""), []).append(entry)
    for text, matches in by_text.items():
        if len(matches) > 1:
            errors.append(f"reader-contract clause is duplicated in coverage: {text!r}")
        if text not in clauses:
            errors.append(f"coverage names a clause not present in reader_contract: {text!r}")

    report_entries: list[dict] = []
    mapped = 0
    untested = 0
    for text in clauses:
        matches = by_text.get(text, [])
        if not matches:
            errors.append(f"reader-contract clause has no coverage declaration: {text!r}")
            report_entries.append({"text": text, "state": "undeclared", "coverage": []})
            continue
        entry = matches[0]
        coverage = entry.get("coverage", [])
        if coverage:
            mapped += 1
            state = "mapped"
        else:
            untested += 1
            state = "untested"
            if not entry.get("untested_reason"):
                errors.append(f"untested reader-contract clause needs untested_reason: {text!r}")
        report_entries.append({"text": text, "state": state, "coverage": coverage,
                               **({"untested_reason": entry["untested_reason"]}
                                  if entry.get("untested_reason") else {})})

    return {
        "project_id": brief.get("id"),
        "status": "declared" if not errors else "invalid",
        "mapped": mapped,
        "untested": untested,
        "clauses": report_entries,
        "errors": errors,
        "verification": "not_assessed",
        "note": "Coverage mapping says how a clause is evaluated; it is not evidence that the clause succeeded.",
    }


def _all_fact_ids(project: Path) -> set[str]:
    fact_ids: set[str] = set()
    for line in (project / "canon" / "facts.jsonl").read_text(encoding="utf-8").splitlines() \
            if (project / "canon" / "facts.jsonl").exists() else []:
        if line.strip():
            fact_ids.add(json.loads(line)["id"])
    for delta_path in (project / "scenes").glob("*/state-delta.json"):
        for fact in _load(delta_path, {}).get("facts_added", []):
            if fact.get("id"):
                fact_ids.add(fact["id"])
    return fact_ids


def disclosure_report(project: Path) -> dict:
    """Validate reader-disclosure annotations and fair-play/curiosity ordering references."""
    project = Path(project)
    brief = _load(project / "brief" / "project.json", {})
    path = project / "planning" / "reader-disclosure.json"
    if not path.exists():
        return {"project_id": brief.get("id"), "status": "missing",
                "errors": ["planning/reader-disclosure.json is missing"],
                "verification": "structural_only"}
    artifact = _load(path, {})
    errors = schema.validate_named(artifact, "reader-disclosure")
    if errors:
        return {"project_id": brief.get("id"), "status": "invalid", "errors": errors,
                "verification": "structural_only"}
    if artifact.get("project_id") != brief.get("id"):
        errors.append("reader-disclosure project_id does not match brief/project.json")

    scene_ids = {path.name for path in (project / "scenes").iterdir() if path.is_dir()} \
        if (project / "scenes").exists() else set()
    fact_ids = _all_fact_ids(project)
    disclosures = artifact.get("disclosures", [])
    disclosure_by_id: dict[str, dict] = {}
    for item in disclosures:
        did = item["id"]
        if did in disclosure_by_id:
            errors.append(f"duplicate disclosure id: {did}")
        disclosure_by_id[did] = item
        if item["scene_id"] not in scene_ids:
            errors.append(f"{did} references unknown scene {item['scene_id']!r}")
        if item["fact"] not in fact_ids:
            errors.append(f"{did} references unknown fact {item['fact']!r}")

    for gap in artifact.get("curiosity_gaps", []):
        if gap["opened_in"] not in scene_ids:
            errors.append(f"{gap['id']} opens in unknown scene {gap['opened_in']!r}")
        closed = gap.get("closed_in")
        if closed is not None:
            if closed not in scene_ids:
                errors.append(f"{gap['id']} closes in unknown scene {closed!r}")
            elif scene_sort_key(closed) < scene_sort_key(gap["opened_in"]):
                errors.append(f"{gap['id']} closes before it opens")

    for surprise in artifact.get("surprises", []):
        reveal = surprise["reveal_scene"]
        if reveal not in scene_ids:
            errors.append(f"{surprise['id']} reveals in unknown scene {reveal!r}")
        setup_ids = surprise.get("setup_disclosures", [])
        if surprise.get("requires_setup") and not setup_ids:
            errors.append(f"{surprise['id']} requires setup but names no setup disclosures")
        for did in setup_ids:
            setup = disclosure_by_id.get(did)
            if setup is None:
                errors.append(f"{surprise['id']} references unknown setup disclosure {did!r}")
                continue
            if setup.get("mode") == "withheld":
                errors.append(f"{surprise['id']} uses withheld disclosure {did!r} as setup")
            if reveal in scene_ids and scene_sort_key(setup["scene_id"]) >= scene_sort_key(reveal):
                errors.append(f"{surprise['id']} setup {did!r} does not precede its reveal")

    return {
        "project_id": brief.get("id"),
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "counts": {
            "disclosures": len(disclosures),
            "curiosity_gaps": len(artifact.get("curiosity_gaps", [])),
            "surprises": len(artifact.get("surprises", [])),
        },
        "verification": "structural_only",
        "note": "Annotations support structural checks; they do not prove what a reader noticed, inferred, or remembered.",
    }
