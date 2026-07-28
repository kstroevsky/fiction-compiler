from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KB = ROOT / "kb"


class KnowledgeBaseTests(unittest.TestCase):
    """The KB must have substance, not just directories."""

    def setUp(self) -> None:
        self.index = json.loads((KB / "index.json").read_text(encoding="utf-8"))
        register = json.loads((KB / "source-register.json").read_text(encoding="utf-8"))
        self.source_ids = {s["id"] for s in register["sources"]}

    def test_starter_concepts_present(self) -> None:
        # A non-trivial starter set (guards against the KB silently emptying).
        self.assertGreaterEqual(len(self.index["concepts"]), 8)

    def test_every_concept_card_exists(self) -> None:
        for concept in self.index["concepts"]:
            card = KB / concept["card"]
            self.assertTrue(card.exists(), f"missing card for {concept['id']}: kb/{concept['card']}")

    def test_every_cited_source_is_registered(self) -> None:
        for concept in self.index["concepts"]:
            for source_id in concept.get("sources", []):
                self.assertIn(source_id, self.source_ids, f"{concept['id']} cites unregistered {source_id}")

    def test_every_concept_declares_a_consumer(self) -> None:
        # 'used_by' is what keeps a card from being inert.
        for concept in self.index["concepts"]:
            self.assertTrue(concept.get("used_by"), f"{concept['id']} has no used_by consumer")

    def test_no_orphan_cards(self) -> None:
        referenced = {(KB / c["card"]).resolve() for c in self.index["concepts"]}
        for card in KB.rglob("*.md"):
            if card.name.lower() == "readme.md":
                continue
            self.assertIn(card.resolve(), referenced, f"orphan card: kb/{card.relative_to(KB)}")


if __name__ == "__main__":
    unittest.main()
