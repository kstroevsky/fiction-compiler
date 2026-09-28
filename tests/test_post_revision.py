from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import acceptance, post_revision  # noqa: E402
from fiction_compiler.promote import promote_candidate  # noqa: E402
from tests.test_promote import PROSE, build, valid_delta, valid_spec, write_review_set  # noqa: E402


class PostRevisionEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.project = build(Path(self.tmp.name), fact_id="fact-plant")
        scene2 = self.project / "scenes" / "ch01-sc02"
        (scene2 / "candidates").mkdir(parents=True)
        (scene2 / "candidates" / "c.md").write_text(PROSE, encoding="utf-8")
        (scene2 / "spec.json").write_text(json.dumps(valid_spec("ch01-sc02")), encoding="utf-8")
        (scene2 / "state-delta.json").write_text(json.dumps(valid_delta("ch01-sc02")), encoding="utf-8")
        write_review_set(scene2)
        promote_candidate(self.project, "ch01-sc01", "c.md")
        promote_candidate(self.project, "ch01-sc02", "c.md")

        scene1 = self.project / "scenes" / "ch01-sc01"
        revised = "The brass plant marker caught the light."
        sha = hashlib.sha256(revised.encode()).hexdigest()
        (scene1 / "candidates" / "revision.md").write_text(revised, encoding="utf-8")
        write_review_set(scene1, candidate_name="revision.md", sha=sha)
        promote_candidate(self.project, "ch01-sc01", "revision.md", revision=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def evidence(self, scope: str, *, scene: str | None = "ch01-sc02", verdict: str = "pass",
                 findings: list | None = None) -> dict:
        if scope == "whole_work":
            scene = None
        packet = post_revision.packet(self.project, scope, scene)
        self.assertNotIn("error", packet)
        result = post_revision.record_evidence(
            self.project, scope, packet["packet_sha256"], "role_runner", "fresh-reviewer",
            "expert_reader", verdict, findings or [], provenance={"source": "test"}, scene_id=scene,
        )
        self.assertNotIn("error", result)
        return result

    def test_reader_packet_is_prefix_only_and_hides_plan(self) -> None:
        result = post_revision.packet(self.project, "reader", "ch01-sc02")
        self.assertNotIn("error", result)
        packet = result["packet"]
        self.assertEqual([item["scene_id"] for item in packet["segments"]], ["ch01-sc01", "ch01-sc02"])
        self.assertNotIn("spec", packet)
        self.assertNotIn("required_events", packet)

    def test_recording_clean_evidence_does_not_silently_close_scope(self) -> None:
        evidence = self.evidence("literary")
        pending = acceptance.load_index(self.project)["rechecks_required"]["ch01-sc02"]["required_scopes"]
        self.assertIn("literary", pending)
        self.assertTrue((self.project / evidence["path"]).exists())

    def test_explicit_resolution_closes_only_bound_scope(self) -> None:
        evidence = self.evidence("literary")
        resolved = post_revision.resolve_scope(
            self.project, evidence["evidence_id"], "owner", "Fresh review supports the rebased scene."
        )
        self.assertNotIn("error", resolved)
        remaining = acceptance.load_index(self.project)["rechecks_required"]["ch01-sc02"]["required_scopes"]
        self.assertNotIn("literary", remaining)
        self.assertIn("reader", remaining)

    def test_whole_work_resolution_clears_global_scope(self) -> None:
        evidence = self.evidence("whole_work")
        resolved = post_revision.resolve_scope(
            self.project, evidence["evidence_id"], "owner", "Whole-work pass reviewed after revision."
        )
        self.assertEqual(resolved["resolved_scenes"], ["ch01-sc02"])
        remaining = acceptance.load_index(self.project)["rechecks_required"]["ch01-sc02"]["required_scopes"]
        self.assertNotIn("whole_work", remaining)

    def test_nonpass_evidence_cannot_resolve_scope(self) -> None:
        evidence = self.evidence("voice", verdict="uncertain")
        result = post_revision.resolve_scope(self.project, evidence["evidence_id"], "owner", "Not resolved.")
        self.assertIn("only clean pass", result["error"])

    def test_pass_with_serious_finding_is_rejected(self) -> None:
        packet = post_revision.packet(self.project, "voice", "ch01-sc02")
        result = post_revision.record_evidence(
            self.project, "voice", packet["packet_sha256"], "role_runner", "reviewer",
            "expert_reader", "pass", [{
                "dimension": "voice", "severity": "material", "evidence": "Prose.",
                "diagnosis": "drift", "repair_layer": "prose",
            }], scene_id="ch01-sc02",
        )
        self.assertIn("pass verdict", result["error"])

    def test_stale_packet_is_rejected_after_head_change(self) -> None:
        old = post_revision.packet(self.project, "literary", "ch01-sc02")
        index = acceptance.load_index(self.project)
        index["head_acceptance"] = "0" * 64
        acceptance.atomic_write(acceptance.index_path(self.project), acceptance.canonical_json_bytes(index))
        result = post_revision.record_evidence(
            self.project, "literary", old["packet_sha256"], "role_runner", "reviewer",
            "expert_reader", "pass", [], scene_id="ch01-sc02",
        )
        self.assertIn("stale", result["error"])

    def test_status_distinguishes_completed_rechecks(self) -> None:
        for scope in ("literary", "reader", "voice"):
            evidence = self.evidence(scope)
            post_revision.resolve_scope(self.project, evidence["evidence_id"], "owner", f"Resolve {scope}.")
        evidence = self.evidence("whole_work")
        post_revision.resolve_scope(self.project, evidence["evidence_id"], "owner", "Resolve whole work.")
        status = post_revision.status(self.project)
        self.assertNotIn("ch01-sc02", status["pending_rechecks"])
        self.assertIn("ch01-sc02", status["completed_rechecks"])


if __name__ == "__main__":
    unittest.main()
