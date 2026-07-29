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
    """Resolve a project directory from a slug or an explicit path.

    Rejects ``..`` traversal outright (defence in depth); absolute paths are returned as given for
    trusted in-process/CLI callers. Untrusted (MCP) callers must go through :func:`confine_project`,
    which additionally requires the result to stay under ``projects/``.
    """
    candidate = Path(name_or_path)
    if ".." in candidate.parts:
        raise ValueError(f"path traversal is not allowed: {name_or_path!r}")
    if candidate.is_absolute():
        return candidate
    # Bare slug -> projects/<slug>; otherwise treat as a path relative to ROOT.
    if candidate.parts and candidate.parts[0] == "projects":
        return (ROOT / candidate).resolve()
    if len(candidate.parts) == 1:
        return (PROJECTS / candidate).resolve()
    return (ROOT / candidate).resolve()


def _within(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def confine_project(name_or_path: str) -> Path:
    """Resolve a project path for UNTRUSTED (MCP) input; reject anything outside ``projects/``."""
    resolved = project_dir(name_or_path)
    if not _within(resolved, PROJECTS):
        raise ValueError(f"project path escapes the approved root (projects/): {name_or_path!r}")
    return resolved


def confine_file(path: str) -> Path:
    """Resolve a file path for UNTRUSTED (MCP) input; reject anything outside the repository root."""
    resolved = Path(path)
    resolved = resolved if resolved.is_absolute() else (ROOT / resolved)
    if ".." in Path(path).parts or not _within(resolved, ROOT):
        raise ValueError(f"file path escapes the approved root: {path!r}")
    return resolved.resolve()
