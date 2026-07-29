from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler.assemble import assemble  # noqa: E402


class AssembleTests(unittest.TestCase):
    def test_stitches_accepted_scenes_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "brief").mkdir()
            (project / "brief" / "project.json").write_text(json.dumps({"title": "Test Story"}))
            (project / "canon").mkdir()
            # deliberately out of order to prove sorting
            (project / "canon" / "index.json").write_text(json.dumps({"accepted_state_deltas": ["ch01-sc02", "ch01-sc01"]}))
            chapters = project / "manuscript" / "chapters"
            chapters.mkdir(parents=True)
            (chapters / "ch01-sc01.md").write_text("First scene body.")
            (chapters / "ch01-sc02.md").write_text("Second scene body.")

            result = assemble(project)
            text = (project / "manuscript" / "manuscript.md").read_text()

            self.assertEqual(result["scenes"], ["ch01-sc01", "ch01-sc02"])
            self.assertIn("# Test Story", text)
            self.assertIn("## Chapter 1", text)
            self.assertLess(text.index("First scene body."), text.index("Second scene body."))
            self.assertIn("·", text)  # a centered scene break between same-chapter scenes

    def test_skips_unpromoted_scene_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "brief").mkdir()
            (project / "brief" / "project.json").write_text(json.dumps({"title": "T"}))
            (project / "canon").mkdir()
            (project / "canon" / "index.json").write_text(json.dumps({"accepted_state_deltas": ["ch01-sc01", "ch01-sc09"]}))
            chapters = project / "manuscript" / "chapters"
            chapters.mkdir(parents=True)
            (chapters / "ch01-sc01.md").write_text("Only real scene.")
            result = assemble(project)  # ch01-sc09 has no file
            self.assertEqual(result["scenes"], ["ch01-sc01"])


if __name__ == "__main__":
    unittest.main()
