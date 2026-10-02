# ADR 0044 — Add a public-domain literature control

## Status

Accepted and implemented, 2026-09-29.

## Context

Review §6.9 observed that the compiler had never been tested on established literature. Without such a
control, style heuristics can look precise simply because they are evaluated mostly on prose produced
inside the same framework, and the scene/state schemas can appear expressive without being forced to
describe a work that was not written for them.

ADR 0043 first made the required EU/DE rights check executable. This milestone then adds one bounded
control rather than treating a famous work as a universal literary gold standard.

## Control and provenance

The first control is James Joyce's **“Araby”** from *Dubliners*, Project Gutenberg eBook #2814,
original English text. Project Gutenberg identifies Joyce as 1882–1941, lists “Araby” in the 1914
collection, and marks the eBook public domain in the USA. EU Directive 2006/116/EC Article 1 provides
an author's term of life plus 70 years. The title-specific source entry
`joyce-araby-gutenberg-2814` records that basis, verification date, source URL, and legal-basis URL;
no modern translation is used.

The control normalizes Project Gutenberg's CRLF line endings to LF, stores four analyst-defined
segments under `kb/corpus-controls/joyce-araby-1914/`, and records the blank-line reassembly rule. The
manifest binds every normalized text segment and the reassembled control text by SHA-256. The
segmentation is explicitly `editorial-analysis`; it is not attributed to Joyce.

## Decision

`fiction_compiler.literature_control` validates:

- the control manifest against `literature-control.schema.json`;
- title-specific `fiction-corpus` rights clearance and `full_text_policy: allowed`;
- exact UTF-8 scene bytes and concatenated-story hashes;
- one hash-bound `scene` spec and `state-delta` probe per segment against the production schemas; and
- unique, confined control paths and scene identities.

`literature_control_report` then runs the real deterministic defaultness linter on each frozen segment
and returns the schema probe alongside a separate manual representation assessment. A schema-valid
spec/delta proves only that the JSON shapes accept the analyst's encoding. It does not prove that the
typed model captures every literary mechanism.

For “Araby”, the current linter produces 17 findings across the four segments (4, 3, 5, 5). Every
finding is minor and all four scenes receive the linter verdict `pass`; therefore the current gate
would block none of them. The hits include perception filters, `seemed to` / `began to`, and one
repeated-sentence-opener rhythm warning. This is maintained as false-positive/control evidence for why
defaultness remains contextual and advisory at minor severity.

The story-format probes are schema-valid, while the manual annotations identify several effects that
are only free-text or not first-class typed concepts: retrospective narrator versus experiencing self,
iterative/habitual summary, attention/affect progression, narrative-duration shifts, epiphanic
revaluation, and symbolic-image progression. The report labels these as manual annotations and uses
`typed_fit: partial`; it does not claim that the story is unrepresentable.

## Critic evidence boundary

No live model-provider credentials were available for this control run. The manifest therefore fixes
`critic_evidence.status` to `unrun`, and the report is
`deterministic_only_critics_unrun`. It does not infer critic approval from Joyce's reputation, from
the linter pass, or from model familiarity with the text. The schema deliberately permits only `unrun`
until an actual critic-evidence binding is designed and exercised.

## Regression evidence

`tests/test_literature_control.py` checks:

- rights clearance, source/story/segment hashes, non-empty text, and schema-valid format probes;
- the current 4/3/5/5 minor-finding baseline and zero blocking scenes;
- manual representation annotations remain separate from schema validation;
- critic evidence remains explicitly unrun;
- text or format-probe tampering invalidates the control;
- the generic Project Gutenberg corpus entry cannot authorize title-level full-text use; and
- the read-only report is exposed through the MCP registry.

Workspace validation verifies every literature control on every run.

## Consequences

The repository now has one reproducible external literary control and a mechanism for adding more
rights-cleared controls. Review §6.9 is only partially empirical: deterministic lint and schema-fit
evidence now exist, but live critics, human discourse baselines, and unseen permissioned controls remain
unrun. One recognizable Joyce story is not enough to estimate population-level false-positive rates.
