---
name: promote-candidate
description: Promotes a reviewed scene candidate into the manuscript, applies its state delta, records the decision, and reruns regression checks.
---
1. Review or create the scene's `state-delta.json` **before promotion**. It must describe the
   candidate's accepted consequences: facts, knowledge, relationships, predicates/resources,
   promises, and scene time. Do not edit seed canon ledgers to make the candidate fit.
2. Run the review policy's required deterministic/literary audits against the exact candidate bytes.
   Resolve, recheck, adjudicate, or explicitly waive applicable predecessor findings as required.
3. Confirm the configured human acceptance gate and record the decision/rubric identity when required.
4. Run `python3 scripts/promote_candidate.py <project-dir> <scene-id> <candidate-file>`. Promotion
   freezes the candidate/spec/delta/review evidence and materializes the accepted canon/manuscript view.
5. Run workspace validation and framework regressions. Verify the canonical acceptance chain.
6. Record why this candidate was chosen and what trade-offs or unresolved advisory evidence remain.
