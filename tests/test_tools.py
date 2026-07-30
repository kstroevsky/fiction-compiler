from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import kb, tools  # noqa: E402


class KbRetrievalTests(unittest.TestCase):
    def test_search_ranks_id_match_first(self) -> None:
        results = kb.search("defaultness")
        self.assertTrue(results)
        self.assertEqual(results[0]["id"], "defaultness")

    def test_search_by_layer(self) -> None:
        results = kb.search("", layer="narratology")
        self.assertTrue(all(r["layer"] == "narratology" for r in results))

    def test_get_returns_full_card_text(self) -> None:
        card = kb.get("scene-dramaturgy")
        self.assertIsNotNone(card)
        self.assertIn("turn", card["card_text"].lower())

    def test_get_unknown_is_none(self) -> None:
        self.assertIsNone(kb.get("no-such-concept"))

    def test_every_concept_carries_structured_depth(self) -> None:
        # P4/ADR 0015: no card may be an inert or over-absolute generalization.
        ids = {c["id"] for c in kb.concepts()}
        grades = {"structural", "craft-heuristic", "theoretical", "contested", "empirical"}
        for c in kb.concepts():
            self.assertTrue(c.get("claim"), c["id"])
            self.assertIn(c.get("evidence_strength"), grades, c["id"])
            self.assertTrue(c.get("dangerous_when"), c["id"])
            self.assertIsInstance(c.get("counterexamples"), list, c["id"])
            for conflict in c.get("conflicts_with", []):
                self.assertIn(conflict, ids, f"{c['id']} conflicts_with unresolved {conflict}")

    def test_conflicting_theories_are_represented(self) -> None:
        # The review wanted conflicting theories, not one-sided rules: eventfulness <-> static-scene.
        self.assertIn("static-scene", kb.get("eventfulness")["conflicts_with"])
        self.assertIn("eventfulness", kb.get("static-scene")["conflicts_with"])


class ToolDispatchTests(unittest.TestCase):
    def test_registry_and_list_shape(self) -> None:
        names = {t["name"] for t in tools.list_tools()}
        self.assertIn("kb_search", names)
        self.assertIn("hard_audit", names)
        for descriptor in tools.list_tools():
            self.assertNotIn("handler", descriptor)  # handlers not exposed over the wire
            self.assertEqual(descriptor["inputSchema"]["type"], "object")

    def test_call_tool_kb_get(self) -> None:
        out = tools.call_tool("kb_get", {"concept_id": "defaultness"})
        self.assertIn("card_text", out)

    def test_call_tool_defaultness(self) -> None:
        out = tools.call_tool("defaultness_lint", {"text": "Her heart pounded and time stood still."})
        self.assertEqual(out["verdict"], "revise")

    def test_call_tool_evaluate_revision(self) -> None:
        out = tools.call_tool("evaluate_revision", {
            "before_findings": [{"findings": [{"dimension": "defaultness", "severity": "material"}]}],
            "after_findings": [{"findings": []}],
            "target": "defaultness",
        })
        self.assertEqual(out["decision"], "accept")

    def test_unknown_tool_returns_error(self) -> None:
        self.assertIn("error", tools.call_tool("nope", {}))

    def test_promote_requires_confirm(self) -> None:
        out = tools.call_tool("promote", {"project": "salt-in-the-wire", "scene_id": "ch01-sc01",
                                          "candidate_file": "candidate-a.md"})
        self.assertIn("error", out)
        self.assertIn("confirm", out["error"])

    def test_call_tool_rejects_project_path_traversal(self) -> None:
        out = tools.call_tool("state_before", {"project": "../../etc", "scene_id": "ch01-sc01"})
        self.assertIn("error", out)

    def test_call_tool_rejects_absolute_project_outside_root(self) -> None:
        out = tools.call_tool("assemble", {"project": "/etc"})
        self.assertIn("error", out)
        self.assertIn("approved root", out["error"])

    def test_call_tool_rejects_file_path_escape(self) -> None:
        out = tools.call_tool("defaultness_lint", {"path": "/etc/passwd"})
        self.assertIn("error", out)

    def test_evaluate_revision_reaches_escalate_via_params(self) -> None:
        no_progress = [{"findings": [{"dimension": "defaultness", "severity": "material"}]}]
        out = tools.call_tool("evaluate_revision", {
            "before_findings": no_progress, "after_findings": no_progress, "target": "defaultness",
            "iteration": 1, "attempts_at_current_layer": 2, "max_attempts_per_layer": 2,
        })
        self.assertEqual(out["decision"], "escalate_layer")


class ToolWriteTests(unittest.TestCase):
    def test_record_revision_lints_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scene = Path(tmp) / "scenes" / "ch01-sc01"
            (scene / "candidates").mkdir(parents=True)
            (scene / "candidates" / "before.md").write_text("Her heart pounded and time stood still.")
            (scene / "candidates" / "after.md").write_text("The relay lay open, two wires bright.")
            out = tools.record_revision(str(Path(tmp)), "ch01-sc01", "before.md", "after.md", target="defaultness")
            self.assertTrue(out["logged"])
            self.assertEqual(out["decision"], "accept")
            self.assertTrue((scene / "revision-log.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
