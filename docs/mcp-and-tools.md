# Tools for the Author (MCP)

## Philosophy: the LLM writes; the tools equip it
You cannot write fiction deterministically, and this system does not try to. The deterministic
layer is **tooling for the author** (the LLM), not a replacement for it:

- **Knowledge** the model reaches for — `kb_search` / `kb_get` over the craft knowledge base.
- **Ground truth** it must respect — `state_before` (who knows what, right now) and `compile_context`.
- **Guardrails** that catch what taste shouldn't have to — `hard_audit`, `defaultness_lint`.
- **A fitness signal** that keeps revision honest — `evaluate_revision`.

The creative acts — premise, structure, character intention, the actual prose, the earned
surprise — stay with the model. The tools remove the failure modes that have nothing to do with
talent (continuity slips, forgotten promises, default phrasing) so the model can spend its
judgment where judgment matters.

## The MCP server
`scripts/fiction_mcp.py` is a **dependency-free** MCP stdio server (newline-delimited JSON-RPC).
It runs anywhere `python3` runs — no install step.

### Tools exposed
| Tool | Purpose |
|---|---|
| `kb_search` | Find relevant craft concept cards by keyword/layer |
| `kb_get` | Full text of one concept card |
| `kb_sources` | Registered sources (craft-instruction / fiction-corpus / reference) with copyright notes |
| `state_before` | Event-sourced story state before a scene (facts, per-character knowledge, promises, time) |
| `compile_context` | The minimal, leak-free drafting bundle for a scene |
| `hard_audit` | Deterministic Audit 1 (knowledge cutoff, causal refs, POV, chronology, promise ledger) |
| `defaultness_lint` | Model-default tics in prose, with evidence |
| `evaluate_revision` | Accept/stop decision for a revision (stateless; takes iteration/attempts to reach every branch) |
| `record_revision` | Runs one revision iteration, derives iteration/attempts from the scene's `revision-log`, and **persists** it — the history-driven, ESCALATE/STOP-capable path |
| `promote` | **State-changing, gated by `confirm`** — copies a reviewed candidate into the manuscript and folds its delta into canon |

Both write-path gaps are closed: an agent driving purely over MCP can now persist revision history
(`record_revision`), reach the full stop-condition logic, and promote (`promote`, confirm-gated).

### Register with Claude Code
`.mcp.json` at the repo root is auto-detected:
```json
{ "mcpServers": { "fiction-compiler": { "command": "python3", "args": ["scripts/fiction_mcp.py"] } } }
```
Or: `claude mcp add fiction-compiler -- python3 scripts/fiction_mcp.py`. Verify with `/mcp`.

### Register with Codex
Already wired in `.codex/config.toml`:
```toml
[mcp_servers.fiction-compiler]
command = "python3"
args = ["scripts/fiction_mcp.py"]
```

### Sanity check by hand
```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
 '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"kb_search","arguments":{"query":"scene turn"}}}' \
 | python3 scripts/fiction_mcp.py
```

## The same tools without MCP
Every tool is a plain function in `fiction_compiler.tools` and a CLI under `scripts/`, so agents
that don't speak MCP (or humans) get the identical behavior. MCP is the ergonomic path, not the
only one.
