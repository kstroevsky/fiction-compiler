"""Reader-facing structural evidence without pretending to model comprehension.

The project can declare where each reader-contract clause is checked (or explicitly untested) and
bind discourse-plan revelations to canonical facts available to the reader.  Revelations that are
choices, recognitions, or other non-factual discourse moves remain explicitly non-factual rather than
being forced into the fact ledger.  These reports only verify annotation structure and references.
They do not infer what a real reader noticed, believed, remembered, or preferred; those remain
measured reader/critic questions.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import reader_probe, schema
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
        reader_questions = reader_probe.question_bindings(project)
        for binding in coverage:
            if binding.get("kind") != "reader-question":
                continue
            ref = binding.get("ref")
            if ref not in reader_questions:
                errors.append(f"reader-question coverage references unknown probe question {ref!r}")
            elif reader_questions[ref] is not None and reader_questions[ref] != text:
                errors.append(
                    f"reader-question {ref!r} is declared for a different reader-contract clause"
                )
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
    """Validate disclosure annotations against discourse-plan revelations and canonical facts."""
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
    discourse = _load(project / "planning" / "discourse-plan.json", {})
    revelation_by_id: dict[str, dict] = {}
    for item in discourse.get("revelations", []) if isinstance(discourse.get("revelations", []), list) else []:
        if not isinstance(item, dict):
            errors.append("discourse-plan revelation must be an object")
            continue
        rid = item.get("id")
        scene_id = item.get("scene")
        if not isinstance(rid, str) or not rid:
            errors.append("discourse-plan revelation needs a non-empty id")
            continue
        if rid in revelation_by_id:
            errors.append(f"duplicate discourse-plan revelation id: {rid}")
        revelation_by_id[rid] = item
        if scene_id not in scene_ids:
            errors.append(f"discourse-plan revelation {rid!r} references unknown scene {scene_id!r}")

    disclosures = artifact.get("disclosures", [])
    disclosure_by_id: dict[str, dict] = {}
    fact_bound_revelations: set[str] = set()
    for item in disclosures:
        did = item["id"]
        if did in disclosure_by_id:
            errors.append(f"duplicate disclosure id: {did}")
        disclosure_by_id[did] = item
        if item["scene_id"] not in scene_ids:
            errors.append(f"{did} references unknown scene {item['scene_id']!r}")
        if item["fact"] not in fact_ids:
            errors.append(f"{did} references unknown fact {item['fact']!r}")
        source = item["source_revelation"]
        revelation = revelation_by_id.get(source)
        if revelation is None:
            errors.append(f"{did} references unknown discourse revelation {source!r}")
        else:
            fact_bound_revelations.add(source)
            if revelation.get("scene") != item["scene_id"]:
                errors.append(
                    f"{did} scene {item['scene_id']!r} does not match source revelation "
                    f"{source!r} scene {revelation.get('scene')!r}"
                )

    non_fact_revelations: set[str] = set()
    for item in artifact.get("non_fact_revelations", []):
        rid = item["revelation_id"]
        if rid in non_fact_revelations:
            errors.append(f"duplicate non-factual revelation declaration: {rid}")
        non_fact_revelations.add(rid)
        if rid not in revelation_by_id:
            errors.append(f"non-factual declaration references unknown discourse revelation {rid!r}")
        if rid in fact_bound_revelations:
            errors.append(f"discourse revelation {rid!r} is both fact-bound and declared non-factual")

    for rid in revelation_by_id:
        if rid not in fact_bound_revelations and rid not in non_fact_revelations:
            errors.append(
                f"discourse revelation {rid!r} has no fact disclosure or explicit non-factual declaration"
            )

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
            "discourse_revelations": len(revelation_by_id),
            "fact_bound_revelations": len(fact_bound_revelations),
            "non_fact_revelations": len(non_fact_revelations),
            "disclosures": len(disclosures),
            "curiosity_gaps": len(artifact.get("curiosity_gaps", [])),
            "surprises": len(artifact.get("surprises", [])),
        },
        "verification": "structural_only",
        "note": (
            "Fact bindings and non-factual declarations account for planned revelations structurally; "
            "they do not prove what a reader noticed, inferred, understood, or remembered."
        ),
    }
