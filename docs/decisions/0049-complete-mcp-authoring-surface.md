# ADR 0049 — Complete the MCP authoring surface

**Status:** accepted
**Date:** 2026-09-29

## Problem

The MCP server exposed the compiler well after authoring artifacts already existed: context,
plan search, audits, critique evidence, revision, promotion, experiments, and assembly were callable,
but project bootstrap, premise diagnostics, character/canon setup, scene specifications, state deltas,
and prose-branch persistence still required direct filesystem edits or CLI calls. A Codex agent could
therefore use the compiler through MCP only after dropping out of MCP for several foundational steps.

The configured MCP command also used the host's bare `python3`. On macOS this repository can encounter
the system Python 3.9 even though `pyproject.toml` requires Python >=3.11, causing the server to fail
before `initialize`.

## Decision

Expose the missing authoring operations as domain-specific MCP tools rather than a generic file-write
primitive. The tool layer now supports project creation/overview, premise probes, declared project and
planning artifacts, seed-canon ledgers, character sheets, scene specs, state deltas, candidate prose,
and workspace validation. Existing compiler tools continue the workflow through plan search, context,
audits, critique/revision, promotion, reader evidence, experiments, and assembly.

Every authoring mutation keeps the repository's existing boundaries:

- schema-backed artifacts are validated before write;
- project and `project_id` identities must match their directory;
- `canon/index.json` authoring can change descriptive world fields but not acceptance fields;
- seed canon is writable only before the first accepted scene;
- accepted scene specs and state deltas cannot be edited through the authoring tools;
- candidate prose is append-only by filename, so revisions and rejected branches remain available;
- no generic path or arbitrary-file write tool is exposed.

The MCP configuration starts through `scripts/fiction_mcp_launcher.py`, which is compatible with the
older macOS system Python and replaces itself with a discovered Python >=3.11 runtime. An explicit
`FICTION_COMPILER_PYTHON` override remains available.

## Evidence

`tests/test_authoring.py` exercises the mutation invariants directly. `tests/test_mcp.py` performs a
wire-level project → character → scene spec → state delta → candidate → context round trip. The tool
registry test asserts that every public handler defined in `fiction_compiler.tools` is represented in
the MCP registry, preventing future Python-only capabilities from silently disappearing at the wire.

## Consequences

An MCP-capable author can now traverse the complete repository-owned fiction lifecycle without using
ad hoc filesystem writes. Creative decisions and prose generation remain model/human work; MCP owns
persistence, retrieval, validation, evidence, and deterministic mechanics. Human gates and existing
confirmation requirements remain unchanged.
