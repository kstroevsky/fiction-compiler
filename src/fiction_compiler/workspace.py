"""Workspace path resolution.

The package lives at ``<ROOT>/src/fiction_compiler``; every script and test can
import this to locate the repository root and the well-known subtrees without
passing paths around. Keeping this in one place means path assumptions are
tested once, not re-derived in five scripts.
"""
from __future__ import annotations

from pathlib import Path

# fiction_compiler -> src -> ROOT
ROOT = Path(__file__).resolve().parents[2]

SCHEMAS = ROOT / "schemas"
PROJECTS = ROOT / "projects"
KB = ROOT / "kb"
RUNS = ROOT / ".runs"


def project_dir(name_or_path: str) -> Path:
    """Resolve a project directory from a slug or an explicit path."""
    candidate = Path(name_or_path)
    if candidate.is_absolute():
        return candidate
    # Bare slug -> projects/<slug>; otherwise treat as a path relative to ROOT.
    if candidate.parts and candidate.parts[0] == "projects":
        return (ROOT / candidate).resolve()
    if len(candidate.parts) == 1:
        return (PROJECTS / candidate).resolve()
    return (ROOT / candidate).resolve()
