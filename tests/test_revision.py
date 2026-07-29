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


def _fe(dimension: str, severity: str, evidence: str) -> dict:
    return {"dimension": dimension, "severity": severity, "evidence": evidence,
            "diagnosis": "", "repair_layer": "prose"}


class FindingIdentityTests(unittest.TestCase):
    def test_diff_classifies_fixed_persisted_worsened_new(self) -> None:
        before = [_fe("cliche", "minor", "heart pounded"), _fe("style", "material", "throat-clearing open")]
        after = [_fe("style", "fatal", "throat-clearing open"),   # same identity, worse -> worsened
                 _fe("rhythm", "material", "monotone sentences")]  # -> newly_introduced
        diff = revision.diff_findings([{"findings": before}], [{"findings": after}])
        self.assertEqual([f["dimension"] for f in diff["fixed"]], ["cliche"])
        self.assertEqual([f["dimension"] for f in diff["worsened"]], ["style"])
        self.assertEqual([f["dimension"] for f in diff["newly_introduced"]], ["rhythm"])
        self.assertEqual(diff["persisted"], [])

    def test_fingerprint_ignores_severity_and_whitespace(self) -> None:
        self.assertEqual(revision.finding_fingerprint(_fe("cliche", "minor", "Heart  Pounded")),
                         revision.finding_fingerprint(_fe("cliche", "fatal", "heart pounded")))


class IdentityDecisionTests(unittest.TestCase):
    def test_count_drop_hiding_a_new_material_is_rejected(self) -> None:
        # The review's motivating example: two minor findings replaced by one NEW material finding.
        # Counts fall (2 -> 1) so a count-only check "accepts" — identity must reject.
        before = [{"findings": [_fe("cliche", "minor", "heart pounded"), _fe("cliche", "minor", "time stood still")]}]
        after = [{"findings": [_fe("cliche", "material", "a wholly new default")]}]
        outcome = revision.evaluate_revision(before, after, target_dimension="cliche")
        self.assertEqual(outcome.decision, revision.REJECT_REGRESSION)
        self.assertEqual([f["dimension"] for f in outcome.new_findings], ["cliche"])

    def test_worsened_same_finding_is_rejected(self) -> None:
        before = [{"findings": [_fe("cliche", "minor", "heart pounded")]}]
        after = [{"findings": [_fe("cliche", "material", "heart pounded")]}]  # same identity, escalated
        outcome = revision.evaluate_revision(before, after, target_dimension="style")
        self.assertEqual(outcome.decision, revision.REJECT_REGRESSION)
        self.assertEqual([f["dimension"] for f in outcome.worsened_findings], ["cliche"])

    def test_target_fixed_cleanly_is_accepted_and_reported(self) -> None:
        before = [{"findings": [_fe("cliche", "material", "heart pounded")]}]
        after: list[dict] = [{"findings": []}]
        outcome = revision.evaluate_revision(before, after, target_dimension="cliche")
        self.assertEqual(outcome.decision, revision.ACCEPT)
        self.assertEqual([f["dimension"] for f in outcome.fixed_findings], ["cliche"])

    def test_no_identity_fix_of_target_does_not_accept(self) -> None:
        # The target finding merely PERSISTS (same fingerprint, unchanged) — nothing resolved by
        # identity, so acceptance must not trigger even though there is no regression.
        same = [{"findings": [_fe("cliche", "material", "heart pounded")]}]
        outcome = revision.evaluate_revision(same, same, target_dimension="cliche",
                                             iteration=1, attempts_at_current_layer=1)
        self.assertNotEqual(outcome.decision, revision.ACCEPT)


class WaiverTests(unittest.TestCase):
    def test_waived_new_finding_does_not_block_acceptance(self) -> None:
        before = [{"findings": [_fe("cliche", "material", "heart pounded")]}]
        after = [{"findings": [_fe("style", "material", "a deliberate genre flourish")]}]  # new material
        waivers = [{"dimension": "style", "evidence": "a deliberate genre flourish",
                    "reason": "genre obligation", "approved_by": "human"}]
        outcome = revision.evaluate_revision(before, after, target_dimension="cliche", waivers=waivers)
        self.assertEqual(outcome.decision, revision.ACCEPT)
        self.assertEqual([f["dimension"] for f in outcome.waived_findings], ["style"])
        self.assertEqual(outcome.waived_findings[0]["reason"], "genre obligation")

    def test_without_the_waiver_the_same_revision_is_rejected(self) -> None:
        before = [{"findings": [_fe("cliche", "material", "heart pounded")]}]
        after = [{"findings": [_fe("style", "material", "a deliberate genre flourish")]}]
        outcome = revision.evaluate_revision(before, after, target_dimension="cliche")
        self.assertEqual(outcome.decision, revision.REJECT_REGRESSION)


if __name__ == "__main__":
    unittest.main()
