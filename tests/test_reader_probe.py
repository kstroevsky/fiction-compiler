from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import reader, reader_probe, tools  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def make_project(root: Path) -> Path:
    project = root / "proj"
    write_json(project / "brief" / "project.json", {
        "id": "proj",
        "reader_contract": ["ambiguity survives"],
    })
    write_json(project / "canon" / "index.json", {
        "accepted_state_deltas": ["ch01-sc01", "ch01-sc02"],
    })
    chapters = project / "manuscript" / "chapters"
    chapters.mkdir(parents=True, exist_ok=True)
    (chapters / "ch01-sc01.md").write_text("Opening prefix. The stranger waits.\n", encoding="utf-8")
    (chapters / "ch01-sc02.md").write_text("LATER SECRET OUTCOME.\n", encoding="utf-8")
    write_json(project / "planning" / "reader-probes.json", {
        "project_id": "proj",
        "probes": [{
            "id": "probe-opening",
            "after_scene": "ch01-sc01",
            "questions": [
                {
                    "id": "rq-expect",
                    "kind": "expectation",
                    "prompt": "What do you expect next?",
                    "response_mode": "free_text",
                    "note": "HIDDEN ANALYSIS NOTE",
                },
                {
                    "id": "rq-role",
                    "kind": "ambiguity",
                    "prompt": "Which role currently seems most plausible?",
                    "response_mode": "single_choice",
                    "options": ["threat", "victim", "unclear"],
                    "contract_clause": "ambiguity survives",
                },
                {
                    "id": "rq-certainty",
                    "kind": "ambiguity",
                    "prompt": "How certain are you? 1=low, 5=high.",
                    "response_mode": "scale_1_5",
                },
            ],
        }],
    })
    write_json(project / "brief" / "contract-coverage.json", {
        "project_id": "proj",
        "clauses": [{
            "text": "ambiguity survives",
            "coverage": [{"kind": "reader-question", "ref": "rq-role"}],
        }],
    })
    return project


def human_answers(scale: int = 2) -> list[dict]:
    return [
        {"question_id": "rq-expect", "text": "The narrator will keep watching."},
        {"question_id": "rq-role", "selected_option": "unclear"},
        {"question_id": "rq-certainty", "scale": scale},
    ]


class ReaderProbeTests(unittest.TestCase):
    def test_packet_contains_only_accepted_prefix_and_reader_visible_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            packet = reader_probe.packet(project, "probe-opening")
            self.assertNotIn("error", packet, packet)
            self.assertEqual([item["scene_id"] for item in packet["packet"]["segments"]], ["ch01-sc01"])
            encoded = json.dumps(packet["packet"])
            self.assertNotIn("LATER SECRET OUTCOME", encoded)
            self.assertNotIn("HIDDEN ANALYSIS NOTE", encoded)
            self.assertNotIn("ambiguity survives", encoded)

    def test_response_modes_and_cohorts_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            packet = reader_probe.packet(project, "probe-opening")
            invalid = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-1",
                "target-audience", [
                    {"question_id": "rq-expect", "scale": 3},
                    {"question_id": "rq-role", "selected_option": "villain"},
                    {"question_id": "rq-certainty", "scale": 9},
                ],
            )
            self.assertEqual(invalid["error"], "invalid reader-probe answers")
            self.assertGreaterEqual(len(invalid["details"]), 3)

            wrong_cohort = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "model", "model-1",
                "target-audience", human_answers(),
            )
            self.assertIn("model respondents", wrong_cohort["error"])

    def test_report_separates_target_audience_and_model_proxy_descriptively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            packet = reader_probe.packet(project, "probe-opening")
            first = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-1",
                "target-audience", human_answers(2), {"session": "pilot-a"},
            )
            self.assertEqual(first["status"], "recorded", first)
            second = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "model", "model-1",
                "model-proxy", [
                    {"question_id": "rq-expect", "text": "He may ask for help."},
                    {"question_id": "rq-role", "selected_option": "threat"},
                    {"question_id": "rq-certainty", "scale": 4},
                ], {"provider": "test-model"},
            )
            self.assertEqual(second["status"], "recorded", second)

            report = reader_probe.report(project)
            self.assertEqual(report["status"], "valid", report["errors"])
            self.assertEqual(report["evidence_status"], "descriptive_reader_evidence_available")
            self.assertEqual(report["fresh_responses"], 2)
            probe = report["probes"][0]
            self.assertEqual(probe["respondent_kinds"], {"human": 1, "model": 1})
            self.assertEqual(probe["cohorts"], {"model-proxy": 1, "target-audience": 1})
            questions = {item["question_id"]: item for item in probe["questions"]}
            self.assertEqual(questions["rq-expect"]["overall"]["semantic_summary"], "not_computed")
            self.assertEqual(questions["rq-role"]["by_cohort"]["target-audience"]["choices"],
                             {"unclear": 1})
            self.assertEqual(questions["rq-certainty"]["overall"]["mean"], 3.0)

    def test_prefix_change_makes_existing_response_stale_and_rejects_old_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            packet = reader_probe.packet(project, "probe-opening")
            recorded = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-1",
                "general-reader", human_answers(),
            )
            self.assertEqual(recorded["status"], "recorded")
            chapter = project / "manuscript" / "chapters" / "ch01-sc01.md"
            chapter.write_text("Changed accepted prefix.\n", encoding="utf-8")

            stale_record = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-2",
                "general-reader", human_answers(),
            )
            self.assertIn("stale", stale_record["error"])
            report = reader_probe.report(project)
            self.assertEqual(report["status"], "valid")
            self.assertEqual(report["fresh_responses"], 0)
            self.assertEqual(report["stale_responses"], 1)

    def test_one_respondent_cannot_duplicate_a_probe_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            packet = reader_probe.packet(project, "probe-opening")
            reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-1",
                "expert", human_answers(),
            )
            duplicate = reader_probe.record_response(
                project, "probe-opening", packet["packet_sha256"], "human", "reader-1",
                "expert", human_answers(3),
            )
            self.assertIn("at most one response", duplicate["error"])

    def test_contract_coverage_reader_question_ref_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = make_project(Path(tmp))
            coverage = reader.contract_coverage(project)
            self.assertEqual(coverage["status"], "declared", coverage["errors"])
            self.assertEqual(coverage["mapped"], 1)

            artifact_path = project / "brief" / "contract-coverage.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            artifact["clauses"][0]["coverage"][0]["ref"] = "rq-missing"
            write_json(artifact_path, artifact)
            invalid = reader.contract_coverage(project)
            self.assertEqual(invalid["status"], "invalid")
            self.assertTrue(any("unknown probe question" in error for error in invalid["errors"]))

    def test_forecourt_plan_is_valid_but_has_no_fabricated_responses(self) -> None:
        project = ROOT / "projects" / "forecourt"
        self.assertEqual(reader_probe.validation_errors(project), [])
        report = reader_probe.report(project)
        self.assertEqual(report["status"], "valid", report["errors"])
        self.assertEqual(report["evidence_status"], "probe_plan_without_responses")
        self.assertEqual(report["fresh_responses"], 0)
        coverage = reader.contract_coverage(project)
        self.assertEqual(coverage["status"], "declared", coverage["errors"])
        self.assertEqual(coverage["mapped"], 2)

    def test_tool_registry_exposes_reader_probe_workflow(self) -> None:
        descriptors = {item["name"]: item for item in tools.list_tools()}
        for name in ("reader_probe_packet", "record_reader_probe_response", "reader_probe_report"):
            self.assertIn(name, descriptors)


if __name__ == "__main__":
    unittest.main()
