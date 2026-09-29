"""Observed prefix-reader evidence without a speculative reader-state model.

Probe definitions are durable planning artifacts. Responses are append-only run evidence bound to an
exact accepted-prose prefix and exact question set. Reports summarize observed responses descriptively;
they do not infer hidden cognition, literary quality, or target-audience success from annotations alone.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import acceptance, schema


_SCENE_ID_RE = re.compile(r"^ch([0-9]+)-sc([0-9]+)$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scene_sort_key(scene_id: str) -> tuple[int, int]:
    match = _SCENE_ID_RE.fullmatch(scene_id)
    if match is None:
        raise ValueError(f"invalid scene id {scene_id!r}")
    return int(match.group(1)), int(match.group(2))


def _load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


def _brief(project: Path) -> dict:
    path = Path(project) / "brief" / "project.json"
    return _load_json(path) if path.exists() else {}


def _plan_path(project: Path) -> Path:
    return Path(project) / "planning" / "reader-probes.json"


def _response_dir(project: Path, probe_id: str) -> Path:
    return Path(project) / ".runs" / "reader-probes" / probe_id / "responses"


def _load_plan(project: Path) -> tuple[dict | None, list[str]]:
    project = Path(project)
    path = _plan_path(project)
    if not path.exists():
        return None, ["planning/reader-probes.json is missing"]
    try:
        plan = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"reader-probes plan is unreadable: {exc}"]
    errors = schema.validate_named(plan, "reader-probes")
    brief = _brief(project)
    if plan.get("project_id") != brief.get("id"):
        errors.append("reader-probes project_id does not match brief/project.json")
    contract = set(brief.get("reader_contract", [])) if isinstance(brief.get("reader_contract"), list) else set()
    accepted = set()
    index_path = project / "canon" / "index.json"
    if index_path.exists():
        try:
            index = _load_json(index_path)
            accepted = {sid for sid in index.get("accepted_state_deltas", []) if isinstance(sid, str)}
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            errors.append(f"canon/index.json is unreadable: {exc}")
    probe_ids: list[str] = []
    question_ids: list[str] = []
    for probe in plan.get("probes", []) if isinstance(plan.get("probes"), list) else []:
        if not isinstance(probe, dict):
            continue
        probe_id = probe.get("id")
        if isinstance(probe_id, str):
            probe_ids.append(probe_id)
        after_scene = probe.get("after_scene")
        if after_scene not in accepted:
            errors.append(f"reader probe {probe_id!r} references non-accepted prefix scene {after_scene!r}")
        local_ids: list[str] = []
        for question in probe.get("questions", []) if isinstance(probe.get("questions"), list) else []:
            if not isinstance(question, dict):
                continue
            qid = question.get("id")
            if isinstance(qid, str):
                local_ids.append(qid)
                question_ids.append(qid)
            clause = question.get("contract_clause")
            if clause is not None and clause not in contract:
                errors.append(f"reader question {qid!r} references a clause not in reader_contract")
        if len(local_ids) != len(set(local_ids)):
            errors.append(f"reader probe {probe_id!r} has duplicate question ids")
    if len(probe_ids) != len(set(probe_ids)):
        errors.append("reader probe ids must be unique")
    if len(question_ids) != len(set(question_ids)):
        errors.append("reader question ids must be unique across the project")
    return plan, errors


def validation_errors(project: Path) -> list[str]:
    """Validate a reader-probe plan if present; absence is allowed until a project opts in."""
    project = Path(project)
    if not _plan_path(project).exists():
        return []
    _, errors = _load_plan(project)
    return errors


def question_bindings(project: Path) -> dict[str, str | None]:
    """Return question id -> declared reader-contract clause for coverage-reference validation."""
    plan, errors = _load_plan(Path(project))
    if plan is None or errors:
        return {}
    return {
        question["id"]: question.get("contract_clause")
        for probe in plan["probes"]
        for question in probe["questions"]
    }


def _probe(plan: dict, probe_id: str) -> dict | None:
    return next((item for item in plan.get("probes", []) if item.get("id") == probe_id), None)


def _accepted_prefix(project: Path, after_scene: str) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    try:
        index = _load_json(Path(project) / "canon" / "index.json")
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], [f"cannot read canon index: {exc}"]
    scene_ids = [sid for sid in index.get("accepted_state_deltas", []) if isinstance(sid, str)]
    if after_scene not in scene_ids:
        return [], [f"reader probe prefix scene {after_scene!r} is not accepted"]
    target = _scene_sort_key(after_scene)
    prefix: list[dict] = []
    for scene_id in sorted(scene_ids, key=_scene_sort_key):
        if _scene_sort_key(scene_id) > target:
            continue
        path = Path(project) / "manuscript" / "chapters" / f"{scene_id}.md"
        if not path.is_file():
            errors.append(f"accepted prefix manuscript is missing {scene_id}.md")
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"accepted prefix manuscript {scene_id}.md is not UTF-8")
            continue
        prefix.append({"scene_id": scene_id, "sha256": acceptance.sha256_bytes(raw), "text": text})
    return prefix, errors


def packet(project: Path, probe_id: str) -> dict:
    """Return only reader-visible accepted prefix + questions, withholding planning annotations."""
    project = Path(project)
    plan, errors = _load_plan(project)
    if plan is None or errors:
        return {"error": "invalid reader-probe plan", "details": errors}
    probe = _probe(plan, probe_id)
    if probe is None:
        return {"error": f"unknown reader probe {probe_id!r}"}
    prefix, prefix_errors = _accepted_prefix(project, probe["after_scene"])
    if prefix_errors:
        return {"error": "invalid accepted reader prefix", "details": prefix_errors}
    questions = []
    for question in probe["questions"]:
        visible = {
            "id": question["id"],
            "kind": question["kind"],
            "prompt": question["prompt"],
            "response_mode": question["response_mode"],
        }
        if "options" in question:
            visible["options"] = question["options"]
        questions.append(visible)
    value = {
        "schema_version": 1,
        "project_id": plan["project_id"],
        "probe_id": probe_id,
        "after_scene": probe["after_scene"],
        "segments": prefix,
        "questions": questions,
        "instructions": (
            "Read only the prose shown here and answer from your current reading experience. Do not use "
            "later scenes, project plans, hidden canon, authorial intent notes, or outside summaries."
        ),
    }
    digest = acceptance.sha256_bytes(acceptance.canonical_json_bytes(value))
    return {"packet_sha256": digest, "packet": value}


def _validate_answers(probe: dict, answers: object) -> list[str]:
    if not isinstance(answers, list):
        return ["answers must be an array"]
    questions = {item["id"]: item for item in probe["questions"]}
    seen: list[str] = []
    errors: list[str] = []
    for answer in answers:
        if not isinstance(answer, dict):
            errors.append("each answer must be an object")
            continue
        qid = answer.get("question_id")
        if not isinstance(qid, str) or qid not in questions:
            errors.append(f"answer references unknown question {qid!r}")
            continue
        seen.append(qid)
        question = questions[qid]
        mode = question["response_mode"]
        if mode == "free_text":
            if not isinstance(answer.get("text"), str) or not answer["text"].strip():
                errors.append(f"free-text question {qid!r} needs non-empty text")
            if "selected_option" in answer or "scale" in answer:
                errors.append(f"free-text question {qid!r} cannot carry choice/scale fields")
        elif mode == "single_choice":
            if answer.get("selected_option") not in question.get("options", []):
                errors.append(f"single-choice question {qid!r} needs one declared option")
            if "scale" in answer:
                errors.append(f"single-choice question {qid!r} cannot carry a scale")
        else:
            scale = answer.get("scale")
            if isinstance(scale, bool) or not isinstance(scale, int) or not 1 <= scale <= 5:
                errors.append(f"scale question {qid!r} needs an integer from 1 to 5")
            if "selected_option" in answer:
                errors.append(f"scale question {qid!r} cannot carry a selected option")
    if len(seen) != len(set(seen)):
        errors.append("a response cannot answer the same question twice")
    missing = sorted(set(questions) - set(seen))
    if missing:
        errors.append(f"response is missing questions: {', '.join(missing)}")
    return errors


def _load_response(path: Path) -> tuple[dict | None, list[str]]:
    try:
        value = _load_json(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, [f"unreadable response {path.name}: {exc}"]
    errors = schema.validate_named(value, "reader-probe-response")
    identity = {key: value[key] for key in value if key not in {"response_id", "recorded_at"}}
    expected_id = "readerresp-" + acceptance.sha256_bytes(acceptance.canonical_json_bytes(identity))
    if value.get("response_id") != expected_id:
        errors.append("response_id does not match response content")
    if path.stem != value.get("response_id"):
        errors.append("response_id does not match response filename")
    packet_value = value.get("packet", {})
    packet_hash = acceptance.sha256_bytes(acceptance.canonical_json_bytes(packet_value))
    if packet_hash != value.get("packet_sha256"):
        errors.append("packet_sha256 does not match embedded reader packet")
    return value, errors


def record_response(project: Path, probe_id: str, packet_sha256: str, respondent_kind: str,
                    respondent_id: str, cohort_kind: str, answers: list[dict],
                    provenance: dict | None = None) -> dict:
    """Persist one immutable observed reader response bound to the current exact prefix packet."""
    project = Path(project)
    current = packet(project, probe_id)
    if "error" in current:
        return current
    if packet_sha256 != current["packet_sha256"]:
        return {"error": "reader-probe packet is stale; rebuild it before recording a response",
                "current_packet_sha256": current["packet_sha256"]}
    plan, _ = _load_plan(project)
    assert plan is not None
    probe = _probe(plan, probe_id)
    assert probe is not None
    answer_errors = _validate_answers(probe, answers)
    if answer_errors:
        return {"error": "invalid reader-probe answers", "details": answer_errors}
    if respondent_kind == "model" and cohort_kind != "model-proxy":
        return {"error": "model respondents must use cohort_kind='model-proxy'"}
    if respondent_kind == "human" and cohort_kind == "model-proxy":
        return {"error": "human respondents cannot use cohort_kind='model-proxy'"}
    if provenance is not None and not isinstance(provenance, dict):
        return {"error": "provenance must be an object"}
    response_dir = _response_dir(project, probe_id)
    for path in sorted(response_dir.glob("*.json")):
        existing, existing_errors = _load_response(path)
        if existing_errors:
            return {"error": "existing reader response is invalid", "details": existing_errors}
        if existing is not None and existing.get("respondent_id") == respondent_id:
            return {"error": "one respondent may record at most one response per reader probe"}
    identity = {
        "schema_version": 1,
        "project_id": current["packet"]["project_id"],
        "probe_id": probe_id,
        "packet_sha256": packet_sha256,
        "packet": current["packet"],
        "respondent_kind": respondent_kind,
        "respondent_id": respondent_id,
        "cohort_kind": cohort_kind,
        "answers": answers,
        "provenance": dict(provenance or {}),
    }
    response_id = "readerresp-" + acceptance.sha256_bytes(acceptance.canonical_json_bytes(identity))
    record = {**identity, "response_id": response_id, "recorded_at": _now()}
    validation = schema.validate_named(record, "reader-probe-response")
    if validation:
        return {"error": "invalid reader-probe response: " + "; ".join(validation)}
    path = response_dir / f"{response_id}.json"
    acceptance.atomic_write(path, acceptance.canonical_json_bytes(record))
    return {"status": "recorded", "path": str(path.relative_to(project)), **record}


def _mode_summary(question: dict, answers: list[dict]) -> dict:
    mode = question["response_mode"]
    if mode == "single_choice":
        counts = Counter(answer["selected_option"] for answer in answers)
        return {"responses": len(answers), "choices": dict(sorted(counts.items()))}
    if mode == "scale_1_5":
        values = [answer["scale"] for answer in answers]
        counts = Counter(values)
        return {
            "responses": len(values),
            "distribution": {str(key): counts.get(key, 0) for key in range(1, 6)},
            "mean": statistics.fmean(values) if values else None,
        }
    return {"responses": len(answers), "semantic_summary": "not_computed"}


def report(project: Path) -> dict:
    """Summarize fresh/stale observed responses without converting them into a quality verdict."""
    project = Path(project)
    plan, errors = _load_plan(project)
    if plan is None:
        return {"status": "missing", "errors": errors, "evidence_status": "no_probe_plan"}
    if errors:
        return {"status": "invalid", "errors": errors, "evidence_status": "invalid_probe_plan"}
    report_errors: list[str] = []
    probe_reports: list[dict] = []
    total_fresh = 0
    total_stale = 0
    for probe in plan["probes"]:
        current = packet(project, probe["id"])
        if "error" in current:
            report_errors.append(f"{probe['id']}: {current['error']}")
            continue
        fresh: list[dict] = []
        stale = 0
        for path in sorted(_response_dir(project, probe["id"]).glob("*.json")):
            response, response_errors = _load_response(path)
            if response_errors:
                report_errors.extend(f"{probe['id']}: {error}" for error in response_errors)
                continue
            assert response is not None
            if response.get("packet_sha256") != current["packet_sha256"]:
                stale += 1
                continue
            answer_errors = _validate_answers(probe, response.get("answers"))
            if answer_errors:
                report_errors.extend(f"{probe['id']}: {error}" for error in answer_errors)
                continue
            fresh.append(response)
        total_fresh += len(fresh)
        total_stale += stale
        question_reports: list[dict] = []
        for question in probe["questions"]:
            all_answers = [
                next(answer for answer in response["answers"] if answer["question_id"] == question["id"])
                for response in fresh
            ]
            by_cohort: dict[str, list[dict]] = defaultdict(list)
            for response, answer in zip(fresh, all_answers):
                by_cohort[response["cohort_kind"]].append(answer)
            question_reports.append({
                "question_id": question["id"],
                "kind": question["kind"],
                "response_mode": question["response_mode"],
                "contract_clause": question.get("contract_clause"),
                "overall": _mode_summary(question, all_answers),
                "by_cohort": {
                    cohort: _mode_summary(question, answers)
                    for cohort, answers in sorted(by_cohort.items())
                },
            })
        probe_reports.append({
            "probe_id": probe["id"],
            "after_scene": probe["after_scene"],
            "packet_sha256": current["packet_sha256"],
            "fresh_responses": len(fresh),
            "stale_responses": stale,
            "respondent_kinds": dict(sorted(Counter(item["respondent_kind"] for item in fresh).items())),
            "cohorts": dict(sorted(Counter(item["cohort_kind"] for item in fresh).items())),
            "questions": question_reports,
        })
    if report_errors:
        status = "invalid"
        evidence_status = "invalid_reader_evidence"
    elif total_fresh:
        status = "valid"
        evidence_status = "descriptive_reader_evidence_available"
    else:
        status = "valid"
        evidence_status = "probe_plan_without_responses"
    return {
        "project_id": plan["project_id"],
        "status": status,
        "evidence_status": evidence_status,
        "fresh_responses": total_fresh,
        "stale_responses": total_stale,
        "probes": probe_reports,
        "errors": report_errors,
        "note": (
            "This report summarizes recorded responses to exact accepted prefixes. Free-text meaning is "
            "not inferred automatically; model-proxy responses stay separate from human cohorts; no "
            "reader-contract or literary-quality verdict is derived from response counts alone."
        ),
    }
