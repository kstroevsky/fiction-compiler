# ADR 0008 — Tournament: judge ledger, disagreement ingestion, and `.runs/` evidence

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Second slice of Priority 2, completing the deferred items of ADR
0007. Recorded here because the change is framework-global.

## 1. Failure observed
ADR 0007 built the deterministic selection math (anonymize, order, Pareto, score-based
disagreement) but deferred three things the review named: ingesting explicit LLM **judge**
rankings, recording **which judge saw which** blinded order (isolation metadata), and **preserving
the evaluation evidence** in `.runs/` (which `AGENTS.md` requires: "Preserve rejected branches and
evaluation evidence in `.runs/`; never overwrite the only copy of a draft"). Without these, judge
disagreement could not be recorded from the judges themselves, and a tournament left no durable,
blinded artifact.

## 2. Exact evidence
- `src/fiction_compiler/tournament.py` (post-ADR-0007): `run_tournament` derived disagreement only
  from critique scores; it had no `judges`/`judge_rankings` parameters and wrote nothing to disk.
- `.claude/skills/triple-audit/SKILL.md` step 5 asks for anonymized, reversed comparison but the
  code produced no blinded copies for a judge to actually read.
- `AGENTS.md` "Architectural invariants": evaluation evidence belongs in `.runs/`.

## 3. Root-layer diagnosis
Selection/evaluation layer — specifically its evidence and isolation machinery, which is
deterministic and therefore code's responsibility.

## 4. Minimal proposed change
- `tournament.py`: `assign_orders(judges, orders)` → a per-judge isolation ledger (cycling the
  forward/reversed/shuffled orders); `disagreement_from_rankings(rankings)` → distinct top picks and
  whether judges agree on the winner. `run_tournament(..., judges, judge_rankings)` attaches a
  `judge_ledger` and a `judge_disagreement`, and OR-folds judge disagreement into the record's
  `disagreement` flag (so a split among judges is recorded even when the scores had a dominator —
  disagreement is never averaged away).
- `tools.tournament(..., persist, judges, judge_rankings)`: with `persist=true`, writes blinded
  candidate copies to `.runs/tournament/<scene>/<ts>/blind/<label>.md` (the only artifact a judge
  should see) and the full record (including the reveal map, for the orchestrator) to
  `record.json`, returning `persisted_to`.

## 5. New regression case
`tests/test_tournament.py`: `assign_orders` cycles orders across judges; `disagreement_from_rankings`
detects agreement and a split; `run_tournament` attaches a judge ledger and marks `disagreement`
true when judges split despite a score dominator; `persist=true` writes `blind/A.md` + `blind/B.md`
+ `record.json`, and the blinded files contain none of the true `candidate-…` identity.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: a tournament was an in-memory dict; judge disagreement could only be inferred from scores;
  no blinded artifact existed for a judge to read.
- After: `persist=true` yields a `.runs/tournament/<scene>/<ts>/` directory whose `blind/` holds only
  label-named prose, with the reveal map confined to `record.json`; supplying `judge_rankings`
  records the judges' distinct top picks and flips `disagreement` to true when they split. Suite 99
  → 103; `validate_workspace` passes.

## 7. Known trade-offs
- Blinding is guaranteed to *exist* (the `blind/` dir is identity-free), but the tool still returns
  the reveal map to its caller; a caller must hand judges only the `blind/` directory. Enforcing
  that boundary at the transport is not yet done.
- `judge_rankings` are trusted as supplied; the engine does not verify a judge actually evaluated the
  blinded prose it was assigned (no signed judgment).
- `.runs/` is written under the project; there is no retention/GC policy yet.

## 8. Human approval status
Authorized as part of the user-directed "continue both" step. The constitution (`AGENTS.md`) is
unchanged. Revert path: git history of `tournament.py`, `tools.py`, and `tests/test_tournament.py`.
