"""Versioned acceptance-review policy.

The project used to equate "triple audit" with three hard-coded audit-class labels.  The audit
showed that this hid a more useful question: which capabilities does this project's contract
actually require, and what evidence cleared them?  A project may now provide
``brief/review-policy.json``; otherwise a versioned compatibility policy is used.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import acceptance, schema


DEFAULT_POLICY = {
    "id": "review-policy@1",
    "minimum_literary_reviews": 1,
    "required_literary_roles": [],
    "require_runtime_provenance": True,
    "require_issue_resolutions": True,
    "defaultness_mode": "blocking",
    "require_prose_audit": False,
}


def load(project: Path) -> tuple[dict, dict]:
    """Return (validated policy, frozen artifact record)."""
    path = Path(project) / "brief" / "review-policy.json"
    if path.exists():
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
        source = str(path.relative_to(project))
    else:
        value = dict(DEFAULT_POLICY)
        raw = acceptance.canonical_json_bytes(value)
        source = "builtin:review-policy@1"
    errors = schema.validate_named(value, "review-policy")
    if errors:
        raise ValueError("review policy is invalid: " + "; ".join(errors))
    return value, {
        "path": source,
        "sha256": acceptance.sha256_bytes(raw),
        "text": raw.decode("utf-8"),
    }
