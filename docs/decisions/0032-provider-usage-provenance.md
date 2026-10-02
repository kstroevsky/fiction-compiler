# ADR 0032 — Preserve provider usage provenance before matched-cost claims

Engineering decision record for the measurement/provenance work required by the September 27–28
audit and review.

## 1. Failure observed

The selection experiment can record token/cost evidence and explicitly preserves missing values, but
the live role runner discarded provider usage at the HTTP boundary. Anthropic, OpenAI and Gemini
responses were reduced to response text before `run_role` wrote its immutable attempt. A later
matched-cost experiment therefore could not recover critique token counts from repository evidence,
even when the provider had returned them. Transport failures also left no attempt artifact.

## 2. Exact evidence

Before this change each live transport's `complete` method returned only `str`; `run_role` persisted
the packet, raw text and parse result. `selection_eval.record_operation` already accepts optional
`input_tokens`, `output_tokens` and `cost_usd`, and its report counts missing usage separately rather
than treating it as zero. The audit explicitly requires equal-total-cost comparisons and inclusion of
all calls/failures before attributing gains to decomposition, selection or plan search.

## 3. Root-layer diagnosis

This is an **execution provenance** defect. The provider adapter is the last place where native usage
metadata exists. Once it is collapsed to text, later experiment code cannot reconstruct tokens or
request identity without guessing. The selection evaluator should continue to own experiment
accounting; the role runner should preserve observations, not invent prices.

## 4. Minimal change

- `CompletionResult` carries response text plus optional normalized input/output/total token counts,
  provider request id, provider-reported model and finish reason. Legacy/injected transports that
  return plain strings remain valid.
- Anthropic Messages maps `input_tokens` / `output_tokens`; OpenAI Chat Completions maps
  `prompt_tokens` / `completion_tokens` / `total_tokens`; Gemini maps
  `promptTokenCount` / `candidatesTokenCount` / `totalTokenCount`. Counts are accepted only as actual
  non-negative integers. A total is derived only when both components are known.
- `run_role` measures local monotonic wall latency, stores normalized provider metadata in every
  completed attempt, copies it into critique provenance, and emits it to the trace for recorded
  critiques. Malformed critique text retains provider usage in the rejected attempt.
- A `VendorUnavailable` failure now writes an immutable attempt with latency, empty usage and the
  transport error before re-raising. Empty usage means unknown; it is not zero.
- No dollar cost is estimated. `selection_eval` continues to accept explicit observed/configured
  cost when a study has a defensible pricing basis.

## 5. Regression evidence

`tests/test_role_runner.py` covers all three provider payload mappings with mocked HTTP responses,
legacy string compatibility, persistence into attempt and critique provenance, malformed-output usage
retention, transport-failure evidence, and rejection of boolean/string pseudo-token counts. The
existing selection-evaluation test continues to require missing token/cost records to remain missing.

## 6. Before/after interpretation

Before: critique calls could consume measurable provider tokens while the repository retained only
their prose response. After: the repository can account for known critique usage without estimation
and can prove when usage was unavailable. This closes one measurement gap; it does **not** make an
experiment matched-cost by itself because generation, revision and any manual/external calls must be
accounted for too.

## 7. Known limits

- The provider payload parsers are exercised against mocked current response shapes; no live API keys
  were used in this implementation run.
- Provider token accounting may differ semantically across vendors. The normalized fields preserve
  common input/output totals for coarse budget accounting; provider-specific billing interpretation
  must be declared by an experiment rather than guessed here.
- Local latency is wall time around the transport call. It is useful execution evidence, not a pure
  server-compute measurement.
- Full matched-cost evidence still requires the generation and revision paths to record their calls
  into the experiment ledger.

## 8. Approval / rollback

This implements already-authorized audit-plan work and changes provenance only; it does not alter the
constitution or grant any reviewer new authority. Rollback is the commit containing this ADR,
`role_runner.py`, the critique provenance schema, tests, and roadmap update.
