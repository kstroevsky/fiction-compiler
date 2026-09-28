from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMOTE = ROOT / "scripts" / "promote_candidate.py"
HARD = ROOT / "scripts" / "hard_audit.py"

sys.path.insert(0, str(ROOT / "src"))
from fiction_compiler import acceptance  # noqa: E402
from tests.test_promote import build  # noqa: E402


class CliTruthTests(unittest.TestCase):
    def test_promote_cli_can_supply_human_gate_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = build(Path(tmp))
            brief = project / "brief" / "project.json"
            brief.parent.mkdir(parents=True)
            brief.write_text(json.dumps({"id": "proj", "human_gates": ["promotion"]}))
            result = subprocess.run(
                [sys.executable, str(PROMOTE), str(project), "ch01-sc01", "c.md",
                 "--approved-by", "editor@test", "--rubric-version", "rubric@7"],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            oid = acceptance.load_index(project)["head_acceptance"]
            snapshot = acceptance.load_object(project, oid)
            self.assertEqual(snapshot["human_gate"]["approver"], "editor@test")
            self.assertEqual(snapshot["rubric_version"], "rubric@7")

    def test_hard_audit_cli_exits_nonzero_on_material_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            scene = project / "scenes" / "ch01-sc01"
            scene.mkdir(parents=True)
            (scene / "spec.json").write_text(json.dumps({
                "id": "ch01-sc01", "pov": "", "participants": ["char-missing"],
                "required_events": [],
            }))
            (project / "canon").mkdir(parents=True)
            (project / "canon" / "index.json").write_text(json.dumps({"accepted_state_deltas": []}))
            result = subprocess.run(
                [sys.executable, str(HARD), str(project), "ch01-sc01"], cwd=ROOT,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("material", result.stdout)


if __name__ == "__main__":
    unittest.main()
