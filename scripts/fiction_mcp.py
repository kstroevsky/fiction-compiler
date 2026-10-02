#!/usr/bin/env python3
"""Dependency-free MCP server exposing the fiction-compiler tools to an LLM agent.

Speaks the Model Context Protocol over stdio (newline-delimited JSON-RPC 2.0) with no
third-party dependencies, so it runs anywhere `python3` does. Register it with Claude Code
(`.mcp.json`) or Codex and the writing agent can call the knowledge base, the event-sourced
state, the hard audit, the defaultness linter, and the revision evaluator directly — the tools
support the author; they do not write for it.

Protocol: handles `initialize`, `notifications/initialized`, `tools/list`, `tools/call`, `ping`.
Logs go to stderr only; stdout carries protocol messages exclusively.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiction_compiler import tools  # noqa: E402

SERVER_INFO = {"name": "fiction-compiler", "version": "0.1.0"}
DEFAULT_PROTOCOL = "2025-06-18"


def log(*args: object) -> None:
    print(*args, file=sys.stderr, flush=True)


def _result(mid: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle(message: object) -> dict | None:
    if not isinstance(message, dict):
        return _error(None, -32600, "invalid request: JSON-RPC message must be an object")
    method = message.get("method")
    mid = message.get("id")
    is_request = "id" in message

    if method == "initialize":
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _error(mid, -32602, "invalid initialize params")
        return _result(mid, {
            "protocolVersion": DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": tools.list_tools()})
    if method == "tools/call":
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _error(mid, -32602, "invalid tools/call params")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(mid, -32602, "tools/call requires string name and object arguments")
        try:
            output = tools.call_tool(name, arguments)
            is_error = isinstance(output, dict) and set(output) == {"error"}
            return _result(mid, {
                "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}],
                "isError": bool(is_error),
            })
        except Exception as exc:  # noqa: BLE001 — surface tool failures to the client, don't crash
            return _result(mid, {"content": [{"type": "text", "text": f"tool error: {exc}"}], "isError": True})

    if is_request:
        return _error(mid, -32601, f"method not found: {method}")
    return None


def _emit(response: dict) -> None:
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    log(f"fiction-compiler MCP server ready ({len(tools.TOOLS)} tools, stdio)")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            log(f"parse error: {exc}")
            continue
        if isinstance(message, list):  # legacy batch
            if not message:
                _emit(_error(None, -32600, "invalid request: empty batch"))
                continue
            for response in (handle(m) for m in message):
                if response is not None:
                    _emit(response)
            continue
        response = handle(message)
        if response is not None:
            _emit(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
