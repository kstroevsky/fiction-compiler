from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "scripts" / "fiction_mcp.py"


def run_session(messages: list[dict]) -> list[dict]:
    """Feed newline-delimited JSON-RPC to the server, return parsed stdout responses."""
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    result = subprocess.run(
        [sys.executable, str(SERVER)],
        input=payload, capture_output=True, text=True, timeout=30, cwd=ROOT,
    )
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]


class McpProtocolTests(unittest.TestCase):
    def test_handshake_list_and_call(self) -> None:
        responses = run_session([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},  # notification -> no response
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "kb_search", "arguments": {"query": "focalization"}}},
        ])
        # Exactly three responses (the notification produced none).
        self.assertEqual([r.get("id") for r in responses], [1, 2, 3])

        init = responses[0]["result"]
        self.assertEqual(init["protocolVersion"], "2025-06-18")
        self.assertEqual(init["serverInfo"]["name"], "fiction-compiler")

        tool_names = {t["name"] for t in responses[1]["result"]["tools"]}
        self.assertIn("kb_search", tool_names)
        self.assertIn("hard_audit", tool_names)

        call = responses[2]["result"]
        self.assertFalse(call["isError"])
        payload = json.loads(call["content"][0]["text"])
        ids = {r["id"] for r in payload["results"]}
        self.assertIn("focalization-and-knowledge", ids)

    def test_unknown_method_errors_only_for_requests(self) -> None:
        responses = run_session([
            {"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"},
            {"jsonrpc": "2.0", "method": "some/notification"},  # no id -> no response
        ])
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 9)
        self.assertEqual(responses[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
