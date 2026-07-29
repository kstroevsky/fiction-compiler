@AGENTS.md

## Claude Code specifics
- Use project subagents for independent audits so the drafting context does not contaminate the judges.
- Prefer skills for procedures and keep this file compact.
- Before finishing a material task, run `python3 scripts/validate_workspace.py` and `python3 -m unittest discover -s tests -v`.
- After changing a prompt, rubric, schema, or the deterministic engine, also run `python3 scripts/run_regression.py`; a non-zero exit means a pinned invariant regressed — reject or roll back rather than accept it.
