# Proposed validation program and bounded improvement transactions

This is a proposal. No new prompt, rubric, schema or process rule has been adopted. No paid model runs or reader recruitment were performed. The purpose is to turn the audit into falsifiable decisions while preserving the user's objective of strong LLM-generated prose.

## Separate the claims

Evaluate four claims independently:

1. **Trust:** accepted artifacts are exactly those reviewed under the declared policy.
2. **Consistency:** narrative facts, beliefs, timing and consequences hold under a declared narrative model.
3. **Literary quality:** specified readers prefer the outputs or experience the intended effects.
4. **Practical value:** those gains justify inference cost, latency, annotation effort and human intervention.

A green unit suite speaks to the first two only where it covers them. A human preference result does not excuse corrupted canon. A lack of statistically significant difference is not evidence of equivalence.

Keep autonomous generation and assisted authorship as separate experimental conditions. Record any human selection, editing or high-level steering. The current hand-operated examples cannot establish fully autonomous end-to-end performance.

## Phase 1: small exploratory baseline

Prepare twelve new briefs: two each in restrained realism, comedy/satire, romance or emotionally direct fiction, suspense/mystery, speculative/exuberant fiction, and a formally different mode such as epistolary or observational narrative. These are test strata, not a complete taxonomy of literature or cultures. Use the same language initially; assess other languages separately with competent readers.

For each brief, define length, audience, narrative access, a few load-bearing constraints and what success means. Do not dictate a preferred plot solution or ban every conspicuous feature of model writing. Freeze briefs before generation and reserve separate briefs for tuning and final confirmation.

Compare four arms, three independent runs per brief: **144 outputs in an exploratory pilot**, if resources permit. This count is a planning example, not a power calculation or a claim that three runs establish reliability.

| Arm | Procedure | Question |
|---|---|---|
| A | Strong base model, careful brief, one whole-story draft | What does the model do without this harness? |
| B | Plain outline, draft, one targeted revision, with deterministic basic checks | Does a simple writing loop already capture most benefit? |
| C | Independent best-of-N drafts and a frozen selection method, at a matched total budget to D | Is any gain just extra sampling and selection? |
| D | Fiction Compiler workflow with trust repairs, documented settings and complete traces | Does the particular decomposition/state/craft machinery add value? |

Use the same underlying model where isolating harness effects. A is a useful lower-cost baseline, not an equal-cost competitor by itself. Match C and D on **total** generation, critique and revision expenditure, with the same final length range; report actual costs and failures. Also evaluate the best affordable stronger-model baseline before attributing value to orchestration. Freeze stopping rules. Include all runs, not only accepted survivors.

Candidate selectors used in production must not be the sole final evaluators. Readers receive plain anonymized texts, no pipeline labels, intended-turn notes, intermediate critiques or model attribution. Randomize order; counterbalance repeated comparisons without showing the same rater every version of a brief. Human-written controls should be newly commissioned or otherwise appropriately permissioned and task-matched; selection from famous edited fiction creates a different comparison and possible recognition bias.

Ask separately about overall preference, distinctive voice, character credibility, emotional force, engagement, global coherence and success under the stated form. Add concise evidence and “no preference / unable to judge.” Do not require every work to score highly on suspense or plot change. Let target readers judge enjoyment; let relevant experts judge craft. Report both populations separately.

Analyze story/brief/run and rater dependence. A Bradley–Terry-style preference model with appropriate tie handling or a mixed-effects model is an option, not a compulsory universal analysis. Confidence intervals should respect the clustered design; hundreds of ratings on a handful of stories are not hundreds of independent stories. Predeclare the primary endpoint and report secondary dimensions and multiplicity honestly.

**Decision:** if D has no useful held-out improvement over B/C at acceptable cost, simplify or change the hypothesis. Do not respond automatically by adding more agents.

## Phase 2: calibrate critics before giving them more power

Build a separate small diagnostic set with controlled corruptions and matched clean controls. Have qualified humans establish defect identity and severity; preserve disputed labels. Keep the final set hidden from critic prompt tuning.

| Test family | Defect case | Clean/control contrast |
|---|---|---|
| Knowledge | Character uses a secret before observing it | Character infers it from a visible clue; inference is labeled appropriately |
| Belief | Narrator treats a false belief as confirmed world truth under a reliable contract | Unreliable narrator or mistaken character allowed by the contract |
| Time/order | Use occurs before acquisition | Acquisition and use occur in successive beats in one scene |
| Quantity | Twelve baked, twelve delivered, one inexplicably left | Thirteen baked, or an explicitly retained/returned loaf |
| Narration | Undeclared access to another mind | Declared variable/omniscient narration or quoted speculation |
| Style | Unmotivated stock imagery | Parody, deliberate cliché, repetition, plain literal language |
| Emotion | Redundant explanation after an already clear beat | Necessary direct admission or precise narratorial interpretation |
| Global structure | Payoff without setup or omitted consequence | Deliberately open ending with a coherent contract |
| Feedback relevance | Major contradiction plus a minor stylistic tic | Critic must prioritize the contradiction rather than report only the tic |
| Evidence | Invented or mismatched quotation | Valid local span; for absence, a defined search scope and paired anchors |

Measure:

* Precision and recall **per defect family**, not only aggregate keyword hits.
* Evidence validity and location accuracy.
* Priority of the most consequential defect.
* False-positive rate on permitted forms and deliberate rule-breaking.
* Pairwise preference agreement with independent humans.
* Selective accuracy when the critic can abstain; calibration of confidence if confidence is retained.
* Actual benefit when following the suggested repair, including losses of valuable qualities.

Reverse presentation order, relabel candidates and insert harmless formatting changes. Test family/self-preference with crossed writer/judge assignments. Distinguish shared-context contamination from correlated training or aesthetic taste: different vendors are not guaranteed independent.

The current two LLM eval cases cannot estimate specificity because neither is a clean control. Do not reuse their labels as objective laws that spoken theme or named emotion always fails.

## Phase 3: isolate the literary mechanism

After the baseline, run one or a few predeclared ablations at a time. Do not change planning, prompts, temperature, critic and cost simultaneously and attribute the outcome to one component.

| Hypothesis | Comparison | Failure signal |
|---|---|---|
| Craft retrieval helps | Same generator/context with and without targeted cards | More compliant prose but no human preference gain; same motifs/cadence across briefs |
| Positive objectives improve prose | Defect-only criticism versus criticism plus evidence-backed strengths and protected effects | Strength descriptions become praise boilerplate or preservation blocks necessary change |
| Role packets help | Current common packet versus purpose-specific packets | Continuity remains inaccurate; reader simply mirrors planned affect |
| Recent prose preserves voice | State-only versus state plus bounded recent prose and motif anchors | Copying/repetition increases; no improvement at scene boundaries |
| Independent branches preserve diversity | Shared editorial draft versus isolated drafting/targeted peer feedback | Differences are cosmetic; cost exceeds simpler best-of-N |
| Exploration improves planning | Strict outline-first versus exploratory prose with proposed upstream revisions | Canon drift or no quality gain under matched budgets |
| Conditional lint reduces flattening | Blocking regex versus advisory findings with explicit resolution | Real contract violations increase beyond an agreed tolerance |
| Richer state earns its cost | Simple state versus typed beliefs/ordered observations on stories that need them | Added structure does not reduce measured errors or harms prose |
| Larger candidate pools help | N=2, 4 and 8 under tracked cost and a fixed selector | Selector increasingly favors artifacts of its rubric; human-selected best diverges from machine choice |

Freeze the baseline and retain every branch, failed attempt, critique and decision. Use separate held-out briefs after choosing a change. Re-scoring old outputs is suitable for testing a grader; it does not establish the effect of a changed generation prompt.

## Phase 4: test longer works and “human-level” claims

Only after short-form signals are credible, test 8–12K-word works and then novella-length outputs. Extend tests for chapter transitions, reintroduced characters, unresolved promises, motif development, pacing and long-range consequences. Check the middle of the narrative as well as its beginning and ending. Compare targeted-state retrieval with bounded raw-text evidence rather than assuming a larger context window solves memory.

Define “human-level” against a named comparator population: ordinary adults, practiced amateurs, working genre writers or professionally edited publication. Define whether the task is whole-story invention, continuation or prose rendering from a fixed plan. Specify the amount of human assistance and revision time in each arm.

For a non-inferiority claim, preregister a meaningful margin and power the study from pilot variability, including clustering and rater disagreement. Require adequate absolute quality and relevant dimension-specific guardrails. Failure to reject a difference is not proof of non-inferiority. Report results by genre/form, length, model and reader cohort; do not inflate success on five-sentence or short-story tasks into general novel-writing capability.

## Bounded improvement proposals under the repository change policy

These transactions are **proposed only**. Engineering failures have before-state reproductions. No after-state implementation or blind prose experiment exists yet; those fields are intentionally pending rather than invented.

| Proposal | Observed failure and evidence | Minimal change | Regression / comparison | Tradeoff | Approval status |
|---|---|---|---|---|---|
| T1: exact acceptance transaction | Spoof, interleaving, stale vendor binding and manuscript mutation probes | Frozen artifacts, runtime-owned checks, one canonical commit, full verification | Same probes plus stale input, crash/retry and public CLI/MCP tests | More explicit artifact lifecycle | Not adopted; implementation not performed |
| T2: conditional style lint | Literal tank sentence becomes material told emotion | Advisory finding with contextual resolution; project-only literal bans | Literal/parody/directness controls and blind prose comparisons | Some bad prose may proceed to literary review | Requires review before changing rubric/policy |
| T3: scoped taste profiles | ADR 0017 derives global premise preferences from one pair; schema restricts resolutions | Move those preferences into an optional realism profile; broaden legal structures | Held-out detective/comic/romantic/static briefs; compare coherence and preference | Less rigid generation control | Requires review before adoption |
| T4: role-specific evidence | Shared judge packet omits canon/profile/prior text and includes intended turn | Separate verification, stylistic and prefix-reader packets | Same candidate under both packet designs, against hidden human labels | More packet management and context cost | Requires review before changing workflow |
| T5: positive objectives and discovery | Defect-only records; prose has no explicit upstream-proposal path | Preserve evidence-backed strengths; permit branch-level spec/delta proposals | Blind before/after scene and whole-story comparison | Additional branching and judgment | Requires review before adopting creative process change |

Route each defect to its responsible layer; do not use a line edit to hide a causal problem. Equally, do not rewrite a premise solely because a critic dislikes a sentence. When implemented, each proposal needs its own recorded before/after evidence, regression coverage, accepted tradeoffs and authorized decision.
