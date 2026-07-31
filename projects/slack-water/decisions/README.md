# Decisions — Slack Water

Each `promote-<scene>.json` is the immutable acceptance manifest written when a reviewed
candidate cleared the triple-audit gate and was folded into canon: the candidate's sha256, the
binding critiques that judged those exact bytes, and the canon hash chain (parent → resulting).
Do not edit these by hand; `validate_workspace.py` verifies canon integrity against them.
