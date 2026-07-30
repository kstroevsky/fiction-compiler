# Implementation Roadmap

Status assessment and staged plan, measured against `docs/original-design-brief.md`.
The brief is treated as **product vision**, not a binding spec — deviations are called out explicitly.

Ground-truth snapshot: `make validate` and `make test` both pass, but they assert almost
nothing (see below). Passing checks here are not evidence of a working compiler.

---

## 1. What this repository actually is today

A **constitution, an operating manual, and a directory skeleton** — plus a structural
JSON linter. It is a well-designed *contract* for a fiction compiler. It is **not yet a
compiler**: the deterministic machinery that the brief's entire thesis depends on
(external, code-level feedback that "rejects malformed output") is the part that is unbuilt.

Everything currently load-bearing is either prose the LLM is asked to follow (skills,
agents, docs) or JSON that nothing enforces. The brief's argument is that fiction quality
should be shifted *off* free LLM judgment and *onto* code wherever possible; right now the
code carries almost none of that load.

### Component status (vision → reality)

| Brief component | Artifact present | Actually implemented? | Evidence |
|---|---|---|---|
| Constitution / reader contract | `constitution/`, `AGENTS.md`, `CLAUDE.md` | **Yes** (as prose) | Complete and coherent |
| 6 typed schemas | `schemas/*.json` | **Decorative** — never enforced | No `jsonschema` in repo; `validate_workspace.py` only parses JSON + matches ids to dir names |
| Workspace validation | `scripts/validate_workspace.py` (90 lines) | **Structural only** | Checks id↔dirname, dup ids, delta-exists-if-promoted. No schema, no narrative constraints |
| Minimal context compilation | `scripts/compile_scene_context.py` (56 lines) | **No** — it's a file concatenator | Statically dumps planning files; no state replay, no relevance filter, no knowledge cutoff |
| Event-sourced canon / `reconstruct_state_before` | `canon/*.jsonl` templates | **No** — the keystone primitive is absent | No code folds deltas/ledgers into a point-in-time state |
| Candidate promotion + `append_state_delta` | `src/fiction_compiler/promote.py`, `integrity.py` | **Yes**, gate **enforced** (ADR 0002) and promotion **tamper-evident + atomic + confined** (ADR 0003) — candidate-bound hashes, an acceptance manifest with a canon hash chain, `os.replace` under a lock with rollback, and MCP path confinement | `evaluate_audit_gate` + `verify_canon`; committed examples retained as negative fixtures. Immutable *acceptance signatures* / human-gate identity still ⬜ |
| Audit 1 — hard/symbolic (as code) | `triple-audit` skill | **No** — delegated to an LLM subagent | Skill step 2 hands continuity to `continuity-auditor` agent; brief says this must be code |
| Audit 2/3 — literary + defaultness | 5 agent defs + skill | **As prose** (LLM personas) | `.claude/agents/*.md`, `.codex/agents/*.toml` — reasonable, but unverified by code |
| Blind tournament / judge-bias mitigation | described in skill | **No code** | Anonymization/order-reversal/disagreement are instructions, not a harness |
| Quality vector Q + Pareto selection | described in brief §1 | **No** | No representation, no scoring, no Pareto logic anywhere |
| Anti-obviousness (continuation ensemble, Originality\*) | brief §5 | **No** | Not present in any form |
| Knowledge base (Tiers 0–4) | `kb/` dirs + `source-register.json` | **Empty** — see §2 | 6 empty dirs; `sources: []` |
| Self-improvement + regression harness | `retrospective` skill, `evals/` dirs | **No** — no fixtures, no runner | `evals/regression/` and `evals/reports/` are empty template dirs |
| `src/fiction_compiler/` library | package dir | **Empty** | `__init__.py` is 1 line; all logic lives in 4 standalone scripts |
| Observability / run manifests / cost | `.runs/` | **Minimal** | Only a timestamped context bundle; no model/prompt-version/token provenance |
| End-to-end example project | `projects/_template/` | **No real project** | Nothing exercises the pipeline; validation passes because there is nothing to validate |

---

## 2. The knowledge base is a set of empty folders

Called out separately because directory structure is the easiest thing to mistake for
completion.

- `kb/narratology/`, `kb/craft/`, `kb/genre/`, `kb/style/`, `kb/research/`,
  `kb/corpus-notes/` — **all empty**.
- `kb/source-register.json` — a schema stub with `"sources": []`. Zero registered sources.
- `docs/knowledge-base.md` describes Tiers 0–4 (constitution → indexes → operational notes
  → deep references → corpora). **Tiers 1–4 contain no content.**

The brief's design (§6) requires Level-0 concept index, Level-1 concept cards (YAML with
`definition / use_when / diagnostic_questions / failure_modes / conflicts_with / sources /
confidence`), Level-2 analytical notes, and Level-3 sources. **None of these exist.** The
craft seed list (Le Guin, Gardner, Prose, Wood, Egri, McKee, Swain) and the Living Handbook
of Narratology are named in the brief but not registered, summarized, or encoded.

**Do not build KB content first.** Inert concept cards that no audit or skill retrieves are
exactly the "folder full of PDFs injected into every prompt" the brief warns against. KB
content is only worth writing once the retrieval machinery that consumes it exists — hence
it lands in Stage 3, after the context compiler and hard audits that reference it.

---

## 3. Where I would push back on the brief

Treating it as vision, not gospel:

- **Reader-cognition simulation (§2.9)** — a full model of reader knowledge/belief/suspense
  is speculative and hard to validate. Scope down to a lightweight *reader-expectation*
  tracker used only by the anti-obviousness engine (Stage 4). Don't build the whole thing.
- **GUI / context viewer (§11 close)** — the brief already defers this. Keep it deferred
  (Stage 6); it is author-experience, not correctness.
- **Agent count** — the brief's own guidance ("five specialists, not twenty") is right; the
  repo already follows it. Keep it.
- **Quality vector precision** — resist turning Q into a single averaged score early. Keep
  it multidimensional and Pareto until a human-defined weighting exists (the brief agrees;
  the risk is implementers collapsing it for convenience).

---

## 4. Staged roadmap (keystone-first, each stage independently shippable)

Ordering principle: build the primitive everything else depends on first
(`reconstruct_state_before`), make the schemas real so later stages can trust their inputs,
and only write KB prose once code consumes it. Every stage ends green and adds a regression
test, not just a feature.

> **Build status (updated).** Stage 0 ✅, Stage 1 ✅, Stage 2 ✅ are implemented and tested.
> Stage 3 🟡 has a starter KB — 16 concept cards across two source streams (craft-instruction,
> many public-domain classics + fiction-corpus), a defaultness catalog, and a source register
> with EU/DE copyright notes, all integrity-checked by `validate_workspace`. Stage 4 🟡 has the
> deterministic defaultness linter; the Pareto/tournament/continuation-ensemble pieces remain.
>
> **Two self-improvement loops** (see `docs/self-improvement-loops.md`): the **story** PDCA loop's
> deterministic CHECK/ACT is built (`src/fiction_compiler/revision.py`, `scripts/revise_scene.py`,
> per-scene `revision-log.jsonl`) — this is the manuscript's own improvement loop. The **framework**
> PDCA loop (Stage 5) still has only the `retrospective` skill + `change-policy`; its
> regression-fixture runner and run-manifest observability remain ⬜. Stage 6 (GUI) ⬜.
> **Tools for the author.** The deterministic engine is exposed to the LLM as callable tools via
> a dependency-free MCP server (`scripts/fiction_mcp.py`, wired in `.mcp.json` and `.codex/config.toml`):
> `kb_search`/`kb_get`, `state_before`, `compile_context`, `hard_audit`, `defaultness_lint`,
> `evaluate_revision`. Plus the `avoid-defaults` anti-obviousness skill (LLM-facing craft, not code).
> The engine equips the author; it does not replace the creative act. See `docs/mcp-and-tools.md`.
>
> **Promotion is now gated (ADR 0002) and tamper-evident (ADR 0003).** The triple-audit protocol is
> *enforced* in code: a candidate promotes only when clean hard, literary, and defaultness critiques
> that judge *that exact candidate* (bound by `candidate_sha256`) exist; a non-`pass` verdict, a
> `material`/`fatal` finding, a wrong/absent hash, or evidence judging a different candidate blocks it,
> before any write. Promotion writes an acceptance manifest with a canon hash chain (`parent`→
> `resulting`), so editing an accepted delta is detected by `verify_canon` (run in `validate_workspace`);
> the three writes commit atomically under a project lock with rollback; and MCP-supplied paths are
> confined to approved roots. The committed `salt-in-the-wire` and `verbatim` examples predate this and
> now fail their own gate by design — retained as negative regression fixtures. **P0 is complete
> (ADR 0012):** a project listing `"promotion"` in its `human_gates` cannot be promoted without a
> recorded `approved_by`, and the acceptance manifest carries `human_gate` + `rubric_version` — so the
> reviewer's headline invariant now holds in full: *the exact candidate passed the exact required
> audits under a recorded rubric and human gate.*
>
> **Story IR is becoming executable (ADR 0004, P1 slice 1).** State now carries typed predicates
> (`predicate_changes` + `canon/world-state.jsonl`, queried via `StoryState.holds`) and *directional*
> relationships (ordered `(subject, object)` with dimensions like trusts/fears/owes; legacy `{pair,
> state}` still works). Event preconditions/effects may be typed atoms, and the hard audit now
> *evaluates* them — an unmet precondition or an effect missing from the scene's delta is a material
> finding, turning the event graph from descriptive into checkable. An optional per-project
> **predicate ontology** (`canon/ontology.json`, ADR 0005) declares legal predicates + arity + entity
> types, so a typo like `located_att` is caught as a material finding instead of silently becoming an
> unsatisfiable predicate. Fabula vs discourse are now distinct (ADR 0006): scene id is discourse
> (reading) order, `delta.time` is fabula (event) time, and a scene's optional `narrative_mode`
> (analepsis/prolepsis) marks a deliberate divergence so a flashback is no longer flagged as "time
> runs backward". Still ⬜ in P1: richer resource/physical state, a real entity type system, and
> fabula-**ordered** state reconstruction (a flashback still replays in discourse order today).
>
> **Selection engine exists (ADR 0007, P2 slice 1).** A deterministic `tournament` module + MCP tool
> owns the fairness machinery the contract requires: seeded anonymization (blinded labels + reveal
> map), forward/reversed presentation orders, per-candidate *multidimensional* penalty scores from
> critiques, a **Pareto** non-dominated set (never collapsed to one number), per-dimension winners,
> and a disagreement flag. It recommends `select` only when one candidate dominates, else
> `human_decision_required` over the tradeoff. Slice 2 (ADR 0008) adds a per-judge isolation ledger,
> ingestion of LLM judges' rankings (a split among judges flips `disagreement`, never averaged), and
> `persist=true` writing blinded candidate copies + the record to `.runs/`. Still ⬜ in P2: enforcing
> the blind/ boundary at transport, and signed judgments.
>
> **Revision loop now diffs by finding identity (ADR 0009, P3 slice 1).** `evaluate_revision` gives
> each finding a fingerprint (dimension + normalized evidence) and classifies fixed / persisted /
> worsened / newly-introduced, so a *new* material finding is rejected even when the raw count falls
> (the review's two-minors→one-material trap). Slice 2 (ADR 0010) makes **acceptance** itself
> identity-based (the target finding must be resolved by fingerprint, not merely by a lower count) and
> adds **waivers** (a human-approved finding, with a recorded reason, that no longer blocks). Still ⬜
> in P3: rerunning prose-reading audits (blocked on the hard audit reading prose, review §4).
>
> **Framework loop now has a regression harness (ADR 0011, P5 slice 1).** `scripts/run_regression.py`
> + the `run_regression` tool run fixed fixtures (`regression/fixtures.json`) that pin the invariants
> the ADRs established — defaultness, the revision traps + waiver, tournament select/defer, ontology
> typo — through a closed check whitelist, and report a **framework fingerprint** (schemas + KB index
> + package source). A change to a prompt/rubric/schema/code that regresses an invariant fails the
> run (non-zero exit). Still ⬜ in P5: fingerprinting prompt/agent files + model params, and
> automating the threshold/approval/rollback workflow around the runner.
>
> See `docs/decisions/0001-structured-state-delta.md`, `0002-promotion-audit-gate.md`,
> `0003-tamper-evident-promotion.md`, `0004-executable-story-ir.md`, `0005-predicate-ontology.md`,
> `0006-fabula-vs-discourse.md`, `0007-tournament-selection-engine.md`,
> `0008-tournament-judges-and-evidence.md`, `0009-revision-by-finding-identity.md`,
> `0010-revision-acceptance-by-identity-and-waivers.md`, `0011-framework-regression-harness.md`,
> and the worked example in `projects/salt-in-the-wire/`.

### Stage 0 — Make the scaffold honest (foundations)
**Goal:** the checks that pass should mean something.
- Add `jsonschema`; enforce all 6 schemas in `validate_workspace.py` (and fail on violation).
- Move logic out of loose scripts into `src/fiction_compiler/` (real package: `state.py`,
  `validators.py`, `context.py`, `io.py`); scripts become thin CLIs.
- Create **one real end-to-end example project** (3–4 scenes, full canon + deltas) as a
  fixture, so every later stage has something to run against.
- Add tests that fail when a schema is violated and when a scene delta is malformed.
- **Exit:** `make validate` rejects a deliberately broken fixture; CI-style test proves it.

### Stage 1 — Event-sourced canon state (**the keystone**)
**Goal:** implement the brief's `reconstruct_state_before(scene_id)`.
- `state.py`: fold `timeline.jsonl` + `knowledge-state.jsonl` + `relationship-state.jsonl`
  + `promises.jsonl` + accepted `state-delta.json` files into a point-in-time state object.
- Wire `promote_candidate.py` to **append the accepted delta to the canon ledgers**
  (currently missing) — closing the event-sourcing loop the brief specifies.
- **Exit:** given scene N, reconstruct state after N−1 deterministically; test proves future
  facts/knowledge do not leak backward.

### Stage 2 — Hard audit as code (Audit 1)
**Goal:** the audit the brief most insists must be code, not an LLM.
- `validators.py` on top of Stage 1 state: chronology/travel-time monotonicity, knowledge
  cutoff (scene's `knowledge_required` ⊆ reconstructed character knowledge), POV access,
  promise created-without-payoff ledger, relationship-state preconditions, causal
  preconditions satisfied from the event graph. Emit `critique.schema`-valid JSON.
- Turn `compile_scene_context.py` into a real minimal-context compiler using Stage 1 state
  (knowledge cutoff enforced → no future-knowledge leak; relevance filter instead of dump).
- **Exit:** a scene that references an unlearned fact or an unpaid-off promise fails a
  deterministic check with a machine-readable finding.

### Stage 3 — Knowledge base content (only what code consumes)
**Goal:** populate the KB the audits and skills actually retrieve — nothing inert.
- Level-1 concept cards for the starter set referenced by Stage 2/4: focalization,
  narrative-distance, causality, character-intentionality, scene-dramaturgy,
  dialogue-subtext, promise/payoff, eventfulness, surprise-vs-postdictability, and a
  defaultness catalog. YAML per the brief's Level-1 schema.
- Populate `source-register.json` with the brief's seed set **plus a German/EU copyright
  verification field** (the brief flags that US-public-domain ≠ EU-clear for this user).
- Level-0 index + Level-2 notes only for concepts a skill/audit references.
- **Exit:** each card is cited by at least one audit rule or skill; a test asserts no
  orphan cards and no dangling source IDs.

### Stage 4 — Selection & anti-obviousness engine (the "search system")
**Goal:** stop selecting by vibe.
- Quality-vector `Q` representation + Pareto selection over candidates.
- Blind pairwise tournament **harness**: code owns anonymization, order reversal, multi-judge
  fan-out, and disagreement recording; LLMs only score.
- Continuation-prediction ensemble + `Originality* = Unexpectedness × RetrospectiveCoherence
  × CharacterNecessity`; lightweight reader-expectation tracker feeds it.
- **Exit:** tournament output is reproducible given fixed judge responses; a random-meteor
  candidate scores near-zero on character necessity in a fixture.

### Stage 5 — Self-improvement & regression harness
**Goal:** make `retrospective` executable, not aspirational.
- Improvement-transaction record + `evals/regression/` fixture runner + before/after blind
  harness; prompt/rubric versioning.
- Run manifests in `.runs/` with model, prompt version, token, and cost provenance.
- **Exit:** a proposed prompt change is accepted only if it fixes its regression fixture
  without regressing others — enforced by the runner, not by an LLM's say-so.

### Stage 6 — Author-facing surfaces (deferred)
Context viewer, event-graph and knowledge-state visualization, promise dashboard, GUI.
Correctness-neutral; build only after Stages 1–5 are trustworthy.

---

## 5. Definition of done (per the operating contract)

A stage is complete only when: files validate against enforced schemas, a regression test
locks the new behavior, no existing test regresses, and `decisions/` records what changed
and why. "The directory exists" and "the checks pass" are necessary but never sufficient.
