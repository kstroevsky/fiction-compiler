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
import fcntl
import json
import os
from pathlib import Path

from . import acceptance

_SEED_LEDGERS = ("facts.jsonl", "knowledge-state.jsonl", "relationship-state.jsonl",
                 "world-state.jsonl", "promises.jsonl", "timeline.jsonl")


def _scene_sort_key(scene_id: str) -> tuple[int, int]:
    try:
        chapter, scene = scene_id.split("-")
        return int(chapter[2:]), int(scene[2:])
    except (ValueError, IndexError):
        return 10**9, 10**9


def _accepted_scene_ids(project: Path) -> list[str]:
    values = acceptance.load_index(project).get("accepted_state_deltas", [])
    return sorted([v for v in values if isinstance(v, str)], key=_scene_sort_key)


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
    for scene_id in reversed(_accepted_scene_ids(project)):
        frozen = acceptance.load_scene_snapshot(project, scene_id)
        if frozen is not None:
            _, snapshot = frozen
            if snapshot.get("resulting_canon_hash"):
                return str(snapshot["resulting_canon_hash"])
        decision = _decision(project, scene_id)
        if decision and decision.get("resulting_canon_hash"):
            return decision["resulting_canon_hash"]
    return seed_hash(project)


def _frozen_bytes(snapshot: dict, field: str, scene_id: str, errors: list[str]) -> bytes | None:
    try:
        return acceptance.frozen_bytes(snapshot, field)
    except (ValueError, TypeError) as exc:
        errors.append(f"{scene_id}: invalid frozen {field}: {exc}")
        return None


def verify_report(project: Path) -> dict:
    """Inspect authoritative snapshots, derived views, legacy records, and unreachable artifacts."""
    project = Path(project)
    index = acceptance.load_index(project)
    accepted = _accepted_scene_ids(project)
    mapping = index.get("acceptance_objects", {})
    mapping = mapping if isinstance(mapping, dict) else {}
    referenced_objects: set[str] = set()
    verified: list[str] = []
    legacy: list[str] = []
    authority_errors: list[str] = []
    view_errors: list[str] = []
    expected_parent: str | None = seed_hash(project)

    history = index.get("acceptance_history", {})
    if isinstance(history, dict):
        for history_scene, object_ids in history.items():
            if not isinstance(object_ids, list):
                authority_errors.append(f"{history_scene}: acceptance history is not a list")
                continue
            for object_id in object_ids:
                if not isinstance(object_id, str) or not object_id:
                    authority_errors.append(f"{history_scene}: invalid historical acceptance object id")
                    continue
                referenced_objects.add(object_id)
                try:
                    acceptance.load_object(project, object_id)
                except (ValueError, json.JSONDecodeError) as exc:
                    authority_errors.append(f"{history_scene}: historical {exc}")

    for scene_id in accepted:
        object_id = mapping.get(scene_id)
        if not isinstance(object_id, str) or not object_id:
            legacy.append(scene_id)
            decision = _decision(project, scene_id)
            if decision and decision.get("resulting_canon_hash"):
                parent = str(decision.get("parent_canon_hash") or "")
                resulting = str(decision["resulting_canon_hash"])
                delta = project / "scenes" / scene_id / "state-delta.json"
                if delta.exists() and link_hash(parent, scene_id, sha256_file(delta)) != resulting:
                    view_errors.append(
                        f"{scene_id}: legacy state-delta.json changed since promotion (canon hash mismatch)"
                    )
                if expected_parent is not None and parent != expected_parent:
                    view_errors.append(
                        f"{scene_id}: legacy canon chain broken — recorded parent does not match prior scene"
                    )
                expected_parent = resulting
            else:
                expected_parent = None
            continue

        referenced_objects.add(object_id)
        try:
            snapshot = acceptance.load_object(project, object_id)
        except (ValueError, json.JSONDecodeError) as exc:
            authority_errors.append(f"{scene_id}: {exc}")
            expected_parent = None
            continue
        if snapshot.get("scene_id") != scene_id:
            authority_errors.append(
                f"{scene_id}: acceptance object names scene {snapshot.get('scene_id')!r}"
            )

        candidate_bytes = _frozen_bytes(snapshot, "candidate", scene_id, authority_errors)
        _frozen_bytes(snapshot, "spec", scene_id, authority_errors)
        delta_bytes = _frozen_bytes(snapshot, "state_delta", scene_id, authority_errors)
        parent = str(snapshot.get("parent_canon_hash") or "")
        resulting = str(snapshot.get("resulting_canon_hash") or "")
        if delta_bytes is not None:
            delta_sha = sha256_bytes(delta_bytes)
            if link_hash(parent, scene_id, delta_sha) != resulting:
                authority_errors.append(
                    f"{scene_id}: acceptance canon hash does not match frozen delta"
                )
        if expected_parent is not None and parent != expected_parent:
            authority_errors.append(
                f"{scene_id}: acceptance chain broken — recorded parent does not match prior scene"
            )
        expected_parent = resulting or None

        for position, item in enumerate(snapshot.get("binding_critiques", [])):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                authority_errors.append(f"{scene_id}: frozen critique #{position} is malformed")
                continue
            data = item["text"].encode("utf-8")
            if item.get("sha256") != sha256_bytes(data):
                authority_errors.append(f"{scene_id}: frozen critique #{position} digest mismatch")

        for position, pair in enumerate(snapshot.get("issue_resolutions", [])):
            if not isinstance(pair, dict):
                authority_errors.append(f"{scene_id}: frozen issue-resolution #{position} is malformed")
                continue
            for kind in ("resolution", "source_critique"):
                item = pair.get(kind)
                if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                    authority_errors.append(
                        f"{scene_id}: frozen issue-resolution #{position} {kind} is malformed"
                    )
                    continue
                data = item["text"].encode("utf-8")
                if item.get("sha256") != sha256_bytes(data):
                    authority_errors.append(
                        f"{scene_id}: frozen issue-resolution #{position} {kind} digest mismatch"
                    )

        live_delta = project / "scenes" / scene_id / "state-delta.json"
        if delta_bytes is not None:
            if not live_delta.exists():
                view_errors.append(f"{scene_id}: derived state-delta.json is missing")
            elif live_delta.read_bytes() != delta_bytes:
                view_errors.append(f"{scene_id}: state-delta.json differs from accepted snapshot")

        manuscript = project / "manuscript" / "chapters" / f"{scene_id}.md"
        if candidate_bytes is not None:
            if not manuscript.exists():
                view_errors.append(f"{scene_id}: derived manuscript chapter is missing")
            elif manuscript.read_bytes() != candidate_bytes:
                view_errors.append(f"{scene_id}: manuscript chapter differs from accepted snapshot")

        decision = _decision(project, scene_id)
        if decision is None:
            view_errors.append(f"{scene_id}: derived promotion decision is missing or invalid")
        elif decision.get("acceptance_object") != object_id:
            view_errors.append(f"{scene_id}: promotion decision points at the wrong acceptance object")

        if not any(
            message.startswith(f"{scene_id}:") for message in authority_errors + view_errors
        ):
            verified.append(scene_id)

    accepted_set = set(accepted)
    orphaned: list[str] = []
    for path in (project / "decisions").glob("promote-*.json") if (project / "decisions").exists() else []:
        if path.stem.removeprefix("promote-") not in accepted_set:
            orphaned.append(str(path.relative_to(project)))
    chapters = project / "manuscript" / "chapters"
    for path in chapters.glob("*.md") if chapters.exists() else []:
        if path.stem not in accepted_set:
            orphaned.append(str(path.relative_to(project)))
    objects = project / "canon" / acceptance.OBJECT_DIR
    for path in objects.glob("*.json") if objects.exists() else []:
        if path.stem not in referenced_objects:
            orphaned.append(str(path.relative_to(project)))
    orphaned.sort()

    invalid = authority_errors + view_errors
    status = (
        "invalid" if invalid else "orphaned" if orphaned else
        "legacy_unverified" if legacy else "verified"
    )
    return {
        "status": status,
        "verified": verified,
        "legacy_unverified": legacy,
        "invalid": invalid,
        "authority_errors": authority_errors,
        "view_errors": view_errors,
        "orphaned": orphaned,
        "accepted": accepted,
        "head_acceptance": index.get("head_acceptance"),
        "rechecks_required": index.get("rechecks_required", {}),
        "revision_events": index.get("revision_events", []),
    }


def verify_canon(project: Path) -> list[str]:
    """Compatibility API used by workspace validation."""
    report = verify_report(project)
    errors = list(report["invalid"])
    errors.extend(f"orphaned acceptance artifact: {path}" for path in report["orphaned"])
    return errors


class PromotionLock:
    """A process-scoped project lock released by the OS after abrupt process exit."""

    def __init__(self, project: Path):
        self._path = project / ".runs" / "promote.lock"
        self._handle = None

    def __enter__(self) -> "PromotionLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise ValueError("another promotion is in progress (project promotion lock is held)") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"pid": os.getpid()}) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def __exit__(self, *exc) -> bool:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None
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
        prior = target.read_bytes() if target.exists() else None
        self._ops.append({"target": target, "data": data, "prior": prior, "committed": False})

    def commit(self) -> None:
        for op in self._ops:
            acceptance.atomic_write(op["target"], op["data"])
            op["committed"] = True

    def rollback(self) -> None:
        for op in reversed(self._ops):
            if op["committed"]:
                if op["prior"] is None:
                    Path(op["target"]).unlink(missing_ok=True)
                else:
                    acceptance.atomic_write(Path(op["target"]), op["prior"])
