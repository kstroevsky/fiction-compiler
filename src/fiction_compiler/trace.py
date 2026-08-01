"""Append-only scene-loop trace (agents-best-practices observability).

A durable, replayable record of the operational events of a scene's loop — candidates drafted,
critiques recorded, revisions decided, promotions — written to ``.runs/trace/<scene_id>.jsonl``.
Best-effort: it must never fail the operation it records. Not canon; ``.runs`` is ephemeral evidence
(``validate_workspace`` skips it), so the trace can be pruned freely.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _trace_path(project: Path, scene_id: str) -> Path:
    return project / ".runs" / "trace" / f"{scene_id}.jsonl"


def log(project: Path, scene_id: str, event: str, **data) -> None:
    """Append one event. Swallows all errors — observability must not break the loop it observes."""
    try:
        path = _trace_path(project, scene_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "scene_id": scene_id, **data}
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001 — a trace failure must never propagate
        pass


def read(project: Path, scene_id: str) -> list[dict]:
    """Return the recorded events for a scene, oldest first."""
    path = _trace_path(project, scene_id)
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events
