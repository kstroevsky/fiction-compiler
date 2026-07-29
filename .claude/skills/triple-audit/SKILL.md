---
name: triple-audit
description: Runs independent hard, literary, and defaultness audits on scene candidates and produces evidence-grounded critique files.
---
Two of the three audits have deterministic tool support; the literary one is LLM judgment. Run all
three independently and preserve disagreement.

1. **Hard audit (code).** `hard_audit(project, scene)` (MCP) or `python3 scripts/hard_audit.py
   <project> <scene>`. Knowledge cutoff, causal refs, POV, chronology, promise ledger. **A fatal
   finding blocks promotion** — fix it before anything else.
2. **Defaultness (code).** `defaultness_lint` each candidate (or `scripts/defaultness_lint.py
   <project> <scene>`). Surface tics only; the literary read below finds the deeper defaults.
3. **Literary audit (LLM).** Delegate to the specialist agents — this is what code cannot check:
   - continuity-auditor for anything the hard audit can't reach,
   - character-simulator for intentionality/agency,
   - style-editor for voice/rhythm (only if structure passes),
   - adversarial-reader for predictability, unearned emotion, false profundity.
4. Require **exact textual evidence** and a **repair-layer** label in every finding.
5. Anonymize candidates and reverse order for at least one pairwise comparison (fight order/label bias).
6. Write separate `critiques/*.json` files (critique.schema). **Preserve disagreement — do not average it away.**
   Each **candidate-specific** critique (the literary personas + defaultness) must carry
   `audit_class` and `candidate_sha256` — the sha256 of the exact candidate file it judged — or the
   promotion gate will not count it as evidence (ADR 0003). Reuse the `candidate_sha256` that
   `defaultness_lint` already stamps for that candidate, or compute `shasum -a 256 <candidate>`. The
   hard audit is candidate-independent and needs no hash.
7. To decide whether a *revision* clears a finding without regressing elsewhere, use `evaluate_revision`
   (the story PDCA CHECK/ACT) rather than judging by feel.
