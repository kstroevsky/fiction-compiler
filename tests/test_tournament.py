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


class JudgeAndPersistenceTests(unittest.TestCase):
    def test_assign_orders_cycles_across_judges(self) -> None:
        orders = [["A", "B"], ["B", "A"]]
        ledger = tournament.assign_orders(["judge-1", "judge-2", "judge-3"], orders)
        self.assertEqual([e["judge"] for e in ledger], ["judge-1", "judge-2", "judge-3"])
        self.assertEqual(ledger[0]["presentation_order"], ["A", "B"])
        self.assertEqual(ledger[1]["presentation_order"], ["B", "A"])  # cycles
        self.assertEqual(ledger[2]["presentation_order"], ["A", "B"])

    def test_disagreement_from_rankings(self) -> None:
        agree = tournament.disagreement_from_rankings([["a", "b"], ["a", "b"]])
        self.assertTrue(agree["agree_on_winner"])
        split = tournament.disagreement_from_rankings([["a", "b"], ["b", "a"]])
        self.assertFalse(split["agree_on_winner"])
        self.assertEqual(split["distinct_top_picks"], ["a", "b"])

    def test_run_tournament_records_judges_and_disagreement(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "findings": []},
            {"candidate": "candidate-b.md", "findings": [{"dimension": "cliche", "severity": "material"}]},
        ]
        result = tournament.run_tournament(
            critiques, seed=1, judges=["judge-1", "judge-2"],
            judge_rankings=[["candidate-a.md", "candidate-b.md"], ["candidate-b.md", "candidate-a.md"]])
        self.assertEqual(len(result["judge_ledger"]), 2)
        self.assertFalse(result["judge_disagreement"]["agree_on_winner"])
        self.assertTrue(result["disagreement"])  # judges split, even though scores had a dominator

    def test_persist_writes_blinded_copies_without_reveal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scenes" / "ch01-sc01"
            (scene / "candidates").mkdir(parents=True)
            (scene / "critiques").mkdir(parents=True)
            (scene / "candidates" / "candidate-a.md").write_text("Clean prose.")
            (scene / "candidates" / "candidate-b.md").write_text("Her heart pounded.")
            (scene / "critiques" / "a.json").write_text(json.dumps(
                {"candidate": "candidate-a.md", "findings": []}))
            (scene / "critiques" / "b.json").write_text(json.dumps(
                {"candidate": "candidate-b.md", "findings": [{"dimension": "cliche", "severity": "material"}]}))
            result = tools.tournament(str(Path(tmp)), "ch01-sc01", persist=True)
            run_dir = Path(tmp) / result["persisted_to"]
            blind = run_dir / "blind"
            self.assertEqual(sorted(p.name for p in blind.glob("*.md")), ["A.md", "B.md"])
            self.assertTrue((run_dir / "record.json").exists())
            # The blind dir must not leak the true candidate identity.
            for md in blind.glob("*.md"):
                self.assertNotIn("candidate-", md.read_text())


class CriticDrivesSelectionTests(unittest.TestCase):
    """The strong LLM critic drives selection, behind the deterministic floor (ADR 0016)."""

    def _clean(self, *names) -> list:
        return [{"candidate": n, "critic": "defaultness-lint", "findings": []} for n in names]

    def test_scores_from_judgments_means_across_judges(self) -> None:
        reveal = {"A": "cand-a", "B": "cand-b"}
        j1 = {"scores": {"A": {"prose": 4}, "B": {"prose": 2}}}
        j2 = {"scores": {"A": {"prose": 2}, "B": {"prose": 4}}}
        s = tournament.scores_from_judgments([j1, j2], reveal)
        self.assertEqual(s["cand-a"]["prose"], 3.0)
        self.assertEqual(s["cand-b"]["prose"], 3.0)

    def test_critic_judgment_drives_the_pick(self) -> None:
        critiques = self._clean("candidate-a.md", "candidate-b.md")  # both floor-clean, no penalties
        labels = tournament.run_tournament(critiques, seed=0)["blind_labels"]  # id -> blind label
        judgment = {"scene_id": "ch01-sc01", "judge": "style-editor@1", "scores": {
            labels["candidate-a.md"]: {"prose": 2, "tension": 2},
            labels["candidate-b.md"]: {"prose": 4, "tension": 4}}}  # critic clearly prefers B
        r = tournament.run_tournament(critiques, seed=0, judgments=[judgment])
        self.assertEqual(r["selection_basis"], "critic-judgments")
        self.assertEqual(r["recommendation"]["decision"], "select")
        self.assertEqual(r["recommendation"]["candidate"], "candidate-b.md")

    def test_floor_excludes_a_candidate_even_if_the_critic_prefers_it(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "critic": "defaultness-lint", "findings": []},
            {"candidate": "candidate-b.md", "critic": "defaultness-lint",
             "findings": [{"dimension": "cliche", "severity": "material"}]}]  # B fails the floor
        labels = tournament.run_tournament(critiques, seed=0)["blind_labels"]
        judgment = {"scene_id": "ch01-sc01", "judge": "x", "scores": {
            labels["candidate-a.md"]: {"prose": 1}, labels["candidate-b.md"]: {"prose": 5}}}  # loves B
        r = tournament.run_tournament(critiques, seed=0, judgments=[judgment])
        self.assertIn("candidate-b.md", r["floor_failed"])
        self.assertEqual(r["recommendation"]["candidate"], "candidate-a.md")  # B excluded despite the critic

    def test_all_candidates_failing_the_floor_yields_no_eligible(self) -> None:
        critiques = [
            {"candidate": "candidate-a.md", "critic": "defaultness-lint",
             "findings": [{"dimension": "cliche", "severity": "material"}]},
            {"candidate": "candidate-b.md", "critic": "prose-audit",
             "findings": [{"dimension": "knowledge", "severity": "fatal"}]}]
        r = tournament.run_tournament(critiques, seed=0)
        self.assertEqual(r["recommendation"]["decision"], "no_eligible_candidates")

    def test_judges_split_forces_human_decision(self) -> None:
        critiques = self._clean("candidate-a.md", "candidate-b.md")
        labels = tournament.run_tournament(critiques, seed=0)["blind_labels"]
        a, b = labels["candidate-a.md"], labels["candidate-b.md"]
        judgments = [{"scene_id": "ch01-sc01", "judge": "j1", "scores": {a: {"q": 5}, b: {"q": 1}}},
                     {"scene_id": "ch01-sc01", "judge": "j2", "scores": {a: {"q": 1}, b: {"q": 5}}}]
        r = tournament.run_tournament(critiques, seed=0, judgments=judgments)
        self.assertTrue(r["disagreement"])
        self.assertFalse(r["judge_disagreement"]["agree_on_winner"])


if __name__ == "__main__":
    unittest.main()
