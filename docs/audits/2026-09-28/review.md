# Review of the 27 September audit: double-check, corrections and additions

Review date: 28 September 2026; second pass the same day added §6 (the project's core idea) and re-ranked §7. Reviewed: [`docs/audits/2026-09-27/`](../2026-09-27/audit.md) at commit `2b8ef0b` (production source identical to the audited `310e50c`). This document does not replace the audit. It records what was rechecked, what should be corrected, and what the audit missed. The original audit files are unchanged.

## Bottom line

**The audit's engineering findings are accurate; all 24 of its probes reproduce byte-for-byte. Its main gap is that it examined what the code *could* allow, not what the pipeline *actually did*.** The stored record changes the priorities:

- Only **3 of 17** accepted scenes (all in *The Overnight*) were reviewed by all three literary critics.
- **5 of 17** accepted scenes would be refused by today's gate, yet workspace validation passes.
- In **7 of 12** gate-era promotions, a critic's `revise` verdict on the promoted text's own earlier draft was never re-checked. One literary `pass` was enough.

Second, the audit's correction on house style is too cautious: the briefs of the two most recent stories quote the premise-probe rubric, so the "contract" that supposedly explains the style is itself a pipeline output. Third, the audit under-weights recent research on judge reliability and on discourse-level (story-structure) signatures of AI fiction. That research makes calibrating the single literary critic that actually decides promotion more urgent than adding state, agents or critics.

Fourth, measured against the project's own design brief, parts of the core idea are missing (§6):

- The system searches over prose rather than over plans.
- Accepted scenes cannot be revised backwards to plant setups.
- Nothing checks that the prose carries out the plan.
- The reader model the brief treats as central was never built.
- The central claim that LLMs are stronger critics than writers is contested and untested.
- All five completed stories end the same way: a small physical act with the outcome withheld.

## 1. What was double-checked

| Item | Method | Result |
| --- | --- | --- |
| Baseline checks | Reran `validate_workspace.py`, the unit suite, `run_regression.py` | Validation passed; 193 tests OK; 28/28 fixtures, as reported |
| 24 audit probes | Ran `probes.py` from a scratch copy against the live library; compared JSON | 24/24 identical |
| Code-level claims | Read every cited module (`promote`, `integrity`, `state`, `hard_audit`, `critique`, `tournament`, `revision`, `defaultness`, `prose_audit`, `context`, `premise`, `tools`, `role_runner`, `critic_eval`, `regression`, `safety`, `workspace`, `assemble`, `trace`, MCP server, promote CLI, skills, personas) | All checked claims confirmed, including CLI exit code, panel unanimity on total failure, Gemini key in exception URL, `NaN` confidence, manifest omissions, the missing `approved_by` CLI option and the contradictory promote-skill order |
| Literary claims | Read the cited passages and the neighbouring scenes and specs | *Overnight* confirmed and strengthened (§2.3); *Forecourt* and *Visiting Order* quotations confirmed |
| Research claims | Re-fetched Tian et al. (abstract and tables), Fabula §4.2, ConStory, reference-based evaluation, reader-preference study, 100-Endings | Mostly accurate; two corrections (§2.4–2.5) |
| New probes | [`evidence/extra_probes.py`](evidence/extra_probes.py) → [`extra-probe-results.json`](evidence/extra-probe-results.json) | 8 new observations, all confirming defects (§4) |
| Record analysis | [`evidence/record_analysis.py`](evidence/record_analysis.py) → [`record-analysis.json`](evidence/record-analysis.json) | §3; story endings and plan layer in §6 |
| Core design | Compared the implementation with the design brief's loop (lines 471–523) and its §§2.7, 2.9 and 2.11; read the endings of all six stories; checked the prose-claims and state-delta schemas | §6 |

## 2. Corrections to the audit

### 2.1 The house style's cause is partly established, not merely "plausible"

The audit argues that the briefs "explicitly demand much of the similarity" and are "legitimate contracts". That treats the brief as independent of the pipeline, and for the latest projects it is not:

- [`projects/forecourt/brief/creative-brief.md:18`](../../../projects/forecourt/brief/creative-brief.md) reads "A single transforming consciousness; a threat that cannot be resolved by proof". Line 32 says "(the probe's flagged risk)".
- [`projects/visiting-order/brief/creative-brief.md:17`](../../../projects/visiting-order/brief/creative-brief.md) reads "A single transforming consciousness; an interpersonal conflict that no proof can settle". Line 30 says "the fault flagged by the premise probe".
- Five of six briefs turn the linter's categories into contract clauses. Four use the identical phrase "no told emotion, no cliche, no adverbial dialogue tags"; *Verbatim* has "emotion earned through behavior, never named".

So for projects built after ADR 0017 there is a documented path: global premise probes → brief wording → contract → lint → prose. The briefs cannot be used to exonerate the pipeline. The audit's proposed remedy, an optional realism profile, is right. It additionally needs **clause-level provenance** in briefs (human-authored / agent-proposed and human-accepted / inherited from framework defaults), otherwise taste can never be attributed.

### 2.2 ADR 0017 may have routed a process defect to the premise layer

The audit criticises ADR 0017 for generalising from one pair but does not test its factual premise that *Slack Water* "passed every downstream audit" ([ADR 0017:11](../../decisions/0017-premise-divergence-and-probes.md)). The record contradicts that premise:

- For scenes 1 and 2, the style-editor's `revise` verdicts on the parent draft (`candidate-b`) were never re-checked on the promoted `candidate-b-r2`.
- On sibling drafts, the character-simulator flagged that Rennie's "defining contradiction (needing the money, tempted by the easy launch) is never dramatized … her honesty costs her nothing". It also flagged that "the narration states the elegy outright".

These are the very features ADR 0017 later attributed to a premise layer the "pipeline had no check on" (line 13). The critics saw them; the gate's single-literary-critic rule let them fall away. By the constitution's own rule ("route every defect to the lowest responsible layer"), the process layer is at least a co-cause. The premise probes may still be useful, but the causal story that motivated making them global is weaker than recorded.

### 2.3 The *Overnight* loaf defect originates in the plan, not only the prose

The audit's quantity finding is correct, and the evidence is stronger than it states. [`ch01-sc01.md:3`](../../../projects/the-overnight/manuscript/chapters/ch01-sc01.md) establishes "Twelve tins", which rules out a thirteenth loaf baked in a tin. The scene spec's `turn` requires "she keeps one loaf back" ([`ch01-sc03/spec.json:22`](../../../projects/the-overnight/scenes/ch01-sc03/spec.json)), and the accepted delta's fact text says "Nadia kept one back".

The contradiction therefore sits in the **structured** artifacts, inside natural-language fields (`turn`, fact `text`) that no check reads. It should be routed to the scene-spec/plot layer. The general lesson is that a turn which depends on a quantity must declare that quantity as typed state at planning time, before any prose exists.

### 2.4 Tian et al.: whose "40%" it is, and one mislabelled figure

The original audit's "more than 40%" repeats the paper's own abstract ("over 40% improvement in neural storytelling in terms of diversity, suspense, and arousal"). The revised audit is right that these are separate task-specific endpoints, but it should say the aggregation is the authors'. Its "overall diversity preference of 23% versus 68%" is the **character-diversity** row of Table 6. Theme diversity is 5% vs 64%, setting 5% vs 55%, and conflict 23% vs 50%.

### 2.5 The 100-Endings headline result is missing where it matters most

The audit cites 100-Endings only as a surprise diagnostic. Its headline finding is that on EQ-Bench, rubric-based LLM judges rank zero-shot AI stories **above New Yorker stories**. This is direct evidence against the premise of ADR 0016 (the LLM critic should drive selection). It belongs in the judge-reliability discussion alongside the audit's more favourable evidence.

### 2.6 Severity should also weigh what actually happened

The audit rates severity by potential harm. In this single-operator repository, the promotion race and path traversal have never occurred. By contrast, single-critic sufficiency and dropped dissent occurred in most gate-era promotions (§3). Keep the P0 labels, but add an "observed in record" column and schedule the observed failures first (§7).

### 2.7 Workstream B does not need to wait for workstream A

The audit says literary measurement should run "alongside" the trust repairs, but its pilot arm D is defined "with trust repairs". The P0 defects protect **shared canon** under concurrent or adversarial use. A pilot that generates on frozen snapshots, in an isolated harness with full logging, does not depend on them. State this decoupling explicitly, or B will silently wait for A.

## 3. What the stored record shows (not in the audit)

The audit inventoried gate status per candidate ([`candidate-status.json`](../2026-09-27/evidence/candidate-status.json)) but did not synthesise it. Results from [`record-analysis.json`](evidence/record-analysis.json):

| Observation | Count | Consequence |
| --- | --- | --- |
| Accepted scenes that fail today's gate (all of *Verbatim*; *Salt in the Wire* sc01–02) | 5 / 17 | Validation passes; nothing records that they were accepted under an older policy. *Verbatim*, counted among the "five completed manuscripts", has no gate-bound literary review |
| Gate-era promotions with exactly one literary critic on the promoted bytes | 9 / 12 | The literary third of the triple audit is, in practice, one `adversarial-reader` pass |
| Gate-era promotions where a literary `revise` on the promoted text's **own parent draft** was never re-checked | 7 / 12 | Dissent is dropped by construction, not by decision |
| Gate-era promotions where a sibling draft drew a literary `revise` never re-checked on the promoted text | 9 / 12 | Signals about shared weaknesses vanish with the rejected branch |
| Scenes with a prose audit (the hard audit's prose half) | 1 / 17 | ADR 0014's check is effectively unused |
| Promoted revisions / scenes with a revision log | 10 / 4 | Most revisions bypassed `record_revision` and `evaluate_revision` |
| Manifests with the human gate required | 0 / 17 | Projects list `premise`, `voice-profile`, `ending`, `final`, none of which is enforced |
| Tournament runs / runs using critic judgments (ADR 0016) | 3 / 0 | Critic-driven selection has never been used on a real scene; one early run "selected" the scene id `ch01-sc01` (the phantom-candidate bug later fixed) |
| Critiques produced by the multi-vendor runner (ADR 0020) | 0 | Every historical literary critique came from the operator's own agent session (in *Forecourt*, via `record_critique`), so writer and critics shared a model family unless models were switched by hand |

**Process erosion.** *The Overnight*, the first story built under the gate, had full literary coverage. Every later project (*Slack Water*, *Visiting Order*, *Forecourt*) settled at the gate's minimum. A gate that requires "a clean literary critique" gets exactly one. This is the most actionable finding in the record.

**Critic independence is not evidenced.** In all three *Forecourt* traces, six literary critiques (three roles × two drafts) were recorded within 33–45 seconds; the gap between the same role's two critiques was 2.5–9.7 seconds (median 3.8). One "independent" reader critique of scene 2 speaks in the author's voice ("Kept as a deliberate trade") and relies on a later scene ("the officer is police in sc03 regardless"). Timestamps mark the recording call, not generation, so this does not prove the drafter wrote the critiques. It shows the record **cannot distinguish** a blind independent reader from the drafting context. That is the deeper form of the audit's "fabricated audit" finding: no attack is needed.

**Blind labels are not blind.** With the default seed, `anonymize(["candidate-a.md", "candidate-b.md"])` returns `A`, `B`: the label is the filename's letter. This holds in every stored tournament record, and the promoted text descends from `candidate-a` in 11 of 17 scenes.

## 4. Additional code defects (reproduced)

| # | Defect | Location | Probe observation | Severity |
| --- | --- | --- | --- | --- |
| N1 | An event effect `knows(c, f)` is checked against `predicate_changes`, but `holds("knows")` reads only the separate knowledge store. The audit passes, and the knowledge never arrives | [`state.py:97`](../../../src/fiction_compiler/state.py#L97), [`hard_audit.py:183`](../../../src/fiction_compiler/hard_audit.py#L183) | Scene 1 `pass`; scene 2 gets a spurious **fatal** "knowledge would leak from the future" | P1 |
| N2 | `facts_removed` leaves the fact in characters' knowledge; the prose audit accepts "she knew" for a fact no longer true | [`state.py:134`](../../../src/fiction_compiler/state.py#L134) | `fact_exists=false`, `knows=true`, prose audit `pass` | P1: a concrete case of the audit's truth-versus-belief gap |
| N3 | Negation cannot be expressed: `value: false` on `knows` is ignored, so "must NOT yet know" fails exactly when it holds | [`state.py:97`](../../../src/fiction_compiler/state.py#L97), event schema | Material causal finding on a satisfied precondition | P1: secrets, dramatic irony and surprise depend on negative knowledge |
| N4 | ISO-like times compare as strings; `T` and space separators mis-order | [`hard_audit.py:62`](../../../src/fiction_compiler/hard_audit.py#L62) | 09:00 → 10:00 flagged as time running backward | P2 |
| N5 | Pareto selection on noisy mean scores with no indifference threshold | [`tournament.py:51`](../../../src/fiction_compiler/tournament.py#L51) | A 0.1-point edge on every dimension → `select`, `disagreement: false` | P1 |
| N6 | Default-seed labels equal the filename letter | [`tournament.py:26`](../../../src/fiction_compiler/tournament.py#L26) | `candidate-a→A`, `candidate-b→B`, every run | P1 for any blindness claim |
| N7 | Character speech is linted as narration | [`defaultness.py:47`](../../../src/fiction_compiler/defaultness.py#L47) | A deadpan quoted "Time stood still" → **material** | P1: extends the audit's style-veto finding from quotation to voice |
| N8 | The lock is an empty `O_EXCL` file with no owner or staleness check; a killed process blocks all later promotions. `os.replace` without `fsync` is also not durable | [`integrity.py:106`](../../../src/fiction_compiler/integrity.py#L106), [`integrity.py:145`](../../../src/fiction_compiler/integrity.py#L145) | Child exited 9; empty lock left; next promotion refused | P2 |

Static findings, not probed:

- **No policy re-evaluation.** [`validate_workspace.py:123`](../../../scripts/validate_workspace.py#L123) checks the hash chain only. Acceptances carry no policy version, so the five legacy scenes are indistinguishable from gated ones.
- **"Material" is undefined for LLM critics.** The output contract ([`role_runner.py:55`](../../../src/fiction_compiler/role_runner.py#L55)) and personas (one to four sentences) give no severity anchors. The promotion threshold therefore rests on an uncalibrated word. The continuity persona says "cite exact files", which a vendor runner without tools cannot do.
- **The drafting input is not kept.** Context bundles, the record of what the writer actually saw, go to the root `.runs/`, which `.gitignore` excludes ([`context.py:101`](../../../src/fiction_compiler/context.py#L101)). The operating contract says evidence in `.runs/` must be preserved; `trace.py` says it can be pruned.
- **Two different ideas of "in canon".** `prose_audit` checks character membership by file stem ([`prose_audit.py:58`](../../../src/fiction_compiler/prose_audit.py#L58)); `hard_audit` checks by `id`. Latent (P2).
- **The change policy was not applied to the most taste-laden changes.** [`change-policy.md`](../../../constitution/change-policy.md) requires blindly evaluated before/after outputs; ADR 0017 §6 evaluated "the invariant, not taste". ADRs 0016 and 0017 are untested hypotheses, not validated process improvements.

## 5. Research the audit missed or under-weighted

Only findings that change a decision are listed. Access depth is recorded in [`evidence/review-sources.json`](evidence/review-sources.json); most were checked at abstract level. The review follows the audit's rule that a study motivates a local test, not a universal rule.

### 5.1 Literary-critic reliability: the decisive question for ADR 0016

- **Single runs are unstable.** LLM judges show low self-consistency across identical reruns; forcing `temperature=0` can *lower* agreement with humans ([Haldar & Hockenmaier, EMNLP Findings 2025](https://aclanthology.org/2025.findings-emnlp.1361/)). → Sample each critic k ≥ 3 times, record dispersion, and treat unstable findings as `uncertain`, not as blocking or clearing.
- **Using several vendors does not make judges independent.** Across 350+ models, when two models both err on one leaderboard dataset they agree about 60% of the time; larger, more accurate models have highly correlated errors even across providers ([Kim et al., ICML 2025](https://arxiv.org/abs/2506.07962)). Panels of diverse families can still beat one large judge ([Verga et al., 2024](https://arxiv.org/abs/2404.18796)). → Measure the error correlation on the calibration set before counting panel members as independent votes; ADR 0020's premise is testable, not given.
- **Judges favour their own family.** Self-preference grows with the judge's ability to recognise its own text ([Panickssery et al., NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html)). Self-refinement amplifies self-bias, while accurate external feedback reduces it ([Xu et al., ACL 2024](https://aclanthology.org/2024.acl-long.826/)). In the record, drafting and every literary critique ran through the same operator agent (§3), and the one critic that decides promotion, the adversarial reader, is assigned to Anthropic in the multi-vendor roster, the vendor of the Claude Code setup this repository is built around. → The sufficient critic must not share a family with the writer, or cross-family agreement must be required.
- **External benchmarks put a ceiling on expectations.** On LitBench, the best zero-shot judge agrees with human story preferences 73% of the time, and trained reward models reach 78% ([Fein et al., EACL 2026](https://aclanthology.org/2026.eacl-long.362/)). On StoryRMB, the best existing reward model manages 66.3% ([Xia et al., 2026](https://arxiv.org/abs/2605.04831)). LLM story ratings outperform other automatic measures at system level but give unsatisfactory explanations ([Chhun et al., TACL 2024](https://aclanthology.org/2024.tacl-1.62/)). And rubric judges rank AI stories above New Yorker fiction (100-Endings). → Useful, but not strong enough to select alone. Use these public sets as cheap pre-calibration before the in-house human labels the audit proposes.
- **Grant gate power by a statistical test, not by assumption.** The alternative annotator test decides from a modest annotated subset whether an LLM may replace human annotators ([Calderon, Reichart & Dror, 2025](https://arxiv.org/abs/2501.10970)). → Apply it per dimension; only dimensions that pass may block or clear promotion.
- **Behavioural tests for critics.** CheckList-style minimum-functionality, invariance and directional tests (Ribeiro et al., ACL 2020) sharpen the audit's Phase 2. The verdict should not change under a character-name swap, a label or filename swap, reversed order or harmless formatting. Inserting a known defect must lower the score. These are cheap and automatable in `critic_eval`.
- **Finding errors is the bottleneck, not fixing them.** Models fix errors well once given their location but are poor at finding them ([Tyen et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.826/)). Self-correction without external feedback does not reliably help (Huang et al., ICLR 2024). → Keep the hybrid: deterministic or structured tools locate problems and the LLM repairs. A revision must be accepted by a **fresh** check, never by the critic that proposed the fix confirming its own finding is gone. The record shows the opposite gap as well: in *Forecourt*, each promoted revision was re-reviewed only by the adversarial reader, never by the style-editor whose `revise` on the parent draft it was presumably answering.

### 5.2 Selection pressure

- **Best-of-N over-optimises its proxy.** A gold reward model, standing in for human labels, first rises and then falls as optimisation against a smaller proxy reward model increases; for best-of-n the divergence grows as log n − (n−1)/n ([Gao, Schulman & Hilton, ICML 2023](https://proceedings.mlr.press/v202/gao23h.html)). The tournament is best-of-N against an LLM critic. → Keep N small until the human-agreement curve over N is measured (the audit's N = 2/4/8 experiment is right). Select on a lower confidence bound over replicated judgments, and use ε-dominance (Laumanns et al., 2002) instead of strict Pareto dominance (N5).
- **Length and position bias** are well documented (Zheng et al., 2023; length-controlled AlpacaEval, Dubois et al., 2024). → Match candidate lengths or control for length. Draw a secret random label seed per run and reveal it after judging (N6).

### 5.3 What "default" means empirically

- **Story structure identifies AI fiction without any style cues.** Across 61,608 stories, narrative features alone reach 93.2% macro-F1 for human-versus-AI detection. AI stories over-explain themes and favour tidy single-track plots; human stories show more morally ambiguous choices and more temporal complexity. Claude shows notably flat event escalation, and AI stories cluster in one region of narrative space ([StoryScope, Russell et al., 2026](https://arxiv.org/abs/2604.03136)). This cuts both ways for this repository:
  - It *supports* two house rules the audit questions as universal: do not state the theme, and keep the protagonist's choice morally ambiguous. The support is as departures from AI defaults, not as universal quality rules.
  - The briefs' "strictly linear … no flashback", single location and three-scene single-track shape place the stories in the AI-typical region.
  - The regex linter cannot see the dominant signal at all.
  - → Measure discourse-level features against human baselines, including between-project homogeneity across the six stories, as diagnostics rather than targets.
- **Derive the phrase catalog from data.** Antislop profiles model-specific over-represented patterns against human baselines ([Paech et al., ICLR 2026](https://arxiv.org/abs/2510.15061)). → Replace hand regexes with per-model over-representation ratios and density thresholds. This also removes the literal-language false positives.
- **Professional edits give a grounded taxonomy.** LAMP: 1,057 LLM paragraphs edited by professional writers, a seven-category taxonomy of idiosyncrasies, and no model family better than another ([Chakrabarty, Laban & Wu, CHI 2025](https://dl.acm.org/doi/full/10.1145/3706598.3713559)). → Use it to calibrate the style critic and test edit-based revision against regeneration.
- **Corpus-relative novelty.** The Creativity Index measures how much of a text can be reconstructed from web text; professional authors score 66.2% higher than LLMs, and alignment lowers the score by 30.1% ([Lu et al., ICLR 2025](https://arxiv.org/abs/2410.04265)). A diagnostic only; optimising it would reward oddity.

### 5.4 Consistency, belief and resources

- **LLM-written stories contain more plot holes, and detection fails on long texts.** LLM story generation raised the plot-hole detection rate by over 100% relative to the human originals, and detection accuracy drops sharply on longer stories ([FlawedFictions, Ahuja, Sclar & Tsvetkov, 2025](https://arxiv.org/abs/2504.11900)). → Supports structured ledgers. Its controlled plot-hole generator is a template for the hidden planted-defect set the audit requests for measuring extractor recall.
- **The knowledge-leak check targets a named, benchmarked failure.** "Point-in-time character hallucination" is benchmarked, and decomposing the reasoning helps ([TimeChara, Ahn et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.197/)). → Evaluate `prose_audit` extraction on it.
- **A reference model for truth versus belief.** Sabre plans with character intentions and possibly wrong beliefs, to arbitrary theory-of-mind depth ([Ware & Siler, AIIDE 2021](https://ojs.aaai.org/index.php/AIIDE/article/view/18896)). Adopt only its minimal core: world state separate from per-agent belief state, and observations as the only way beliefs change. That fixes N2 and N3 and fills the first row of the audit's state table.
- **Countable props.** Linear logic treats resources as consumed by actions ([Ceptre, Martens, AIIDE 2015](https://ojs.aaai.org/index.php/AIIDE/article/view/12784)). The practical analogue is the film script supervisor's or copyeditor's style sheet: track countable, load-bearing props per scene. → Declare the quantity in the spec whenever a turn depends on it (§2.3).

### 5.5 Reader effect can be partly planned and checked

Structural-affect theory (Brewer & Lichtenstein, 1982, *Journal of Pragmatics* 6) derives suspense (outcome withheld), curiosity (outcome shown first) and surprise (unexpected disclosure) from the *discourse ordering* of fabula events. The repository already separates fabula from discourse, so a scene can declare its intended structure and have the reveal order checked deterministically. The audit's "intended vs observed reader effect" distinction becomes concrete: the structure is checked in code; the affect is measured with prefix-only readers.

### 5.6 Human-evaluation method

- **Crowdworkers are not enough.** Even with qualification filters, crowdworkers could not distinguish model-generated stories while English teachers could; human reference texts improved judgments ([Karpinska, Akoury & Iyyer, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.97/)). → Recruit qualified readers and show references.
- **Use validated instruments instead of ad-hoc questions.** Options: the six-item Transportation Scale–Short Form ([Appel et al., 2015](https://www.tandfonline.com/doi/abs/10.1080/15213269.2014.987400)), the Psychological Depth Scale (inter-rater α = 0.72; [Harel-Canada et al., EMNLP 2024](https://aclanthology.org/2024.emnlp-main.953/)) and the Narrative Engagement Scale (Busselle & Bilandzic, 2009). Best–worst scaling (Kiritchenko & Mohammad, 2017) gives reliable relative judgments with fewer annotations.
- **The target population can flip the result.** Under prompting, which is what this repository does, MFA-trained writers strongly disfavoured AI quality (OR 0.13) while lay readers favoured it (OR 1.82) (audit source `audit26-reader-preference`). → Pre-register which population decides.
- **The number of briefs, not raters, limits power** (after Card et al., EMNLP 2020). Detecting a 60/40 preference at α = 0.05 with 80% power needs about 194 *independent* comparisons. Comparisons cluster by brief, so the effective sample size is capped at `briefs / ICC`. With 12 briefs and an illustrative intra-brief correlation of 0.10, the cap is 120: no number of raters reaches the target. At 0.05 it needs about 80 comparisons per brief. → Treat the 12-brief pilot as variance estimation, as the audit says. The more useful lever for the confirmatory study is **more briefs**.

### 5.7 Engineering practice

- **Crash consistency.** `rename` without `fsync` of both the file and its directory is a classic application crash-consistency bug (Pillai et al., OSDI 2014). Use `fcntl.flock`, which is released when the process dies, and record lock-owner metadata.
- **Compare-and-swap commit.** `git update-ref <ref> <new> <old>` updates a ref only if it still holds `<old>`: an atomic compare-and-swap on the canon head, over content-addressed immutable objects with reachability checking (`git fsck`). That covers the race, orphan and manuscript-byte findings with a store the repository already uses. SQLite, as the audit suggests, is the alternative. Either way, the agent's shell access limits what this proves (the audit's threat-model note).
- **Provenance as a declared layout.** in-toto's layout names each step, who is authorised to perform it, and the expected inputs and outputs (Torres-Arias et al., USENIX Security 2019). It fits the triple audit: inputs are candidate, spec and canon head; the output is a critique; the performer is a role and runner. Signatures matter only once keys sit outside the agent's reach, but the *layout* alone gives the gate a machine-checkable policy.

## 6. Missed at the level of the project's core idea

Sections 2–5 ask whether the checking machinery can be trusted. This section asks whether the implementation carries out the idea it was built for. It compares the code and the six stories with the design brief's scene loop ([`original-design-brief.md:471–523`](../../original-design-brief.md)) and its sections on dialogue (brief §2.7), reader cognition (brief §2.9) and editorial passes (brief §2.11). Each item gives the gap with its evidence, a proposal, and how to test the proposal. All proposals are hypotheses until tested.

### A. Search and composition

**6.1 The system searches over prose, not over plans.**
- *Gap.* The brief's loop generates four divergent plans per scene (`generate_divergent_plans(context, count=4)`, line 479). It simulates the characters and the reader on each plan (line 485), and only then writes prose. The implementation holds exactly one spec per scene. All 18 specs carry `candidate_strategies`, which vary how that single plan is written, not the plan itself ([`record-analysis.json`](evidence/record-analysis.json), `plan_layer`). ADR 0017 concluded that quality is fixed before the prose, but applied that finding only to the premise.
- *Proposal.* Generate three or four scene plans that differ in turn, tactic, cost and what the reader learns. Hard-audit them, run the character simulator and a prefix reader on the plans, then write only the best one or two. Plans are short, so search is cheaper there, and the plan is where the quality ceiling is set. For stakes-driven stories, add a "why don't they just…" test: the simulator plays each side competently, and the plan fails if the conflict collapses in one obvious move.
- *Test.* At equal total cost, compare plan-level search plus one realization with one plan plus N realizations, using blind reader preference.

**6.2 Scene-by-scene acceptance is greedy: the pipeline cannot revise backwards.**
- *Gap.* Accepted scenes are frozen, and re-promoting one breaks the canon chain (audit probe `repromotion`). Yet the `avoid-defaults` skill asks the writer to "add or relocate a **setup**" ([`SKILL.md:18`](../../../.claude/skills/avoid-defaults/SKILL.md)), which usually means editing an earlier, already frozen scene.
- The brief's whole-work check at chapter and act ends (`run_global_audit`, line 519) exists only as `audit_canon`, which checks facts, not literature.
- The promise ledger records `id`, `text` and `owed_by`, with no trigger and no check that the prose pays the promise off.
- LLMs frequently leave "Chekhov's guns" unfired even with the necessary context. Encoding foreshadow–trigger–payoff triples as verifiable conditions addresses this ([CFPG, Yun et al., 2026](https://arxiv.org/abs/2601.07033)). Writers do the same by hand: they find the ending, then go back and plant its setups.
- *Proposal.*
  - Accept scenes provisionally, then run a whole-work literary pass at act or story end that may reopen earlier scenes.
  - Record each scene's *read set* (the facts, predicates and promises it depends on), so an upstream change invalidates only the scenes that depend on it, as incremental compilation does.
  - Type promises with a trigger condition and a payoff check.
- *Test.* A fixture where a later scene needs a plant in scene 1. The pipeline must produce a new version of scene 1, invalidate exactly the scenes that depend on it, keep the history, and leave canon verification clean.

**6.3 Nothing checks that the prose carries out the plan.**
- *Gap.* A compiler's basic correctness check, that the output implements the specification, has no counterpart here. The prose-claims schema offers only `character_present`, `focalizer_knows`, `interiority_of`, `located_at`, `closes_promise` and `states_fact` ([`prose-claims.schema.json`](../../../schemas/prose-claims.schema.json)). Nothing checks that the required events happen, that the turn lands, or that the exit state is reached. The hard audit checks the spec against canon, not the prose against the spec. Only LLM critics judge realization, and they are shown the intended turn, which is the priming risk the audit identified.
- *Proposal.* Borrow the compiler technique of translation validation. An extractor that has not seen the plan lists the events and state changes that occur in the prose, each with a quoted span. Code then matches them against the spec's required events, turn and exit state. An unmatched plan element is a material "plan not realized" finding. An unplanned consequential event is routed to the delta or back to the plan.
- *Test.* Planted cases where the turn exists only in the spec; controls where it is realized obliquely but recognisably.

### B. The reader

**6.4 The reader model was never built.**
- *Gap.* The brief treats reader cognition as central: what the reader knows, suspects, expects and has forgotten (brief §2.9, line 302). The code tracks what *characters* know and never what the *reader* knows. The discourse plan's `revelations` are free text; *Forecourt*'s last one reads "enacted, not explained; the man's nature is never confirmed". Dialogue subtext (brief §2.7) has no representation either.
- *Proposal.* A reader-disclosure ledger in the discourse layer: which facts are disclosed to the reader, in which scene, and how (stated, implied or withheld). It enables deterministic checks for:
  - dramatic irony: the reader knows something a character doesn't;
  - fair play: each clue is disclosed before its reveal;
  - retrospective coherence: every surprise has an earlier disclosed plant;
  - curiosity gaps that are opened and later closed;
  - the declared suspense, curiosity or surprise structure (§5.5).

  Optionally, key lines of dialogue record what they *say* and what they *do* (ask, evade, misdirect, concede), so critics judge subtext against intent. The measured side is prefix reading: readers, or LLM probes explicitly labelled as predictions, say what they expect and what they want to know.
- *Test.* Fixtures for irony, fair play and an unplanted surprise.

**6.5 The reader contract is not compiled into tests.**
- *Gap.* Contract clauses are free strings and nothing maps them to a check. For example, *Forecourt*'s "the man stays genuinely ambiguous to the end: never confirmed victim or villain" is judged only implicitly.
- *Proposal.* A contract-coverage report that maps each clause to a deterministic check, a critic question, a reader question, or "untested". The ambiguity clause becomes a prefix-reader question ("victim or villain?") whose answers should split rather than cluster near one answer.
- *Test.* Coverage reports for the six projects; no load-bearing clause left untested.

**6.6 The owner's taste is not recorded as data.**
- *Gap.* The decisive reader is the project owner, who picks premises and rejects whole batches. No structured record of those choices exists: `projects/*/decisions/` holds only promotion manifests, READMEs and one ending-strategy note. The contracts name "adult literary readers"; the owner's revealed preferences are not captured anywhere the pipeline can use.
- *Proposal.* A preference log recording each choice, the alternatives shown, the stated reason and the date. It serves as a calibration target (does a critic predict the owner's picks better than chance?) and as input to premise generation. Keep it separate from general-reader evaluation, and report both.
- *Test.* Agreement between each critic and the logged choices.

### C. The central claim and how it is evaluated

**6.7 The core thesis is contested and untested.**
- *Gap.* ADR 0016 builds selection on "the LLM is a strong critic but a weak writer". The Generative AI Paradox finds the opposite pattern: models' generation can exceed their understanding of the same kind of output, and the two correlate weakly ([West et al., ICLR 2024](https://arxiv.org/abs/2311.00059)). 100-Endings finds rubric judges ranking AI stories above New Yorker fiction, and §5.1 gives the benchmark ceilings.
- *Test, before any further selection machinery.* On human-labelled story pairs (a LitBench subset plus in-house pairs), compare three selectors: the critic's pick, the writer's first sample, and a random choice. Then, on the project's own tasks, compare critic-selected with first-draft scenes by blind human preference. If the critic is not clearly better than taking the first draft, selection adds cost and noise.

**6.8 The system repeats itself across stories.**
- *Gap.* All five completed stories withhold the outcome ([`record-analysis.json`](evidence/record-analysis.json), `endings`). Four end on a small physical act followed by a return to routine or a departure:
  - *Forecourt*: she pockets the fob, locks the door and recounts the till.
  - *Slack Water*: "She left the cover off."
  - *The Overnight*: she files her card and "started the mixer for the morning bake".
  - *Visiting Order*: "She turned the key."

  *Verbatim* ends on the interpreter drinking water while the verdict is pending. `avoid-defaults` predicts the model's default continuation within the current story only. Nothing compares a new story with the system's own earlier ones.
- *Proposal.* Treat the system's own previous stories as the first default to avoid. Record typed features per story (ending type, turn type, resolution, recurring object motifs, focalization). A new premise or plan must differ from earlier projects on the declared axes, unless the brief asks for continuity. Report discourse-level homogeneity across projects as a diagnostic (§5.3).
- *Test.* The homogeneity measure across the next set of stories, compared with the current six.

**6.9 Real literature is never used as a control.**
- *Proposal.* Run the linter, the critics and the story format on public-domain masterworks (for example Chekhov in public-domain translation, Joyce's *Dubliners*). This yields:
  - how often the gate would block accepted literature;
  - whether spec and delta can represent such scenes without distortion, and which fields are missing;
  - human baselines for the discourse measures;
  - known-good controls for critic calibration.

  Check German/EU public-domain status first ([`original-design-brief.md:717`](../../original-design-brief.md)).
- *Test.* A per-scene record of what the gate would have blocked and what the story format could not represent.

**6.10 The planned pilot tests the architecture where it should help least.**
- *Gap.* Every story so far has two or three scenes of roughly 1,300–1,800 words and fits in one context window. The canon ledger's advantage, consistency over length, cannot show at that size, and the audit schedules long-form work last (Phase 4).
- *Proposal.* Include one 8–12k-word condition in the first pilot, on fewer briefs. Otherwise a null result is predictable and uninformative about the architecture.

**6.11 Only one model family writes.**
- *Gap.* Every candidate was drafted in the operator's session. StoryScope finds recognisable per-model fingerprints and AI stories clustering in one region (§5.3). Heterogeneity was applied to critics (ADR 0020), not to writers.
- *Proposal.* Draft candidates with different model families, and test edit-based revision (LAMP) against regeneration. Fine-tuning on public-domain works or the owner's own writing is a later, optional lever; the operating contract forbids imitating a living author.
- *Test.* Diversity between candidates and blind preference, at equal cost.

## 7. Revised priorities

Ordered by expected value per unit of work, given §3 and §6. Items 1–4 are small changes that address observed failures or the missing plan-to-prose check. Item 5 decides whether the selection architecture deserves further investment. Items 8–11 extend the architecture toward the design brief.

| # | Change | Why | Exit evidence |
|---|---|---|---|
| 1 | **Declared review policy in the gate.** List the required literary roles per project. Any role that issued a non-pass verdict anywhere in the promoted text's history must re-review the final bytes, or a human waiver with a reason is recorded. Unresolved dissent → `human_decision_required` | Observed in 7–9 of 12 promotions | The historical pattern in §3 is refused; a regression fixture pins it |
| 2 | **Reviewer provenance.** Each critique records runner, model, session or context digest, generation time and packet type. Critiques written from the drafting context are labelled self-review and cannot fill a blind-reader role. Reader packets are prefix-only | The independence of the evidence is currently unknowable | A trace can prove which view each reviewer saw |
| 3 | **Plan-to-prose realization check** (§6.3). Blind event extraction, matched in code against required events, turn and exit state | The "compiler" has no correctness check between plan and output | Planted unrealized turns are caught; oblique realizations pass |
| 4 | **Policy-versioned acceptance.** Every acceptance records its policy version; validation reports scenes accepted under an older policy instead of passing them silently | 5 of 17 scenes fail the current gate | The validator lists `legacy_policy` scenes; `assemble` marks or refuses them per project setting |
| 5 | **Test the thesis, then calibrate critics** (§6.7, §5.1). Critic pick vs first draft vs random on human-labelled pairs; then public sets, clean controls, CheckList invariance and directional cases, professional-vs-AI pairs, k-sample stability, alt-test per dimension; the sufficient critic comes from a different family than the writer | ADR 0016 rests on an untested, contested assumption | Selection earns its cost, or is simplified; only dimensions that pass keep blocking power |
| 6 | **Selection statistics.** ε- or confidence-bound dominance, secret per-run seed revealed after judging, length control, small N until the curve over N is measured | N5, N6; best-of-N over-optimisation | Noise-level differences produce `human_decision_required` |
| 7 | **Style: from veto to measurement.** Dialogue- and quotation-aware lint; catalog derived from data; discourse-level diagnostics; premise probes as an opt-in profile; brief-clause provenance; cross-project repetition check (§6.8); public-domain literature as controls (§6.9) | §2.1, N7, §6.8–6.9 | Literal, voiced and deliberate uses survive; homogeneity across projects is measured; the gate's block rate on masterworks is known |
| 8 | **Plan-level search** (§6.1) with character simulation, a prefix-reader probe and the "why don't they just…" test | The brief's core loop; quality ceiling set before prose | Equal-budget comparison against prose-level search |
| 9 | **Belief, resource and reader semantics.** One knowledge store; typed values with negation; world state versus belief; countable props declared when a turn needs them; a reader-disclosure ledger; typed promises with triggers (§6.2, §6.4) | N1–N3, §2.3, §6.4 | Fixtures: changed door code, "she believes the dog is alive", negative knowledge, loaf count, dramatic irony, fair-play clue, unplanted surprise |
| 10 | **Provisional canon and whole-work revision** with read-set dependency invalidation (§6.2) | Backward planting is impossible today | The backward-planting fixture passes with history preserved |
| 11 | **Contract coverage and owner preference log** (§6.5–6.6) | Contracts and the deciding reader are not testable | Coverage report per project; critic–owner agreement reported |
| 12 | **Transactional commit** (the audit's workstream A), with CAS on the head, `fsync` and `flock` | Correct, but not yet observed in practice | The audit's probes plus N8 fail safely |
| 13 | **Reader pilot**, decoupled from #12. Validated instruments, named population, qualified readers, power planned by brief count, one 8–12k-word condition, and a multi-family-writer arm (§6.10–6.11) | §2.7, §5.6, §6.10 | As in the audit's experiments document, plus a pre-registered population, design effect and length condition |
| 14 | **Governance.** Mark ADRs 0016 and 0017 as unvalidated hypotheses until blind before/after comparisons exist. Turn all 32 probes into maintained fixtures with expected *safe* outcomes, which requires extending the regression whitelist beyond pure functions to scenario runners | The constitution's own change policy | `run_regression` fails on any reappearance of the recorded defects |

What *not* to do next: add critic personas, add a vector store, or build a richer simulator before items 1–5. The record shows the existing critics are not used as designed, and their reliability must be measured first. Plan-level search (#8) and multi-family drafting (#13) redistribute the existing generation budget; they do not add reviewers.

## 8. Limits of this review

- The timing and voice evidence in §3 is circumstantial. It shows the record cannot establish reviewer independence; it does not establish who wrote any critique.
- Most new sources were checked at abstract level, some via search summaries. Canonical references (CheckList, Card et al., MT-Bench, length-controlled AlpacaEval, Huang et al., Pillai et al., in-toto, ε-dominance, best–worst scaling, Busselle & Bilandzic) were cited from established literature and not re-read in this session. Access depth per source is in [`evidence/review-sources.json`](evidence/review-sources.json).
- The power figures illustrate the design effect under stated assumptions; they are not a power analysis for this project.
- §6 compares the implementation with the design brief and with craft practice; its proposals are untested hypotheses. The ending pattern in §6.8 is an observation about five stories, not a measured homogeneity statistic.
- This review was written by a Claude model, very likely the same family that drafted the stories and recorded the historical critiques. §5.1 applies to it: its few literary judgments (§2.2–2.3) are about countable facts and recorded verdicts, not about quality.
- No production code, tests, prompts, stories or constitution were changed. No model or human-reader study was run.

# Sources

- [StoryScope](https://arxiv.org/abs/2604.03136)
- [Correlated Errors in LLMs](https://arxiv.org/abs/2506.07962)
- [Rating Roulette](https://aclanthology.org/2025.findings-emnlp.1361/)
- [Self-recognition and self-preference](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html)
- [Self-bias in self-refinement](https://aclanthology.org/2024.acl-long.826/)
- [LitBench](https://aclanthology.org/2026.eacl-long.362/)
- [StoryAlign](https://arxiv.org/abs/2605.04831)
- [Alternative annotator test](https://arxiv.org/abs/2501.10970)
- [Spoiler Alert / 100-Endings](https://arxiv.org/abs/2604.09854)
- [Tian et al.](https://arxiv.org/abs/2407.13248)
- [Fabula](https://arxiv.org/html/2606.14411v1)
- [Reward model overoptimization](https://proceedings.mlr.press/v202/gao23h.html)
- [FlawedFictions](https://arxiv.org/abs/2504.11900)
- [TimeChara](https://aclanthology.org/2024.findings-acl.197/)
- [Antislop](https://arxiv.org/abs/2510.15061)
- [LAMP](https://dl.acm.org/doi/full/10.1145/3706598.3713559)
- [Creativity Index](https://arxiv.org/abs/2410.04265)
- [Sabre](https://ojs.aaai.org/index.php/AIIDE/article/view/18896)
- [Ceptre](https://ojs.aaai.org/index.php/AIIDE/article/view/12784)
- [MTurk perils](https://aclanthology.org/2021.emnlp-main.97/)
- [Psychological Depth Scale](https://aclanthology.org/2024.emnlp-main.953/)
- [TS-SF](https://www.tandfonline.com/doi/abs/10.1080/15213269.2014.987400)
- [Card et al.](https://aclanthology.org/2020.emnlp-main.745/)
- [Reader-preference study](https://arxiv.org/abs/2510.13939v4)
- [Tyen et al.](https://aclanthology.org/2024.findings-acl.826/)
- [Juries (PoLL)](https://arxiv.org/abs/2404.18796)
