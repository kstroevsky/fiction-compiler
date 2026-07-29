# ADR 0003 — Tamper-evident, atomic, confined promotion

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. This is slice 2 of the promotion trust core; it builds directly on
ADR 0002 (which enforced the triple-audit gate). Recorded here because the change is framework-global.

## 1. Failure observed
After ADR 0002 the gate proved the *right kinds* of clean audits were present, but it still **trusted**
each critique's `candidate` field, and canon was **mutable and non-atomic**:
- A critique could claim to judge candidate B while the code had no way to prove it judged B's exact
  bytes — the reviewer's target invariant ("the exact candidate passed the required audits") was unmet.
- Canon reconstruction reads each accepted scene's *current* `state-delta.json`; editing an old
  accepted delta silently rewrites all downstream story history, with no hash, chain, or detection.
- `promote_candidate` performed three separate filesystem writes (manuscript, canon index, decision)
  with no lock and no rollback; a crash or concurrent promotion could leave canon half-updated.
- `workspace.project_dir` returned arbitrary absolute paths and `..`-containing paths unchanged, so an
  agent-controlled MCP call could point tools outside the project tree.

## 2. Exact evidence
- `src/fiction_compiler/state.py` `_load_delta`: reads `scenes/<id>/state-delta.json` at replay time;
  nothing pins its content. `promote.py` decision record (post-ADR-0002) stored no hashes.
- `schemas/critique.schema.json`: `candidate` is a free string; no content binding.
- `src/fiction_compiler/promote.py`: `shutil.copy2` + two `write_text` calls, no lock/rollback.
- `src/fiction_compiler/workspace.py` `project_dir`: `if candidate.is_absolute(): return candidate`;
  no traversal check. `project_dir` is used only by the MCP layer (`tools.py`) — the agent surface.

## 3. Root-layer diagnosis
Computational-operations / verification layer. The intermediate representation (canon) lacked content
identity, and the promotion operation lacked transactional and confinement properties. No narrative or
schema change is required — the artifacts already carried the bytes; nothing hashed or guarded them.

## 4. Minimal proposed change
New module `src/fiction_compiler/integrity.py`:
- `sha256_file` / `seed_hash` / `link_hash`; a **linear canon hash chain** where each accepted scene
  records `parent_canon_hash` (the chain it built on) and `resulting_canon_hash =
  link_hash(parent, scene_id, sha256(delta))`; `verify_canon(project)` recomputes the chain and flags
  any accepted delta or seed ledger edited since promotion. Legacy scenes without a manifest are
  skipped, so pre-ADR-0003 projects still validate.
- `PromotionLock` (O_EXCL lock file) and `AtomicBatch` (staged temp writes → atomic `os.replace`, with
  prior-bytes rollback on any exception).

`promote_candidate` now: hashes the candidate; passes that hash to the gate, which credits a
candidate-specific critique toward its class **only** if the critique's `candidate_sha256` matches (a
present-but-wrong hash is a loud block; the scene-level hard audit is exempt); confines the candidate
to the project; writes an **acceptance manifest** (`candidate_sha256`, `state_delta_sha256`,
`parent_canon_hash`, `resulting_canon_hash`, per-critique `sha256`) atomically under the lock.

Supporting: `critique.schema` gains optional `candidate_sha256` (+ `audit_class` from ADR 0002);
`defaultness.lint_file` auto-stamps both; the triple-audit skill instructs literary critics to stamp;
`workspace.confine_project` / `confine_file` enforce approved roots at the `call_tool` MCP boundary;
`validate_workspace` runs `verify_canon` per project.

## 5. New regression case
`tests/test_promote.py` (`PromotionIntegrityTests`): the manifest records all hashes; `verify_canon`
is clean after promotion and flags a post-hoc delta edit; a held lock blocks a second promotion; a
simulated crash mid-commit rolls back (no manuscript, canon index unchanged, lock released); a
candidate outside the project is refused. `PromoteTests`: a wrong `candidate_sha256` is refused; a
literary critique with the hash stripped no longer counts as coverage. `tests/test_tools.py`: the
MCP boundary rejects project `..` traversal, an absolute project outside root, and a file path escape.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: editing an accepted `state-delta.json` changed reconstructed history with no detection; a
  critique's `candidate` string was taken on trust; a mid-promotion crash could orphan a manuscript.
- After: `verify_canon` returns `"<scene>: state-delta.json changed since promotion (canon hash
  mismatch)"`; a critique whose `candidate_sha256` ≠ the promoted bytes is refused; a crash mid-commit
  leaves no manuscript and an unchanged canon index. Suite: 62 → 72 tests, all passing; `validate_
  workspace` still passes (committed examples are legacy/skipped by `verify_canon`).

## 7. Known trade-offs
- The canon chain is linear and assumes fabula-order promotion; inserting an earlier scene later is
  reported as a chain break rather than supported (documented in `integrity.py`).
- `AtomicBatch` is exception-safe, not kill-safe: a SIGKILL between two `os.replace` calls can still
  land a subset of files — but `verify_canon` / workspace validation then detect the torn state.
- The hard audit remains candidate-independent and unhashed against its spec/delta inputs; a stale
  hard audit from before a revision is still not detected (carried over from ADR 0002 §7).
- Hash binding is enforced for coverage, but a dishonest critic could still compute the correct hash
  over prose it did not truly read; the manifest records the hashes for audit, and no code can prove
  honest reading. Content binding raises the floor, it does not make critics trustworthy.

## 8. Human approval status
Authorized as the user-selected "build all of P0" continuation of the reviewer's Priority 0. The
constitution (`AGENTS.md`) is unchanged. Revert path: remove `src/fiction_compiler/integrity.py`, and
git history of `promote.py`, `workspace.py`, `tools.py`, `defaultness.py`, `schemas/critique.schema.json`,
`scripts/validate_workspace.py`, and the test files.
