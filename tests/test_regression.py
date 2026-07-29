from __future__ import annotations

import sys
import unittest
from pathlib import Path

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

    def test_tool_runs_regressions(self) -> None:
        out = tools.call_tool("run_regression", {})
        self.assertTrue(out["ok"])
        self.assertIn("framework_fingerprint", out["manifest"])


if __name__ == "__main__":
    unittest.main()
