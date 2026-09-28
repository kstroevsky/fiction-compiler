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
| Event-sourced canon / `reconstruct_state_before` | `src/fiction_compiler/state.py` | **Implemented** | Seed state + accepted deltas, typed values/relationships/knowledge, parsed chronology semantics |
| Candidate promotion | `promote.py`, `acceptance.py`, `integrity.py` | **Implemented** | Frozen candidate/spec/delta/review policy/evidence; atomic idempotent acceptance chain and verifier |
| Hard/symbolic audit | `hard_audit.py`, `prose_audit.py` | **Implemented, extraction boundary remains empirical** | Code checks state/event constraints; extracted prose claims are judged deterministically |
| Literary review | `role_runner.py`, role personas, review policy | **Implemented as evidence-producing model review** | Role-specific blind packets, immutable attempts, provenance, issue applicability/resolution |
| Defaultness/style heuristics | `defaultness.py`, catalog | **Advisory by default** | Contextual evidence; a project can explicitly opt into blocking mode |
| Blind tournament / Pareto | `tournament.py`, `tools.tournament` | **Implemented** | Anonymization, order balancing, complete-matrix checks, eligibility floors, dissent preservation |
| Anti-obviousness search | `avoid-defaults` skill, premise probes | **Partial/experimental** | Search prompts/probes exist; no validated continuation ensemble or universal originality metric |
| Knowledge base | `kb/`, source register | **Starter set implemented** | Structured concept cards, conflicts/counterexamples, rights-aware provenance, one owned-scene annotation |
| Framework regression | `regression.py`, fixtures, critic cases | **Implemented** | Closed checks plus fingerprint of code, schemas, KB, prompts/skills, roster/probes, eval data, scripts, runtime config |
| Observability | project `.runs/`, trace, review attempts | **Substantial but incomplete** | Candidate-bound request/response packets and collision-safe runs; full token/cost accounting still missing |
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
> PDCA loop (Stage 5) now has a regression-fixture runner, critic-calibration corpus and broad
> framework fingerprint. Automated before/after policy transactions, threshold/approval/rollback
> orchestration and complete token/cost manifests remain ⬜. Stage 6 (GUI) ⬜.
> **Tools for the author.** The deterministic engine is exposed to the LLM as callable tools via
> a dependency-free MCP server (`scripts/fiction_mcp.py`, wired in `.mcp.json` and `.codex/config.toml`):
> `kb_search`/`kb_get`, `state_before`, `compile_context`, `hard_audit`, `defaultness_lint`,
> `evaluate_revision`. Plus the `avoid-defaults` anti-obviousness skill (LLM-facing craft, not code).
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
> `persist=true` writing blinded candidate copies + the record to `.runs/`. Role-runner transport now
> uses role-specific evidence views (experiential reader, canon-aware continuity, style/profile,
> character-local state, plan-aware architecture) while withholding candidate strategy identity.
> Still ⬜ in P2: a first-class live pairwise-judgment transport and signed/external judgments.
>
> **Revision loop now diffs by finding identity (ADR 0009, P3 slice 1).** `evaluate_revision` gives
> each finding a fingerprint (dimension + normalized evidence) and classifies fixed / persisted /
> worsened / newly-introduced, so a *new* material finding is rejected even when the raw count falls
> (the review's two-minors→one-material trap). Slice 2 (ADR 0010) makes **acceptance** itself
> identity-based (the target finding must be resolved by fingerprint, not merely by a lower count) and
> adds **waivers** (a human-approved finding, with a recorded reason, that no longer blocks).
>
> **KB now has enforced structured depth (ADR 0015, P4 slice 1).** Every concept carries a `claim`, an
> `evidence_strength` grade, `dangerous_when` conditions, `counterexamples`, and resolvable
> `conflicts_with` — `validate_workspace` enforces it, so no card can be inert or over-absolute. The
> three cards the review flagged (eventfulness, scene-dramaturgy, monotonic knowledge) are conditioned;
> a conflicting-theory card (`static-scene`) and the first annotated scene (the repo's own
> `the-overnight/ch01-sc02`) are added. Still ⬜ in P4: genre/period modules, a larger annotated
> corpus (extract-not-copy, public-domain), semantic retrieval — depth first, never volume.
>
> **The hard audit now reads the prose (ADR 0014 + ADR 0024, review §§4, 6.3).** A `prose_audit` proves
> an extraction agent's `prose-claims` (pov, tense, typed factual/epistemic claims with evidence) against
> reconstructed state + the spec — a focalizer knowing an ungranted fact (knowledge leak), an
> unplanned character, head-hopping, a tense break, a spatial contradiction, or a promise closed in
> prose but not in the delta are material findings. The realization prototype now separates
> **plan-blind observed events** from a later plan-aware alignment: explicit required-event omission is
> material, while missing/uncertain alignment stays `uncertain`; free-text turn/exit-state remain
> unverified. Still ⬜: calibrating extraction/alignment on planted omissions + oblique controls before
> making `prose_audit` a required gate, and auto-rerunning calibrated prose-reading audits after revision.
>
> **Framework loop now has a regression harness (ADR 0011, P5 slice 1).** `scripts/run_regression.py`
> + the `run_regression` tool run fixed fixtures (`regression/fixtures.json`) that pin the invariants
> the ADRs established — defaultness, the revision traps + waiver, tournament select/defer, ontology
> typo — through a closed check whitelist, and report a **framework fingerprint** covering package
> source, schemas, full KB/defaultness content, scripts, model roster/premise probes, eval/regression
> corpora, personas/skills/governance text and runtime configuration. A change that regresses an
> invariant fails the run (non-zero exit). Still ⬜ in P5: automating the before/after
> threshold/approval/rollback workflow and recording complete live token/cost/provider metadata.
>
> See `docs/decisions/0001-structured-state-delta.md`, `0002-promotion-audit-gate.md`,
> `0003-tamper-evident-promotion.md`, `0004-executable-story-ir.md`, `0005-predicate-ontology.md`,
> `0006-fabula-vs-discourse.md`, `0007-tournament-selection-engine.md`,
> `0008-tournament-judges-and-evidence.md`, `0009-revision-by-finding-identity.md`,
> `0010-revision-acceptance-by-identity-and-waivers.md`, `0011-framework-regression-harness.md`,
> `0012-human-gate-and-rubric.md`, `0013-operational-cleanups.md`, `0014-prose-audit.md`,
> `0015-kb-structured-depth.md`, and the worked examples in `projects/salt-in-the-wire/` and
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
