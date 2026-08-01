from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import trace  # noqa: E402


class TraceTests(unittest.TestCase):
    def test_log_appends_in_order_with_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            trace.log(proj, "ch01-sc01", "critique", critic="adversarial-reader", verdict="pass")
            trace.log(proj, "ch01-sc01", "promote", candidate="candidate-a.md")
            events = trace.read(proj, "ch01-sc01")
            self.assertEqual([e["event"] for e in events], ["critique", "promote"])
            self.assertEqual(events[0]["critic"], "adversarial-reader")
            self.assertTrue(all("ts" in e and e["scene_id"] == "ch01-sc01" for e in events))

    def test_read_missing_scene_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(trace.read(Path(tmp), "ch01-sc99"), [])

    def test_scenes_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            trace.log(proj, "ch01-sc01", "critique", critic="x")
            trace.log(proj, "ch01-sc02", "critique", critic="y")
            self.assertEqual(len(trace.read(proj, "ch01-sc01")), 1)
            self.assertEqual(len(trace.read(proj, "ch01-sc02")), 1)


if __name__ == "__main__":
    unittest.main()
