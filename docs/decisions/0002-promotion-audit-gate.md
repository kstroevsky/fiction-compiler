# ADR 0002 — Enforce the triple-audit gate at promotion

Engineering decision record for a repo-global change, following the eight fields required by
`constitution/change-policy.md`. Recorded here (not under a single `projects/<slug>/decisions/`)
because the change is framework-global, not story-specific.

## 1. Failure observed
`AGENTS.md` states a candidate "cannot be promoted until it passes" a hard, literary, and
defaultness audit, over critiques bound to the specific candidate. The code did not enforce this.
`promote_candidate()` checked only that **at least one** JSON file existed under `critiques/` — it
never read a critique's contents, so a critique reporting `revise`, a critique judging a *different*
candidate, or an empty `{"critic": "..."}` shell all satisfied the gate. The declared architecture
and the enforced architecture had diverged: canon could advance without the audits the constitution
requires.

## 2. Exact evidence
- `src/fiction_compiler/promote.py` (pre-change): `critiques = sorted(... .glob("*.json"))`; the only
  check was `if not critiques: raise`. No verdict, candidate, critic, or severity was inspected.
- `projects/salt-in-the-wire/scenes/ch01-sc02/`: `candidate-b.md` was promoted, but 3 of its 4 listed
  critiques judge `candidate-a.md`; `character-simulator.json` records `verdict: revise` with a
  `material` knowledge finding; **no hard-audit critique exists for the scene**. Two candidate-A
  critiques record `verdict: pass` while carrying `material` findings.
- `projects/verbatim/scenes/ch01-sc01` and `ch01-sc02`: only a `hard-audit.json` critique is present;
  no literary or defaultness audit was required to promote.
- `schemas/critique.schema.json`: `candidate` is a free string; there is no cross-field rule tying
  `verdict` to `findings`, so `verdict: pass` + `material` finding is schema-valid.
- `tests/test_promote.py` (pre-change): the happy-path fixture used `{"critic": "hard-audit"}` — an
  empty shell — as a *sufficient* critique, so the green suite proved nothing about the invariant.

## 3. Root-layer diagnosis
Verification layer (promotion gate). The critiques carried enough information to enforce the
constitution; the gate simply never consulted it. This is a process/enforcement defect, not a
schema or narrative defect — routed to the lowest responsible layer per `AGENTS.md`.

## 4. Minimal proposed change
Make `promote_candidate()` read the critiques and refuse unless, over the critiques that actually
judge **this** candidate:
- each is schema-valid;
- `verdict == "pass"` and it carries no `material`/`fatal` finding (a `pass` may not contradict a
  blocking finding; a non-`pass` verdict is unresolved and blocks);
- all three audit classes — **hard**, **literary**, **defaultness** — are covered by a *clean*
  critique.

A critique binds to the candidate when it judges that exact candidate file; the hard audit is
candidate-independent (its `candidate` is the scene id) and binds to every candidate of the scene.
Critiques judging a *different* candidate are ignored as evidence. Audit class is read from an
optional new `audit_class` field, falling back to a critic→class map sourced from the `triple-audit`
skill (`hard-audit`→hard, `defaultness-lint`→defaultness, the LLM personas→literary). The gate runs
**before** any filesystem write, so a rejected promotion leaves no trace. The decision record now
lists the `binding_critiques` actually credited.

**Explicitly out of scope for this slice** (deferred to a later ADR): content-hash binding of
critique↔candidate, an immutable acceptance manifest with parent/resulting canon hashes, atomic
promotion (lock + temp-write + rename + rollback), and MCP path confinement. This slice closes the
*enforcement* hole first; those harden it.

## 5. New regression case
`tests/test_promote.py`:
- positive: a full clean triple-audit set promotes; the decision's `binding_critiques` cover all
  three classes;
- negative unit cases: the old lone-empty-critique shape is now refused; critiques for another
  candidate are not counted; `pass` + `material` is refused; `revise` is refused; a missing
  defaultness audit is refused;
- committed-example regression: promoting `salt-in-the-wire/ch01-sc02` (candidate-b) and
  `verbatim/ch01-sc01` — run against a copy so the committed evidence stays untouched — now raises,
  encoding the exact historical failures as permanent guards.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: `promote_candidate(salt-in-the-wire, ch01-sc02, candidate-b.md)` would succeed on evidence
  that judged a different candidate and omitted the hard and defaultness audits.
- After: it raises `Audit gate failed for ch01-sc02 candidate candidate-b.md: no clean hard audit
  found …; no clean defaultness audit found …`, and no manuscript/canon/decision file is written.
- Suite: 55 → 62 tests, all passing; `validate_workspace.py` still passes (the committed post-promotion
  projects are unchanged — the gate runs only at promotion time).

## 7. Known trade-offs
- The critic→class map is a fixed table; a new critic persona must be added to it (or carry an
  explicit `audit_class`) to count toward coverage.
- The hard audit is still candidate-independent and does not yet read the prose; a stale hard audit
  from before a revision is not detected (deferred with the hashing/manifest slice).
- The gate trusts that a critique file's contents are honest; without content hashes it cannot yet
  prove the critique judged the candidate *bytes* that are being promoted (deferred).
- The committed examples now fail their own gate by design; they are retained as negative fixtures
  rather than retrofitted, so the repo ships a guard against the failure it once contained.

## 8. Human approval status
Authorized as the user-selected "enforcement gate only" first slice of the reviewer's Priority 0
("make canon promotion trustworthy"), with the committed examples chosen to serve as regression
fixtures. The constitution (`AGENTS.md`) is unchanged — this enforces an existing rule, it does not
add one. Revert path: git history of `src/fiction_compiler/promote.py`, `tests/test_promote.py`,
and the `audit_class` addition in `schemas/critique.schema.json`.
