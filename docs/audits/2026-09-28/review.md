# Review of the 27 September audit: double-check, corrections and additions

Review date: 28 September 2026; second pass the same day added §6 (the project's core idea) and re-ranked §7. Reviewed: [`docs/audits/2026-09-27/`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-27/audit.md) at commit `2b8ef0b` (production source identical to the audited `310e50c`). This document does not replace the audit. It records what was rechecked, what should be corrected, and what the audit missed. The 27 September documents retain their original bodies with dated correction notes. This version additionally rechecks commit `158eed65db5a194c5ad24a0ca99ca8099b93d5e7`; the changes and fresh evidence are recorded in [recheck notes](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/recheck.md). Production source remains unchanged.

## Assessment

**The audit's engineering findings are accurate; all 24 of its probes reproduce byte-for-byte. Its main gap is that it examined what the code *could* allow, not what the pipeline *actually did*.** The stored record changes the priorities:

- Only **3 of 17** accepted scenes (all in *The Overnight*) have hash-bound records from adversarial-reader, style-editor and character-simulator. These records establish coverage, not reviewer independence.
- **5 of 17** accepted scenes would be refused by today's gate, yet workspace validation passes.
- In **7 of 12** gate-era promotions, a non-pass literary record on a filename-inferred predecessor has no same-role, hash-bound re-review on the promoted candidate. That is a missing evidence trail, not proof that the defect persisted or no review happened. One literary `pass` was sufficient for the gate.

Second, the audit's correction on house style is too cautious: the briefs of the two most recent stories quote the premise-probe rubric, so the contract contains documented framework influence. Clause authorship, human endorsement and the size of the resulting style effect remain unknown. Third, the audit under-weights recent research on judge reliability and on discourse-level (story-structure) signatures of AI fiction. That research makes calibrating the single literary critic supplying the literary evidence in nine recorded promotions more urgent than adding state, agents or critics.

Fourth, measured against the project's own design brief, parts of the core idea are missing (§6):

- The stored scene workflow lacks versioned alternative plans; prior operator-side planning is not recoverable from that fact alone.
- Accepted scenes cannot be revised backwards to plant setups.
- There is no systematic, evidence-bound plan-to-prose realization check; literary critiques can address it incompletely.
- The reader model the brief treats as central was never built.
- The central claim that LLMs are stronger critics than writers is contested and untested.
- The completed stories repeatedly close with objects, small physical acts and restraint; their central outcomes are not all withheld.

## 1. What was double-checked

| Item | Method | Result |
| --- | --- | --- |
| Baseline checks | Reran `validate_workspace.py`, the unit suite, `run_regression.py` | Validation passed; 193 tests OK; 28/28 fixtures, as reported |
| 24 audit probes | Ran `probes.py` from a scratch copy against the live library; compared JSON | 24/24 identical |
| Code-level claims | Read every cited module (`promote`, `integrity`, `state`, `hard_audit`, `critique`, `tournament`, `revision`, `defaultness`, `prose_audit`, `context`, `premise`, `tools`, `role_runner`, `critic_eval`, `regression`, `safety`, `workspace`, `assemble`, `trace`, MCP server, promote CLI, skills, personas) | All checked claims confirmed, including CLI exit code, panel unanimity on total failure, Gemini key in exception URL, `NaN` confidence, manifest omissions, the missing `approved_by` CLI option and the contradictory promote-skill order |
| Literary claims | Read the cited passages and the neighbouring scenes and specs | *Overnight* confirmed and strengthened (§2.3); *Forecourt* and *Visiting Order* quotations confirmed |
| Research claims | Re-fetched Tian et al. (abstract and tables), Fabula §4.2, ConStory, reference-based evaluation, reader-preference study, 100-Endings | Mostly accurate; two corrections (§2.4–2.5, with the proposed Tian correction itself corrected on recheck) |
| New probes | [`evidence/extra_probes.py`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/extra_probes.py) → [`extra-probe-results.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/extra-probe-results.json) | 8 additional observations: implementation defects, overlapping failure cases and policy/semantic gaps distinguished in §4 |
| Record analysis | [`evidence/record_analysis.py`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/record_analysis.py) → [`record-analysis.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/record-analysis.json) | §3; story endings and plan layer in §6 |
| Core design | Compared the implementation with the design brief's loop (lines 471–523) and its §§2.7, 2.9 and 2.11; read the five completed endings and the final accepted scene of the unfinished sixth project; checked the prose-claims and state-delta schemas | §6 |

## 2. Corrections to the audit

### 2.1 The briefs establish influence, not the full causal effect of the pipeline

The earlier audit correctly observed that the briefs prescribe the repeated style, but their origin matters:

- `projects/forecourt/brief/creative-brief.md` refers explicitly to the probe's flagged risk and requests a single transforming consciousness and a threat not resolvable by proof.
- `projects/visiting-order/brief/creative-brief.md` likewise names the premise probe and an interpersonal conflict that no proof can settle.
- The record analysis finds repeated lint-category constraints in five briefs.

This directly establishes uptake of framework vocabulary and explicit references in two briefs. It does not establish who proposed or approved each clause, that the framework originated every preference, or how much those clauses caused the resulting similarity. Preserve the optional realism-profile proposal and add clause provenance: human-authored, agent-proposed/human-accepted, inherited default, or unknown. A controlled with/without-profile experiment is still needed to estimate the effect.

### 2.2 Slack Water shows missing re-review, not established persistence of every defect

ADR 0017 says Slack Water passed every downstream audit. Read narrowly as “passed the implemented gate,” that can be true; read as “every specialist reviewed and passed the final candidate,” it is unsupported. Scenes 1 and 2 have style-editor non-pass records for `candidate-b.md` without same-role records for promoted `candidate-b-r2.md`. This predecessor relation is inferred from filenames, not a recorded parent artifact.

Some sibling critiques identify weak financial stakes or overly explicit elegy, which overlap the later premise diagnosis. But sibling findings cannot automatically be transferred to the winner. Moreover, scene 2's style-editor complains that the water test is absent from the dramatized action; the promoted revision explicitly stages Rennie running the hose over the garboard and the resulting leak. The record therefore contains an example of a criticized feature being addressed despite missing same-role re-review.

The confirmed problem is that issue resolution and adjudication are not traceable. The proposition that gate omissions caused the final story's alleged inferiority remains untested. Track each applicable finding through `resolved`, `persists`, `disputed`, `not_applicable`, or authorized waiver; do not treat every historic rejection as a permanent veto. A fresh qualified reviewer may adjudicate a finding rather than requiring the same model to return forever.

### 2.3 The *Overnight* loaf defect appears in the plan as well as the prose

The audit's quantity finding is correct, and the evidence is stronger than it states. [`ch01-sc01.md:3`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/projects/the-overnight/manuscript/chapters/ch01-sc01.md) establishes "Twelve tins", reinforcing that no spare loaf is established in the scene. The scene spec's `turn` requires "she keeps one loaf back" ([`ch01-sc03/spec.json:22`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/projects/the-overnight/scenes/ch01-sc03/spec.json)), and the accepted delta's fact text says "Nadia kept one back".

The contradiction therefore sits in the **structured** artifacts, inside natural-language fields (`turn`, fact `text`) that no check reads. It should be routed to the scene-spec/plot layer. For this scene, make baked, delivered and retained quantities explicit and check their conservation. A focused planning question may suffice initially; a typed resource ledger is justified when such constraints recur. Textual presence in a spec proves the inconsistency crosses layers, not the chronological origin of the mistake.

### 2.4 Tian et al.: the proposed table correction was wrong

The “over 40%” phrase is indeed the authors' abstract claim and should be attributed to them. However, the 27 September audit correctly labeled 23% versus 68% as **overall diversity preference**. Reinspection of the published PDF, printed page 17666 / PDF page 8, Table 6, and the versioned arXiv HTML confirms:

| Dimension | Outline-Only | Tie | Arc-Enhanced |
|---|---:|---:|---:|
| Theme | 5% | 32% | 64% |
| Setting | 32% | 36% | 32% |
| Conflict | 5% | 41% | 55% |
| Character | 23% | 27% | 50% |
| Overall | 23% | 9% | 68% |

The earlier review shifted column labels. Restore the correct labels in the dated update note. These remain task-specific preferences, not a percentage improvement in general literary quality. [Published paper](https://aclanthology.org/2024.emnlp-main.978.pdf), [versioned HTML Table 6](https://arxiv.org/html/2407.13248v2).

### 2.5 The 100-Endings headline result is missing where it matters most

The audit cites 100-Endings only as a surprise diagnostic. Its headline finding is that on EQ-Bench, rubric-based LLM judges rank zero-shot AI stories **above New Yorker stories**. This challenges the particular rubric’s validity for that comparison; it does not establish that every expert would prefer every New Yorker story under every contract, or that a critic cannot improve selection within an AI-generated candidate pool. It belongs in the judge-reliability discussion alongside the audit's more favourable evidence.

### 2.6 Severity should also weigh what actually happened

The audit rates severity by potential harm. In this single-operator repository, the stored artifacts do not establish that the promotion race or path traversal occurred; absence from an incomplete record does not establish that they never occurred. By contrast, single-critic sufficiency and missing same-role re-review artifacts are directly observable in most manifest-bearing promotions (§3). Keep the P0 labels, but add an "observed in record" column and prioritize by both demonstrated frequency and impact; run bounded trust repairs and measurement in parallel (§7).

### 2.7 Workstream B does not need to wait for workstream A

The audit says literary measurement should run "alongside" the trust repairs, but its pilot arm D is defined "with trust repairs". The P0 defects affect ordinary single-operator use too, through stale evidence, re-promotion and interrupted writes. A pilot that generates on frozen snapshots, in an isolated harness with full logging, does not depend on them. State this decoupling explicitly, or B will silently wait for A.

## 3. What the stored record shows (not in the audit)

The audit inventoried gate status per candidate ([`candidate-status.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-27/evidence/candidate-status.json)) but did not synthesise it. Results from [`record-analysis.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/record-analysis.json). The revised analyzer enumerates canon-indexed acceptances, checks candidate digests and manuscript equality, and preserves multiple records per critic. “Gate-era” below means a manifest with nonempty `binding_critiques`, not a verified historical policy version. Predecessor and sibling categories use filenames; they do not establish a causal lineage or defect persistence:

| Observation | Count | Consequence |
| --- | --- | --- |
| Accepted scenes that fail today's gate (all of *Verbatim*; *Salt in the Wire* sc01–02) | 5 / 17 | Validation passes; the manifests lack an explicit policy version; their legacy status is reconstructed from repository history and record shape. *Verbatim*, counted among the "five completed manuscripts", has no gate-bound literary review |
| Gate-era promotions with exactly one literary critic on the promoted bytes | 9 / 12 | The literary third of the triple audit is, in practice, one `adversarial-reader` pass |
| Gate-era promotions where a literary `revise` on the filename-inferred predecessor has no same-role bound review on the promoted bytes | 7 / 12 | No issue-level resolution record establishes how these findings were handled |
| Gate-era promotions where a sibling draft drew a non-pass literary record without that role reviewing the promoted bytes | 9 / 12 | Potential shared weaknesses merit applicability review; sibling-only defects need not transfer |
| Scenes with a prose audit (the hard audit's prose half) | 1 / 17 | Only one retained scene-level record establishes its use |
| Promoted revisions / scenes with a revision log | 10 / 4 | Four scenes retain logs. Stateless calls, manual review and deleted/missing logs cannot be excluded |
| Manifests with the human gate required | 0 / 17 | Projects list `premise`, `voice-profile`, `ending`, `final`, none of which is enforced |
| Tournament runs / runs using critic judgments (ADR 0016) | 3 / 0 | No retained tournament record establishes use of critic-judgment selection; one early run "selected" the scene id `ch01-sc01` (the phantom-candidate bug later fixed) |
| Retained `vendor_critique` provenance events (ADR 0020) | 0 | No vendor-runner provenance event was found. Session identity, model family and review context are unknown where provenance is absent |

**Recorded coverage narrowed.** All three *The Overnight* scenes have bound records from the three named literary roles; all nine scenes across *Slack Water*, *Visiting Order* and *Forecourt* have one. This supports an explicit project review policy and resolution tracking; it does not establish that those additional roles improve prose in every contract.

**Critic independence is not evidenced.** In all three *Forecourt* traces, six literary critiques (three roles × two drafts) were recorded within 33–45 seconds; the gap between the same role's two critiques was 2.5–9.7 seconds (median 3.8). One "independent" reader critique of scene 2 speaks in the author's voice ("Kept as a deliberate trade") and relies on a later scene ("the officer is police in sc03 regardless"). Timestamps mark the recording call, not generation, so this does not prove the drafter wrote the critiques. It shows the record **cannot distinguish** a blind independent reader from the drafting context. That is the deeper form of the audit's "fabricated audit" finding: no attack is needed.

**Blinding is predictable under the default seed.** With the default seed, `anonymize(["candidate-a.md", "candidate-b.md"])` returns `A`, `B`: the label is the filename's letter. Two of the three stored tournament mappings match both filename letters. The older phantom-candidate run does not (`candidate-b` maps to `C`). Eleven of 17 promoted filenames are in the `candidate-a` family; that frequency does not establish a selection bias without generation order, candidate quality and actual judge-packet evidence. A reproducible seed is compatible with blinding if its mapping is withheld from judges; a reused public mapping weakens that boundary.

## 4. Additional observations: defects, overlaps and policy gaps

| # | Defect | Location | Probe observation | Severity |
| --- | --- | --- | --- | --- |
| N1 | An event effect `knows(c, f)` is checked against `predicate_changes`, but `holds("knows")` reads only the separate knowledge store. The audit passes, and the knowledge never arrives | [`state.py:97`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/state.py:97), [`hard_audit.py:183`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/hard_audit.py:183) | Scene 1 `pass`; scene 2 gets a spurious **fatal** "knowledge would leak from the future" | P1 |
| N2 | `facts_removed` leaves its ID in knowledge and the prose checker accepts “she knew”; historical memory, stale belief and current factive knowledge are not distinguished | [`state.py:134`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/state.py:134) | `fact_exists=false`, `knows=true`, prose audit `pass` | P1 semantic gap; deletion need not erase memory or automatically update a character’s belief |
| N3 | Negation cannot be expressed: `value: false` on `knows` is ignored, so "must NOT yet know" fails exactly when it holds | [`state.py:97`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/state.py:97), event schema | Material causal finding on a satisfied precondition | P1; overlaps the original ignored-value defect. Negative knowledge is not the same as belief in a false proposition |
| N4 | ISO-like times compare as strings; `T` and space separators mis-order | [`hard_audit.py:62`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/hard_audit.py:62) | 09:00 → 10:00 flagged as time running backward | P2 |
| N5 | Strict Pareto selection has no calibrated indifference or uncertainty policy | [`tournament.py:51`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/tournament.py:51) | A 0.1-point edge on every dimension → `select`, `disagreement: false` | Policy gap, not incorrect Pareto mathematics. Probe scores 7/6.9 also exceed the documented 0–5 rubric; a valid-scale 4/3.9 recheck gives the same result |
| N6 | Default-seed labels equal the filename letter | [`tournament.py:26`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/tournament.py:26) | `candidate-a→A`, `candidate-b→B`, every run | Blinding risk; deterministic labels alone do not prove a judge saw origin information |
| N7 | Character speech is linted as narration | [`defaultness.py:47`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/defaultness.py:47) | A deadpan quoted "Time stood still" → **material** | P1; another instance of the original contextual-style false positive, not a distinct root cause |
| N8 | The lock is an empty `O_EXCL` file with no owner or staleness check; a killed process blocks all later promotions. `os.replace` without `fsync` is also not durable | [`integrity.py:106`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/integrity.py:106), [`integrity.py:145`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/integrity.py:145) | Child used `os._exit(9)`; empty lock left; next lock acquisition refused. No SIGKILL, full promotion or power-loss test was performed | P2 |

Static findings, not probed:

- **No policy re-evaluation.** [`validate_workspace.py:123`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/scripts/validate_workspace.py:123) checks the hash chain only. Acceptances carry no explicit policy version. Shape and history distinguish legacy records, but the verifier does not report that status directly.
- **"Material" is undefined for LLM critics.** The output contract ([`role_runner.py:55`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/role_runner.py:55)) and personas (one to four sentences) give no severity anchors. The promotion threshold therefore rests on an uncalibrated word. The continuity persona says "cite exact files", which a vendor runner without tools cannot do.
- **The drafting input is not guaranteed to be retained.** Context bundles, the record of what the writer actually saw, go to the root `.runs/`, which `.gitignore` excludes ([`context.py:101`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/context.py:101)). The operating contract says evidence in `.runs/` must be preserved; `trace.py` says it can be pruned.
- **Two different ideas of "in canon".** `prose_audit` checks character membership by file stem ([`prose_audit.py:58`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/src/fiction_compiler/prose_audit.py:58)); `hard_audit` checks by `id`. Latent (P2).
- **The change policy was not applied to the most taste-laden changes.** [`change-policy.md`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/constitution/change-policy.md) requires blindly evaluated before/after outputs; ADR 0017 §6 evaluated "the invariant, not taste". ADRs 0016 and 0017 record mechanical checks, not evidence of improved literary outcomes. Their engineering behaviors and literary hypotheses need separate statuses.

## 5. Research the audit missed or under-weighted

Only findings that change a decision are listed. Access depth is recorded in [`evidence/review-sources.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/review-sources.json); most were checked at abstract level. The review follows the audit's rule that a study motivates a local test, not a universal rule.

### 5.1 Literary-critic reliability: the decisive question for ADR 0016

- **Single runs are unstable.** LLM judges show low self-consistency across identical reruns; forcing `temperature=0` can *lower* agreement with humans ([Haldar & Hockenmaier, EMNLP Findings 2025](https://aclanthology.org/2025.findings-emnlp.1361/)). → Estimate repeatability on a calibration subset first. Three repeats are a possible pilot allocation, not a validated minimum; adapt repetition to measured variance and cost, and distinguish disagreement from correctness.
- **Using several vendors does not make judges independent.** Across 350+ models, when two models both err on one leaderboard dataset they agree about 60% of the time; larger, more accurate models have highly correlated errors even across providers ([Kim et al., ICML 2025](https://arxiv.org/abs/2506.07962)). Panels of diverse families can still beat one large judge ([Verga et al., 2024](https://arxiv.org/abs/2404.18796)). → Measure the error correlation on the calibration set before counting panel members as independent votes; ADR 0020's premise is testable, not given.
- **Judges favour their own family.** Self-preference grows with the judge's ability to recognise its own text ([Panickssery et al., NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/hash/7f1f0218e45f5414c79c0679633e47bc-Abstract-Conference.html)). Self-refinement amplifies self-bias, while accurate external feedback reduces it ([Xu et al., ACL 2024](https://aclanthology.org/2024.acl-long.826/)). Historical model/session identities are not established (§3). The repository supports Codex and Claude, and its roster describes intended routing rather than proving past execution. → Cross writer and judge families in calibration; choose reviewers by measured agreement, false positives, independence of context and cost. Cross-family review is a testable mitigation, not an unconditional requirement or guarantee.
- **External benchmarks give task-specific reference results.** On LitBench, the best zero-shot judge agrees with human story preferences 73% of the time, and trained reward models reach 78% ([Fein et al., EACL 2026](https://aclanthology.org/2026.eacl-long.362/)). On StoryRMB, the best existing reward model manages 66.3% ([Xia et al., 2026](https://arxiv.org/abs/2605.04831)). LLM story ratings outperform other automatic measures at system level but give unsatisfactory explanations ([Chhun et al., TACL 2024](https://aclanthology.org/2024.tacl-1.62/)). And rubric judges rank AI stories above New Yorker fiction (100-Endings). → These are reported results, not capability ceilings or sufficient reasons to forbid automated selection. LitBench uses Reddit-derived preferences; StoryRMB has a different candidate/ranking task. Use public sets for preliminary calibration, then measure local selection benefit and error costs on unseen briefs.
- **Use annotation-substitution tests as one calibration input.** The alternative annotator test decides from a modest annotated subset whether an LLM may replace human annotators ([Calderon, Reichart & Dror, 2025](https://arxiv.org/abs/2501.10970)). → Consider it per dimension alongside localization accuracy, false-positive costs and distribution shift. Passing an annotation-substitution test does not by itself authorize a hard creative veto.
- **Behavioural tests for critics.** CheckList-style minimum-functionality, invariance and directional tests (Ribeiro et al., ACL 2020) sharpen the audit's Phase 2. Declare which transformations preserve meaning: metadata relabeling, presentation-order swaps and carefully chosen formatting changes should preserve preferences after remapping. Character names can carry cultural or plot meaning, and typography can be artistically functional; neither is universally invariant. A planted defect should worsen its targeted assessment, not necessarily every global score. These are cheap and automatable in `critic_eval`.
- **Separate defect localization from repair.** In the studied reasoning tasks, models could correct errors more successfully when given their location; transfer to literary diagnosis remains untested ([Tyen et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.826/)). Self-correction without external feedback does not reliably help (Huang et al., ICLR 2024). → Keep the hybrid: deterministic or structured tools locate problems and the LLM repairs. A revision must be accepted by a **fresh** check, with an uncontaminated packet and, for consequential disputed repairs, an independently calibrated review. Fresh context matters; an absolute ban on reusing the same model is not established. The record shows the opposite gap as well: in *Forecourt*, each promoted revision was re-reviewed only by the adversarial reader, never by the style-editor with non-pass records on the filename-inferred predecessor; the records do not establish which findings the revision targeted.

### 5.2 Selection pressure

- **Best-of-N over-optimises its proxy.** A gold reward model, standing in for human labels, first rises and then falls as optimisation against a smaller proxy reward model increases; best-of-n also shifts the selected-output distribution under the paper’s assumptions ([Gao, Schulman & Hilton, ICML 2023](https://proceedings.mlr.press/v202/gao23h.html)). The tournament is best-of-N against an LLM critic. → Keep N small until the human-agreement curve over N is measured (the audit's N = 2/4/8 experiment is right). Test a predeclared indifference band or paired uncertainty-aware comparison. ε-dominance is an approximation/search tool; an arbitrary epsilon or lower-bound score is not a calibrated statistical test and does not remove correlated bias (N5).
- **Length and position bias** are well documented (Zheng et al., 2023; length-controlled AlpacaEval, Dubois et al., 2024). → Match candidate lengths or control for length. Draw a secret random label seed per run and reveal it after judging (N6).

### 5.3 What "default" means empirically

- **Story structure identifies AI fiction without any style cues.** Across 61,608 stories, narrative features alone reach 93.2% macro-F1 for human-versus-AI detection. AI stories over-explain themes and favour tidy single-track plots; human stories show more morally ambiguous choices and more temporal complexity. Claude shows notably flat event escalation, and AI stories cluster in one region of narrative space ([StoryScope, Russell et al., 2026](https://arxiv.org/abs/2604.03136)). This cuts both ways for this repository:
  - It identifies distributional associations worth measuring; it does **not** validate prohibitions on explicit theme or morally clear choices as quality interventions.
  - The briefs' "strictly linear … no flashback", single location and three-scene single-track shape resemble some reported features, but the repository stories have not been embedded or classified with that pipeline. No location in its feature space has been measured.
  - The regex linter cannot see the dominant signal at all.
  - → Measure discourse-level features against human baselines, including between-project homogeneity across the six stories, as diagnostics rather than targets.
- **Derive the phrase catalog from data.** Antislop profiles model-specific over-represented patterns against human baselines ([Paech et al., ICLR 2026](https://arxiv.org/abs/2510.15061)). → Test corpus-derived, model/form-conditioned patterns as advisory diagnostics. Antislop also uses sequence/regex suppression; frequency ratios do not resolve literal, quoted or deliberately clichéd uses. Contextual adjudication and clean controls remain necessary.
- **Professional edits give a grounded taxonomy.** LAMP: 1,057 LLM paragraphs edited by professional writers, a seven-category taxonomy of idiosyncrasies, and no model family better than another ([Chakrabarty, Laban & Wu, CHI 2025](https://dl.acm.org/doi/full/10.1145/3706598.3713559)). → Use it to calibrate the style critic and test edit-based revision against regeneration.
- **Corpus-relative novelty.** The Creativity Index measures how much of a text can be reconstructed from web text; professional authors score 66.2% higher than LLMs, and alignment lowers the score by 30.1% ([Lu et al., ICLR 2025](https://arxiv.org/abs/2410.04265)). A diagnostic only; optimising it would reward oddity.

### 5.4 Consistency, belief and resources

- **LLM-written stories contain more plot holes, and detection fails on long texts.** LLM story generation raised the plot-hole detection rate by over 100% relative to the human originals, and detection accuracy drops sharply on longer stories ([FlawedFictions, Ahuja, Sclar & Tsvetkov, 2025](https://arxiv.org/abs/2504.11900)). → Supports structured ledgers. Its controlled plot-hole generator is a template for the hidden planted-defect set the audit requests for measuring extractor recall.
- **The knowledge-leak check targets a named, benchmarked failure.** "Point-in-time character hallucination" is benchmarked, and decomposing the reasoning helps ([TimeChara, Ahn et al., ACL Findings 2024](https://aclanthology.org/2024.findings-acl.197/)). → Evaluate `prose_audit` extraction on it.
- **A reference model for truth versus belief.** Sabre plans with character intentions and possibly wrong beliefs, to arbitrary theory-of-mind depth ([Ware & Siler, AIIDE 2021](https://ojs.aaai.org/index.php/AIIDE/article/view/18896)). Adopt only its minimal core: world state separate from per-agent belief state, and typed belief updates through perception, testimony, inference, correction and forgetting where relevant. This addresses N2’s semantic ambiguity. N3 additionally needs explicit negation and typed-value evaluation; separating stores alone does not fix it.
- **Countable props.** Linear logic treats resources as consumed by actions ([Ceptre, Martens, AIIDE 2015](https://ojs.aaai.org/index.php/AIIDE/article/view/12784)). The practical analogue is the film script supervisor's or copyeditor's style sheet: track countable, load-bearing props per scene. → Declare the quantity in the spec whenever a turn depends on it (§2.3).

### 5.5 Reader effect can be partly planned and checked

Structural-affect theory (Brewer & Lichtenstein, 1982, *Journal of Pragmatics* 6) derives suspense (outcome withheld), curiosity (outcome shown first) and surprise (unexpected disclosure) from the *discourse ordering* of fabula events. The repository already separates fabula from discourse, so a scene can declare its intended structure and have the reveal order checked deterministically. The audit's "intended vs observed reader effect" distinction becomes concrete: the structure is checked in code; the affect is measured with prefix-only readers.

### 5.6 Human-evaluation method

- **Rater suitability must be measured for the task.** Even with qualification filters, crowdworkers could not distinguish model-generated stories while English teachers could; human reference texts improved judgments ([Karpinska, Akoury & Iyyer, EMNLP 2021](https://aclanthology.org/2021.emnlp-main.97/)). → Use comprehension/attention checks and relevant expertise for craft judgments. General readers remain valid for target-audience enjoyment. Reference texts can help calibration but may anchor taste; standardize and test their use.
- **Use instruments validated for the intended construct and population.** Options: the six-item Transportation Scale–Short Form ([Appel et al., 2015](https://www.tandfonline.com/doi/abs/10.1080/15213269.2014.987400)), the Psychological Depth Scale (inter-rater α = 0.72; [Harel-Canada et al., EMNLP 2024](https://aclanthology.org/2024.emnlp-main.953/)) and the Narrative Engagement Scale (Busselle & Bilandzic, 2009). Best–worst scaling is a candidate design supported in sentiment-intensity annotation, not a demonstrated fiction-evaluation efficiency guarantee. PDS also reports favorable GPT-4 results against highly rated Reddit stories: the same literature supports useful evaluation and warns against a blanket inferiority conclusion. Preserve overall preference and form-specific questions; transport/engagement scales do not exhaust literary merit.
- **The target population can flip the result.** Under prompting, which is what this repository does, MFA-trained writers strongly disfavoured AI quality (OR 0.13) while lay readers favoured it (OR 1.82) (audit source `audit26-reader-preference`). → Pre-register which population decides.
- **Power depends on the actual sampling design.** About 194 independent binary comparisons is a normal-approximation illustration for a two-sided 5% test of 50% versus a true 60% preference with 80% power, not a sample-size prescription. In a balanced, single-level, exchangeable cluster model, `N_eff = B*m / (1 + (m-1)*rho)` tends to `B/rho`. With B=12 and rho=0.10 that toy model caps at 120; with rho=0.05 about 81 observations per cluster reach 194. Real studies cross raters with stories and include briefs, seeds, genres and repeated pairs; this cap does not generally apply unchanged. Pilot variance components and simulate power for the chosen mixed-effects design, rather than adding raters or briefs by a universal rule. [Card et al.](https://aclanthology.org/2020.emnlp-main.745/).

### 5.7 Engineering practice

- **Crash consistency.** `rename` without `fsync` of both the file and its directory is a classic application crash-consistency bug (Pillai et al., OSDI 2014). Use `fcntl.flock`, which is released when the process dies, and record lock-owner metadata.
- **Compare-and-swap commit.** `git update-ref <ref> <new> <old>` updates a ref only if it still holds `<old>`: an atomic compare-and-swap on the canon head, over content-addressed immutable objects with reachability checking (`git fsck`). That can supply an atomic head update over immutable objects, but `git fsck` checks Git object integrity/connectivity, not whether every accepted scene has valid audits or an authoritative manuscript mapping. Files left in the working tree are not automatically bound to the ref. Domain validation, retention/recovery and the manuscript-as-derived-view design are still required. SQLite, as the audit suggests, is the alternative. Either way, the agent's shell access limits what this proves (the audit's threat-model note).
- **Provenance as a declared layout.** in-toto's layout names each step, who is authorised to perform it, and the expected inputs and outputs (Torres-Arias et al., USENIX Security 2019). It fits the triple audit: inputs are candidate, spec and canon head; the output is a critique; the performer is a role and runner. Signatures matter only once keys sit outside the agent's reach, but the *layout* alone gives the gate a machine-checkable policy.

## 6. Missed at the level of the project's core idea

Sections 2–5 ask whether the checking machinery can be trusted. This section asks whether the implementation carries out the idea it was built for. It compares the code and the six stories with the design brief's scene loop ([`original-design-brief.md:471–523`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/original-design-brief.md)) and its sections on dialogue (brief §2.7), reader cognition (brief §2.9) and editorial passes (brief §2.11). Each item gives the gap with its evidence, a proposal, and how to test the proposal. All proposals are hypotheses until tested.

### A. Search and composition

**6.1 The system searches over prose, not over plans.**
- *Gap.* The brief's loop generates four divergent plans per scene (`generate_divergent_plans(context, count=4)`, line 479). It simulates the characters and the reader on each plan (line 485), and only then writes prose. The implementation holds exactly one spec per scene. All 18 stored specs carry `candidate_strategies`; there is one stored spec per scene and no versioned alternative-plan artifact. Strategy descriptions can vary tactics and disclosure, so the file inventory alone cannot establish that no planning variation occurred ([`record-analysis.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/record-analysis.json), `plan_layer`). ADR 0017 concluded that quality is fixed before the prose, but applied that finding only to the premise.
- *Proposal.* Generate three or four scene plans that differ in turn, tactic, cost and what the reader learns. Hard-audit them, run a plan feasibility/intentionality reviewer (explicitly plan-aware) and reserve the prefix-reader evaluation for realized prose, then write only the best one or two. Plans are short, so search there may be cheaper; prose realization also creates or limits literary value, and a strong plan ranker is not established. For stakes-driven stories, add a "why don't they just…" test: the simulator checks apparent easy solutions against available information, capability, cost and motive. Characters need not act optimally; flag unsupported conflict, not every missed efficient action.
- *Test.* At equal total cost, compare plan-level search plus one realization with one plan plus N realizations, using blind reader preference.

**6.2 Scene-by-scene acceptance is greedy: the pipeline cannot revise backwards.**
- *Gap.* Accepted scenes are frozen, and re-promoting one breaks the canon chain (audit probe `repromotion`). Yet the `avoid-defaults` skill asks the writer to "add or relocate a **setup**" ([`SKILL.md:18`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/.claude/skills/avoid-defaults/SKILL.md)), which usually means editing an earlier, already frozen scene.
- The brief's whole-work check at chapter and act ends (`run_global_audit`, line 519) exists only as `audit_canon`, which checks facts, not literature.
- The promise ledger records `id`, `text` and `owed_by`, with no trigger and no check that the prose pays the promise off.
- LLMs frequently leave "Chekhov's guns" unfired even with the necessary context. Encoding foreshadow–trigger–payoff triples as verifiable conditions addresses this ([CFPG, Yun et al., 2026](https://arxiv.org/abs/2601.07033)). Writers do the same by hand: they find the ending, then go back and plant its setups.
- *Proposal.*
  - Accept scenes provisionally, then run a whole-work literary pass at act or story end that may reopen earlier scenes.
  - Record each scene's *read set* (the facts, predicates and promises it depends on), along with the exact prose/context/policy artifacts supplied to generation and review. This enables conservative invalidation; thematic, voice and reader-expectation dependencies need not appear in a fact read set. Until dependency completeness is demonstrated, recheck downstream chapters and whole-work effects too.
  - Type promises with a trigger condition and a payoff check.
- *Test.* A fixture where a later scene needs a plant in scene 1. The pipeline must produce a new version of scene 1, invalidate all known dependents and conservatively recheck downstream reader/voice effects, keep the history, and leave canon verification clean.

**6.3 There is no systematic, evidence-bound plan-to-prose realization check; literary critiques can address it incompletely.**
- *Gap.* A compiler's basic correctness check, that the output implements the specification, has no counterpart here. The prose-claims schema offers only `character_present`, `focalizer_knows`, `interiority_of`, `located_at`, `closes_promise` and `states_fact` ([`prose-claims.schema.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/schemas/prose-claims.schema.json)). Nothing checks that the required events happen, that the turn lands, or that the exit state is reached. The hard audit checks the spec against canon, not the prose against the spec. Only LLM critics judge realization, and they are shown the intended turn, which is the priming risk the audit identified.
- *Proposal.* Borrow the compiler technique of translation validation. An extractor that has not seen the plan lists the events and state changes that occur in the prose, each with a quoted span. A separate alignment step maps extracted events to canonical IDs; semantic alignment remains fallible. Code can compare validated IDs/typed effects, but cannot prove a free-text emotional turn from string matching. An unmatched element first means `unverified`: distinguish actual omission from extractor/alignment failure before assigning a material finding. An unplanned consequential event is routed to the delta or back to the plan.
- *Test.* Planted cases where the turn exists only in the spec; controls where it is realized obliquely but recognisably.

### B. The reader

**6.4 The reader model was never built.**
- *Gap.* The brief treats reader cognition as central: what the reader knows, suspects, expects and has forgotten (brief §2.9, line 302). The code tracks what *characters* know and never what the *reader* knows. The discourse plan's `revelations` are free text; *Forecourt*'s last one reads "enacted, not explained; the man's nature is never confirmed". Dialogue subtext (brief §2.7) has no representation either.
- *Proposal.* A reader-disclosure ledger in the discourse layer: which facts are disclosed to the reader, in which scene, and how (stated, implied or withheld). It enables structural checks on validated disclosure annotations, not proof of what a reader understood. Candidate checks include:
  - dramatic irony support: annotated reader-accessible evidence precedes character access;
  - fair play: each clue is disclosed before its reveal;
  - retrospective coherence support: a surprise declared to require setup links to an earlier disclosed plant;
  - curiosity gaps that are opened and later closed;
  - the declared suspense, curiosity or surprise structure (§5.5).

  Optionally, key lines of dialogue record what they *say* and what they *do* (ask, evade, misdirect, concede), for a plan-aware editor. Keep that intention out of the experiential reader packet, which tests what the line actually communicates. The measured side is prefix reading: readers, or LLM probes explicitly labelled as predictions, say what they expect and what they want to know.
- *Test.* Fixtures for irony, fair play and an unplanted surprise.

**6.5 The reader contract is not compiled into tests.**
- *Gap.* Contract clauses are free strings and nothing maps them to a check. For example, *Forecourt*'s "the man stays genuinely ambiguous to the end: never confirmed victim or villain" is judged only implicitly.
- *Proposal.* A contract-coverage report that maps each clause to a deterministic check, a critic question, a reader question, or "untested". For the ambiguity clause, ask readers for plausible interpretations, supporting evidence, unresolved facts and confidence. Ambiguity need not produce a 50/50 split across readers; all readers may recognize the same unresolved alternatives, while an even split could reflect confusion.
- *Test.* Coverage reports for the six projects; every load-bearing clause has a check or an explicit `untested` status; coverage declaration alone is not successful verification.

**6.6 The owner's taste is not recorded as data.**
- *Gap.* For an owner-taste mode, the deciding reader may be the project owner, who picks premises and rejects whole batches. No structured record of those choices exists: `projects/*/decisions/` holds only promotion manifests, READMEs and one ending-strategy note. The contracts name "adult literary readers"; the owner's revealed preferences are not captured anywhere the pipeline can use.
- *Proposal.* A preference log recording each choice, the alternatives shown, the stated reason and the date. It serves as a calibration target (does a critic predict the owner's picks better than chance?) and as input to premise generation. Keep it separate from general-reader evaluation, and report both.
- *Test.* Agreement between each critic and the logged choices.

### C. The central claim and how it is evaluated

**6.7 The core thesis is contested and untested.**
- *Gap.* ADR 0016 builds selection on "the LLM is a strong critic but a weak writer". The Generative AI Paradox finds the opposite pattern: models' generation can exceed their understanding of the same kind of output, and the two correlate weakly ([West et al., ICLR 2024](https://arxiv.org/abs/2311.00059)). 100-Endings finds rubric judges ranking AI stories above New Yorker fiction, and §5.1 gives the benchmark ceilings.
- *Test, before any further selection machinery.* Use public human-labeled pairs to assess ranking agreement, with labels hidden from the judge. These pairs generally have no meaningful “writer first sample.” For the three-selector test, freeze candidate pools generated for unseen in-house briefs with their order recorded; compare the critic’s pick, first generated candidate, and random choice from the same pool. Then, on the project's own tasks, compare critic-selected with first-draft scenes by blind human preference. Estimate preference gain, selection regret and cost with uncertainty. An underpowered null is inconclusive; a powered failure to deliver useful benefit supports simplifying selection. The useful claim is local selection benefit, not that judgment is universally a stronger faculty than generation.

**6.8 The system repeats itself across stories.**
- *Gap.* The completed stories share restrained, object/action-centered closures; they do not all withhold their central outcome ([`record-analysis.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/record-analysis.json), `endings`). Four end on a small physical act followed by a return to routine or a departure:
  - *Forecourt*: she pockets the fob, locks the door and recounts the till.
  - *Slack Water*: "She left the cover off."
  - *The Overnight*: she files her card and "started the mixer for the morning bake".
  - *Visiting Order*: "She turned the key."

  *Verbatim* ends on the interpreter drinking water while the verdict is pending. By contrast, *The Overnight* delivers the order and records Nadia’s own recipe; *Slack Water* completes the constrained launching. Similar closing gestures do not imply identical resolution structures. `avoid-defaults` predicts the model's default continuation within the current story only. Nothing compares a new story with the system's own earlier ones.
- *Proposal.* Treat the system's own previous stories as the first default to avoid. Record typed features per story (ending type, turn type, resolution, recurring object motifs, focalization). Report recurring choices and offer alternatives; do not require every new story to differ or optimize detector evasion. Repetition can be intentional, and declared brief similarity is a confound. Report discourse-level homogeneity across projects as a diagnostic (§5.3).
- *Test.* The homogeneity measure across the next set of stories, compared with the current six.

**6.9 Real literature is never used as a control.**
- *Proposal.* Run the linter, the critics and the story format on public-domain masterworks (for example Chekhov in public-domain translation, Joyce's *Dubliners*). This yields:
  - how often the gate would block accepted literature;
  - whether spec and delta can represent such scenes without distortion, and which fields are missing;
  - human baselines for the discourse measures;
  - challenging controls for false positives and representational limits, not error-free or universally preferred gold labels. Public-domain works may be recognizable from model training and mismatched to modern briefs; pair them with unseen, permissioned controls and appropriate contracts.

  Check German/EU public-domain status first ([`original-design-brief.md:717`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/original-design-brief.md)).
- *Test.* A per-scene record of what the gate would have blocked and what the story format could not represent.

**6.10 The planned pilot tests the architecture where it should help least.**
- *Gap.* The five assembled manuscripts are roughly 1,300–1,800 words each; the unfinished sixth project is shorter. These fit in one context window. Short-form tests can expose consistency problems, but do not establish the ledger’s benefit over much longer narratives, and the audit schedules long-form work last (Phase 4).
- *Proposal.* Include one 8–12k-word condition in the first pilot, on fewer briefs. This tests the state/memory hypothesis separately. A short-form null remains informative about short-form costs and benefits; one long-form run is a diagnostic case, not evidence of population-level efficacy.

**6.11 Writer-family diversity is not established by the record.**
- *Gap.* The stored artifacts lack sufficient writer-model/session provenance to establish which families produced the candidates. StoryScope finds recognisable per-model fingerprints and AI stories clustering in one region (§5.3). The implemented roster targets critics (ADR 0020); it does not establish heterogeneous writing runs.
- *Proposal.* Draft candidates with different model families, and test edit-based revision (LAMP) against regeneration. Fine-tuning on public-domain works or the owner's own writing is a later, optional lever; the operating contract forbids imitating a living author.
- *Test.* Diversity between candidates and blind preference, at equal cost.

## 7. Revised priorities and dependencies

Run a measurement track and a trust track in parallel. The list is not a fourteen-step dependency chain, and historical frequency is not the only priority criterion. Keep verified blockers distinct from optional literary experiments.

| Track | Deliverable | Why / prerequisite | Exit evidence |
|---|---|---|---|
| **A1 — immediate trust** | Frozen input bindings, boundary confinement/validation, safe idempotent promotion and a complete verifier | Prevents false success in ordinary and concurrent use; reuse the existing failure probes | Spoof/stale-input/race/retry cases fail safely; exact evidence bindings and legacy/unverified status are inspectable |
| **A2 — observed review coverage** | Versioned project review policy; runtime provenance; issue applicability and resolution records | Three named critics are not a universal requirement. Required capabilities follow the contract | Relevant predecessor findings are resolved, independently rechecked or explicitly adjudicated; unrelated sibling findings are not inherited automatically |
| **B1 — immediate measurement** | Frozen isolated candidate pools, independent human labels, first/random/critic comparison, cost and failure accounting | Does not require shared-canon repairs; excludes unlogged manual intervention | Local selection benefit and uncertainty measured; inadequate power reported as inconclusive |
| **B2 — critic calibration** | Public screening plus hidden local controls; conditional invariance; repeatability and crossed families | No benchmark score, family distinction or three-repeat rule grants authority automatically | Precision, priority, localization, false positives and repair benefit meet predeclared task-specific tolerances |
| **C — contextual style** | Advisory lint with contextual adjudication, optional taste profiles, clause provenance and repertoire diagnostics | Addresses direct false positives; preserve legitimate artistic choices | Literal/quoted/voiced controls survive; readers assess prose gain rather than detector avoidance |
| **D — realization prototype** | Plan-blind extraction, separate alignment and typed comparison; coverage/unknown states | First measure extraction and alignment. Free-text turn/affect remains a literary question | Omitted events caught; oblique realizations pass; omitted extraction yields uncertainty rather than a fabricated failure |
| **E — state semantics** | Coherent knowledge queries/effects; typed values/negation; versioned propositions; explicit memory/belief/current truth; load-bearing resources | Fix known semantics before adding a broad simulator | Changed-code, false-belief, learning-effect, negative-knowledge, acquire/use and quantity cases pass |
| **F — search and revision experiments** | Plan-level branches, edit-versus-regeneration, multi-family writers; provisional accepted snapshots and backward revision | Requires A for canonical mutation; isolated experiments can begin earlier | Equal-budget human comparison; conservative dependency invalidation preserves history and rechecks downstream experience |
| **G — reader and contract coverage** | Annotated disclosure structure, actual reader probes, owner preferences kept separate from audience outcomes | Intended disclosure is not observed comprehension | Coverage with explicit unknowns; fair-play/setup annotations checked; ambiguity measured without forced 50/50 responses |
| **H — scale and governance** | Early bounded long-form diagnostic; powered longer-work study when feasible; evidence-labeled ADRs and regression cases | No fixed architecture claim from short stories alone; no blanket claim that short-form tests are useless | Outcome studies separate model/prompt effects from mechanical invariants; policy changes retain tradeoffs and authorization |

Selection statistics belong in B2: test rubric validation and indifference/uncertainty handling on paired judgments. They must not turn a mathematically correct strict Pareto result into a “bug” solely because a new policy would prefer abstention. Convert reproduced implementation defects into maintained regression tests after repair is authorized; turn policy hypotheses into comparative experiments, not assertions that enshrine taste.

The smallest useful next result is an evidence-bound generation-and-review run plus a modest independent assessment of selection value. Adding more critics, a vector store or a full narrative simulator is not a prerequisite.

## 8. Limits of this review

- The timing and voice evidence in §3 is circumstantial. It shows the record cannot establish reviewer independence; it does not establish who wrote any critique.
- Most new sources were checked at abstract level, some via search summaries. At the initial review, canonical references (CheckList, Card et al., MT-Bench, length-controlled AlpacaEval, Huang et al., Pillai et al., in-toto, ε-dominance, best–worst scaling, Busselle & Bilandzic) were cited from established literature. This recheck revisited selected consequential sources, not all full texts; updated access details are in recheck-source-verification.json. Access depth per source is in [`evidence/review-sources.json`](/Users/kstroevsky/Desktop/dev/fiction-compiler-starter/docs/audits/2026-09-28/evidence/review-sources.json).
- The power figures illustrate the design effect under stated assumptions; they are not a power analysis for this project.
- §6 compares the implementation with the design brief and with craft practice; its proposals are untested hypotheses. The ending pattern in §6.8 is an observation about five stories, not a measured homogeneity statistic.
- The prior reviewer described itself as Claude; the artifacts do not establish the model families that produced all stories or critiques. This recheck uses direct evidence and reproducible analysis, not an assertion of independent human literary judgment.
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
