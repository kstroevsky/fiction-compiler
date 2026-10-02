from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import regression, tools  # noqa: E402


class FrameworkRegressionTests(unittest.TestCase):
    def test_committed_fixtures_all_pass(self) -> None:
        report = regression.run_regressions()
        self.assertTrue(report["total"] >= 8)
        failed = [r for r in report["results"] if not r["passed"]]
        self.assertTrue(report["ok"], f"regressed invariants: {failed}")

    def test_a_wrong_expectation_is_detected(self) -> None:
        result = regression.run_fixture({
            "name": "deliberately wrong", "check": "defaultness_verdict",
            "input": {"text": "The relay lay open."}, "expect": "revise"})  # clean prose is not 'revise'
        self.assertFalse(result["passed"])

    def test_unknown_check_fails_gracefully(self) -> None:
        result = regression.run_fixture({"name": "x", "check": "no_such_check", "input": {}, "expect": 1})
        self.assertFalse(result["passed"])
        self.assertIn("unknown check", result["error"])

    def test_broken_fixture_input_is_a_failure_not_a_crash(self) -> None:
        result = regression.run_fixture({"name": "x", "check": "defaultness_verdict", "input": {}, "expect": "pass"})
        self.assertFalse(result["passed"])
        self.assertIn("error", result)

    def test_manifest_fingerprints_the_framework(self) -> None:
        manifest = regression.framework_manifest()
        self.assertEqual(len(manifest["framework_fingerprint"]), 64)  # sha256 hex
        self.assertTrue(manifest["schemas_sha256"])
        self.assertTrue(manifest["source_sha256"])
        self.assertTrue(manifest["configuration_sha256"])
        self.assertTrue(manifest["evaluation_data_sha256"])
        self.assertTrue(manifest["agent_instructions_sha256"])

    def test_manifest_changes_when_external_behavior_artifacts_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = {
                "schemas/x.json": "{}",
                "kb/style/defaultness-catalog.json": "{}",
                "src/fiction_compiler/x.py": "X = 1\n",
                "scripts/tool.py": "print('x')\n",
                "config/model-roster.json": "{}",
                "premise-probes.json": "{}",
                "evals/critic-cases.json": "{}",
                "regression/fixtures.json": "{}",
                ".claude/agents/style-editor.md": "review style\n",
                ".agents/skills/draft-scene/SKILL.md": "draft\n",
                "constitution/change-policy.md": "policy\n",
                "AGENTS.md": "agents\n",
                "CLAUDE.md": "claude\n",
                "pyproject.toml": "[project]\nname='fixture'\n",
            }
            for rel, content in fixtures.items():
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            before = regression.framework_manifest(root)
            watched = [
                "kb/style/defaultness-catalog.json",
                "config/model-roster.json",
                "premise-probes.json",
                "evals/critic-cases.json",
                "regression/fixtures.json",
                ".claude/agents/style-editor.md",
                ".agents/skills/draft-scene/SKILL.md",
                "scripts/tool.py",
                "pyproject.toml",
            ]
            for rel in watched:
                path = root / rel
                original = path.read_text(encoding="utf-8")
                path.write_text(original + "\nchanged", encoding="utf-8")
                changed = regression.framework_manifest(root)
                self.assertNotEqual(before["framework_fingerprint"], changed["framework_fingerprint"], rel)
                path.write_text(original, encoding="utf-8")

    def test_tool_runs_regressions(self) -> None:
        out = tools.call_tool("run_regression", {})
        self.assertTrue(out["ok"])
        self.assertIn("framework_fingerprint", out["manifest"])

    def test_framework_path_classifier_covers_current_and_new_behavior_files(self) -> None:
        self.assertTrue(regression.is_framework_path("src/fiction_compiler/new_check.py"))
        self.assertTrue(regression.is_framework_path("config/new-policy.json"))
        self.assertTrue(regression.is_framework_path(".agents/skills/new-skill/SKILL.md"))
        self.assertFalse(regression.is_framework_path("docs/decisions/proposal.md"))
        self.assertFalse(regression.is_framework_path("projects/demo/manuscript.md"))

    def test_runtime_source_status_detects_stale_imported_code(self) -> None:
        with mock.patch.object(regression, "_RUNTIME_SOURCE_SHA256", "0" * 64):
            status = regression.runtime_source_status()
        self.assertTrue(status["checked"])
        self.assertFalse(status["fresh"])


if __name__ == "__main__":
    unittest.main()
