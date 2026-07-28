from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceTests(unittest.TestCase):
    def test_workspace_validates(self) -> None:
        result = subprocess.run(
            ["python3", "scripts/validate_workspace.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scene_schema_has_repair_relevant_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "scene.schema.json").read_text())
        required = set(schema["required"])
        self.assertTrue({"desire", "conflict", "turn", "exit_state"}.issubset(required))


if __name__ == "__main__":
    unittest.main()
