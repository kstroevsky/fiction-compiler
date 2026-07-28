from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import defaultness, schema  # noqa: E402

DEFAULT_HEAVY = """Her heart pounded in her chest.
She felt a wave of fear wash over her.
She saw the door slowly open.
She realized she was too late.
Little did she know, time stood still.
"Run," he said quietly."""

CLEAN = (
    "The relay hung open, two wires bright where the cutter had bitten. "
    "Mara pressed her thumb to the cold copper and counted to ten before she moved."
)


class DefaultnessTests(unittest.TestCase):
    def test_default_heavy_prose_is_flagged(self) -> None:
        findings = defaultness.lint_text(DEFAULT_HEAVY)
        dims = {f["dimension"] for f in findings}
        self.assertIn("defaultness", dims)
        self.assertIn("rhythm", dims)  # 'She ...' opener run
        self.assertTrue(any(f["severity"] == "material" for f in findings))
        # specific cliché detected with evidence
        self.assertTrue(any("heart pounded" in f["evidence"] for f in findings))

    def test_clean_prose_passes(self) -> None:
        self.assertEqual(defaultness.lint_text(CLEAN), [])

    def test_output_is_schema_valid(self) -> None:
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(DEFAULT_HEAVY)
            path = Path(handle.name)
        critique = defaultness.lint_file(path)
        self.assertEqual(critique["verdict"], "revise")
        self.assertEqual(schema.validate_named(critique, "critique"), [])

    def test_catalog_loads_from_kb(self) -> None:
        catalog = defaultness.load_catalog()
        self.assertIn("cliches", catalog)
        self.assertIn("patterns", catalog["cliches"])


if __name__ == "__main__":
    unittest.main()
