from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import tools, tournament  # noqa: E402


class SelectionMathTests(unittest.TestCase):
    def test_anonymize_is_deterministic_and_reversible(self) -> None:
        labels1, reveal1 = tournament.anonymize(["candidate-a.md", "candidate-b.md"], seed=7)
        labels2, _ = tournament.anonymize(["candidate-a.md", "candidate-b.md"], seed=7)
        self.assertEqual(labels1, labels2)  # deterministic for a seed
        for cid, label in labels1.items():
            self.assertEqual(reveal1[label], cid)  # round-trips
        self.assertEqual(set(labels1.values()), {"A", "B"})

    def test_presentation_orders_include_a_reversed_order(self) -> None:
        orders = tournament.presentation_orders(["A", "B"], seed=0)
        self.assertIn(["A", "B"], orders)
        self.assertIn(["B", "A"], orders)

    def test_dominates(self) -> None:
        self.assertTrue(tournament.dominates({"style": 0.0, "cliche": 0.0}, {"style": -4.0, "cliche": -1.0}))
        self.assertFalse(tournament.dominates({"style": 0.0, "cliche": -2.0}, {"style": -4.0, "cliche": 0.0}))

    def test_pareto_front_single_dominator(self) -> None:
        scores = {"a": {"style": 0.0, "cliche": 0.0}, "b": {"style": -4.0, "cliche": -1.0}}
        self.assertEqual(tournament.pareto_front(scores), {"a"})

    def test_pareto_front_keeps_a_tradeoff(self) -> None:
        # a is cleaner on style, b is cleaner on cliche -> neither dominates.
        scores = {"a": {"style": 0.0, "cliche": -2.0}, "b": {"style": -3.0, "cliche": 0.0}}
        self.assertEqual(tournament.pareto_front(scores), {"a", "b"})
        self.assertTrue(tournament.has_disagreement(scores))

    def test_scores_from_critiques_accumulate_penalties(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "findings": [
                {"dimension": "cliche", "severity": "material"}, {"dimension": "cliche", "severity": "minor"}]},
            {"candidate": "candidate-a.md", "findings": [{"dimension": "style", "severity": "minor"}]},
        ]
        scores = tournament.scores_from_critiques(critiques)
        self.assertEqual(scores["candidate-a.md"]["cliche"], -5.0)  # material(4) + minor(1)
        self.assertEqual(scores["candidate-a.md"]["style"], -1.0)


class RunTournamentTests(unittest.TestCase):
    def test_single_winner_is_selected(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "findings": []},
            {"candidate": "candidate-b.md", "findings": [{"dimension": "cliche", "severity": "material"}]},
        ]
        result = tournament.run_tournament(critiques, seed=1)
        self.assertEqual(result["pareto_front"], ["candidate-a.md"])
        self.assertEqual(result["recommendation"]["decision"], "select")
        self.assertEqual(result["recommendation"]["candidate"], "candidate-a.md")
        self.assertFalse(result["disagreement"])

    def test_tradeoff_requires_human_decision(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "findings": [{"dimension": "style", "severity": "material"}]},
            {"candidate": "candidate-b.md", "findings": [{"dimension": "cliche", "severity": "material"}]},
        ]
        result = tournament.run_tournament(critiques, seed=1)
        self.assertEqual(sorted(result["pareto_front"]), ["candidate-a.md", "candidate-b.md"])
        self.assertEqual(result["recommendation"]["decision"], "human_decision_required")
        self.assertTrue(result["disagreement"])

    def test_tool_reads_scene_critiques(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            crit = Path(tmp) / "scenes" / "ch01-sc01" / "critiques"
            crit.mkdir(parents=True)
            (crit / "adversarial-reader.json").write_text(json.dumps(
                {"candidate": "candidate-a.md", "critic": "adversarial-reader", "verdict": "pass", "findings": []}))
            (crit / "style-editor.json").write_text(json.dumps(
                {"candidate": "candidate-b.md", "critic": "style-editor", "verdict": "revise",
                 "findings": [{"dimension": "style", "severity": "material"}]}))
            result = tools.tournament(str(Path(tmp)), "ch01-sc01")
            self.assertEqual(result["recommendation"]["candidate"], "candidate-a.md")


if __name__ == "__main__":
    unittest.main()
