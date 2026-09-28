# ADR 0022 — Record a review of the 2026-09-27 audit without adopting its proposals

## Request and scope

The user asked for the 2026-09-27 audit (ADR 0021) to be analysed and double-checked against the code, the stored project record and the research literature, and for additions that would significantly improve the project. Reviewed commit: `2b8ef0b`; production source is identical to the audited `310e50c`.

## What changed and why

Added [`docs/audits/2026-09-28/review.md`](../audits/2026-09-28/review.md) with its evidence: eight new isolated probes, a read-only analysis of the stored record, and a source list. Registered 36 references in `kb/source-register.json` (`review28-*`), each with its access depth.

The review confirms the audit's engineering findings (all 24 probes reproduce) and corrects or extends it in four places:

* **The record shows the triple audit was rarely applied as designed.** Full literary coverage in 3 of 17 accepted scenes; 5 accepted scenes fail today's gate; unreviewed dissent on the promoted text's own earlier draft in 7 of 12 gate-era promotions.
* **The latest briefs are pipeline outputs.** They reuse premise-probe wording, so they cannot explain the house style independently of the pipeline.
* **New state and selection defects.** Split knowledge store, removed facts still known, negation that cannot be expressed, noise-driven Pareto selection, labels that equal the filename letter, dialogue linted as narration, stale lock.
* **Under-weighted research** on judge self-inconsistency, correlated errors across vendors, self-preference, discourse-level signatures of AI fiction, and reader-study power.

A second pass the same day, at the user's request, added review §6: gaps measured against the project's core idea in `docs/original-design-brief.md`.

* Search runs over prose rather than over plans.
* Accepted scenes cannot be revised backwards to plant setups.
* Nothing checks that the prose carries out the plan.
* The reader model was never built.
* Reader contracts are not compiled into tests.
* The owner's choices are not recorded as data.
* The "strong critic, weak writer" thesis is untested.
* All five completed stories end the same way: a small physical act with the outcome withheld.
* Public-domain literature is not used as a control.
* The pilot tests only short stories.
* A single model family does all the writing.

Review §7 re-ranks the priorities accordingly. Dated update notes were prepended to the three 2026-09-27 audit documents, pointing to these corrections; their original text is otherwise unchanged.

## Verification

Workspace validation, the unit suite and the regression fixtures were run before and after the change; results are in the review.

## Decision and approval status

Records analysis and proposals only. Production code, tests, schemas, prompts, rubric, roster, skills, stories and constitution are unchanged. The review recommends, among other things, marking ADRs 0016 and 0017 as unvalidated hypotheses. That, and every other proposal, requires human approval under `constitution/change-policy.md`; nothing is adopted here. No commits or external publication were made.
