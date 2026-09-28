# ADR 0028 — Freeze candidate pools before measuring selection value

## Context

The 2026-09-28 review §6.7 and revised priority B1 identified an empirical gap that the production
`tournament` cannot answer. The tournament can blind candidates, balance presentation order and
preserve multidimensional critic disagreement, but its candidate set is reconstructed from current
scene artifacts. It did not preserve the generation order needed for a `first` baseline, independent
human pairwise labels, a seeded random baseline on the same pool, or explicit cost/failure missingness.

Without those artifacts, a later claim that critic selection beat first/random can accidentally compare
different pools or use labels observed after selection. Missing token/cost data could also be mistaken
for zero. The audit explicitly requires frozen pools and independent labels before treating the
"strong critic" thesis as an empirical property of this system.

## Decision

Selection-value measurement is a separate evidence workflow under
`<project>/.runs/selection-eval/<scene>/<experiment>/`:

- `freeze_selection_pool` accepts candidate filenames **in generation order**, copies their exact bytes
  to blind `A.md`/`B.md`/... artifacts, records SHA-256 identity and a pool fingerprint, and creates
  both left/right orientations of every unordered pair. Later edits to scene candidates do not alter
  the experiment.
- `selection_reader_packet` exposes only blind prose and the scheduled pair orders. It withholds true
  filenames, generation order and the reveal map.
- `record_selector_choice` binds a named selector (for example `critic`) to one frozen candidate and
  refuses new selector choices after reader preferences exist. `first` and seeded `random` are
  compiler-owned baselines derived from that same frozen pool.
- `record_pairwise_preference` preserves tie and abstention, the actual scheduled left/right order,
  rater identity, declared human/model origin, and reader cohort. Target/expert human judgments form
  the independent audience result; owner choices and model probes remain visible but separate.
- `record_selection_operation` stores generation/critique/selection/reader/revision success or failure
  plus provider/model and token/cost fields when known. Missing usage is reported as missing, never as
  zero.
- `selection_experiment_report` computes per-candidate observed wins/losses/ties and preference score,
  verifies counterbalanced pair coverage, and compares first/random/recorded selector choices. It
  reports empirical regret only after every pair has non-abstaining human audience evidence in both
  orientations.

The report is intentionally descriptive. It does not fit a Bradley–Terry or mixed-effects model, run a
significance test, infer a population winner, or turn an underpowered null into evidence of equivalence.
Those analyses belong to the actual predeclared pilot once enough independent briefs/runs/raters exist.

## Verification

Regression tests cover preserved generation order, post-freeze source edits, reader-packet blinding,
frozen-byte tamper detection, complete and incomplete pair/order coverage, first/random/critic
comparison, owner/model separation, prevention of post-outcome selector choices, token/cost missingness,
failure accounting, and MCP tool registration. Repository schema validation loads all four evidence
schemas.

## Consequences

The repository can now run the audit's B1 comparison without silently changing the candidate pool or
mixing owner/model labels into target-reader evidence. It still has **no result about literary quality**:
no new human study was performed by this change. The next evidence step is to populate these artifacts
on frozen unseen briefs, including the audit's matched-cost arms and multi-family/long-form conditions,
then analyze the crossed brief/run/rater design with appropriate uncertainty.
