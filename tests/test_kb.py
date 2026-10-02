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
        self.sources = register["sources"]
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

    def test_fiction_corpus_has_machine_readable_eu_de_rights_gate(self) -> None:
        for source in self.sources:
            if source.get("stream") != "fiction-corpus":
                continue
            with self.subTest(source=source["id"]):
                rights = source.get("rights")
                self.assertIsInstance(rights, dict)
                self.assertIn(rights.get("eu_de_status"), {
                    "cleared", "repository-owned", "per-title-verification-required", "not-cleared",
                })
                self.assertTrue(rights.get("basis"))
                status = rights["eu_de_status"]
                policy = rights.get("full_text_policy")
                if status in {"cleared", "repository-owned"}:
                    self.assertEqual(policy, "allowed")
                    self.assertTrue(rights.get("verified_on"))
                elif status == "per-title-verification-required":
                    self.assertEqual(policy, "blocked-pending-title-check")
                else:
                    self.assertEqual(policy, "blocked")


if __name__ == "__main__":
    unittest.main()
