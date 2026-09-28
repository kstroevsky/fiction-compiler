# Implementation Roadmap

Status assessment and staged plan, measured against `docs/original-design-brief.md`.
The brief is treated as **product vision**, not a binding spec — deviations are called out explicitly.

Ground-truth snapshot (2026-09-28): the repository has a working deterministic compiler kernel,
acceptance/provenance layer, review runner, selection harness, and regression suite. Passing checks
establish the encoded invariants; they do **not** establish literary quality or the untested empirical
claims in the audit. Those require independent reader/critic measurement.

---

## 1. What this repository actually is today

It is a **working fiction-compiler kernel plus an evidence harness**, with important research and
authoring surfaces still unfinished. Deterministic code now owns schema validation, state replay,
hard constraints, acceptance binding, evidence integrity, selection mechanics, issue-resolution
coverage, and regression checks. LLMs remain responsible for extraction and literary judgment where
the project has no sound deterministic oracle. The active architecture deliberately distinguishes
mechanical validity, modeled/extracted consistency, and literary preference.

### Component status (vision → reality)

| Brief component | Artifact present | Actually implemented? | Evidence |
|---|---|---|---|
| Constitution / reader contract | `constitution/`, `AGENTS.md`, `CLAUDE.md` | **Yes** (as prose) | Complete and coherent |
| Schemas | `schemas/*.json` | **Enforced** | Workspace, critique, policy, premise, ontology, claims, judgment and state payloads are validated |
| Workspace validation | `scripts/validate_workspace.py` | **Implemented** | Schema/integrity checks plus canon verification; maintained tests exercise failures |
| Minimal context compilation | `src/fiction_compiler/context.py` | **Implemented, coarse relevance** | Replays state-before, filters to participants/required facts, writes collision-safe project-local evidence |
| Scene-plan search | `plan_search.py`, `schemas/scene-plan*.json`, `generate-scene-plans` skill | **Implemented as experimental evidence workflow** | 3–4-plan divergence floor, typed feasibility, hash-bound plan review, explicit 1–2 selection; no automatic quality ranker |
| Event-sourced canon / `reconstruct_state_before` | `src/fiction_compiler/state.py` | **Implemented** | Seed state + accepted deltas, typed comparisons/relationships/knowledge, declared value/entity domains, fabula-ordered replay with explicit legacy fallback |
| Candidate promotion / backward revision | `promote.py`, `acceptance.py`, `integrity.py`, `dependencies.py` | **Implemented, subjective recheck closure remains explicit** | Frozen candidate/spec/delta/review policy/evidence; immutable discourse-order chains, conservative read sets, discourse rebasing plus fabula-aware invalidation |
| Hard/symbolic audit | `hard_audit.py`, `prose_audit.py` | **Implemented, extraction boundary remains empirical** | Code checks state/event constraints; candidate/spec/state-bound prose claims use exact spans and ordered truth, belief and typed-predicate evidence |
| Realization calibration | `realization_calibration.py`, planted controls, ADR 0030 | **Evidence infrastructure implemented; live calibration not yet run** | Plan-blind extraction and plan-aware alignment are measured separately; extractor misses cannot become proved omissions |
| Literary review | `role_runner.py`, role personas, review policy | **Implemented as evidence-producing model review** | Role-specific blind packets, immutable attempts, provenance, issue applicability/resolution |
| Defaultness/style heuristics | `defaultness.py`, catalog | **Advisory by default** | Contextual evidence; a project can explicitly opt into blocking mode |
| Blind tournament / Pareto | `tournament.py`, `tools.tournament` | **Implemented** | Anonymization, order balancing, complete-matrix checks, eligibility floors, dissent preservation |
| Selection-value measurement | `selection_eval.py`, `selection_experiment.py`, ADR 0028 | **Implemented as evidence infrastructure; study not yet run** | Frozen generation-order pools, independent pairwise labels, first/random/critic comparison, cost/failure missingness |
| Critic calibration | `critic_calibration.py`, `critic_calibration.py` CLI, ADR 0029 | **Implemented as evidence infrastructure; calibrated study not yet run** | Frozen cases, repeated runs, conditional invariance/directional comparisons, crossed writer/judge families, joint-error bookkeeping, human-label disagreement preserved |
| Anti-obviousness search | `avoid-defaults` skill, premise probes | **Partial/experimental** | Search prompts/probes exist; no validated continuation ensemble or universal originality metric |
| Knowledge base | `kb/`, source register | **Starter set implemented** | Structured concept cards, conflicts/counterexamples, rights-aware provenance, one owned-scene annotation |
| Framework regression | `regression.py`, fixtures, critic cases | **Implemented** | Closed checks plus fingerprint of code, schemas, KB, prompts/skills, roster/probes, eval data, scripts, runtime config |
| Observability | project `.runs/`, trace, review attempts | **Substantial** | Candidate-bound packets and collision-safe runs; live role transports preserve provider token metadata/latency when available, and selection experiments keep unknown usage distinct from zero |
| End-to-end projects | `projects/*` | **Present** | Multiple worked projects exercise promotion, state, audits and manuscript assembly |

---

## 2. Knowledge-base status

The KB is no longer empty. It contains structured narratology/craft/style cards, a defaultness
catalog, a source register with evidence/right-status metadata, conflicting-theory links, and the first
repository-owned corpus annotation. Validation checks card depth and dangling references; tools expose
targeted retrieval.

The remaining work is evidence-driven expansion: genre/period modules only when a project needs them,
more rights-cleared or repository-owned annotated controls, and retrieval experiments that show a
larger KB improves decisions. The original caution still applies: do not grow a library merely because
storage is available, and do not turn one successful sample into a global stylistic rule.

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

> **Build status (updated 2026-09-28).** Stage 0 ✅, Stage 1 ✅, Stage 2 ✅ are implemented and tested.
> Stage 3 🟡 has a structured starter KB, rights-aware source register, defaultness catalog and one
> repository-owned annotation. Stage 4 🟡 has advisory defaultness diagnostics plus deterministic
> blind-label/order/Pareto tournament mechanics; continuation-prediction/originality experiments
> remain unvalidated research work.
>
> **Two self-improvement loops** (see `docs/self-improvement-loops.md`): the **story** PDCA loop's
> deterministic CHECK/ACT is built (`src/fiction_compiler/revision.py`, `scripts/revise_scene.py`,
> per-scene `revision-log.jsonl`) — this is the manuscript's own improvement loop. The **framework**
> PDCA loop (Stage 5) now has a regression-fixture runner, critic-calibration corpus, broad framework
> fingerprint, and an evidence-bound change transaction (ADR 0033): clean baseline + declared scope,
> exact rollback snapshots, blind before/after evidence, predeclared thresholds, explicit human
> approval, and stale-safe restoration. Complete experiment-wide cost manifests remain ⬜.
> Role-runner provider usage capture is implemented (ADR 0032); generation/revision paths still need
> the same accounting before a matched-cost study can claim complete expenditure. Stage 6 (GUI) ⬜.
> **Tools for the author.** The deterministic engine is exposed to the LLM as callable tools via
> a dependency-free MCP server (`scripts/fiction_mcp.py`, wired in `.mcp.json` and `.codex/config.toml`):
> `kb_search`/`kb_get`, `state_before`, `compile_context`, `hard_audit`, `defaultness_lint`,
> `record_scene_plan`/`scene_plan_search`/`plan_review_packet`/`record_plan_review`/
> `select_scene_plans`, `evaluate_revision`, `revise_acceptance`, and `revision_status`. Plus the `avoid-defaults`
> anti-obviousness skill (LLM-facing craft, not code).
> The engine equips the author; it does not replace the creative act. See `docs/mcp-and-tools.md`.
>
> **Promotion is now gated (ADR 0002) and tamper-evident (ADR 0003).** The versioned review policy is
> *enforced* in code: hard failures block; required literary reviews must bind to the exact candidate
> and runtime provenance; predecessor issues require resolution coverage; defaultness is advisory by
> default and blocks only when a project explicitly selects blocking mode; prose audit can likewise be
> required by policy. A non-`pass` required review, a `material`/`fatal` blocking finding, a wrong/absent
> hash, or stale evidence blocks before any write. Promotion writes an acceptance manifest with a canon hash chain (`parent`→
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
> runs backward". **Track-E epistemic/resource semantics are now executable (ADR 0034):** current
> world truth is separate from retained memory and possibly false per-character belief; stable
> propositions may be defined without being asserted true; `knows` is factive; and opt-in,
> load-bearing resource balances support acquire/consume/transfer with underflow, unit and scene
> quantity checks. Context packets and backward-revision dependencies carry those distinctions.
> **Linear event execution is now ordered (ADR 0035):** each required event checks causes and
> preconditions against a beat-level shadow state, matched effects advance that state, fact effects
> may establish later preconditions, graph cycles/unresolved endpoints are material, and
> `event_references` separates discourse reappearance from executing a canonical world event twice.
> **Declared story domains are now enforceable (ADR 0037):** JSON-like equality does not coerce
> booleans into numeric zero/one; event preconditions support explicit numeric comparisons; predicate
> declarations may constrain value type/enumeration/range; optional closed entity registries validate
> only explicitly closed types; and predicate-specific exclusivity checks domain invariants such as
> one active location without imposing that physics globally. Plan feasibility, hard audit,
> critic-eval and regression use the same semantics. **Fabula-ordered nonlinear reconstruction is
> now implemented (ADR 0038):** comparable accepted timestamps replay in story-time order; a live
> nonlinear planning/revision target supplies its proposed historical boundary; canon
> fact/knowledge/promise/event checks use the same order; discourse-only `event_references` do not
> execute world effects twice; and retroactive insertions/revisions preserve immutable acceptance
> objects while scheduling conservative rechecks for scenes whose historical entry state may change.
> Missing/mixed time domains and attempts to precede the seed state are surfaced explicitly rather
> than guessed. Still ⬜ in P1: richer domain modeling only when a story actually requires it; within
> a scene, temporal granularity remains explicit event-beat order rather than timestamped prose.
> Promise obligations now optionally carry typed `trigger_event` / `payoff_event` references
> (ADR 0025): triggered-but-unpaid promises and payoff events without closure are material, while
> legacy/untriggered open promises remain advisory. Prose-level payoff legibility is still a reader/
> realization question rather than a hard fact.
>
> **Selection engine exists (ADR 0007, P2 slice 1).** A deterministic `tournament` module + MCP tool
> owns the fairness machinery the contract requires: seeded anonymization (blinded labels + reveal
> map), forward/reversed presentation orders, per-candidate *multidimensional* penalty scores from
> critiques, a **Pareto** non-dominated set (never collapsed to one number), per-dimension winners,
> and a disagreement flag. It recommends `select` only when one candidate dominates, else
> `human_decision_required` over the tradeoff. Slice 2 (ADR 0008) adds a per-judge isolation ledger,
> ingestion of LLM judges' rankings (a split among judges flips `disagreement`, never averaged), and
> `persist=true` writing blinded candidate copies + the record to `.runs/`. Role-runner transport now
> uses role-specific evidence views (experiential reader, canon-aware continuity, style/profile,
> character-local state, plan-aware architecture) while withholding candidate strategy identity.
> **Selection measurement now has frozen evidence (ADR 0028, audit B1).** An experiment freezes exact
> candidate bytes plus generation order before readers see them, counterbalances every pair, records
> human/model and target/expert/owner cohorts separately, and compares compiler-owned first/random
> baselines with a critic/editor choice bound before reader outcomes. Reports expose incomplete pair/
> orientation coverage and missing token/cost data rather than treating either as success/zero. This is
> measurement infrastructure, not a positive result: the independent human study has not been run.
> Still ⬜ in P2: a live/signed external judgment transport and the powered crossed-brief/run/rater
> analysis required for a population-level selection claim.
>
> **Scene-level composition now has an explicit search layer (ADR 0027, review §6.1).** The compiler
> stores 3–4 immutable scene-plan alternatives bound to the current spec, requires real batch variation
> across tactic/turn/cost/reader disclosure, hard-checks knowledge/event feasibility, records plan-aware
> reviewer evidence including easy-solution analysis, and permits an explicitly reasoned 1–2-plan
> selection only from current reviewed plans. Selected plans flow into drafting context; stale plan
> evidence is exposed and omitted. There is deliberately no deterministic best-plan score. Still ⬜:
> automate live plan-review transport if warranted, and run the audit's equal-cost blind experiment to
> learn whether plan search actually improves reader preference versus spending the same budget on
> additional prose realizations.
>
> **Critic calibration now has a separate evidence track (ADR 0029, review B2).** A study freezes the
> exact diagnostic cases before live runs, with provisional corpus labels kept distinct from qualified
> human labels. Repeated observations carry exact judge/writer-family provenance, trial index, and an
> explicit behavioral-transform expectation; reports measure run-to-run repeatability, matched
> invariance/directional behavior, crossed-family cells and joint-error counts without treating vendor
> diversity as independence. Expert disagreement is preserved and excluded from human-agreement
> estimates. This remains measurement infrastructure: no qualified human calibration study or repair-
> benefit experiment has been run, and the report has no promotion-gate authority.
>
> **Revision loop now diffs by finding identity (ADR 0009, P3 slice 1).** `evaluate_revision` gives
> each finding a fingerprint (dimension + normalized evidence) and classifies fixed / persisted /
> worsened / newly-introduced, so a *new* material finding is rejected even when the raw count falls
> (the review's two-minors→one-material trap). Slice 2 (ADR 0010) makes **acceptance** itself
> identity-based (the target finding must be resolved by fingerprint, not merely by a lower count) and
> adds **waivers** (a human-approved finding, with a recorded reason, that no longer blocks).
> **Backward revision now has canonical versioning (ADR 0026, review §6.2).** An explicitly revised
> accepted scene creates a new immutable acceptance object and rebases every downstream acceptance
> onto the new canon hash while retaining superseded objects as verified history. New acceptances carry
> a conservative fact/predicate/promise read set. Changed typed state marks known dependents, while
> every downstream scene is still invalidated for literary/reader/voice/whole-work review because the
> typed read set is not complete for literary effects. Deterministic hard audits rerun immediately.
> **ADR 0031 now makes the subjective closure path first-class:** literary/voice packets bind the exact
> active acceptances, reader packets expose only the accepted prefix, and one global whole-work packet
> binds the complete active manuscript. Evidence is append-only and cannot clear a scope by itself;
> explicit resolution rechecks freshness and records who decided and why. A reconstructed context basis
> remains labeled reconstructed rather than claimed as the original drafting prompt.
>
> **KB now has enforced structured depth (ADR 0015, P4 slice 1).** Every concept carries a `claim`, an
> `evidence_strength` grade, `dangerous_when` conditions, `counterexamples`, and resolvable
> `conflicts_with` — `validate_workspace` enforces it, so no card can be inert or over-absolute. The
> three cards the review flagged (eventfulness, scene-dramaturgy, monotonic knowledge) are conditioned;
> a conflicting-theory card (`static-scene`) and the first annotated scene (the repo's own
> `the-overnight/ch01-sc02`) are added. Still ⬜ in P4: genre/period modules, a larger annotated
> corpus (extract-not-copy, public-domain), semantic retrieval — depth first, never volume.
>
> **The hard audit now reads the prose (ADR 0014 + ADR 0024 + ADR 0036, review §§4, 6.3).** A `prose_audit` proves
> an extraction agent's `prose-claims` (pov, tense, typed factual/epistemic claims with evidence) against
> reconstructed state + the spec. Candidate/spec/pre-state/delta/context hashes and exact prose spans
> make those claims stale-safe and occurrence-specific. Event-aligned replay now checks when world
> facts, beliefs/knowledge, and typed predicates such as `located_at` become effective, so a later
> fact/move cannot justify an earlier sentence and false-valued location predicates are not treated as
> active. Fixed-internal head-hopping follows the discourse focalization policy instead of being
> imposed on explicitly variable/omniscient modes. An unplanned character, tense break, spatial contradiction, or a promise closed in
> prose but not in the delta are material findings. The realization prototype now separates
> **plan-blind observed events** from a later plan-aware alignment: explicit required-event omission is
> material, while missing/uncertain alignment stays `uncertain`; free-text turn/exit-state remain
> unverified. Candidate-bound claims now carry hashes for the candidate/spec/pre-scene state/delta,
> a full verifier-context digest, and exact character spans. In-scene knowledge/belief can satisfy a
> prose claim only after an aligned, effect-backed `at_event`; later learning is a material temporal
> leak, earlier fact removal/correction invalidates stale entry-state knowledge/belief, and missing ordering stays
> explicit uncertainty. Logical `consistency` and extractor `coverage` are reported separately, with
> deterministic coverage remaining `unverified`. **ADR 0030 supplies the calibration harness:** frozen planted omission,
> literal-realization and oblique-realization controls are presented first to a plan-blind extractor,
> then to a separate plan-aware aligner with the frozen prose available for targeted re-inspection.
> Reports distinguish extractor misses from alignment misses and never convert a missed extraction into
> proof of omission. Still ⬜: run the live/hidden-set calibration and adopt predeclared tolerances before
> making `prose_audit` a required gate; auto-rerun calibrated prose-reading audits after revision.
>
> **Framework loop now has an executable change transaction (ADR 0011 + ADR 0033, P5).** `scripts/run_regression.py`
> + the `run_regression` tool run fixed fixtures (`regression/fixtures.json`) that pin the invariants
> the ADRs established — defaultness, the revision traps + waiver, tournament select/defer, ontology
> typo — through a closed check whitelist, and report a **framework fingerprint** covering package
> source, schemas, full KB/defaultness content, scripts, model roster/premise probes, eval/regression
> corpora, personas/skills/governance text and runtime configuration. The fixed suite now also pins
> repeated-flashback fabula replay. A change that regresses an
> invariant fails the run (non-zero exit). `framework_change.py` wraps that floor in a clean-baseline,
> declared-scope transaction with exact pre-change snapshots, randomized blind A/B output evidence,
> predeclared evidence thresholds, independent-of-agent-proposer accounting, a separate confirmed
> human approve/reject decision, and rollback that refuses to clobber post-evaluation edits. Still ⬜
> in P5: extend ADR 0032's provider-usage provenance across the remaining generation/revision paths so
> experiment-wide matched-cost accounting is complete, and actually run the independent human studies.
>
> See `docs/decisions/0001-structured-state-delta.md`, `0002-promotion-audit-gate.md`,
> `0003-tamper-evident-promotion.md`, `0004-executable-story-ir.md`, `0005-predicate-ontology.md`,
> `0006-fabula-vs-discourse.md`, `0007-tournament-selection-engine.md`,
> `0008-tournament-judges-and-evidence.md`, `0009-revision-by-finding-identity.md`,
> `0010-revision-acceptance-by-identity-and-waivers.md`, `0011-framework-regression-harness.md`,
> `0012-human-gate-and-rubric.md`, `0013-operational-cleanups.md`, `0014-prose-audit.md`,
> `0015-kb-structured-depth.md`, `0024-plan-to-prose-realization-evidence.md`,
> `0025-typed-promise-obligations.md`, `0026-backward-revision-and-conservative-invalidation.md`,
> `0027-plan-level-search-before-prose.md`, `0028-frozen-selection-measurement.md`,
> `0029-critic-behavioral-calibration.md`,
> `0030-realization-calibration-evidence.md`,
> `0031-post-revision-subjective-rechecks.md`,
> `0032-provider-usage-provenance.md`, `0033-framework-change-transactions.md`,
> `0034-epistemic-and-resource-state.md`,
> `0035-ordered-event-execution.md`, `0036-ordered-prose-evidence.md`,
> `0037-declared-story-domains.md`, `0038-fabula-ordered-reconstruction.md`,
> and the worked examples in `projects/salt-in-the-wire/` and
> `projects/the-overnight/`.

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
- ✅ Improvement-transaction record + regression fixture runner + blind before/after harness with
  declared file scope, frozen rollback bytes, predeclared thresholds, and human approval authority.
- 🟡 Run manifests in `.runs/` carry exact framework fingerprints and role-runner provider usage;
  generation/revision token and cost provenance is still incomplete.
- **Exit status:** mechanical and governance acceptance is implemented; empirical process changes
  still require their actual independent blind evidence rather than infrastructure being counted as
  a positive result.

### Stage 6 — Author-facing surfaces (deferred)
Context viewer, event-graph and knowledge-state visualization, promise dashboard, GUI.
Correctness-neutral; build only after Stages 1–5 are trustworthy.

---

## 5. Definition of done (per the operating contract)

A stage is complete only when: files validate against enforced schemas, a regression test
locks the new behavior, no existing test regresses, and `decisions/` records what changed
and why. "The directory exists" and "the checks pass" are necessary but never sufficient.
