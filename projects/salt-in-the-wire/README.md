# Salt in the Wire — worked example

A real, small project (a 5–15 page short story seed) that exercises the whole deterministic
pipeline end to end. It exists to demonstrate the infrastructure, not to be a finished story:
scene 1 is drafted and promoted; scenes 2–3 are specified and left for drafting.

## The premise (deliberately non-default)
A signal-station operator finds the distress relay was **cut by hand, years before her
posting** — and that she has been keeping a silence someone else chose. The "sabotage" turns
out to be an act of mercy (the approach chart is wrong; the relay was guiding ships onto a
reef). The antagonist force is *duty itself*. See `brief/creative-brief.md`.

## What is wired up
- **Seed canon** (`canon/*.jsonl`, `canon/index.json`): facts, per-character knowledge,
  relationships, and the opening time. Note that `fact-chart-mis-surveyed` is true from the
  start and known to Jonas, but **not** to Mara — the fabula/knowledge split.
- **Event graph** (`planning/event-graph.json`): the three causal events behind the scenes.
- **Scenes** (`scenes/ch01-sc0{1,2,3}/spec.json`): typed specs with `knowledge_required`,
  so the hard audit can check knowledge cutoffs.
- **Scene 1**: two candidates — `candidate-a.md` (restraint-first) and `candidate-b.md`
  (a default-heavy control sample) — plus critiques and a `state-delta.json`. `candidate-a`
  is promoted into `manuscript/chapters/ch01-sc01.md`.

## Reproduce the pipeline
```bash
# 1. Deterministic hard audit of the promoted scene (passes)
python3 scripts/hard_audit.py projects/salt-in-the-wire ch01-sc01

# 2. Defaultness linter separates the two candidates:
#    candidate-a -> PASS (0 findings); candidate-b -> REVISE (~15 evidence-bearing findings)
python3 scripts/defaultness_lint.py projects/salt-in-the-wire ch01-sc01

# 3. Leak-free context for scene 2 — Mara's knowledge excludes what she learns *in* scene 2
python3 scripts/compile_scene_context.py projects/salt-in-the-wire ch01-sc02

# 4. Whole-project audit (canon + accepted scenes). One expected MINOR: the central
#    promise is still open because scenes 2-3 are not promoted yet.
python3 scripts/hard_audit.py projects/salt-in-the-wire
```

## The guardrail, demonstrated
Scene 3 needs Mara to know `fact-chart-mis-surveyed`, which she only learns in scene 2.
Because scene 2 is not promoted, auditing scene 3 **correctly fails** with a fatal
knowledge-leak finding — the system refusing to let the future leak into the past:
```bash
python3 scripts/hard_audit.py projects/salt-in-the-wire ch01-sc03   # -> REJECT (fatal)
```
Promote scene 2 first and the finding clears. That is the intended workflow, not a bug.
