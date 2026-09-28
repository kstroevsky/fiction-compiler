---
name: promote-candidate
description: Promotes a reviewed scene candidate into the manuscript, applies its state delta, records the decision, and reruns regression checks.
---
1. Verify triple-audit artifacts exist and no unresolved fatal finding remains.
2. Confirm the human/configured acceptance gate.
3. Run `python3 scripts/promote_candidate.py <project-dir> <scene-id> <candidate-file>`.
4. Review or create `state-delta.json`.
5. Update promises, knowledge, relationships, and timeline as needed.
6. Run validation and tests.
7. Record why this candidate won and what trade-offs remain.
