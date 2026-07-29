# Two Self-Improvement Loops

The system improves along two axes that must **never be conflated**. Confusing them is how an
agent "learns" a bad rule: a single clichéd scene should be *revised*, not turned into a global
prompt edit; a recurring process failure should be fixed in the *process*, not patched by hand in
one manuscript.

| | **Story loop** | **Framework loop** |
|---|---|---|
| Improves | the manuscript | the compiler (prompts, rubrics, schemas) |
| Trigger | any critique on a candidate | *repeated, evidenced* failures across scenes |
| Cycle | PLAN → DO → CHECK → ACT per scene | improvement transaction (8 fields) |
| Code | `src/fiction_compiler/revision.py`, `scripts/revise_scene.py` | (deferred) regression-fixture runner |
| Record | `scenes/<id>/revision-log.jsonl` | `constitution/change-policy.md`, `docs/decisions/*.md` |
| Decides | accept / route lower / stop (deterministic CHECK+ACT) | **human** (agents may propose only) |
| Danger | revising toward blandness | silently rewriting the constitution |

## Story loop (per scene)
```
PLAN   name the target defect and the lowest layer that owns it
DO     draft a revision that changes THAT layer (LLM)
CHECK  re-run audits; compare to the prior version (deterministic — revision.py)
ACT    accept iff target improved AND no material regression AND no fatals;
       else route the defect one layer lower, or stop
```
Stop conditions (enforced in `evaluate_revision`, from the operating contract):
- all fatal/hard failures resolved **and** the target improved without material regression → **accept**;
- a material/fatal regression appears elsewhere → **reject** the revision;
- two attempts at a layer without acceptance → **escalate one layer lower**;
- N iterations without progress (or budget spent) → **stop, escalate to a human**.

Why deterministic CHECK/ACT: an LLM asked "is my revision better?" tends to say yes. Counting
findings by dimension and severity, and refusing to accept a revision that regresses something
material, is what keeps the loop from converging on the evaluator's preferred safeness.
See the craft grounding in `kb/craft/revision-as-craft.md`.

## Framework loop (across scenes)
Driven by the `retrospective` skill under `constitution/change-policy.md`. A proposal must carry:
observed failure, exact evidence, root-layer diagnosis, minimal change, a **new regression case**,
blind before/after outputs, known trade-offs, and **human approval**. Agents write proposals; they
do not approve their own constitutional changes. ADR `docs/decisions/0001-structured-state-delta.md`
is a worked example of the transaction.

## The one healthy coupling
The loops meet in exactly one place: **the story loop's evidence feeds the framework loop.** When
the same defect recurs across many scenes and survives revision, that clustered, evidenced pattern
is the *input* to a retrospective — a candidate framework change. A single scene's defect never is.
