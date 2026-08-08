# ADR 0020 — External multi-vendor role runner (decentralization by heterogeneity)

Engineering decision record for repo-global changes, following the eight fields required by
`constitution/change-policy.md`. User-directed: after confirming the whole pipeline runs through the
deterministic MCP server, the user asked whether we can run *several LLMs with a flexible
configuration architecture — different LLMs for different roles*, and chose the **external
multi-vendor runner** over an in-family model-roster or a docs-only design.

## 1. Failure observed
The gate's cognition is a **monoculture**. The five judge subagents
(`adversarial-reader`, `character-simulator`, `style-editor`, `continuity-auditor`,
`narrative-architect`) carry no `model:` in their frontmatter, so they all silently inherit the
orchestrator's model. One model wearing five hats is exactly the "too influential single LLM"
shape the project keeps guarding against ([[story-premise-taste]] aside; see the decentralization
constraint in ADR 0016/0017) — just spread across roles instead of concentrated in one stage. There
was no way to have genuinely different model *families* judge in parallel, and no legible place to
assign who judges what.

## 2. Exact evidence
- `grep -rEi 'anthropic|openai|httpx|requests|litellm' src/` → no matches: the MCP server makes zero
  LLM calls. It is a deterministic support layer that speaks in artifacts.
- `.claude/agents/*.md` frontmatter has `tools:` but no `model:` — every judge runs on the parent
  model.
- `judge_bundle` (ADR 0019) already emits a blind, fenced, strategy-stripped single-candidate packet,
  and `record_critique` (ADR 0018) already refuses a verdict/severity contradiction and stamps the
  sha from bytes. Those two tools were already a **vendor-neutral seam** — bundle in, critique out —
  but nothing consumed it across vendors.

## 3. Root-layer diagnosis
Not the story loop and not the server: this is the **model-assignment / orchestration policy** layer
sitting *on top of* the deterministic seam. The server must stay deterministic (calling vendor APIs
from inside a tool handler would re-centralize cognition into the server and add secrets/network to
the trusted core), so the multi-vendor capability belongs in an **external client**.

## 4. Minimal proposed change
- **`src/fiction_compiler/role_runner.py`** — an external client of the seam. `load_roster` reads a
  human-editable `role -> vendor + model` map; `resolve_persona` reuses `.claude/agents/<role>.md` as
  the vendor-neutral system prompt (one definition of a role, whether it runs as a Claude Code
  subagent or via a third-party vendor); `build_messages` composes the trusted persona + a pinned
  critique-output contract as `system`, and the blind `judge_bundle` (fenced as DATA) as `user`.
  Transports turn `(system, user, model)` into raw text: a deterministic `OfflineTransport` for
  tests/dry-runs, and dependency-free stdlib-`urllib` HTTP adapters for `anthropic` / `openai` /
  `gemini`, lazily selected and API-key-gated. `parse_vendor_critique` strictly parses the UNTRUSTED
  reply; `run_role` routes one role and (optionally) writes back via `record_critique`, logging
  vendor+model provenance to the scene trace; `run_panel` runs several roles and **reports their
  (dis)agreement without averaging it**.
- **`config/model-roster.json`** (+ `schemas/role-roster.schema.json`) — the versioned, human-owned
  policy file. The default assigns three vendors across four roles to make the decentralization
  concrete. The runner never edits it.
- **`scripts/run_role.py`** — the LIVE CLI (real vendor calls; `--role` or `--panel`; `--record`).
- **`role_prompt` MCP tool** — a DETERMINISTIC (no-LLM) preview of the exact messages the external
  runner would send, so the seam is inspectable from inside the server without the server ever
  calling a model.

## 5. New regression case
`regression/fixtures.json` gains four `vendor_output` fixtures pinning the untrusted-output boundary:
a clean pass parses consistent; a `pass` carrying a `material` finding is flagged inconsistent (and so
refused at `record_critique`); a ```json-fenced `revise` is unwrapped and parsed; non-JSON prose is
rejected. New unit suite `tests/test_role_runner.py` (24 tests): strict parsing, roster load/validate,
persona resolution + frontmatter strip, message blindness (the A/B strategy value and the
`candidate_strategies` key never reach the payload), record-back writes a sha-bound critique + trace,
an inconsistent vendor `pass` is refused, a finding whose `evidence` legitimately quotes an
injection-looking line is NOT scanned away, malformed output raises, panel disagreement is reported
not averaged, per-role vendor failure is captured not fatal, and the API-key gate raises before any
network I/O.

## 6. Before/after outputs (evaluated for the invariant, not for taste)
- Before: one model judged every role; no way to assign or run heterogeneous vendors; the
  vendor-neutral seam had no consumer.
- After: `role_prompt` (deterministic) previews the blind packet for any role; `scripts/run_role.py`
  routes a role/panel to `anthropic|openai|gemini` per the roster and records findings through the
  same gate; a vendor cannot smuggle a `pass` or an instruction past `record_critique`. The MCP
  server still makes **zero** LLM calls. Framework regression 24→28; suite 169→193;
  `validate_workspace` passes.

## 7. Known trade-offs
- **The live vendor HTTP paths are unexercised in this environment** (no keys, sandboxed network).
  They are dependency-free and key-gated, and the whole runner is tested through the offline
  transport; the request/response shapes should be confirmed against each vendor's current API before
  first production use, and the openai/gemini model ids in the roster are examples to edit.
- Cross-vendor judging is **outside Claude Code's subagent dispatch** (which is Claude-family only) —
  it is a separate process, by design, to keep the server deterministic.
- Vendor output is deliberately **not** injection-scanned: a `evidence` field legitimately quotes the
  untrusted prose, so scanning would false-positive on the judge's own citations. The defense is
  strict JSON + schema + consistency refusal + never executing the reply.
- The roster gets **top-level** schema validation plus explicit per-entry checks in `load_roster`,
  because the project's dependency-free validator supports `additionalProperties: false` but not
  `additionalProperties: {schema}`, and role keys are open-ended.
- The `role_prompt` tool requires an MCP server restart to appear on the wire (long-lived process);
  the library, CLI, and regression paths work immediately.

## 8. Human approval status
Authorized as a user-directed change: the user chose "External multi-vendor runner" from the offered
scope options. The constitution (`AGENTS.md`) is unchanged — the runner is additive tooling and calls
no living-author imitation; provenance (vendor+model) is recorded per critique. Revert path: git
history of `role_runner.py`, `config/model-roster.json`, `schemas/role-roster.schema.json`,
`scripts/run_role.py`, `tests/test_role_runner.py`, and the `role_prompt` / `vendor_output` additions
to `tools.py`, `regression.py`, and `regression/fixtures.json`.
