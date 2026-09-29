# Implementation Roadmap

Status assessment and staged plan, measured against `docs/original-design-brief.md`.
The brief is treated as **product vision**, not a binding spec — deviations are called out explicitly.

Ground-truth snapshot (2026-09-29): the repository has a working deterministic compiler kernel,
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
| Reader/contract structure and measurement | `reader.py`, `reader_probe.py`, disclosure/coverage/probe schemas, ADRs 0040/0045 | **Structural + prefix-response evidence infrastructure implemented; audience study unrun** | Discourse revelations stay structural; accepted-prefix packets bind observed human/model responses to exact bytes, keep cohorts separate, detect staleness, and never manufacture cognition/quality verdicts |
| Owner preference evidence | `owner_preference.py`, owner-preference schemas, ADR 0042 | **Prospective evidence implemented; calibration data not yet accumulated** | Exact alternatives, owner choice/reason/date, choice-hidden critic packets, and descriptive agreement stay separate from audience outcomes; no historical backfill |
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
| Anti-obviousness search / repertoire | `avoid-defaults` skill, premise probes, `repertoire.py`, ADR 0041 | **Cross-project recurrence implemented; generative originality remains experimental** | Complete-story feature tags expose repeated endings/turns/resolutions/motifs/focalization without an originality score or gate |
| Knowledge base / literature controls | `kb/`, `literature_control.py`, ADRs 0043–0044 | **Starter set + first external control implemented; live critic/human baselines unrun** | Machine-readable EU/DE rights gate; hash-bound Joyce/“Araby” control yields 17 minor linter hits, zero blocks, and schema-valid format probes with explicit manual representation losses |
| Framework regression | `regression.py`, fixtures, critic cases | **Implemented** | Closed checks plus fingerprint of code, schemas, KB, prompts/skills, roster/probes, eval data, scripts, runtime config |
| Observability | project `.runs/`, trace, review attempts | **Substantial** | Candidate-bound packets and collision-safe runs; live role transports preserve provider token metadata/latency when available, and selection experiments keep unknown usage distinct from zero |
| End-to-end projects | `projects/*` | **Present** | Multiple worked projects exercise promotion, state, audits and manuscript assembly |

### Audit §6 implementation status

This table is the current checkpoint for the Sept. 28 review. “Implemented” below means the
mechanism or evidence-capture path exists and is regression-tested. It does not convert an unrun
reader/model experiment into a positive result.

| Review item | Current implementation | Evidence still missing |
|---|---|---|
| §6.1 plan-level search | **Mechanics implemented** — ADR 0027 records divergent frozen plans, feasibility/review evidence, and explicit selection without a deterministic best-plan score | Equal-cost blind comparison of plan search vs additional prose realizations |
| §6.2 backward revision | **Mechanics implemented** — ADRs 0026/0031 preserve immutable acceptance history, rebase downstream canon, rerun hard checks, and keep subjective rechecks pending until explicitly resolved | Comparative literary benefit of backward revision on real work |
| §6.3 plan-to-prose realization | **Calibration infrastructure implemented** — ADRs 0024/0030/0036 separate plan-blind extraction, alignment, ordered evidence, consistency, and coverage | Live/hidden-set calibration with predeclared tolerances before promotion-gate authority |
| §6.4 reader model | **Structural disclosure + measured-prefix path implemented** — ADRs 0040/0045 deliberately avoid a simulated reader mind | Actual target-audience responses and any predeclared free-text coding protocol |
| §6.5 contract coverage | **Implemented** — coverage maps deterministic, critic, and reader checks while retaining explicit `untested`/`not_assessed` states | Reader evidence for mapped experiential clauses; broader mappings as projects require them |
| §6.6 owner taste | **Prospective evidence implemented** — ADR 0042 freezes alternatives, choices/reasons, and choice-hidden critic predictions | Accumulated owner decisions and a prospective critic-prediction study |
| §6.7 selection thesis | **Measurement harness implemented** — ADR 0028 freezes pools/order, reader comparisons, first/random/critic selectors, and cost/failure missingness | Independent human study with uncertainty; no universal critic-superiority claim is established |
| §6.8 cross-story repetition | **Descriptive diagnostic implemented** — ADR 0041 records recurring endings/turns/resolutions/motifs/focalization without an originality gate | Reader evidence that changing a repeated choice improves outcomes rather than novelty alone |
| §6.9 literature control | **First control implemented** — ADRs 0043/0044 enforce rights status and run schema/defaultness probes on Joyce's “Araby” | Live critics, human discourse baselines, and additional unseen permissioned/public-domain controls |
| §6.10 long-form scale | **Unrun empirical diagnostic** — existing state/provenance mechanics can support it, but no 8–12k-word condition has been executed | One bounded 8–12k-word diagnostic first; broader claims require more than one case |
| §6.11 writer-family diversity | **Provenance/accounting mechanics exist** — ADRs 0032/0039 can record family/provider and operation cost | Equal-cost multi-family drafting plus edit-vs-regeneration experiment and blind preference evidence |

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
  is speculative and hard to validate. Keep the implemented discourse ledger structural, and use
  prefix-reader probes for measured expectation/comprehension rather than promoting annotations into
  a simulated reader mind. Don't build the whole thing.
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

> **Build status (updated 2026-09-29).** Stage 0 ✅, Stage 1 ✅, and Stage 2 ✅ are implemented and
> tested. Stage 3 ✅ has the validated starter KB, rights-aware source register, contextual
> defaultness catalog, repository-owned annotation, and the first rights-cleared literature control;
> further corpus growth is evidence-driven expansion rather than a blocker. Stage 4 ✅ for selection
> mechanics: blind/order-balanced Pareto selection, disagreement preservation, frozen selection
> experiments, plan-level search, and cross-project repertoire diagnostics are implemented. The
> empirical studies remain unrun. The old continuation-prediction/`Originality*` proposal is not an
> active required mechanism: ADRs 0041/0045 use descriptive repertoire evidence and measured prefix
> readers instead of a speculative originality score or simulated reader-expectation state.
>
> **Two self-improvement loops** (see `docs/self-improvement-loops.md`): the **story** PDCA loop's
> deterministic CHECK/ACT is built (`src/fiction_compiler/revision.py`, `scripts/revise_scene.py`,
> per-scene `revision-log.jsonl`) — this is the manuscript's own improvement loop. The **framework**
> PDCA loop (Stage 5) now has a regression-fixture runner, critic-calibration corpus, broad framework
> fingerprint, and an evidence-bound change transaction (ADR 0033): clean baseline + declared scope,
> exact rollback snapshots, blind before/after evidence, predeclared thresholds, explicit human
> approval, and stale-safe restoration. Scene-level resumable operation manifests are now implemented
> (ADR 0039): generation/revision/manual/provider operations can share one immutable run ledger with
> exact candidate snapshots, failures/retries, provider usage, and declared call/token/cost budgets;
> existing role-runner attempts link without another call. This closes the missing general accounting
> mechanism, but a matched-cost study must still actually route/bind every call and run the independent
> evaluation before it can claim complete expenditure or benefit. Stage 6 (GUI) ⬜.
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
> **Reader disclosure is now bound to the discourse plan (ADR 0040, review §§6.4–6.5 / Track G).**
> Every fact disclosure names the planned revelation and exact scene it realizes; every planned
> revelation must instead be explicitly declared non-factual when it is an enacted choice,
> recognition, or unresolved ambiguity. The six worked projects now carry structurally valid ledgers
> with curiosity-gap declarations where applicable. This is `structural_only`: it does not establish
> what any reader noticed or understood. Existing contract-coverage files continue to keep untested
> clauses explicit.
>
> **Prefix-reader evidence is now recordable without a simulated reader model (ADR 0045, Track G).**
> Probe plans bind questions to accepted scene boundaries and optional reader-contract clauses;
> reader-facing packets expose only the exact accepted prefix and question text. Immutable responses
> preserve the packet, respondent kind and cohort, become stale when the prefix changes, and are
> summarized descriptively. Forecourt carries the first two probe points and two contract mappings but
> deliberately has zero recorded responses. Still ⬜ in Track G: recruit actual target-audience readers,
> collect comprehension/expectation/ambiguity responses, define any semantic coding protocol before
> scoring free text, and compare human results with separately labeled model proxies.
>
> **Cross-project repertoire is now explicit (ADR 0041, review §6.8 / Track C).** Project-owned
> ending/turn/resolution/motif/focalization tags are checked against manuscript completeness and counted
> across complete stories only. The current five complete worked manuscripts reproduce the audit's
> `small-physical-act` ending recurrence (5/5) and common close-third/fixed-internal focalization;
> `salt-in-the-wire` remains a partial prefix and is excluded from those frequencies rather than having
> its ending guessed. The report is descriptive and advisory: no aggregate originality score, promotion
> gate, or requirement to differ is introduced. Still empirical: whether changing one of these repeated
> choices improves reader outcomes or merely produces arbitrary novelty.
>
> **Owner preference is now a prospective evidence stream (ADR 0042, review §6.6 / Track G).** Each
> new owner decision can freeze the exact alternatives shown together with the selected option, stated
> reason, and date. A separate packet withholds the choice and reason so critics can predict against the
> same immutable alternatives; one pick or abstention per critic is then hash-bound to that packet.
> Reports are descriptive for this owner only and remain separate from audience evaluation. Historical
> project choices are deliberately not reconstructed from commits or accepted manuscripts because the
> original alternative sets are unknown. Still empirical: accumulate prospective choices and run the
> critic-prediction study before claiming predictive value or using this as a premise-generation signal.
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
> **ADR 0043 makes the copyright prerequisite executable:** every `fiction-corpus` source now declares
> EU/DE clearance state and a full-text policy. US-public-domain aggregators remain blocked pending a
> title/translation/edition check; only explicitly cleared or repository-owned sources can declare full
> text allowed.
>
> **The first real-literature control is now executable (ADR 0044, review §6.9).** Joyce's “Araby” is
> stored from the original-English Project Gutenberg #2814 source under a title-specific cleared rights
> record, split into four explicitly analyst-defined segments, and hash-bound together with four
> production-schema `scene`/`state-delta` probes. The current defaultness linter reports 17 minor hits
> (4/3/5/5) but blocks zero segments, while manual format annotations expose typed losses without
> confusing schema validity with literary adequacy. Live critics remain explicitly `unrun` because no
> provider credentials were available; human/discourse baselines and unseen permissioned controls are
> still empirical work.
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
> human approve/reject decision, and rollback that refuses to clobber post-evaluation edits. ADR 0039
> now supplies the general generation/revision/run accounting mechanism. Still ⬜ in P5: route a
> powered matched-cost study through it and run the independent human evaluation. Historical studies
> with missing usage remain incomplete rather than being backfilled or guessed.
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
> `0039-resumable-scene-run-provenance.md`, `0040-bind-reader-disclosures-to-discourse.md`,
> `0041-cross-project-repertoire-diagnostic.md`, `0042-record-owner-preference-evidence.md`,
> `0043-enforce-fiction-corpus-rights-gate.md`,
> `0044-add-public-domain-literature-control.md`,
> `0045-measure-prefix-reader-responses.md`, `0046-reconcile-roadmap-with-evidence-state.md`,
> and the worked examples in `projects/salt-in-the-wire/` and
> `projects/the-overnight/`.

### Stage 0 — Make the scaffold honest (foundations) ✅
**Goal:** checks that pass mean the encoded thing they claim to check.
- Schemas are enforced by workspace validation; malformed fixtures fail maintained tests.
- Core behavior lives in `src/fiction_compiler/`; scripts are CLI/tool entry points.
- Multiple worked projects now exercise full state/spec/delta/manuscript paths.
- **Exit status:** complete for the current schema surface. New schemas must enter the same validation
  path rather than relying on directory presence.

### Stage 1 — Event-sourced canon state (**the keystone**) ✅
**Goal:** implement the brief's `reconstruct_state_before(scene_id)` without mutable-history leakage.
- `state.py` reconstructs seed canon plus accepted scene deltas and prefers fabula order when times are
  comparable, with an explicit discourse fallback when they are not.
- Promotion no longer follows the early roadmap's literal “append accepted delta to canon ledgers”
  design. The authority transaction writes an immutable content-addressed acceptance object and
  atomically updates `canon/index.json` (`accepted_state_deltas`, `acceptance_objects`,
  `head_acceptance`). State replay reads the frozen delta from the active acceptance object. Revisions
  preserve superseded objects and rebase the active chain instead of rewriting accepted history.
- **Exit status:** complete; state-before is deterministic, accepted bytes are tamper-evident, and
  nonlinear history is reconstructed/invalidation-scheduled in fabula order where defined.

### Stage 2 — Hard audit as code (Audit 1) ✅
**Goal:** deterministic constraints remain code-owned where the repository has a sound oracle.
- Hard audit evaluates chronology/state, knowledge and belief access, typed predicates/resources,
  relationship and promise obligations, ordered event preconditions/effects, POV policy, and declared
  story domains against reconstructed state.
- Context compilation uses state-before and relevance filtering rather than exposing future canon.
- Prose realization has a separate evidence-bound extraction/alignment path; semantic literary effects
  that code cannot prove remain explicitly empirical.
- **Exit status:** complete for declared deterministic semantics; richer domain rules are added only
  when a story makes them load-bearing.

### Stage 3 — Knowledge base content (only what code consumes) ✅ baseline
**Goal:** maintain a small, validated, evidence-aware KB rather than accumulate inert craft prose.
- Structured concept cards, conflicting-theory links, defaultness evidence, source provenance, and
  dangling-reference/orphan checks are in the validation path.
- ADR 0043 adds EU/DE rights/full-text policy. ADR 0044 adds the first title-specific cleared external
  literature control; aggregator-level public-domain status alone is insufficient.
- **Exit status:** starter baseline complete. Open work is empirical expansion: more rights-cleared or
  repository-owned controls and retrieval/craft additions only when they answer an observed need.

### Stage 4 — Selection & anti-obviousness engine (the "search system") ✅ mechanics
**Goal:** make selection evidence inspectable without pretending literary preference has a deterministic
oracle.
- Tournament code owns seeded anonymization, forward/reverse presentation orders, deterministic
  eligibility floors, multidimensional scoring, Pareto fronts, and disagreement preservation.
- ADR 0028 freezes generation-order candidate pools and separates critic/first/random selectors from
  subsequent human/model reader outcomes. ADR 0027 adds divergent scene-plan search before prose.
- ADR 0041 records cross-project repertoire recurrence descriptively. ADR 0045 measures reader
  expectation/comprehension from accepted prefixes. These supersede the early plan to make
  `Originality*` or a simulated reader-expectation tracker an architectural gate.
- **Exit status:** mechanics complete; actual selection benefit, plan-search benefit, critic calibration,
  and any originality intervention remain empirical studies whose null/unknown outcomes must stay
  explicit.

### Stage 5 — Self-improvement & regression harness
**Goal:** make `retrospective` executable, not aspirational.
- ✅ Improvement-transaction record + regression fixture runner + blind before/after harness with
  declared file scope, frozen rollback bytes, predeclared thresholds, and human approval authority.
- ✅ Scene runs in `.runs/scene-runs/` now provide resumable step state, frozen candidate/source
  evidence, role-runner import, explicit unknown usage, and call/token/cost budget preflight for
  generation/revision/review/selection/reader/promotion operations. This is accounting infrastructure;
  the independent matched-cost studies themselves remain unrun.
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
