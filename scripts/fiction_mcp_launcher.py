#!/usr/bin/env python3
"""Start the MCP server with a Python runtime supported by the project.

macOS still ships ``/usr/bin/python3`` as Python 3.9 on some systems while this
project declares Python >=3.11.  MCP clients normally execute the configured
command directly, so they never get a chance to activate a newer interpreter.
This tiny launcher is intentionally Python-3.9-compatible and replaces itself
with the first compatible interpreter it can find.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


MIN_VERSION = (3, 11)


def _compatible(executable: str) -> bool:
    try:
        result = subprocess.run(
            [executable, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _candidates() -> list[str]:
    values: list[str] = []
    override = os.environ.get("FICTION_COMPILER_PYTHON")
    if override:
        values.append(override)
    values.append(sys.executable)
    for name in ("python3.13", "python3.12", "python3.11", "python3"):
        path = shutil.which(name)
        if path:
            values.append(path)
    # Preserve preference order while avoiding repeated version probes.
    return list(dict.fromkeys(values))


def main() -> int:
    server = Path(__file__).with_name("fiction_mcp.py")
    for executable in _candidates():
        if _compatible(executable):
            os.execv(executable, [executable, str(server), *sys.argv[1:]])
    required = ".".join(str(part) for part in MIN_VERSION)
    print(
        f"fiction-compiler MCP requires Python >= {required}; no compatible interpreter was found. "
        "Set FICTION_COMPILER_PYTHON to a compatible executable.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
