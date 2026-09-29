# Tools for the Author (MCP)

## Philosophy: the LLM writes; the tools equip it
You cannot write fiction deterministically, and this system does not try to. The deterministic
layer is **tooling for the author** (the LLM), not a replacement for it:

- **Knowledge** the model reaches for — `kb_search` / `kb_get` over the craft knowledge base.
- **Ground truth** it must respect — `state_before` (who knows what, right now) and `compile_context`.
- **Guardrails** that catch what taste shouldn't have to — `hard_audit`, `defaultness_lint`.
- **A fitness signal** that keeps revision honest — `evaluate_revision`.

The creative acts — premise, structure, character intention, the actual prose, the earned
surprise — stay with the model. The tools remove the failure modes that have nothing to do with
talent (continuity slips, forgotten promises, default phrasing) so the model can spend its
judgment where judgment matters.

## The MCP server
`scripts/fiction_mcp.py` is a **dependency-free** MCP stdio server (newline-delimited JSON-RPC).
It runs anywhere `python3` runs — no install step.

### Tools exposed
| Tool | Purpose |
|---|---|
| `kb_search` | Find relevant craft concept cards by keyword/layer |
| `kb_get` | Full text of one concept card |
| `kb_sources` | Registered sources (craft-instruction / fiction-corpus / reference) with copyright notes |
| `state_before` | Event-sourced story state before a scene (facts, per-character knowledge, promises, time) |
| `compile_context` | The minimal, leak-free drafting bundle for a scene |
| `contract_coverage` | Show how each reader-contract clause is mapped or explicitly untested; mapping never means the clause passed |
| `reader_disclosure` | Validate discourse-revelation → canonical-fact bindings, explicit non-factual revelations, curiosity gaps, and surprise setup without claiming reader comprehension |
| `reader_probe_packet` | Build an exact accepted-prose prefix with predeclared reader questions while withholding contract bindings, planning notes, later prose and hidden canon |
| `record_reader_probe_response` | Persist one hash-bound human/model response per respondent and probe, with target-audience and model-proxy cohorts kept distinct |
| `reader_probe_report` | Report fresh/stale observed responses and descriptive choice/scale distributions; free-text semantics and reader-contract success are not auto-inferred |
| `repertoire_report` | Count repeated project-owned ending/turn/resolution/motif/focalization tags across complete manuscripts; partial stories stay visible but are excluded from observed frequencies, and no originality score is produced |
| `literature_control_report` | Run deterministic lint and schema-fit probes for a rights-cleared, hash-bound literature control while keeping manual representation limits and unrun critic evidence explicit |
| `record_owner_preference` | Prospectively freeze the exact alternatives behind one owner choice plus decision kind, chosen option, reason, and date; this is owner-taste evidence only |
| `owner_preference_packet` | Return the frozen alternatives with the owner's pick and reason withheld, plus a packet hash for blind critic prediction |
| `record_owner_preference_prediction` | Persist one hash-bound critic pick or abstention per owner choice; one critic gets one immutable prediction for that choice |
| `owner_preference_report` | Report descriptive critic agreement with recorded owner choices while keeping owner taste separate from target-reader and quality claims |
| `record_scene_plan` | Persist one immutable alternative scene plan bound to the current scene-spec hash |
| `scene_plan_search` | Inspect 3–4-plan search width, deterministic feasibility, review coverage, and explicit selection without ranking plans |
| `plan_review_packet` | Build a plan-aware feasibility/intentionality packet with no candidate prose |
| `record_plan_review` | Persist plan-review evidence bound to the exact plan hash, including “why don't they just…?” assessments |
| `select_scene_plans` | Explicitly select 1–2 reviewed plans, recording who chose and why; deterministic code does not choose the winner |
| `freeze_selection_pool` | Freeze exact candidate bytes and generation order for an independent selection-value experiment |
| `selection_reader_packet` | Reader-safe blinded prose plus counterbalanced pair assignments; no reveal map or generation order |
| `record_pairwise_preference` | Persist tie/abstain-capable pairwise evidence with human/model and audience/owner provenance |
| `record_selector_choice` | Bind a critic/editor pick to the frozen pool before reader outcomes exist |
| `record_selection_operation` | Record known cost/token/provider evidence and failures without converting missing usage to zero |
| `selection_experiment_report` | Descriptively compare first/random/recorded selectors when independent pair/order coverage supports it |
| `freeze_writer_study` | Freeze writer-family/edit-vs-regeneration arms against exact selection-pool bytes and scene-run provenance before reader outcomes |
| `writer_study_report` | Check predeclared matched-cost completeness/tolerance and reuse blind reader evidence without ranking writer families |
| `start_scene_run` | Create/resume an immutable scene-operation plan with optional call/token/cost budgets |
| `scene_run_status` | Derive completed/failed/pending steps, candidate freshness, evidence integrity, and accounting from append-only artifacts |
| `scene_run_budget` | Preflight one more operation; missing usage/estimates stay unknown and exhausted limits block continuation |
| `record_scene_run_operation` | Freeze candidate bytes and append provider/manual/compiler success/failure evidence with optional idempotency |
| `link_scene_run_review` | Link an existing role-runner attempt into the run without another provider call |
| `start_critic_calibration` | Freeze a B2 critic study and its provisional case labels before live runs |
| `critic_calibration_packet` | Judge-safe frozen case input with the calibration label/signals withheld |
| `record_critic_calibration_observation` | Persist repeat/family/transform-bound live critic evidence |
| `record_critic_human_label` | Persist independent human labels while preserving disagreement |
| `critic_calibration_report` | Report repeatability, conditional invariance, crossed families, joint errors, and human agreement without granting gate authority |
| `start_realization_calibration` | Freeze planted omission/literal/oblique prose-realization controls before observations |
| `realization_extractor_packet` | Prose-only packet for plan-blind observed-event extraction |
| `record_realization_extraction` | Persist evidence-bound extractor output with family/run provenance |
| `realization_aligner_packet` | Frozen prose + observations + required-event descriptions, with expected labels hidden |
| `record_realization_alignment` | Persist the separate plan-aware realized/omitted/unverified mapping |
| `realization_calibration_report` | Separate extractor misses, alignment misses, omissions and unresolved cases without enabling the prose-audit gate |
| `hard_audit` | Deterministic Audit 1 (knowledge cutoff, causal refs, POV, chronology, promise ledger) |
| `defaultness_lint` | Model-default tics in prose, with evidence |
| `evaluate_revision` | Accept/stop decision for a revision (stateless; takes iteration/attempts to reach every branch) |
| `record_revision` | Runs one revision iteration, derives iteration/attempts from the scene's `revision-log`, and **persists** it — the history-driven, ESCALATE/STOP-capable path |
| `promote` | **State-changing, gated by `confirm`** — copies a reviewed candidate into the manuscript and folds its delta into canon |
| `revise_acceptance` | **State-changing, gated by `confirm`** — replace an accepted scene, preserve superseded acceptance objects, rebase downstream canon, rerun hard checks, and invalidate downstream literary/reader/voice plus policy-required prose-audit evidence |
| `revision_status` | Read-only view of pending downstream rechecks and the preserved backward-revision event ledger |
| `post_revision_recheck_packet` | Build exact active-acceptance prose context for a pending subjective scope; reader packets are prefix-only and whole-work is global |
| `record_post_revision_evidence` | Persist packet-bound reviewer/reader evidence without automatically clearing the scope |
| `resolve_post_revision_scope` | Explicitly clear a still-current scope from clean pass evidence while recording who decided and why |
| `recheck_post_revision_prose_audit` | For a pending policy-required prose audit, rerun deterministic checking on freshly rebound extractor claims; stale scene/context hashes are refused and only a clean pass clears this scope |
| `run_regression` | Run the deterministic framework regression floor and fingerprint the exact behavior-relevant framework |
| `start_framework_change` | Freeze a clean framework baseline, the eight-field process-change proposal, declared scope, rollback bytes, and blind-comparison thresholds |
| `evaluate_framework_change` | Bind the edited framework, rerun regression, and detect undeclared behavior-relevant edits |
| `prepare_framework_comparison` | Freeze a before/after output pair and expose randomized A/B labels without the reveal map |
| `framework_comparison_packet` | Reopen a frozen comparison as a blind evaluator packet |
| `record_framework_comparison` | Record A/B/tie/abstain evidence; an agent proposer's own model vote is excluded from approval thresholds |
| `framework_change_status` | Show evaluation freshness, scope/regression status, comparison threshold evidence, human decision, and rollback state |
| `decide_framework_change` | **State-changing authority record, gated by `confirm`** — record explicit human approve/reject after fresh required evidence |
| `rollback_framework_change` | **State-changing, human-decider + `confirm` gated** — restore exact declared pre-change bytes only while the evaluated state is still current |

The write path now supports both forward acceptance and explicit backward correction: an agent driving
purely over MCP can persist revision history (`record_revision`), reach the full stop-condition logic,
promote (`promote`, confirm-gated), and revise accepted history (`revise_acceptance`, confirm-gated)
without erasing the superseded acceptance chain.

Operational provenance is separate from authorship. `start_scene_run` declares a resumable sequence;
generation/revision can remain external or manual and then be bound with `record_scene_run_operation`.
Role-runner attempts are imported with `link_scene_run_review`, which preserves their existing provider
metadata and source hash rather than repeating the call. `scripts/scene_run.py` exposes the same flow
for non-MCP callers.

The §6.11 writer comparison composes that provenance with the existing frozen selection experiment.
`freeze_writer_study` must run before reader preferences exist and binds every frozen candidate to the
scene run that produced it, its provider/model, declared writer family, and independent-draft,
regenerate, or edit strategy. An edit arm additionally binds the earlier source-draft hash in the same
run. `writer_study_report` then checks the predeclared token/cost tolerance and exposes the existing
blind human preference evidence. Missing provider usage stays unknown, and the report does not infer a
winning family or a population-level quality effect.

### Register with Claude Code
`.mcp.json` at the repo root is auto-detected:
```json
{ "mcpServers": { "fiction-compiler": { "command": "python3", "args": ["scripts/fiction_mcp.py"] } } }
```
Or: `claude mcp add fiction-compiler -- python3 scripts/fiction_mcp.py`. Verify with `/mcp`.

### Register with Codex
Already wired in `.codex/config.toml`:
```toml
[mcp_servers.fiction-compiler]
command = "python3"
args = ["scripts/fiction_mcp.py"]
```

### Sanity check by hand
```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"kb_search","arguments":{"query":"scene turn"}}}' \
 | python3 scripts/fiction_mcp.py
```

## The same tools without MCP
Every tool is a plain function in `fiction_compiler.tools` and a CLI under `scripts/`, so agents
that don't speak MCP (or humans) get the identical behavior. MCP is the ergonomic path, not the
only one.
