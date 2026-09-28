# Recheck of the final audit revision

Target: `158eed65db5a194c5ad24a0ca99ca8099b93d5e7` (Docs: Update audit). Completed 28 September 2026. The working-tree review is revised in place; this note records why. No production behavior, fiction text, constitution, prompt or review policy has been changed.

**The stored-record analysis is the strongest addition to the earlier audit. Its headline counts survive stricter byte-binding checks. The main improvements in this pass concern what those counts prove, a misread research table, and proposed rules that would otherwise recreate the system’s current false-certainty problem.**

## Retained and strengthened

- All 24 original probe observations and all eight extra observations reproduce identically against unchanged production code. The original record-analysis output also reproduced before editing the analyzer.
- Five of 17 indexed acceptances fail the current gate. Nine of 12 manifests with binding critiques have exactly one hash-bound literary role. Three scenes have bound records from the three named literary roles. These are counts of retained artifacts, not proof of independent review.
- Seven of those 12 have non-pass criticism on a filename-inferred predecessor without a same-role bound record on the promoted candidate. This supports better lineage and issue-resolution records.
- Two briefs explicitly refer to premise probes, demonstrating framework influence. Clause authorship and its causal contribution to stylistic similarity remain unmeasured.
- The split `knows` store, lexical timestamp comparison and stale lock after abrupt exit are real implementation problems. Proposals for plan alternatives, backward revision, contract coverage and reader-disclosure annotations are useful avenues for testing.

## Corrected or qualified

| Claim in the previous revision | Rechecked conclusion |
|---|---|
| Tian Table 6: 23% versus 68% is character diversity | Incorrect. The published PDF and arXiv v2 both place these in **Overall**. Character is 23% versus 50%. All five columns are now transcribed correctly in review §2.4 |
| Missing same-role review means dissent was ignored or the final defect persisted | Not established. Slack Water’s final scene-2 revision explicitly includes the water test missing from the earlier draft. Missing resolution evidence is still a process problem |
| All historical writers and critics shared a model family/session | Not established by missing provenance. The default roster and app configuration cannot recover past model identities |
| Every stored tournament maps both filenames to matching letters | Two of three do. In the phantom-candidate run, candidate-b maps to C |
| Eight added probes are eight independent new defects | Some overlap prior findings; strict Pareto math is correct but lacks an uncertainty policy; removed facts raise temporal belief/memory semantics, not automatic memory erasure |
| Every completed story withholds its central outcome | Overstated. The Overnight delivers the bread and establishes Nadia’s authorship; Slack Water completes the constrained launch. Shared restrained closing gestures are a narrower observation |
| All unobserved race/traversal failures never occurred | An incomplete record cannot establish that negative claim |
| Data-derived phrase suppression removes literal-language false positives | Unsupported. Corpus frequency and full-sequence matching do not distinguish deliberate, quoted or literal uses |
| A model being different-family or passing alt-test justifies gate power | Neither establishes task-specific precision, failure costs, or review authority. Calibrate locally and preserve abstention |
| An unmatched extracted event proves a missing turn | Extraction/alignment may have missed it. Mark unverified first; typed comparisons cannot establish literary effects from free-text fields |
| Reader-disclosure records prove reader knowledge; ambiguity requires split binary answers | Annotations express available evidence, not actual comprehension. Ask about interpretations, evidence and uncertainty; neither disagreement nor 50/50 voting is necessary for ambiguity |
| Typed read sets identify exactly all downstream dependencies | Literary and reader-expectation dependencies extend beyond facts. Record exact context inputs and conservatively recheck downstream effects |
| Git ref CAS plus fsck solves all acceptance verification | Useful primitives, but neither supplies the domain policy, working-tree binding, retention or recovery design |
| The statistical sample-size cap applies generally | It follows only under the stated balanced single-level cluster approximation; crossed raters/stories/runs require their own power model |

## Evidence-code improvements

`record_analysis.py` now enumerates accepted scenes from canon indexes rather than treating every promotion manifest as accepted. It preserves every critique record, checks SHA-256 bindings, reports candidate/manuscript equality and flags filename-only unbound records. It labels predecessor inference and absence-of-evidence limits explicitly. One legacy Salt in the Wire literary record names the promoted candidate without binding its bytes; it is no longer counted as a bound review.

The analyzer’s current headline counts remain unchanged. All 17 candidate/manuscript pairs match. `recheck.py` verifies that an invalid digest removes a role from bound coverage and that multiple records from one role are not silently overwritten. It also repeats the small Pareto-margin example within the documented 0–5 scale; the original N5 probe used 7/6.9. These checks operate only on temporary copies and audit evidence.

## Improved implementation logic

The current review’s §7 replaces the serial fourteen-item list with parallel trust and measurement tracks. It preserves the substantive proposals while making their evidence requirements explicit:

- Mechanical failures need deterministic regression cases and reliable artifact identity.
- Literary findings need applicability, disposition and calibrated evaluation; an old critic cannot acquire a permanent veto merely by saying “revise.”
- First/random/critic selection must use the same ordered, frozen candidate pool. Public preference pairs are useful for ranking calibration but do not identify a first generated sample.
- Plan-aware feasibility review and prefix-only reader evaluation are different tasks and should receive different packets.
- Early long-form work can be a bounded diagnostic; neither one long story nor an underpowered short-story null settles the architecture’s value.
- Diversity, corpus-relative rarity and detector features remain diagnostics. No mandatory “be different from every previous story” rule was adopted.

## Verification and limits

The recorded source rechecks include visual inspection of the published Tian Table 6 (PDF page 8, printed page 17666), with URL, PDF digest and table values preserved in `evidence/recheck-source-verification.json`. No full copyrighted paper was added to the repository. Targeted primary-source checks were made for the consequential extrapolations; this is not a fresh full-text review of all 36 newly registered references.

The baseline validator, unit suite, regression fixtures and critic-corpus command are rerun after these changes; command outputs are retained as `evidence/recheck-validation-*.txt`. No live model call or human-reader study was performed. Passing the maintained suite confirms no tested behavior regressed; it does not establish that the proposed literary interventions work.

The source register preserves prior access descriptions and adds explicit recheck metadata for revisited references. Only the Git fsck documentation is newly registered. Historical ADR 0022 is annotated rather than silently rewritten as if its prior claims had never existed; ADR 0023 records this pass.
