"""Read-only analysis of how the pipeline was actually used in the six stored projects.

Reads promotion manifests, critiques, traces, tournament records and briefs. Writes only the sibling
record-analysis.json. Does not modify any project file. Run from anywhere:

    python3 docs/audits/2026-09-28/evidence/record_analysis.py
"""
import collections
import datetime as dt
import glob
import json
import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
from fiction_compiler import critique  # noqa: E402

LITERARY = {"adversarial-reader", "style-editor", "character-simulator", "continuity-auditor"}
PROBE_TERMS = ["transforming consciousness", "proof can settle", "resolved by proof", "premise probe",
               "probe's flagged risk"]
LINT_TERMS = ["told emotion", "no cliche", "adverbial dialogue", "emotion earned through behavior",
              "never named"]


def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def scenes():
    rows = []
    for dec_path in sorted(glob.glob(str(ROOT / "projects/*/decisions/promote-*.json"))):
        dec = load(dec_path)
        project = pathlib.Path(dec_path).parts[-3]
        scene_id = dec["scene_id"]
        promoted = os.path.basename(dec["candidate"])
        parent = re.sub(r"-r\d+\.md$", ".md", promoted)
        scene_dir = ROOT / "projects" / project / "scenes" / scene_id
        verdicts = collections.defaultdict(dict)
        for path in sorted((scene_dir / "critiques").glob("*.json")):
            c = load(path)
            verdicts[os.path.basename(str(c.get("candidate")))][c.get("critic")] = c.get("verdict")
        on_promoted = sorted(k for k in verdicts.get(promoted, {}) if k in LITERARY)
        lineage = sorted(k for k, v in verdicts.get(parent, {}).items()
                         if parent != promoted and k in LITERARY and v != "pass" and k not in on_promoted)
        sibling = sorted({k for cand, m in verdicts.items() if cand not in (promoted, parent)
                          for k, v in m.items() if k in LITERARY and v != "pass" and k not in on_promoted})
        status = critique.scene_status(ROOT / "projects" / project, scene_id, promoted)
        rows.append({
            "project": project, "scene": scene_id, "promoted": promoted,
            "gate_era_manifest": bool(dec.get("binding_critiques")),
            "passes_current_gate": status["audit_gate"]["ready"],
            "current_gate_reasons": status["audit_gate"]["reasons"],
            "literary_critics_on_promoted_bytes": on_promoted,
            "unreviewed_parent_dissent": lineage,
            "unreviewed_sibling_dissent": sibling,
            "prose_audit_present": any("prose-audit" in m for m in verdicts.values()),
            "revision_log_present": (scene_dir / "revision-log.jsonl").exists(),
            "human_gate_required": (dec.get("human_gate") or {}).get("required"),
        })
    return rows


def tournaments():
    out = []
    for path in sorted(glob.glob(str(ROOT / "projects/*/.runs/tournament/*/*/record.json"))):
        rec = load(path)
        labels = rec.get("blind_labels", {})
        letters = {cid: re.fullmatch(r"candidate-([a-z])\.md", cid) for cid in labels}
        identity = all(m.group(1).upper() == labels[cid] for cid, m in letters.items() if m)
        out.append({"record": str(pathlib.Path(path).relative_to(ROOT)),
                    "selection_basis": rec.get("selection_basis"),
                    "blind_labels": labels,
                    "labels_equal_filename_letter": identity,
                    "recommendation": rec.get("recommendation")})
    return out


def traces():
    events = collections.Counter()
    gaps = []
    for path in sorted(glob.glob(str(ROOT / "projects/*/.runs/trace/*.jsonl"))):
        rows = [json.loads(line) for line in pathlib.Path(path).read_text().splitlines() if line.strip()]
        events.update(r["event"] for r in rows)
        literary = [r for r in rows if r.get("critic") in LITERARY]
        times = [dt.datetime.fromisoformat(r["ts"]) for r in literary]
        first_six = times[:6]
        if len(first_six) >= 2:
            gaps.append({"trace": str(pathlib.Path(path).relative_to(ROOT)),
                         "first_six_literary_records_span_s": round((first_six[-1] - first_six[0]).total_seconds(), 1),
                         "gaps_s": [round((b - a).total_seconds(), 1) for a, b in zip(first_six, first_six[1:])]})
    return {"event_counts": dict(events), "vendor_critique_events": events.get("vendor_critique", 0),
            "literary_record_timing": gaps}


def briefs():
    out = []
    for path in sorted(glob.glob(str(ROOT / "projects/*/brief"))):
        project = pathlib.Path(path).parts[-2]
        if project == "_template":
            continue
        text = " ".join(p.read_text(encoding="utf-8").lower() for p in pathlib.Path(path).glob("*"))
        out.append({"project": project,
                    "premise_probe_vocabulary": [t for t in PROBE_TERMS if t in text],
                    "lint_category_constraints": [t for t in LINT_TERMS if t in text]})
    return out


def endings():
    """Final paragraph of each project's last accepted scene (for the cross-project template check)."""
    out = []
    for index_path in sorted(glob.glob(str(ROOT / "projects/*/canon/index.json"))):
        project_dir = pathlib.Path(index_path).parents[1]
        accepted = load(index_path).get("accepted_state_deltas", [])
        if not accepted or project_dir.name == "_template":
            continue
        last = sorted(accepted)[-1]
        text = (project_dir / "manuscript" / "chapters" / f"{last}.md").read_text(encoding="utf-8")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        out.append({"project": project_dir.name, "scene": last,
                    "complete": (project_dir / "manuscript" / "manuscript.md").exists(),
                    "final_paragraph": paragraphs[-1]})
    return out


def plan_layer():
    """How many plans exist per scene, and what varies between candidates."""
    specs = sorted(glob.glob(str(ROOT / "projects/*/scenes/*/spec.json")))
    strategies = [len(load(p).get("candidate_strategies", []) or []) for p in specs]
    return {"scene_specs": len(specs),
            "alternative_plans_per_scene": "none: the scene schema holds exactly one spec per scene",
            "specs_with_candidate_strategies": sum(1 for n in strategies if n),
            "note": "candidate_strategies vary prose realization of the single plan, not the plan itself"}


def main():
    rows = scenes()
    gated = [r for r in rows if r["gate_era_manifest"]]
    single = [r for r in gated if len(r["literary_critics_on_promoted_bytes"]) == 1]
    summary = {
        "accepted_scenes": len(rows),
        "accepted_but_failing_current_gate": [f"{r['project']}/{r['scene']}" for r in rows if not r["passes_current_gate"]],
        "gate_era_promotions": len(gated),
        "gate_era_with_one_literary_critic_on_promoted_bytes": len(single),
        "gate_era_with_unreviewed_parent_dissent": sum(bool(r["unreviewed_parent_dissent"]) for r in gated),
        "gate_era_with_unreviewed_sibling_dissent": sum(bool(r["unreviewed_sibling_dissent"]) for r in gated),
        "scenes_with_prose_audit": sum(r["prose_audit_present"] for r in rows),
        "scenes_with_revision_log": sum(r["revision_log_present"] for r in rows),
        "promoted_candidates_that_are_revisions": sum(bool(re.search(r"-r\d+\.md$", r["promoted"])) for r in rows),
        "manifests_requiring_human_gate": sum(bool(r["human_gate_required"]) for r in rows),
    }
    result = {"summary": summary, "scenes": rows, "tournaments": tournaments(), "traces": traces(), "briefs": briefs(),
              "endings": endings(), "plan_layer": plan_layer()}
    out = pathlib.Path(__file__).with_name("record-analysis.json")
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
