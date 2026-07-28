Q: LLMs are not really good at generating fiction stories: constraint amount cliche narration structures, small variance of stylistics and and weak narration understanding. I know, that it's because vendors aren't really interested in train LLMs to generate fiction, it's useless. But. LLMs generate code really good, regardless of complexity and lack of obviousness of tasks. We can apply the same mechanic to fiction generation, like: 
1. describe all domains of information, which are necessary for write a world-class fiction story (like narration structure, text stylistics, fiction word organising, etc). Double-check yourself, do not stop until you find every domain. 
2. for each domain, find best sources of information, best tips and practices, best patterns you can apply 
3. run the parallel deep research process of analyzing, why LLMs write bad fiction: invent a agentic loop-like schema (with which you will be able to avoid these common mistakes and traps) with triple-check self-estimation, removing obviousness, etc. Double-check your schema. 
4. apply your findings to your schema with efficient architecture separation (so everything could be improving separately), like: 
- agnostic-like (to literature best practices and etc) schema algorithm with triple-checking and self-improvement loop mechanincs 
- literature knowledge base with several levels of nesting (the main points and concepts and links to deeper information (websites and articles, where agent could find more related information)) and deep analysis of literature sources and deep analysis of wide variety fiction stories
- branched file structure with temporary files for story creating (like the world description, characters description, main narration branches, etc)
- anything more that will be useful for fiction story writing 
5. Make sure self-improvement loop works, and the system will continue iteration-per-iteration improve itself for the initial goal (writing world-class fiction story)
6. Search through internet (after all previous steps) to find some similar solutions, analyze them and try to carefully hypothethise where they are better, where are worse, and what can we take from them 

So, what do you think about it, and how the initial configuration for the Codex/Claude Code for it should look like? 

A: My assessment: Your idea is strong. The crucial shift is to stop treating fiction generation as **“produce a lot of prose from a prompt”** and instead treat it as a **compiler, simulator, search system, and editorial pipeline**.

The analogy with code is useful, with one correction: code generation is not necessarily better because vendors care more about code. Code has unusually powerful external feedback:

* compilers reject malformed output;
* tests distinguish many correct and incorrect behaviors;
* type systems expose inconsistencies;
* execution produces concrete evidence;
* defects can usually be localized.

Fiction has no natural equivalent. Quality is delayed, multidimensional, culturally dependent, and sometimes intentionally ambiguous. Current research finds recurring weaknesses in LLM stories: homogeneous positive emotional trajectories, weak tension, low structural diversity, difficulty representing character intentionality and dramatic conflict, and contradictions in long-form facts, traits, timelines, and world rules. ([ACL Anthology][1])

Therefore, the project should create an **artificial executable specification for fiction**.

I built an initial implementation of that architecture:

It has been structurally validated, and its included tests pass.

---

# 1. What the system is actually optimizing

“World-class fiction” cannot be reduced to a single numerical score, and no loop can guarantee it. A maximally optimized averaged score would probably produce safe, over-explained, technically competent mediocrity.

The system should instead optimize a quality vector:

[
Q = [C, I, A, D, E, S, V, O, R]
]

Where:

* **C — Coherence:** causal, temporal, spatial and factual integrity.
* **I — Intentionality:** characters act from comprehensible yet complicated motives.
* **A — Agency:** choices change events and incur costs.
* **D — Dramatic force:** conflict, uncertainty, escalation and irreversible consequences.
* **E — Emotional truth:** emotional changes are earned rather than announced.
* **S — Style:** distinctive language, rhythm, imagery, syntax and narrative distance.
* **V — Voice differentiation:** narrator and characters do not collapse into the model’s default voice.
* **O — Originality:** resistance to predictable continuations, stock scenes and inherited clichés.
* **R — Reader experience:** curiosity, comprehension, inference, surprise, suspense and satisfaction.

Candidates should remain on a **Pareto frontier**. For example, one candidate may be more original but less clear; another may be clearer but emotionally flatter. Do not silently average that disagreement away.

The creative brief defines the relative priorities for the particular work.

---

# 2. Practically exhaustive domain map

No finite classification can be proven to include every possible literary concern. However, the following map is practically exhaustive because it covers the work from five complementary directions:

1. what exists in the fictional world;
2. what happens;
3. how it is narrated;
4. how readers experience it;
5. how the production system operates.

## 2.1 Reader and author contract

The system must know:

* medium and expected length;
* intended readership;
* genre promises and forbidden shortcuts;
* tone and emotional range;
* accessibility and assumed knowledge;
* thematic questions, not merely “messages”;
* desired after-effect;
* acceptable ambiguity;
* content boundaries;
* relationship to literary traditions and market conventions;
* originality policy;
* division of authority between the human and the system.

Without this layer, the model optimizes generic “good writing.”

## 2.2 Storyworld semantics

This is not merely a worldbuilding encyclopedia. It is an executable model containing:

* physical, technological, magical or supernatural laws;
* geography, distances and transportation;
* ecology and material resources;
* climate and seasons;
* historical chronology;
* institutions and political power;
* law, enforcement and legitimacy;
* economics, labor and class;
* religion, ritual and cosmology;
* family and kinship systems;
* cultural norms and taboos;
* language, naming and communication;
* medicine, food, clothing and material culture;
* logistical constraints;
* what inhabitants believe incorrectly about their world;
* invariants that cannot be broken;
* affordances that characters can exploit.

A good world is not just detailed. Its constraints generate consequences.

## 2.3 Character system

Every consequential character requires more than a biography:

* body, age, social position and material conditions;
* desire, need and consciously stated goal;
* values and moral boundaries;
* fear, shame, grief, resentment and attachment;
* self-image and how others see them;
* beliefs, misconceptions and uncertainty;
* secrets and knowledge boundaries;
* competencies and blind spots;
* typical strategy under pressure;
* capacity for self-deception;
* contradictory traits;
* status behavior;
* voice, vocabulary, rhythm and nonverbal habits;
* relationships and changing relationship states;
* short-, medium- and long-term goals;
* arc, resistance to change and possible failure of the arc;
* conditions under which the character would make an exceptional choice.

Character believability particularly depends on actions forming interpretable chains of intention, not merely serving the desired plot. This was already central in symbolic narrative-planning research and remains difficult for current LLMs. ([arXiv][2])

## 2.4 Event and plot mechanics

The event model should represent:

* initial conditions;
* destabilizing change;
* causal prerequisites;
* character-generated actions;
* opposition and counteraction;
* stakes;
* cost and sacrifice;
* escalation;
* reversals;
* discoveries;
* false conclusions;
* irreversible decisions;
* complications and secondary effects;
* subplot interaction;
* coincidence and its narrative cost;
* setup, foreshadowing and payoff;
* promises made to the reader;
* mystery and revelation scheduling;
* climax and aftermath;
* closure versus deliberate non-closure.

Represent this as a graph, not only an outline. Each event should record:

```text
preconditions
causes
participants
character intentions
knowledge required
world-state changes
relationship changes
new information
costs
promises created
promises resolved
possible downstream events
```

## 2.5 Narrative discourse

The system must separately decide **how the events are told**:

* narrator and grammatical person;
* narrator reliability;
* focalization;
* narrative distance;
* access to interiority;
* order of events;
* flashbacks, anticipations and omissions;
* duration: scene, summary, pause and ellipsis;
* frequency: singular, repeated and iterative narration;
* tense;
* narrative levels and embedded narratives;
* chapter boundaries;
* scene ordering;
* information asymmetry;
* dramatic irony;
* reveal timing;
* transition grammar;
* alternation among viewpoints;
* deliberate withholding.

The distinction between **fabula**—the causal and chronological event model—and **discourse/sjuzhet**—the particular telling—is foundational in narratology and computational narrative systems. It lets the system fix presentation without accidentally rewriting causality. ([FDM Webseiten-Archiv][3])

## 2.6 Scene dramaturgy

Every scene needs a typed specification:

* why the scene must exist;
* whose scene it is;
* local desire;
* obstacle;
* tactics;
* source of pressure;
* entry condition;
* beat sequence;
* turning point;
* outcome;
* cost;
* emotional delta;
* relationship delta;
* knowledge delta;
* status delta;
* promises introduced or paid off;
* exit condition;
* what would be lost if the scene were removed.

This avoids “characters converse pleasantly until the scene reaches its word count.”

## 2.7 Dialogue

Dialogue requires independent analysis of:

* each participant’s objective;
* what cannot be said directly;
* tactics and tactical changes;
* status negotiation;
* misunderstanding;
* interruption and silence;
* implication;
* conversational asymmetry;
* rhythm and turn length;
* idiolect;
* physical activity during speech;
* exposition pressure;
* concealed versus revealed emotion;
* difference between literal and pragmatic meaning;
* how the relationship changes during the exchange.

## 2.8 Prose realization

The prose layer covers:

* diction and register;
* syntax and sentence architecture;
* rhythm and cadence;
* paragraph movement;
* narrative distance;
* concrete versus abstract language;
* sensory selection;
* metaphor and image systems;
* motif and symbolic recurrence;
* semantic fields;
* sound, alliteration and repetition;
* compression and expansion;
* foreground and background;
* humor and irony;
* clarity;
* ambiguity;
* defamiliarization;
* genre- and period-appropriate language;
* model-default phrases and rhetorical habits.

The style profile should describe measurable tendencies rather than name an author to imitate.

For example:

```json
{
  "narrative_distance": "close but not fully interior",
  "sentence_distribution": {
    "short": 0.32,
    "medium": 0.52,
    "long": 0.16
  },
  "abstraction_budget": "low",
  "metaphor_policy": "rare, material, character-specific",
  "explanation_policy": "prefer implication",
  "dialogue_tags": "mostly invisible",
  "forbidden_defaults": [
    "emotion followed by explanatory paraphrase",
    "three-item rhetorical crescendo",
    "generic sensory inventory",
    "prematurely therapeutic self-awareness"
  ]
}
```

## 2.9 Reader cognition and emotion

The system should model what the reader currently:

* knows;
* believes;
* suspects;
* expects;
* misunderstands;
* wants to know;
* fears will happen;
* hopes will happen;
* has forgotten;
* is prepared to reinterpret.

It should track:

* curiosity;
* suspense;
* surprise;
* postdictability—whether a surprise makes sense retrospectively;
* empathy;
* identification and distance;
* cognitive load;
* salience;
* inference requirements;
* emotional trajectory;
* immersion;
* ambiguity;
* catharsis;
* reread value.

A surprising event is not valuable merely because it was unlikely. Strong surprise is unexpected beforehand but intelligible afterward. Current work on narrative surprise similarly distinguishes surprise from retrospective interpretability. ([ACL Anthology][4])

## 2.10 Research, representation and ethics

The pipeline also needs:

* factual research;
* source provenance;
* uncertainty labels;
* distinction between historical fact and invention;
* cultural and historical context;
* stereotype auditing;
* sensitivity and representation review;
* privacy rules;
* copyright and quotation tracking;
* attribution;
* restrictions against directly imitating a living writer’s distinctive style.

## 2.11 Revision and editorial disciplines

Separate passes should exist for:

* conceptual revision;
* developmental editing;
* structural editing;
* character-intentionality editing;
* continuity;
* scene necessity;
* pacing;
* dialogue;
* line editing;
* copy editing;
* proofreading;
* manuscript formatting;
* beta-reader synthesis;
* final acceptance.

A line editor must not be allowed to hide a causally broken scene beneath prettier sentences.

## 2.12 Computational operations

Finally, the engineering layer includes:

* schemas and typed intermediate representations;
* context retrieval;
* context compression;
* event-sourced canonical state;
* branch generation;
* candidate search;
* deterministic validators;
* model-based critics;
* judge-bias mitigation;
* model routing;
* prompt and rubric versioning;
* observability;
* reproducibility;
* cost and token budgets;
* failure recovery;
* regression testing;
* permissions;
* human approval gates;
* process improvement.

---

# 3. The “fiction compiler” architecture

The architecture should have six cleanly separated planes.

```text
┌──────────────────────────────────────────────┐
│ 0. CONSTITUTION                             │
│ Reader contract, quality definition, ethics │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ 1. KNOWLEDGE PLANE                          │
│ Narratology, craft, genre, research, corpus │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ 2. FABULA / STORY-STATE PLANE               │
│ World, characters, goals, events, knowledge │
│ chronology, relationships, promises         │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ 3. DISCOURSE PLANE                          │
│ POV, focalization, ordering, pacing, reveals│
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ 4. REALIZATION PLANE                        │
│ Scenes, dialogue, prose, imagery, rhythm    │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────▼───────────────────────┐
│ 5. VERIFICATION AND LEARNING                │
│ Validators, critics, tournaments, regressions│
└──────────────────────────────────────────────┘
```

Each plane emits an intermediate representation that can be inspected and revised independently.

## Canon should be event-sourced

Do not maintain a single mutable `world.md` containing “the current story.”

Instead, accepted scenes append state deltas:

```json
{
  "scene_id": "ch04-sc03",
  "time_advanced": "P2D",
  "facts_created": [],
  "facts_invalidated": [],
  "knowledge_changes": [
    {
      "character": "mara",
      "learned": "the lighthouse signal was manually interrupted",
      "confidence": 0.85,
      "source": "observed damaged relay"
    }
  ],
  "relationship_changes": [],
  "physical_changes": [],
  "promises_created": [],
  "promises_resolved": []
}
```

This allows the system to reconstruct the exact state at any scene and prevents future knowledge from leaking backward.

Recent long-story systems increasingly obtain coherence improvements from event-based outlines, dynamic history compression, explicit world state, persona-grounded character agents and graph-based verification. ([arXiv][5])

---

# 4. The generation and triple-audit loop

```python
def develop_unit(unit, project):
    contract = load_reader_contract(project)
    state = reconstruct_state_before(unit)
    context = compile_minimal_context(unit, state, contract)

    plans = generate_divergent_plans(context, count=4)
    plans = hard_validate(plans, state)

    for plan in plans:
        plan.character_simulation = simulate_character_choices(plan, state)
        plan.causal_analysis = inspect_causal_graph(plan, state)
        plan.reader_model = simulate_reader_state(plan)

    plans = discard_unmotivated_or_redundant(plans)

    candidates = [
        realize_with_distinct_strategy(plan, context)
        for plan in select_pareto_plans(plans)
    ]

    audit_1 = deterministic_audit(candidates, state)
    audit_2 = specialist_literary_audit(candidates, contract)
    audit_3 = adversarial_defaultness_audit(candidates, contract)

    survivors = repair_at_lowest_responsible_layer(
        candidates,
        audit_1 + audit_2 + audit_3
    )

    result = blind_pairwise_tournament(
        survivors,
        hide_origin=True,
        reverse_order=True,
        multiple_judges=True
    )

    if result.material_disagreement:
        return request_human_decision(result)

    accepted = result.pareto_winner
    commit_prose(accepted)
    append_state_delta(accepted)
    add_evaluation_evidence(accepted)

    if unit.ends_chapter_or_act:
        run_global_audit(project)

    return accepted
```

## Audit 1: hard and symbolic

This pass checks things that should not depend on taste:

* JSON/schema validity;
* chronology;
* travel time;
* age and dates;
* object location;
* world rules;
* physical preconditions;
* who knows what;
* point-of-view access;
* unresolved causal prerequisites;
* relationship state;
* explicit user constraints;
* setup and payoff records.

Use scripts for these whenever possible. Do not ask an LLM whether a date comparison is correct when ordinary code can calculate it.

## Audit 2: specialist literary review

Independent critics inspect:

* causal necessity;
* character intentionality;
* agency;
* conflict;
* cost;
* escalation;
* emotional movement;
* status movement;
* subtext;
* pacing;
* information control;
* thematic pressure;
* scene necessity;
* stylistic coherence.

Every criticism must quote exact textual evidence and name the layer responsible for repair.

## Audit 3: adversarial defaultness review

This critic searches specifically for:

* the statistically obvious next event;
* stock archetype behavior;
* emotion explained immediately after being shown;
* characters who possess suspiciously modern therapeutic self-awareness;
* generic beauty, darkness or atmosphere;
* convenient agreement;
* symmetrical “lesson learned” endings;
* tension resolved as soon as it becomes uncomfortable;
* repeated cadence and sentence templates;
* ornamental metaphors that do not change perception;
* fake profundity;
* morally sanitized conflict;
* synonym-based “style variation.”

The repair is not “find a less common adjective.” It should move downward:

```text
generic sentence
    ↓
generic scene behavior
    ↓
generic character tactic
    ↓
generic conflict
    ↓
generic premise assumptions
```

Repair the lowest layer where the genericity originates.

---

# 5. A better anti-obviousness mechanism

I would add an independent **continuation-prediction ensemble**.

Before drafting the next event, ask three isolated agents:

> Given only the accepted story so far, predict the three most likely next developments.

High agreement identifies the model’s default continuation basin.

The architect then generates alternatives under three constraints:

1. the development must not appear in the consensus prediction;
2. it must follow naturally from existing character motives and world affordances;
3. after it happens, the reader should be able to identify earlier evidence that made it possible.

This produces **non-obvious causality**, rather than randomness.

A useful score is:

[
Originality^* =
Unexpectedness
\times
Retrospective\ Coherence
\times
Character\ Necessity
]

A random meteor has high unexpectedness but nearly zero character necessity. A good reversal scores strongly on all three.

---

# 6. Knowledge-base design

The knowledge base should not be a folder full of enormous PDFs injected into every prompt.

Use four nested levels.

## Level 0: concept index

A concise map:

```text
narrative/
  causality
  character-intentionality
  eventfulness
  focalization
  narrative-distance
  order-duration-frequency
  suspense-surprise-curiosity
  scene-dramaturgy
  dialogue-subtext
  ...
```

## Level 1: concept cards

Each card should contain:

```yaml
concept: focalization
definition: ...
use_when: ...
diagnostic_questions: ...
failure_modes: ...
conflicts_with: ...
related_concepts: ...
examples:
  public_domain:
  project_specific:
sources:
  - source_id: ...
    section: ...
confidence: ...
```

## Level 2: analytical notes

Longer synthesis containing:

* competing theories;
* where the concept is useful;
* where it oversimplifies;
* genre and cultural variation;
* positive examples;
* counterexamples;
* diagnostic procedures;
* transformation patterns.

## Level 3: original sources and corpus observations

These may include:

* research papers;
* licensed reference works;
* user-provided materials;
* public-domain stories;
* project-specific research;
* source-linked annotations.

The Living Handbook of Narratology is a good foundational index because it covers concepts such as focalization and computational narratology without pretending that one commercial story formula is universal. ([FDM Webseiten-Archiv][6])

A reasonable craft seed library would include works such as:

* Ursula K. Le Guin, *Steering the Craft*;
* John Gardner, *The Art of Fiction*;
* Francine Prose, *Reading Like a Writer*;
* James Wood, *How Fiction Works*;
* Lajos Egri, *The Art of Dramatic Writing*;
* Robert McKee, *Dialogue*;
* Dwight Swain, *Techniques of the Selling Writer*.

These should be encoded as **claims, heuristics, counterexamples and failure conditions**, not commandments.

For corpus analysis, use licensed, user-owned or genuinely public-domain texts. Standard Ebooks offers carefully produced U.S.-public-domain editions, while Project Gutenberg’s status and licensing are likewise primarily determined with reference to U.S. copyright. Because you are in Germany, the ingestion tool must verify German/EU copyright separately rather than assuming that “public domain in the USA” is sufficient. ([Standard Ebooks][7])

---

# 7. Agents: use specialization without creating a committee simulator

Begin with five specialists, not twenty.

| Agent               | Responsibility                             | Write permissions     |
| ------------------- | ------------------------------------------ | --------------------- |
| Narrative architect | Premise, event graph, structure, discourse | Planning only         |
| Character simulator | Character-generated actions and objections | Suggestions only      |
| Continuity auditor  | Facts, chronology, knowledge, world rules  | Read-only             |
| Style editor        | Voice, rhythm, imagery, line-level defects | Candidate branch only |
| Adversarial reader  | Predictability, cliché, reader experience  | Read-only             |

The main orchestrator owns promotion into canon.

The drafter should not see the critics’ prior preferences before producing candidates. The critics should not see candidate names, model names, generation temperature or which candidate the architect preferred.

Multi-agent and iterative-critic research supports decomposition and revision, including Agents’ Room and CritiCS, but these approaches still require protection against groupthink and evaluator bias. ([arXiv][8])

---

# 8. Self-improvement that does not corrupt itself

Self-refinement and verbal episodic reflection can improve agent performance, but “the model critiques itself until it says the result is good” is not reliable. Self-Refine and Reflexion demonstrate the value of iteration and retained feedback; separate research shows that LLM judges can prefer familiar or self-generated styles and can exhibit order bias. ([NeurIPS Proceedings][9])

Therefore, the system may **propose** process changes but should never silently rewrite its constitution.

## Improvement transaction

Every proposed improvement must contain:

```yaml
observed_failure:
evidence:
frequency:
root_cause_layer:
current_rule_or_prompt:
minimal_proposed_change:
expected_benefit:
possible_regressions:
new_regression_fixture:
blind_before_after_result:
judge_disagreement:
human_decision:
version:
rollback_path:
```

Example:

```text
Observed failure:
Three consecutive scenes end with a character privately naming
the emotional lesson of the scene.

Bad response:
Add “do not be clichéd” to every prompt.

Better response:
1. Add an evaluation fixture containing explicit emotional paraphrase.
2. Add a diagnostic to the defaultness critic.
3. Modify only the realization skill.
4. Regenerate a blinded test set.
5. Check whether implication improves without making scenes unintelligible.
6. Accept only after human review.
```

## Stop conditions

A revision loop stops when any of these becomes true:

* all hard failures are resolved;
* the target dimension improves without material regression;
* two repair attempts fail because the defect belongs to a higher layer;
* three iterations produce no Pareto improvement;
* judges remain materially divided;
* the revision budget is exhausted;
* a human decision is required.

Infinite self-improvement is not improvement. It often converges toward the evaluator’s preferred blandness.

---

# 9. Recommended repository structure

The starter uses this arrangement:

```text
fiction-compiler/
├── AGENTS.md
├── CLAUDE.md
├── constitution/
│   ├── quality-contract.md
│   └── change-policy.md
├── .codex/
│   ├── config.toml
│   └── agents/
├── .claude/
│   ├── settings.json
│   ├── agents/
│   └── skills/
├── kb/
│   ├── source-register.json
│   ├── narratology/
│   ├── craft/
│   ├── genre/
│   ├── style/
│   ├── research/
│   └── corpus-notes/
├── schemas/
│   ├── project.schema.json
│   ├── character.schema.json
│   ├── event.schema.json
│   ├── scene.schema.json
│   ├── critique.schema.json
│   └── state-delta.schema.json
├── projects/
│   └── my-novel/
│       ├── brief/
│       ├── canon/
│       │   ├── characters/
│       │   ├── world/
│       │   ├── timeline.jsonl
│       │   ├── knowledge-state.jsonl
│       │   ├── relationship-state.jsonl
│       │   └── promises.jsonl
│       ├── planning/
│       │   ├── event-graph.json
│       │   ├── discourse-plan.json
│       │   └── style-profile.json
│       ├── scenes/
│       │   └── ch01-sc01/
│       │       ├── spec.json
│       │       ├── context.json
│       │       ├── candidates/
│       │       ├── critiques/
│       │       ├── decision.json
│       │       └── state-delta.json
│       ├── manuscript/
│       ├── research/
│       ├── decisions/
│       └── evals/
├── .runs/
├── scripts/
└── tests/
```

Generated alternatives stay under `.runs/` or `candidates/`. They do not become canon simply because they were generated last.

---

# 10. Codex and Claude Code configuration

## Shared operating contract

Put durable architectural invariants in `AGENTS.md`:

```md
# Fiction Compiler Operating Contract

- Separate fabula, discourse, and prose realization.
- Canon changes only through reviewed state deltas.
- Generate meaningfully different candidates for consequential choices.
- Run hard, literary, and defaultness audits before promotion.
- Route defects to the lowest responsible layer.
- Preserve rejected branches and evaluation evidence.
- Critics must cite exact textual evidence.
- Process changes require a regression case and human approval.
```

Codex reads applicable `AGENTS.md` files before working and supports layered project guidance, reusable skills and specialized subagents. OpenAI recommends keeping durable project guidance practical and moving reusable procedures into skills. ([OpenAI Developers][10])

## Claude Code

The root `CLAUDE.md` can simply import the shared contract:

```md
@AGENTS.md

## Claude Code specifics

- Use isolated subagents for independent audits.
- Keep procedures in project skills.
- Run workspace validation and regression tests before completion.
```

Claude Code supports project instructions, skills, custom subagents and lifecycle hooks. Hooks are appropriate for deterministic enforcement—such as running validation—not for asking another unconstrained LLM whether the story is “good.” ([Claude Platform Docs][11])

## Codex

The starter’s `.codex/config.toml` enables concurrent subagents and registers the shared skills:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 6
default_subagent_reasoning_effort = "high"

[[skills.config]]
path = ".claude/skills/bootstrap-story/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/generate-premises/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/compile-scene-context/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/draft-scene/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/triple-audit/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/promote-candidate/SKILL.md"
enabled = true

[[skills.config]]
path = ".claude/skills/retrospective/SKILL.md"
enabled = true
```

These mechanisms correspond to the current Codex customization model: project guidance, skills, configuration and subagents. ([OpenAI Developers][12])

---

# 11. Similar systems and what to borrow

| System                     | Stronger than the proposed starter                                                                                                                                                           | Weaker or missing                                                                                                            | What to borrow                                                                                                          |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Dramatron**              | Mature hierarchical human co-writing concept; logline → characters → beats → locations → dialogue                                                                                            | Top-down structure may not fit every writer; participants also described output as formulaic                                 | Hierarchical decomposition and interactive regeneration at each level. ([Google DeepMind][13])                          |
| **Agents’ Room / CritiCS** | Strong specialist collaboration and repeated editorial refinement                                                                                                                            | Possible shared-model groupthink; limited hard-state verification; judge bias remains                                        | Independent roles and critique at both plan and prose layers. ([arXiv][8])                                              |
| **StoryWriter**            | Event-based outlining, chapter planning and dynamic compression of prior history                                                                                                             | Less emphasis on discourse theory, deterministic continuity and evaluator calibration                                        | Event-based outlines and relevance-sensitive history compression. ([arXiv][5])                                          |
| **MAGNET + ATLAS**         | Persona-grounded character action proposals and graph-based scene verification; a July 2026 preprint reports substantial reductions in annotated inconsistencies compared with its baselines | Still dependent on LLM editing and currently a preprint; less visible emphasis on prose-level literary individuality         | Character agents acting from goals, shared state and graph comparison between scenes. ([arXiv][14])                     |
| **Fabula**                 | Participatory design with writers, exposed narrative plans and hierarchical scene/beat revision                                                                                              | More product- and interface-oriented; public description does not indicate the same regression-driven constitutional process | Human-visible plans, editable hierarchy and evaluation calibrated against expert writers. ([arXiv][15])                 |
| **Novelcrafter**           | Excellent story-bible UX, automatic mentions, time-sensitive progressions and flexible metadata                                                                                              | Publicly described system is less explicit about causal graphs, knowledge-state tests, blind evaluation and process learning | Codex ergonomics, entity linking, progression tracking and concise context retrieval. ([novelcrafter][16])              |
| **Sudowrite**              | Integrated synopsis, characters, worldbuilding, outline and scene-generation workflow                                                                                                        | More guided product workflow than transparent verification architecture                                                      | A unified author-facing project view and automatic context assembly. ([Sudowrite | Documentation][17])                  |
| **NovelAI**                | Fine control over memory, Lorebook activation and visibility into the exact context sent to the model                                                                                        | Context management does not by itself supply causal simulation or editorial verification                                     | A context viewer showing exactly why every piece of information entered the generation prompt. ([docs.novelai.net][18]) |

The closest combined direction is therefore:

```text
Novelcrafter’s story bible
+ NovelAI’s context visibility
+ Dramatron/Fabula’s hierarchy
+ StoryWriter’s event planning and compression
+ MAGNET’s character simulation
+ ATLAS’s graph verification
+ CritiCS’s specialist revision
+ software-style tests and versioned retrospectives
```

The proposed architecture is likely **better for auditability, experimentation and long projects**, but initially **worse in usability, speed and author experience** than polished commercial products. A later graphical interface should show:

* the causal event graph;
* current character knowledge;
* relationship progressions;
* open narrative promises;
* context assembled for the next scene;
* candidate branches;
* critic disagreement;
* the exact reason a candidate was promoted.

---

# 12. How to start using the repository

```bash
unzip fiction-compiler-starter.zip
cd fiction-compiler-starter

python3 scripts/new_project.py my-novel
make validate
make test

codex
# or:
claude
```

Use this as the first instruction:

> Run the `bootstrap-story` skill for `projects/my-novel`. Interview me until the reader contract and creative brief contain no material ambiguities. Do not draft prose yet. Then produce four structurally distinct premise engines, run the character-intentionality and defaultness audits, and present the surviving Pareto alternatives with their tradeoffs.

The repository already contains:

* shared `AGENTS.md` and `CLAUDE.md`;
* Codex and Claude subagent configurations;
* seven reusable workflow skills;
* project templates;
* character, event, scene, critique and state-delta schemas;
* context compilation;
* candidate promotion;
* workspace validation;
* regression tests;
* knowledge-base source registration;
* a constitutional change policy;
* a detailed domain map and agent-loop specification.

[1]: https://aclanthology.org/2024.emnlp-main.978/?utm_source=chatgpt.com "Are Large Language Models Capable of Generating ..."
[2]: https://arxiv.org/abs/1401.3841?utm_source=chatgpt.com "Narrative Planning: Balancing Plot and Character"
[3]: https://www-archiv.fdm.uni-hamburg.de/lhn/node/43.html?utm_source=chatgpt.com "Computational Narratology | the living handbook of narratology"
[4]: https://aclanthology.org/2025.wnu-1.7.pdf?utm_source=chatgpt.com "A Theoretical Framework for Evaluating Narrative Surprise ..."
[5]: https://arxiv.org/abs/2506.16445?utm_source=chatgpt.com "StoryWriter: A Multi-Agent Framework for Long Story Generation"
[6]: https://www-archiv.fdm.uni-hamburg.de/lhn/node/18.html?utm_source=chatgpt.com "Focalization | the living handbook of narratology"
[7]: https://standardebooks.org/about?utm_source=chatgpt.com "About Standard Ebooks - Standard Ebooks: Free and liberated ebooks, carefully produced for the true book lover"
[8]: https://arxiv.org/pdf/2410.02603?utm_source=chatgpt.com "narrative generation through multi-step collaboration"
[9]: https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html?utm_source=chatgpt.com "Iterative Refinement with Self-Feedback"
[10]: https://developers.openai.com/codex/agent-configuration/agents-md?utm_source=chatgpt.com "Custom instructions with AGENTS.md | ChatGPT Learn"
[11]: https://docs.anthropic.com/en/docs/claude-code/overview?utm_source=chatgpt.com "Overview - Claude Code Docs"
[12]: https://developers.openai.com/codex/customization/overview?utm_source=chatgpt.com "Customization | ChatGPT Learn - OpenAI Developers"
[13]: https://deepmind.google/research/publications/13609/?utm_source=chatgpt.com "Co-Writing Screenplays and Theatre Scripts with Language Models: An Evaluation by Industry Professionals — Google DeepMind"
[14]: https://arxiv.org/abs/2607.00918?utm_source=chatgpt.com "From Personas to Plot: Character-Grounded Multi-Agent Story Generation for Long-Form Narratives"
[15]: https://arxiv.org/abs/2606.14411?utm_source=chatgpt.com "Fabula: Building a Narrative Storytelling Sidekick with the Writers' Community"
[16]: https://www.novelcrafter.com/help/docs/codex/the-codex?utm_source=chatgpt.com "The Codex - Codex - Novelcrafter Help"
[17]: https://docs.sudowrite.com/using-sudowrite/1ow1qkGqof9rtcyGnrWUBS/what-is-story-bible/jmWepHcQdJetNrE991fjJC?utm_source=chatgpt.com "What is Story Bible – Sudowrite | Documentation"
[18]: https://docs.novelai.net/en/text/lorebook/?utm_source=chatgpt.com "| NovelAI Documentation"
