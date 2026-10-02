from __future__ import annotations

import sys
import tempfile
import unittest
import inspect
from pathlib import Path
from unittest.mock import patch

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
        self.assertIn("project_create", names)
        self.assertIn("candidate_write", names)
        self.assertIn("workspace_validate", names)
        self.assertIn("kb_search", names)
        self.assertIn("hard_audit", names)
        self.assertIn("revise_acceptance", names)
        self.assertIn("revision_status", names)
        for descriptor in tools.list_tools():
            self.assertNotIn("handler", descriptor)  # handlers not exposed over the wire
            self.assertEqual(descriptor["inputSchema"]["type"], "object")
            annotations = descriptor["annotations"]
            self.assertEqual(
                set(annotations),
                {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"},
            )
            self.assertEqual(
                annotations["openWorldHint"], descriptor["name"] in tools._OPEN_WORLD_TOOLS
            )

    def test_mcp_annotations_match_tool_behavior(self) -> None:
        by_name = {tool["name"]: tool["annotations"] for tool in tools.list_tools()}
        self.assertTrue(by_name["kb_search"]["readOnlyHint"])
        self.assertTrue(by_name["run_regression"]["readOnlyHint"])
        self.assertTrue(by_name["project_overview"]["idempotentHint"])

        self.assertFalse(by_name["candidate_write"]["readOnlyHint"])
        self.assertFalse(by_name["record_revision"]["idempotentHint"])
        self.assertTrue(by_name["project_write_artifact"]["destructiveHint"])
        self.assertTrue(by_name["revise_acceptance"]["destructiveHint"])
        self.assertTrue(by_name["assemble"]["destructiveHint"])
        self.assertTrue(by_name["rollback_framework_change"]["destructiveHint"])
        self.assertFalse(by_name["promote"]["destructiveHint"])
        self.assertTrue(by_name["run_role_review"]["openWorldHint"])
        self.assertTrue(by_name["run_review_panel"]["openWorldHint"])
        self.assertFalse(by_name["run_role_review"]["readOnlyHint"])
        self.assertFalse(by_name["run_role_review"]["idempotentHint"])
        self.assertFalse(by_name["role_prompt"]["openWorldHint"])

        self.assertTrue(tools._READ_ONLY_TOOLS <= set(by_name))
        self.assertTrue(tools._DESTRUCTIVE_TOOLS <= set(by_name))
        self.assertTrue(tools._OPEN_WORLD_TOOLS <= set(by_name))
        for name, annotations in by_name.items():
            self.assertEqual(annotations["readOnlyHint"], name in tools._READ_ONLY_TOOLS, name)
            self.assertEqual(annotations["destructiveHint"], name in tools._DESTRUCTIVE_TOOLS, name)
            self.assertEqual(annotations["idempotentHint"], name in tools._READ_ONLY_TOOLS, name)
            self.assertEqual(annotations["openWorldHint"], name in tools._OPEN_WORLD_TOOLS, name)

    def test_every_public_tool_handler_is_registered(self) -> None:
        public = {
            name for name, fn in inspect.getmembers(tools, inspect.isfunction)
            if fn.__module__ == tools.__name__ and not name.startswith("_")
        } - {"list_tools", "call_tool"}
        handlers = {descriptor["handler"].__name__ for descriptor in tools.TOOLS}
        self.assertEqual(public, handlers)

    def test_every_handler_parameter_is_exposed_by_mcp_schema(self) -> None:
        """Registered locally is insufficient if Codex cannot supply the handler's full API."""
        for descriptor in tools.TOOLS:
            signature = inspect.signature(descriptor["handler"])
            public_parameters = {
                name
                for name, parameter in signature.parameters.items()
                if not name.startswith("_")
                and parameter.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                )
            }
            required_parameters = {
                name
                for name, parameter in signature.parameters.items()
                if name in public_parameters and parameter.default is inspect.Parameter.empty
            }
            schema = descriptor["inputSchema"]
            self.assertEqual(set(schema["properties"]), public_parameters, descriptor["name"])
            self.assertEqual(set(schema["required"]), required_parameters, descriptor["name"])

    def test_authoring_tools_expose_canonical_nested_schemas(self) -> None:
        by_name = {tool["name"]: tool["inputSchema"] for tool in tools.list_tools()}

        character = by_name["character_write"]["properties"]["character"]
        self.assertEqual(
            set(character["required"]),
            {"id", "name", "desire", "values", "beliefs", "constraints", "voice"},
        )
        self.assertEqual(set(character["properties"]["voice"]["required"]), {"lexicon", "syntax", "avoid"})

        scene = by_name["scene_spec_write"]["properties"]["spec"]
        self.assertIn("chapter", scene["required"])
        self.assertIn("required_events", scene["required"])
        self.assertEqual(scene["properties"]["id"]["pattern"], "^ch[0-9]{2}-sc[0-9]{2}$")

        delta = by_name["state_delta_write"]["properties"]["state_delta"]
        self.assertIn("knowledge_changes", delta["required"])
        self.assertEqual(
            delta["properties"]["knowledge_changes"]["items"]["required"],
            ["character", "fact"],
        )

        project = by_name["project_create"]["properties"]["project_data"]
        self.assertIn("reader_contract", project["required"])
        self.assertEqual(project["properties"]["id"]["pattern"], "^[a-z0-9-]+$")
        self.assertIn("id must exactly equal the slug", project["description"])
        self.assertIn("char-mara", character["description"])

        for tool_name in ("scene_spec_write", "state_delta_write", "candidate_write", "candidate_get"):
            self.assertEqual(
                by_name[tool_name]["properties"]["scene_id"]["pattern"],
                "^ch[0-9]{2}-sc[0-9]{2}$",
            )
            self.assertIn("ch01-sc01", by_name[tool_name]["properties"]["scene_id"]["description"])

    def test_premise_report_is_reachable_through_dispatch(self) -> None:
        candidates = [
            {"id": "a", "logline": "A courier hides a letter and inherits its consequences.",
             "pov_character": "char-a", "theme_question": "What does concealment cost?"},
            {"id": "b", "logline": "Three siblings secretly bid against one another for a workshop.",
             "pov_character": "char-b", "theme_question": "What can inheritance buy?"},
            {"id": "c", "logline": "A night guard finds one gallery open only on her shifts.",
             "pov_character": "char-c", "theme_question": "What does attention obligate?"},
        ]
        out = tools.call_tool("premise_report", {"candidates": candidates})
        self.assertTrue(out["floor"]["ok"], out)

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

    def test_call_tool_rejects_unknown_arguments(self) -> None:
        out = tools.call_tool("kb_get", {"concept_id": "defaultness", "surprise": True})
        self.assertIn("additional property", out["error"])

    def test_promote_requires_confirm(self) -> None:
        out = tools.call_tool("promote", {"project": "salt-in-the-wire", "scene_id": "ch01-sc01",
                                          "candidate_file": "candidate-a.md"})
        self.assertIn("error", out)
        self.assertIn("confirm", out["error"])

    def test_backward_revision_requires_confirm(self) -> None:
        out = tools.call_tool(
            "revise_acceptance",
            {"project": "salt-in-the-wire", "scene_id": "ch01-sc01",
             "candidate_file": "candidate-a.md"},
        )
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

    def test_call_tool_rejects_scene_and_nested_path_escape(self) -> None:
        bad_scene = tools.call_tool(
            "scene_status", {"project": "salt-in-the-wire", "scene_id": "../canon",
                             "candidate": "candidate-a.md"})
        self.assertIn("invalid scene_id", bad_scene["error"])
        bad_candidate = tools.call_tool(
            "scene_status", {"project": "salt-in-the-wire", "scene_id": "ch01-sc01",
                             "candidate": "../../canon/index.json"})
        self.assertIn("traversal", bad_candidate["error"])

    def test_call_tool_rejects_critique_filename_escape(self) -> None:
        out = tools.call_tool("record_critique", {
            "project": "salt-in-the-wire", "scene_id": "ch01-sc01",
            "candidate": "candidate-a.md", "critic": "style-editor", "verdict": "pass",
            "filename": "../escaped",
        })
        self.assertIn("single path component", out["error"])

    def test_evaluate_revision_reaches_escalate_via_params(self) -> None:
        no_progress = [{"findings": [{"dimension": "defaultness", "severity": "material"}]}]
        out = tools.call_tool("evaluate_revision", {
            "before_findings": no_progress, "after_findings": no_progress, "target": "defaultness",
            "iteration": 1, "attempts_at_current_layer": 2, "max_attempts_per_layer": 2,
        })
        self.assertEqual(out["decision"], "escalate_layer")


class ToolWriteTests(unittest.TestCase):
    def test_run_role_review_uses_roster_and_records_by_default(self) -> None:
        sentinel_roster = {"style-editor": object()}
        expected = {"role": "style-editor", "verdict": "pass", "recorded": {"written": "x.json"}}
        with patch("fiction_compiler.role_runner.load_roster", return_value=sentinel_roster) as load, \
             patch("fiction_compiler.role_runner.run_role", return_value=expected) as run:
            out = tools.run_role_review("project-a", "ch01-sc01", "candidate-a.md", "style-editor")

        self.assertEqual(out, expected)
        load.assert_called_once_with(None)
        run.assert_called_once_with(
            "project-a", "ch01-sc01", "candidate-a.md", "style-editor",
            roster=sentinel_roster, record=True,
        )

    def test_run_role_review_returns_vendor_failure_as_tool_error(self) -> None:
        from fiction_compiler import role_runner

        with patch("fiction_compiler.role_runner.load_roster", return_value={"style-editor": object()}), \
             patch(
                 "fiction_compiler.role_runner.run_role",
                 side_effect=role_runner.VendorUnavailable("OPENAI_API_KEY is not set"),
             ):
            out = tools.run_role_review(
                "project-a", "ch01-sc01", "candidate-a.md", "style-editor", record=False
            )

        self.assertEqual(out["error"], "VendorUnavailable: OPENAI_API_KEY is not set")

    def test_run_review_panel_preserves_requested_roles_and_record_flag(self) -> None:
        sentinel_roster = {"a": object(), "b": object()}
        expected = {"completion": {"requested": 2, "completed": 2, "complete": True}}
        with patch("fiction_compiler.role_runner.load_roster", return_value=sentinel_roster), \
             patch("fiction_compiler.role_runner.run_panel", return_value=expected) as run:
            out = tools.run_review_panel(
                "project-a", "ch01-sc01", "candidate-a.md", ["a", "b"], record=False
            )

        self.assertEqual(out, expected)
        run.assert_called_once_with(
            "project-a", "ch01-sc01", "candidate-a.md", ["a", "b"],
            roster=sentinel_roster, record=False,
        )

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
