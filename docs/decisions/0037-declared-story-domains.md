# ADR 0037 — Enforce declared story domains

Engineering decision record for the remaining typed-state defect in Track E of the September audit.
This change strengthens deterministic story-state semantics; it does not establish literary quality.

## 1. Failure observed

The executable IR distinguished predicate names, arity, and entity ID prefixes, but still inherited
Python equality and an effectively open value/entity domain. That created several unsound cases:

- `False` could compare equal to numeric `0` when matching event effects;
- event preconditions had no explicit numeric comparison semantics;
- predicates could not declare that their values must be booleans, numbers, integers, strings, or a
  bounded/enumerated set;
- an ID with the correct prefix could name an entity that the story had never declared; and
- a story could not state a domain-specific invariant such as one active `located_at` target per
  subject without hard-coding that rule globally.

The same semantics also needed to agree across hard audit, plan feasibility, critic-eval fixtures,
and regression checks.

## 2. Exact evidence

- `docs/audits/2026-09-27/audit.md` requires explicit typed equality/comparison and boolean semantics,
  value-domain validation, stable proposition identity, and entity existence/exclusivity only for
  declared domain constraints. It specifically calls for negative, numeric, zero, and string cases.
- `docs/audits/2026-09-28/review.md` Track E requires coherent typed values/negation alongside the
  already-implemented truth/belief/resource semantics.
- The audit probe `typed-value-ignored` demonstrated that a typed precondition could be reduced to
  presence/truthiness; the historical `effect-value-ignored` probe motivated exact effect matching.

## 3. Root-layer diagnosis

The defect is in the **state/ontology layer**. It is not a prose-realization problem and should not be
repaired by asking a model to infer whether two values or two locations "mean the same thing."
Predicates need explicit machine-readable domains, while stories retain control over which domains
are closed or exclusive.

## 4. Decision

Typed value comparison is now explicit:

- equality/inequality use JSON-like type-aware semantics, so booleans do not coerce to numbers;
- ordered comparisons are `lt`, `lte`, `gt`, and `gte` and execute only on numeric values;
- event preconditions can declare a comparison, and both hard audit and plan feasibility evaluate it;
- event-effect matching uses the same type-aware equality semantics.

Predicate declarations may opt into:

- `value_type`: `boolean`, `number`, `integer`, or `string`;
- `allowed_values`;
- numeric `minimum` / `maximum`; and
- `exclusive_object_per_subject` for binary predicates whose active value is boolean.

These constraints are opt-in. A predicate without a declared value domain keeps the legacy open
value behavior. Ordered comparisons require a declared numeric domain so an arbitrary string-valued
predicate cannot silently acquire ordering semantics.

Projects may also add `canon/entity-registry.json`. Only entity types listed in `closed_types` are
closed-world: an ID of one of those types must resolve to a declared registry entry. Other types stay
open. Registry entries carry an explicit type rather than deriving semantic type solely from the ID
prefix, while prefix-shaped IDs remain supported by the ontology's existing type checks.

Exclusivity is likewise declared per predicate. The engine does not assume universal spatial physics
or that every binary relationship is one-to-one. When a predicate opts into
`exclusive_object_per_subject`, hard audit checks both the pre-scene snapshot and the post-scene
predicate snapshot for multiple active objects.

`predicate_specs` continues to accept the schema document form and the legacy name-to-spec map used
by older tests/callers. Existing projects are not silently migrated into closed-world semantics.
The project template now demonstrates the intended stricter default for newly declared locations and
objects through an empty closed registry that authors populate as they introduce entities.

## 5. Cross-surface consistency

The same domain rules are applied by:

- `hard_audit` for event preconditions/effects, predicate changes, relationship edges, and declared
  exclusivity;
- `plan_search` for executable event preconditions;
- `critic_eval` deterministic ontology cases;
- `regression.ontology_valid`; and
- `validate_workspace`, which schema-validates and semantically validates ontology/registry files.

Relationship edges preserve their legacy default value of `True` when `value` is omitted; ontology
validation no longer manufactures a `None` value for such an edge.

## 6. Regression cases

Tests prove that:

- `False` is not numeric zero and `True` is not numeric one;
- numeric ordering works while string ordering is rejected;
- value types, enumerations, minimums, and maximums are enforced when declared;
- closed entity types reject undeclared IDs while open types remain backward compatible;
- duplicate predicate/entity declarations are reported;
- hard audit executes numeric preconditions and rejects wrong-typed ones;
- event effects cannot be satisfied by a bool/int-coerced value;
- plan feasibility honors numeric comparison operators;
- the deterministic critic uses the same value/entity semantics;
- declared location exclusivity rejects two simultaneous active targets; and
- regression fixtures cover boolean-vs-zero, ordered numeric comparison, and closed-entity rejection.

## 7. Compatibility and limits

- There is no universal entity registry and no universal closed-world assumption.
- Existing maintained projects remain open unless they explicitly add `entity-registry.json`; a
  repository-wide JSON/JSONL inventory found additional object IDs in seed ledgers that a JSON-only
  migration would have missed, so closure is not inferred automatically.
- Exclusivity is a snapshot invariant. This change does not introduce continuous spatial simulation
  or transient physics between event beats.
- Nonlinear scenes still reconstruct pre-scene world state in discourse order. Fabula-ordered
  reconstruction/event-exposure separation is the next Track E limitation.
- Deterministic domain checks establish consistency of declared semantics, not whether the ontology
  is narratively sufficient or the resulting prose is good.

## 8. Human approval status

Authorized as implementation of the user-requested September audit/plan. The change is intentionally
limited to explicit value/entity/cardinality semantics and their deterministic enforcement.
