from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import revision  # noqa: E402


def crit(*findings) -> dict:
    return {"findings": [{"dimension": d, "severity": s} for d, s in findings]}


class RevisionDecisionTests(unittest.TestCase):
    def test_accept_when_target_improves_without_regression(self) -> None:
        before = [crit(("defaultness", "material"), ("defaultness", "material"), ("defaultness", "material"))]
        after = [crit()]
        outcome = revision.evaluate_revision(before, after, target_dimension="defaultness", iteration=1)
        self.assertEqual(outcome.decision, revision.ACCEPT)
        self.assertEqual((outcome.target_before, outcome.target_after), (3, 0))

    def test_reject_when_a_regression_appears_elsewhere(self) -> None:
        before = [crit(("defaultness", "material"), ("defaultness", "material"))]
        after = [crit(("structure", "material"))]  # fixed defaultness but broke structure
        outcome = revision.evaluate_revision(before, after, target_dimension="defaultness", iteration=1)
        self.assertEqual(outcome.decision, revision.REJECT_REGRESSION)
        self.assertIn("structure", outcome.material_regressions)

    def test_stop_after_max_iterations_without_progress(self) -> None:
        before = [crit(("defaultness", "material"), ("defaultness", "material"))]
        after = [crit(("defaultness", "material"), ("defaultness", "material"))]  # no change
        outcome = revision.evaluate_revision(
            before, after, target_dimension="defaultness", iteration=3, max_iterations=3
        )
        self.assertEqual(outcome.decision, revision.STOP_NO_PROGRESS)

    def test_escalate_layer_after_attempts_exhausted(self) -> None:
        before = [crit(("defaultness", "material"))]
        after = [crit(("defaultness", "material"))]  # no change
        outcome = revision.evaluate_revision(
            before, after, target_dimension="defaultness",
            iteration=1, max_iterations=3, attempts_at_current_layer=2, max_attempts_per_layer=2,
        )
        self.assertEqual(outcome.decision, revision.ESCALATE_LAYER)

    def test_continue_while_fatals_remain(self) -> None:
        before = [crit(("knowledge", "fatal"))]
        after = [crit(("knowledge", "fatal"))]
        outcome = revision.evaluate_revision(before, after, target_dimension="knowledge", iteration=1)
        self.assertEqual(outcome.decision, revision.CONTINUE)
        self.assertEqual(outcome.fatals_after, 1)

    def test_accept_when_fatal_cleared(self) -> None:
        before = [crit(("knowledge", "fatal"))]
        after = [crit()]
        outcome = revision.evaluate_revision(before, after, target_dimension="knowledge", iteration=1)
        self.assertEqual(outcome.decision, revision.ACCEPT)

    def test_tally_flattens_and_counts(self) -> None:
        t = revision.tally([crit(("a", "fatal"), ("b", "material"), ("c", "minor"))])
        self.assertEqual((t["fatal"], t["material"], t["minor"], t["total"]), (1, 1, 1, 3))

    def test_history_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scenes" / "ch01-sc01"
            revision.log_revision(scene, {"iteration": 1, "decision": revision.CONTINUE, "target_dimension": "defaultness"})
            revision.log_revision(scene, {"iteration": 2, "decision": revision.ACCEPT, "target_dimension": "defaultness"})
            history = revision.revision_history(scene)
            self.assertEqual(len(history), 2)
            self.assertEqual(history[1]["decision"], revision.ACCEPT)


if __name__ == "__main__":
    unittest.main()
