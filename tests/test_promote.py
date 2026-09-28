from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import acceptance, assemble, integrity, promote, state  # noqa: E402
from fiction_compiler.promote import promote_candidate  # noqa: E402

PROSE = "Prose."
PROSE_SHA = hashlib.sha256(PROSE.encode("utf-8")).hexdigest()


def valid_spec(scene_id: str = "ch01-sc01") -> dict:
    return {
        "id": scene_id,
        "chapter": scene_id.split("-")[0],
        "pov": "",
        "participants": [],
        "purpose": [],
        "entry_state": [],
        "desire": "",
        "conflict": "",
        "turn": "",
        "exit_state": [],
        "required_events": [],
        "forbidden_moves": [],
    }


def valid_delta(scene_id: str = "ch01-sc01", *, fact_id: str | None = None) -> dict:
    facts = [{"id": fact_id, "text": f"{fact_id} is true"}] if fact_id else []
    return {
        "scene_id": scene_id,
        "facts_added": facts,
        "facts_removed": [],
        "knowledge_changes": [],
        "relationship_changes": [],
        "promises_opened": [],
        "promises_closed": [],
    }


def _provenance(sha: str, role: str = "style-editor") -> dict:
    return {
        "source": "role_runner",
        "run_id": "test-run",
        "role": role,
        "vendor": "offline",
        "model": "fixture-model",
        "candidate_sha256": sha,
        "packet_sha256": hashlib.sha256(b"fixture-packet").hexdigest(),
    }


def _critique(**fields) -> str:
    base = {
        "candidate": "c.md",
        "candidate_sha256": PROSE_SHA,
        "critic": "style-editor",
        "audit_class": "literary",
        "verdict": "pass",
        "findings": [],
        "confidence": 0.9,
        "provenance": _provenance(PROSE_SHA),
    }
    base.update(fields)
    return json.dumps(base)


def write_review_set(scene: Path, *, candidate_name: str = "c.md", sha: str = PROSE_SHA) -> None:
    crit = scene / "critiques"
    crit.mkdir(parents=True, exist_ok=True)
    (crit / "style-editor.json").write_text(
        _critique(candidate=candidate_name, candidate_sha256=sha,
                  provenance=_provenance(sha)), encoding="utf-8"
    )


def build(root: Path, *, scene_id: str = "ch01-sc01", audits: bool = True,
          fact_id: str | None = None) -> Path:
    project = root / "proj"
    scene = project / "scenes" / scene_id
    (scene / "candidates").mkdir(parents=True)
    (scene / "candidates" / "c.md").write_text(PROSE, encoding="utf-8")
    (scene / "spec.json").write_text(json.dumps(valid_spec(scene_id)), encoding="utf-8")
    (scene / "state-delta.json").write_text(
        json.dumps(valid_delta(scene_id, fact_id=fact_id)), encoding="utf-8"
    )
    if audits:
        write_review_set(scene)
    (project / "canon").mkdir(parents=True)
    (project / "canon" / "index.json").write_text(
        json.dumps({"accepted_state_deltas": []}), encoding="utf-8"
    )
    return project


class PromoteTests(unittest.TestCase):
    def test_happy_path_commits_snapshot_then_materializes_views(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            result = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertFalse(result["idempotent"])
            index = acceptance.load_index(project)
            self.assertEqual(index["accepted_state_deltas"], ["ch01-sc01"])
            self.assertEqual(index["head_acceptance"], result["acceptance_object"])
            self.assertEqual(index["acceptance_objects"]["ch01-sc01"], result["acceptance_object"])
            snapshot = acceptance.load_object(project, result["acceptance_object"])
            self.assertEqual(acceptance.frozen_bytes(snapshot, "candidate"), PROSE.encode())
            self.assertEqual(snapshot["candidate"]["sha256"], PROSE_SHA)
            self.assertEqual(snapshot["review_policy"]["id"], "review-policy@2")
            self.assertTrue(snapshot["binding_critiques"])
            self.assertEqual(integrity.verify_report(project)["status"], "verified")

    def test_full_scene_schema_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "scenes" / "ch01-sc01" / "spec.json").write_text(
                json.dumps({"id": "ch01-sc01"}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "spec.json is invalid"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_missing_delta_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            (project / "scenes" / "ch01-sc01" / "state-delta.json").unlink()
            with self.assertRaisesRegex(ValueError, "state-delta.json is required"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_literary_review_requires_runtime_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            review = project / "scenes" / "ch01-sc01" / "critiques" / "style-editor.json"
            data = json.loads(review.read_text())
            data.pop("provenance")
            review.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "runtime role-runner provenance"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_stale_literary_review_is_not_credited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            review = project / "scenes" / "ch01-sc01" / "critiques" / "style-editor.json"
            data = json.loads(review.read_text())
            stale = hashlib.sha256(b"older bytes").hexdigest()
            data["candidate_sha256"] = stale
            data["provenance"]["candidate_sha256"] = stale
            review.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not bound to the frozen candidate bytes"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_candidate_must_stay_inside_scene_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            outside = Path(tmp) / "outside.md"
            outside.write_text(PROSE, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "scene's candidates directory"):
                promote_candidate(project, "ch01-sc01", str(outside))


class AcceptanceIntegrityTests(unittest.TestCase):
    def test_live_view_edits_do_not_change_authoritative_replay_or_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp), fact_id="fact-original")
            promote_candidate(project, "ch01-sc01", "c.md")
            delta_path = project / "scenes" / "ch01-sc01" / "state-delta.json"
            delta_path.write_text(json.dumps(valid_delta(fact_id="fact-tampered")), encoding="utf-8")
            chapter = project / "manuscript" / "chapters" / "ch01-sc01.md"
            chapter.write_text("tampered manuscript", encoding="utf-8")

            replayed = state.reconstruct_state_before(project, "ch01-sc02")
            self.assertTrue(replayed.fact_exists("fact-original"))
            self.assertFalse(replayed.fact_exists("fact-tampered"))
            assembled = assemble.assemble(project)
            manuscript = (project / assembled["manuscript"]).read_text(encoding="utf-8")
            self.assertIn(PROSE, manuscript)
            self.assertNotIn("tampered manuscript", manuscript)
            report = integrity.verify_report(project)
            self.assertEqual(report["status"], "invalid")
            self.assertTrue(any("state-delta.json differs" in e for e in report["view_errors"]))

    def test_acceptance_object_tamper_is_authority_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            result = promote_candidate(project, "ch01-sc01", "c.md")
            object_path = acceptance.object_path(project, result["acceptance_object"])
            object_path.write_bytes(object_path.read_bytes() + b" ")
            report = integrity.verify_report(project)
            self.assertEqual(report["status"], "invalid")
            self.assertTrue(any("content-hash mismatch" in e for e in report["authority_errors"]))

    def test_mutable_inputs_changed_during_validation_are_refused(self) -> None:
        for relative in ("candidates/c.md", "spec.json", "state-delta.json"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                project = build(Path(tmp))
                target = project / "scenes" / "ch01-sc01" / relative
                real_gate = promote._policy_gate

                def mutate_after_gate(*args, **kwargs):
                    result = real_gate(*args, **kwargs)
                    target.write_bytes(target.read_bytes() + b" ")
                    return result

                with mock.patch("fiction_compiler.promote._policy_gate", side_effect=mutate_after_gate):
                    with self.assertRaisesRegex(ValueError, "changed during validation"):
                        promote_candidate(project, "ch01-sc01", "c.md")
                self.assertEqual(acceptance.load_index(project)["accepted_state_deltas"], [])

    def test_same_scene_rewrite_is_refused_but_identical_retry_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            first = promote_candidate(project, "ch01-sc01", "c.md")
            retry = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertTrue(retry["idempotent"])
            self.assertEqual(retry["acceptance_object"], first["acceptance_object"])
            (project / "scenes" / "ch01-sc01" / "candidates" / "c.md").write_text(
                "rewritten", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "already accepted with different frozen inputs"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_out_of_order_insertion_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            index = acceptance.load_index(project)
            index["accepted_state_deltas"] = ["ch01-sc02"]
            acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))
            with self.assertRaisesRegex(ValueError, "insert before"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_index_commit_failure_leaves_only_reported_orphan_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            real_write = acceptance.atomic_write

            def fail_index(path, data):
                if Path(path).resolve() == acceptance.index_path(project).resolve():
                    raise RuntimeError("simulated index failure")
                return real_write(path, data)

            with mock.patch("fiction_compiler.acceptance.atomic_write", side_effect=fail_index):
                with self.assertRaisesRegex(RuntimeError, "index failure"):
                    promote_candidate(project, "ch01-sc01", "c.md")
            self.assertEqual(acceptance.load_index(project)["accepted_state_deltas"], [])
            report = integrity.verify_report(project)
            self.assertEqual(report["status"], "orphaned")
            self.assertTrue(any(path.startswith("canon/objects/") for path in report["orphaned"]))

    def test_retry_repairs_views_after_authoritative_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            with mock.patch("fiction_compiler.promote._materialize_snapshot",
                            side_effect=RuntimeError("view crash")):
                with self.assertRaisesRegex(RuntimeError, "view crash"):
                    promote_candidate(project, "ch01-sc01", "c.md")
            self.assertEqual(acceptance.load_index(project)["accepted_state_deltas"], ["ch01-sc01"])
            retry = promote_candidate(project, "ch01-sc01", "c.md")
            self.assertTrue(retry["idempotent"])
            self.assertEqual(integrity.verify_report(project)["status"], "verified")

    def test_review_policy_bytes_are_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            policy = {
                "id": "project-review@7",
                "minimum_literary_reviews": 1,
                "required_literary_roles": ["style-editor"],
                "require_runtime_provenance": True,
                "require_issue_resolutions": True,
                "defaultness_mode": "blocking",
                "require_prose_audit": False,
            }
            path = project / "brief" / "review-policy.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
            result = promote_candidate(project, "ch01-sc01", "c.md")
            snapshot = acceptance.load_object(project, result["acceptance_object"])
            self.assertEqual(snapshot["review_policy"]["id"], "project-review@7")
            self.assertEqual(snapshot["review_policy"]["artifact"]["sha256"], integrity.sha256_file(path))

    def test_builtin_policy_treats_defaultness_as_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            candidate = project / "scenes" / "ch01-sc01" / "candidates" / "c.md"
            candidate.write_text("Her heart pounded in her chest.", encoding="utf-8")
            sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            write_review_set(project / "scenes" / "ch01-sc01", sha=sha)
            result = promote_candidate(project, "ch01-sc01", "c.md")
            snapshot = acceptance.load_object(project, result["acceptance_object"])
            runtime = snapshot["runtime_checks"]["defaultness"]
            self.assertEqual(runtime["verdict"], "revise")
            self.assertEqual(snapshot["review_policy"]["id"], "review-policy@2")

    def test_project_can_explicitly_opt_into_blocking_defaultness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            candidate = project / "scenes" / "ch01-sc01" / "candidates" / "c.md"
            candidate.write_text("Her heart pounded in her chest.", encoding="utf-8")
            sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            write_review_set(project / "scenes" / "ch01-sc01", sha=sha)
            policy = {
                "id": "project-review@blocking-style",
                "minimum_literary_reviews": 1,
                "required_literary_roles": [],
                "require_runtime_provenance": True,
                "require_issue_resolutions": True,
                "defaultness_mode": "blocking",
                "require_prose_audit": False,
            }
            path = project / "brief" / "review-policy.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "runtime defaultness check"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_flock_is_released_after_process_death(self) -> None:
        if not hasattr(os, "fork"):
            self.skipTest("requires POSIX fork/flock")
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:  # pragma: no cover - child process
                os.close(read_fd)
                with integrity.PromotionLock(project):
                    os.write(write_fd, b"1")
                    os._exit(9)
            os.close(write_fd)
            self.assertEqual(os.read(read_fd, 1), b"1")
            os.close(read_fd)
            os.waitpid(pid, 0)
            with integrity.PromotionLock(project):
                pass


class HumanGateTests(unittest.TestCase):
    def _gated_project(self, root: Path) -> Path:
        project = build(root)
        (project / "brief").mkdir(parents=True)
        (project / "brief" / "project.json").write_text(
            json.dumps({"id": "proj", "human_gates": ["promotion"]}), encoding="utf-8"
        )
        return project

    def test_gated_promotion_refused_without_approver(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._gated_project(Path(tmp))
            with self.assertRaisesRegex(ValueError, "human gate"):
                promote_candidate(project, "ch01-sc01", "c.md")

    def test_gated_promotion_records_approver_and_rubric(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = self._gated_project(Path(tmp))
            result = promote_candidate(project, "ch01-sc01", "c.md",
                                       approved_by="editor@example", rubric_version="literary-rubric@1")
            snapshot = acceptance.load_object(project, result["acceptance_object"])
            self.assertEqual(snapshot["human_gate"],
                             {"required": True, "approved": True, "approver": "editor@example"})
            self.assertEqual(snapshot["rubric_version"], "literary-rubric@1")


class LegacyStatusTests(unittest.TestCase):
    def test_legacy_acceptance_is_reported_as_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            index = acceptance.load_index(project)
            index["accepted_state_deltas"] = ["ch01-sc01"]
            acceptance.atomic_write(acceptance.index_path(project), acceptance.canonical_json_bytes(index))
            report = integrity.verify_report(project)
            self.assertEqual(report["status"], "legacy_unverified")
            self.assertEqual(report["legacy_unverified"], ["ch01-sc01"])


if __name__ == "__main__":
    unittest.main()
