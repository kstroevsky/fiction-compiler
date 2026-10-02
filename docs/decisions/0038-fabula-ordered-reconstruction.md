# ADR 0038 — Reconstruct nonlinear history in fabula order

Engineering decision record for the remaining nonlinear-state defect in Track E of the September
audit. This change strengthens deterministic historical consistency; it does not establish literary
quality or validate reader response.

## 1. Failure observed

Scene IDs encode discourse/repository order, while story state is caused in fabula order. Before
this change, a later-narrated flashback could be audited against facts, resources, promises, beliefs,
or events that only existed later in story time. The same mismatch also made accepted revisions
unsafe: changing an earlier fabula event could alter the entry state of a scene that appears earlier
in discourse, while the revision invalidation path only followed discourse descendants.

The audit also required canonical event execution to remain distinct from discourse reappearance.
A flashback or recollection that references an already executed event must not execute its world
effects again.

## 2. Evidence and root layer

- `docs/audits/2026-09-27/audit.md` requires event/exposure separation and repeated-flashback
  regression cases.
- `docs/audits/2026-09-28/review.md` Track E calls for fabula-ordered reconstruction after typed
  state, truth/belief separation, resources, and ordered beats.
- ADR 0037 explicitly left fabula-ordered reconstruction as the remaining Track E state gap.

The defect is in the **state/history layer**. It cannot be repaired in prose or by asking a model to
infer what was true during a flashback.

## 3. Decision

Three order concepts stay separate:

- scene ID remains discourse/repository identity and acceptance-chain order;
- `state-delta.time` is canonical fabula time for an accepted scene; and
- `spec.fabula_time` is the planning/revision timestamp used before acceptance.

When every relevant timestamp is comparable, `StoryState` replays accepted deltas in fabula order.
Equal fabula times use discourse scene ID as the deterministic tie-break. Numeric times, naive ISO
datetimes, and timezone-aware ISO datetimes are supported as separate domains; incompatible domains
are never silently coerced.

For a planning or revision target, reconstruction deliberately prefers that target's live
`state-delta.json`/`spec.json` timestamp while all other accepted scenes continue to come from
immutable acceptance snapshots. This prevents the target's old accepted timestamp from masking the
history being proposed by a revision.

`reconstruction_order` and `reconstruction_issues` expose whether fabula replay was possible.
Legacy histories with missing/incomparable scene times fall back deterministically to discourse
order and report the limitation. A target or accepted scene that precedes the seed canon time, or
uses a time domain incomparable with the seed, is reported as unsupported: the current seed model
cannot reconstruct history before its own opening state.

## 4. Canon audit and event exposure

Cross-scene factual, knowledge, promise, and canonical-event checks now replay in fabula order.
Chronology diagnostics still inspect the linear discourse thread so a declared analepsis/prolepsis
is not mistaken for accidental backward narration.

`required_events` continues to mean canonical world-event execution. The same event ID may execute
only once across accepted canon. Later narrative appearances belong in `event_references`; those
references affect discourse evidence but do not apply world effects again.

Within a scene, required events still execute in their declared beat order using ADR 0035's shadow
state. Fabula ordering chooses the scene's historical entry state; beat ordering chooses the
in-scene causal sequence.

## 5. Retroactive acceptance and revision

Accepting a discourse-later scene whose fabula time is earlier can change the entry state of already
accepted scenes. Their immutable acceptance objects are preserved. The acceptance index records
rechecks_required with reason `retroactive_fabula_insertion`; deterministic hard audit reruns
immediately, while literary, reader, voice, and whole-work scopes remain pending for explicit
subjective closure.

Revision uses both order systems:

- the immutable acceptance hash chain is rebased only for discourse descendants, preserving its
  repository/reading-order meaning;
- recheck invalidation additionally follows old/new fabula dependence, including scenes that are
  earlier in discourse but later in story time; and
- a scene is conservatively rechecked when the revised scene entered its historical state before or
  after the change, or when a time move changes that membership/order.

Retries after an authoritative index commit resume pending hard rechecks and repair derived views,
including retroactive fabula insertions.

## 6. Dependency semantics

The conservative acceptance read set now includes unary typed predicates and directional
relationship dimensions. Changed-state references include directional relationship effects as well
as facts, predicates, resources, promises, knowledge, and beliefs. This makes
known_state_dependency meaningful for the newly possible retroactive rechecks.

The read set remains conservative rather than a complete literary dependency graph. Therefore a
false `known_state_dependency` never suppresses the required subjective recheck scopes.

## 7. Regression cases

Tests and fixed fixtures prove that:

- a flashback sees only state established before its fabula time;
- full replay orders multiple accepted scenes by fabula time;
- two separately narrated flashbacks replay in their historical order;
- canon knowledge/promise/event checks use fabula order;
- a nonlinear target before seed time is rejected as a material temporal condition;
- live revision timestamps determine the proposed reconstruction boundary;
- retroactive insertion rechecks later-fabula acceptances without replacing their immutable objects;
- an earlier-discourse/later-fabula scene is rechecked when a later-discourse revision changes its
  historical entry state; and
- interrupted retroactive rechecks resume on idempotent promotion retry.

## 8. Limits

- The seed canon is still a single opening snapshot, not an arbitrarily rewindable prehistory.
- Mixed or missing time domains remain a surfaced legacy fallback instead of guessed chronology.
- Fabula order is scene-granular. Within-scene temporal granularity is the explicit required-event
  beat order, not timestamped prose sentences.
- Deterministic consistency does not prove that a nonlinear presentation is clear, effective, or
  emotionally successful; those remain reader/literary questions.

## 9. Human approval status

Authorized as implementation of the user-requested September audit/plan. The change preserves the
existing immutable acceptance model and adds only the historical ordering and invalidation semantics needed to make nonlinear state defensible.
