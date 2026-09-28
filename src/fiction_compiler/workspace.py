"""Workspace path resolution.

The package lives at ``<ROOT>/src/fiction_compiler``; every script and test can
import this to locate the repository root and the well-known subtrees without
passing paths around. Keeping this in one place means path assumptions are
tested once, not re-derived in five scripts.
"""
from __future__ import annotations

import re
from pathlib import Path

# fiction_compiler -> src -> ROOT
ROOT = Path(__file__).resolve().parents[2]

SCHEMAS = ROOT / "schemas"
PROJECTS = ROOT / "projects"
KB = ROOT / "kb"
RUNS = ROOT / ".runs"

_SCENE_ID_RE = re.compile(r"^ch[0-9]{2}-sc[0-9]{2}$")


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


def validate_scene_id(scene_id: str) -> str:
    """Validate the canonical scene-id shape before it is interpolated into a path."""
    if not isinstance(scene_id, str) or _SCENE_ID_RE.fullmatch(scene_id) is None:
        raise ValueError(f"invalid scene_id {scene_id!r}; expected chNN-scNN")
    return scene_id


def validate_leaf_filename(filename: str, suffix: str | None = None) -> str:
    """Accept one filename component only; never a path or traversal alias."""
    if not isinstance(filename, str) or not filename:
        raise ValueError("filename must be a non-empty string")
    path = Path(filename)
    if path.is_absolute() or len(path.parts) != 1 or filename in {".", ".."}:
        raise ValueError(f"filename must be a single path component: {filename!r}")
    if suffix is not None and path.suffix != suffix:
        raise ValueError(f"filename must end with {suffix!r}: {filename!r}")
    return filename


def resolve_scene_candidate(project: Path, scene_id: str, candidate: str) -> Path:
    """Resolve a candidate while confining it to one scene's ``candidates/`` directory.

    Absolute paths are accepted for trusted in-process callers only when they still resolve inside
    the scene's candidate directory. Existing symlinks are resolved, so a symlink cannot widen the
    boundary.
    """
    validate_scene_id(scene_id)
    root = (Path(project).resolve() / "scenes" / scene_id / "candidates").resolve()
    raw = Path(candidate)
    if ".." in raw.parts:
        raise ValueError(f"candidate path traversal is not allowed: {candidate!r}")
    path = raw if raw.is_absolute() else root / raw
    resolved = path.resolve()
    if not _within(resolved, root):
        raise ValueError("candidate must live inside this scene's candidates directory")
    return resolved
