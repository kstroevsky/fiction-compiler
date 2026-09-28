# ADR 0030 — Calibrate extraction and alignment before trusting prose realization

## Context

ADR 0024 added the representation needed for translation validation: plan-blind observed events,
followed by a separate plan-aware alignment to required event IDs. The 2026-09-28 review §6.3 and
priority D explicitly require measuring both stages on planted omissions and oblique controls before
`prose_audit` can be treated as a required production gate.

The distinction matters because an empty extraction is not evidence that the prose omitted an event.
It may be an extractor miss. Likewise, a correctly extracted oblique action can still be misaligned.
Collapsing those errors would recreate the audit's central failure mode: model uncertainty presented
as deterministic truth.

## Decision

Add a separate project-local realization-calibration study under `.runs/realization-calibration/`.
The study freezes exact prose cases and provisional expected event states before any observations are
recorded.

The two evidence stages remain isolated:

1. The **extractor packet** contains only the frozen prose. It withholds the plan, required event IDs,
   expected realized/omitted labels and fixture evidence anchors. Extracted events must quote spans
   that occur in the frozen prose.
2. The **aligner packet** contains the frozen prose, the plan-blind observations and required event
   IDs/descriptions. It still withholds expected labels and fixture anchors. The prose is included so
   the aligner can re-inspect it before declaring an event omitted. A realized event must reference a
   plan-blind observation; if extractor failure or semantic uncertainty cannot be ruled out, the
   correct representation is `unverified`.

Reports classify extractor misses separately from alignment misses. In particular, if a fixture event
is present but its planted evidence was not extracted, a later `omitted` answer is reported as
`unverified_extractor_miss`, never as a proven omission. Literal and oblique controls use planted
evidence anchors only for fixture scoring. Those anchors do not establish a general semantic oracle.

## Evidence status

The first corpus contains one planted omission, one literal realization and one oblique realization.
These are provisional local controls. No live extractor/aligner study has been run, no hidden external
set has been evaluated, and no task-specific tolerance has been adopted. The report therefore always
states `authority: not_a_prose_audit_gate`.

Free-text emotional turns and exit-state effects remain outside deterministic validation. This ADR
does not change review policy or make `require_prose_audit` mandatory.

## Regression cases

Tests prove that stage packets preserve blinding, oblique realization can be credited, planted
omission can be represented, extractor misses remain unresolved instead of becoming false omissions,
alignment errors remain distinct, free-text turn/affect stays open evidence, and tampered extraction
evidence invalidates a report.
