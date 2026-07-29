"""Content-integrity primitives for promotion: hashing, an append-only canon hash chain,
an atomic multi-file write with rollback, and a coarse project lock.

This is slice 2 of the promotion trust core (ADR 0003). Slice 1 (ADR 0002) proved the *right*
audits were present and clean; this makes a promotion **tamper-evident** — you cannot edit an
accepted ``state-delta.json`` (or the seed ledgers) without ``verify_canon`` noticing — and
**crash-safe** — a promotion either lands fully or leaves no trace.

The canon chain is deliberately linear: scenes are promoted in fabula order, so each accepted
scene records the ``parent_canon_hash`` it was built on and a ``resulting_canon_hash`` that binds
that parent to this scene's delta bytes. Out-of-order insertion of an earlier scene is an
unsupported edge (``verify_canon`` will report the resulting chain break rather than silently
rewrite history).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .state import accepted_scene_ids

_SEED_LEDGERS = ("facts.jsonl", "knowledge-state.jsonl", "relationship-state.jsonl",
                 "promises.jsonl", "timeline.jsonl")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def seed_hash(project: Path) -> str:
    """Hash of the initial-condition ledgers, so edits to seed canon are detectable."""
    canon = project / "canon"
    parts = [f"{name}:{sha256_file(canon / name) if (canon / name).exists() else ''}"
             for name in _SEED_LEDGERS]
    return sha256_bytes("\n".join(parts).encode("utf-8"))


def link_hash(parent_hash: str, scene_id: str, delta_sha256: str) -> str:
    """One link of the canon chain: binds this delta's bytes to the exact prior state."""
    return sha256_bytes(f"{parent_hash}:{scene_id}:{delta_sha256}".encode("utf-8"))


def _decision(project: Path, scene_id: str) -> dict | None:
    path = project / "decisions" / f"promote-{scene_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def canon_head(project: Path) -> str:
    """Resulting canon hash of the latest accepted scene that carries a manifest.

    Falls back to the seed hash when no accepted scene has a manifest (a fresh project, or one
    whose accepted scenes predate ADR 0003), so the next promotion anchors on the seed ledgers.
    """
    for scene_id in reversed(accepted_scene_ids(project)):
        decision = _decision(project, scene_id)
        if decision and decision.get("resulting_canon_hash"):
            return decision["resulting_canon_hash"]
    return seed_hash(project)


def verify_canon(project: Path) -> list[str]:
    """Recompute the canon chain and flag any accepted delta edited since promotion.

    For each manifest-bearing accepted scene, the recorded ``resulting_canon_hash`` must equal
    ``link_hash(recorded_parent, scene_id, current_delta_hash)`` (delta integrity), and the
    recorded parent must equal the previous link's resulting hash (chain continuity, anchored at
    the seed hash). Legacy scenes without a manifest are skipped and break the anchor for the next
    scene rather than failing. Returns human-readable errors (empty == intact).
    """
    errors: list[str] = []
    expected_parent: str | None = seed_hash(project)
    for scene_id in accepted_scene_ids(project):
        decision = _decision(project, scene_id)
        if not decision or not decision.get("resulting_canon_hash"):
            expected_parent = None  # anchor lost: cannot verify continuity past a legacy scene
            continue
        recorded_parent = decision.get("parent_canon_hash") or ""
        recorded_resulting = decision["resulting_canon_hash"]
        delta = project / "scenes" / scene_id / "state-delta.json"
        if not delta.exists():
            errors.append(f"{scene_id}: accepted but state-delta.json is missing")
            expected_parent = recorded_resulting
            continue
        if link_hash(recorded_parent, scene_id, sha256_file(delta)) != recorded_resulting:
            errors.append(f"{scene_id}: state-delta.json changed since promotion (canon hash mismatch)")
        if expected_parent is not None and recorded_parent != expected_parent:
            errors.append(f"{scene_id}: canon chain broken — recorded parent does not match the prior scene")
        expected_parent = recorded_resulting
    return errors


class PromotionLock:
    """A coarse per-project lock so two promotions cannot interleave their writes."""

    def __init__(self, project: Path):
        self._path = project / ".promote.lock"

    def __enter__(self) -> "PromotionLock":
        try:
            fd = os.open(str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise ValueError(
                "another promotion is in progress (.promote.lock present); remove it only if you "
                "are certain no promotion is running"
            ) from exc
        os.close(fd)
        return self

    def __exit__(self, *exc) -> bool:
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass
        return False


class AtomicBatch:
    """Stage several file writes, then commit them with atomic renames; roll back on failure.

    Not a true cross-file transaction (a hard kill mid-commit can still land some files), but it
    makes promotion safe against exceptions, and ``verify_canon`` / workspace validation detect a
    torn write afterward. Each staged write records the target's prior bytes so a rollback restores
    exactly what was there before.
    """

    def __init__(self) -> None:
        self._ops: list[dict] = []

    def write(self, target: Path, data: bytes) -> None:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.parent / f"{target.name}.tmp{os.getpid()}"
        tmp.write_bytes(data)
        prior = target.read_bytes() if target.exists() else None
        self._ops.append({"target": target, "tmp": tmp, "prior": prior, "committed": False})

    def commit(self) -> None:
        for op in self._ops:
            os.replace(op["tmp"], op["target"])
            op["committed"] = True

    def rollback(self) -> None:
        for op in self._ops:
            if op["committed"]:
                if op["prior"] is None:
                    Path(op["target"]).unlink(missing_ok=True)
                else:
                    op["target"].write_bytes(op["prior"])
            else:
                Path(op["tmp"]).unlink(missing_ok=True)
