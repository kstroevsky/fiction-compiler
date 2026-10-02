"""Immutable accepted-scene snapshots and atomic manifest updates.

The mutable project tree is convenient for drafting, but it is a poor authority for accepted
canon: candidate prose, state deltas, critiques and even a manuscript chapter can all be edited
after promotion.  An acceptance snapshot freezes the exact bytes promotion validated.  The
canonical index then points at the content-addressed snapshot, making one small JSON file the
transaction boundary.  Manuscript chapters and decision files are materialized views.

This module deliberately has no dependency on ``state`` or ``integrity`` so both may consume
snapshots without creating an import cycle.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


OBJECT_DIR = "objects"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """Stable bytes used for content-addressing acceptance objects and index views."""
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def atomic_write(path: Path, data: bytes) -> None:
    """Durably replace one file.

    The accepted-object store is immutable, while the index and derived views are replaceable.  A
    temporary file is fsynced before ``os.replace`` and the containing directory is fsynced after
    the rename so a process crash cannot leave a successful return with only volatile metadata.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        tmp.unlink(missing_ok=True)


def index_path(project: Path) -> Path:
    return Path(project) / "canon" / "index.json"


def load_index(project: Path) -> dict:
    path = index_path(project)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def acceptance_map(project: Path) -> dict[str, str]:
    mapping = load_index(project).get("acceptance_objects", {})
    return dict(mapping) if isinstance(mapping, dict) else {}


def object_path(project: Path, object_id: str) -> Path:
    return Path(project) / "canon" / OBJECT_DIR / f"{object_id}.json"


def object_id(snapshot: dict) -> str:
    return sha256_bytes(canonical_json_bytes(snapshot))


def write_object(project: Path, snapshot: dict) -> str:
    """Write one immutable content-addressed snapshot and return its id."""
    payload = canonical_json_bytes(snapshot)
    oid = sha256_bytes(payload)
    path = object_path(project, oid)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"acceptance object collision/corruption at {path}")
        return oid
    atomic_write(path, payload)
    return oid


def load_object(project: Path, object_id_value: str) -> dict:
    path = object_path(project, object_id_value)
    if not path.exists():
        raise ValueError(f"acceptance object {object_id_value} is missing")
    payload = path.read_bytes()
    if sha256_bytes(payload) != object_id_value:
        raise ValueError(f"acceptance object {object_id_value} has a content-hash mismatch")
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"acceptance object {object_id_value} is not a JSON object")
    return data


def load_scene_snapshot(project: Path, scene_id: str) -> tuple[str, dict] | None:
    oid = acceptance_map(project).get(scene_id)
    if not oid:
        return None
    return oid, load_object(project, oid)


def frozen_bytes(snapshot: dict, field: str) -> bytes:
    artifact = snapshot.get(field)
    if not isinstance(artifact, dict) or not isinstance(artifact.get("text"), str):
        raise ValueError(f"acceptance snapshot has no frozen {field} bytes")
    data = artifact["text"].encode("utf-8")
    expected = artifact.get("sha256")
    actual = sha256_bytes(data)
    if expected != actual:
        raise ValueError(f"acceptance snapshot {field} digest mismatch")
    return data


def frozen_json(snapshot: dict, field: str) -> dict:
    data = json.loads(frozen_bytes(snapshot, field).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"acceptance snapshot {field} is not a JSON object")
    return data
