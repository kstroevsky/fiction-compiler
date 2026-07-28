"""Fiction Compiler core library.

Deterministic machinery for the fiction pipeline: schema validation, event-sourced
state reconstruction, hard (symbolic) audits, and a defaultness linter. Everything
here is code the pipeline can trust without an LLM in the loop.
"""
from __future__ import annotations

from . import schema, workspace

__all__ = ["schema", "workspace"]
