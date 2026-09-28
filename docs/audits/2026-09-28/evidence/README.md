# Review evidence

Target: commit `2b8ef0b` (production source identical to the audited `310e50c`). Supports [`../review.md`](../review.md).

* `extra_probes.py` → `extra-probe-results.json`: eight isolated observations (N1–N8 in the review). Disposable projects in a temporary directory; no network or credentials. Observations, not assertions.
* `record_analysis.py` → `record-analysis.json`: read-only analysis of the stored projects. For each accepted scene: current gate readiness, literary critics on the promoted bytes, unreviewed parent and sibling dissent, prose-audit and revision-log presence, human gate. Also tournament label mappings, trace event counts, literary-critique recording times, brief vocabulary shared with the premise probes and lint catalog, the final paragraph of each project's last accepted scene (review §6.8), and plan-layer facts (review §6.1).
* `review-sources.json`: the 36 references added to `kb/source-register.json` under `review28-*`, each with its access depth. Existing `audit26-*` entries are reused where the review cites them.

Rerun from the repository root:

```sh
python3 docs/audits/2026-09-28/evidence/extra_probes.py
python3 docs/audits/2026-09-28/evidence/record_analysis.py
```

Each script overwrites only its own sibling JSON file. The audit's original `probes.py` was also rerun, from a scratch copy so that `docs/audits/2026-09-27/` stays untouched; all 24 observations matched the stored results exactly.

Recording times in traces mark when `record_critique` was called, not when a critique was generated. The timing observations therefore show that the record cannot establish reviewer independence; they do not establish authorship.
