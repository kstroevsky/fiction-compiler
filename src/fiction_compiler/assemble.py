"""Assemble accepted scenes into one readable manuscript.

The pipeline promotes scenes into ``manuscript/chapters/<id>.md`` one at a time; this stitches
the *accepted* ones (event-sourced order) into a single ``manuscript/manuscript.md`` with the
title and chapter/scene breaks. It is the "output the whole story" step — deliberately dumb:
it only concatenates what has actually been promoted, so the assembled story can never contain
an unreviewed scene.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import acceptance
from .state import scene_sort_key

SCENE_BREAK = "\n\n· · ·\n\n"  # a quiet centered break between scenes in a chapter


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def assemble(project: Path) -> dict:
    index = _load(project / "canon" / "index.json", {})
    brief = _load(project / "brief" / "project.json", {})
    accepted = sorted(index.get("accepted_state_deltas", []), key=scene_sort_key)

    # Legacy scenes still depend on their manuscript view. Current acceptances carry prose in the
    # immutable snapshot, so assembly remains correct even if a derived chapter needs repair.
    missing = [
        s for s in accepted
        if acceptance.load_scene_snapshot(project, s) is None
        and not (project / "manuscript" / "chapters" / f"{s}.md").exists()
    ]
    if missing:
        raise ValueError(
            f"accepted scene(s) missing a manuscript file: {missing}; canon records them as promoted "
            "but the prose is gone — refusing to assemble a corrupt manuscript"
        )

    pieces: list[str] = []
    prev_chapter: str | None = None
    included: list[str] = []
    for scene_id in accepted:
        md = project / "manuscript" / "chapters" / f"{scene_id}.md"
        chapter = scene_id[2:4]
        if chapter != prev_chapter:
            pieces.append(f"\n## Chapter {int(chapter)}\n")
            prev_chapter = chapter
        elif pieces:
            pieces.append(SCENE_BREAK)
        frozen = acceptance.load_scene_snapshot(project, scene_id)
        if frozen is not None:
            _, snapshot = frozen
            text = acceptance.frozen_bytes(snapshot, "candidate").decode("utf-8")
        else:
            text = md.read_text(encoding="utf-8")
        pieces.append(text.strip())
        included.append(scene_id)

    title = brief.get("title", "Untitled")
    body = f"# {title}\n" + "".join(pieces) + "\n"
    out = project / "manuscript" / "manuscript.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    return {
        "manuscript": str(out.relative_to(project)),
        "scenes": included,
        "word_count": len(body.split()),
    }
