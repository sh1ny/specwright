# design-constraints Specification

## Purpose

Keeps the constraints a change's design establishes, such as invariants, deliberate gaps and rejected alternatives, where later changes will read them, so no planner has to read archived designs.

## Requirements

### Requirement: A design lists the constraints it carries forward
design.md SHALL have a `## Carried constraints` section in both tiers. Each fact a future change must respect SHALL be one entry with an id (`C1`, `C2`...), the fact, and one destination: a doc comment on named code, a requirement in this change's delta spec, or an ADR. The section SHALL read `None` when nothing outlives the change.

#### Scenario: Deliberate gap in the data
- **WHEN** a design decides that some indexed inputs are deliberately not carried and that vendoring them is rejected
- **THEN** `## Carried constraints` lists it as `C1` with a doc comment destination naming the file and symbol that hold those inputs

#### Scenario: Behavioural guarantee
- **WHEN** a design establishes that an exported file always lists entries in index order
- **THEN** the entry's destination is a named requirement in this change's delta spec

#### Scenario: Nothing outlives the change
- **WHEN** a design fixes a typo in a message and makes no lasting decision
- **THEN** the section reads `None`

#### Scenario: LIGHT design
- **WHEN** a `TIER: LIGHT` design rejects an alternative that a future change could reintroduce
- **THEN** the LIGHT design still holds `## Carried constraints` with that entry, since the section sits above the LIGHT boundary

### Requirement: Apply writes each carried constraint at its destination
tasks.md SHALL hold a task per Carried constraints entry that writes it at its destination, ticked only when the text is there. When the destination is gone, or no longer fits, during apply, the entry SHALL be amended under the design drift rule before its task is ticked.

#### Scenario: Doc comment destination
- **WHEN** design.md lists `C1` with destination `tool/maps/pack.dart`, `FrozenInputs`
- **THEN** tasks.md has a task naming `C1` that adds the fact to that symbol's doc comment, and the task is ticked only after the comment is written

#### Scenario: Destination moved during apply
- **WHEN** the symbol named as `C1`'s destination was removed by an earlier task
- **THEN** apply stops that task, design.md's entry gets a new destination through the drift rule, and the task then writes it there

### Requirement: The design review checks the list is complete
The FULL design review SHALL record a Moderate finding for a stated fact a future change could break (a rejected alternative, an invariant, a deliberate gap) that `## Carried constraints` does not list, and for an entry with no destination or more than one. The LIGHT re-check SHALL apply the same test, record each failure in review.md as a Moderate finding, and SHALL NOT write `SKIPPED_LIGHT` until design.md lists every such fact with exactly one destination.

#### Scenario: Rejected alternative not carried
- **WHEN** a decision rejects vendoring the missing tiles and `## Carried constraints` reads `None`
- **THEN** the review records a Moderate finding naming that decision

#### Scenario: Entry without a destination
- **WHEN** `C2` states an invariant but names no destination
- **THEN** the review records a Moderate finding on `C2`

#### Scenario: LIGHT design omits a constraint
- **WHEN** the LIGHT re-check finds that a LIGHT design rejects an alternative a future change could reintroduce, and its `## Carried constraints` reads `None`
- **THEN** review.md records a Moderate finding naming that alternative, with no `VERDICT:` line, so the tasks precheck stops; after the author adds the entry with one destination, the re-check writes `VERDICT: SKIPPED_LIGHT` with the finding marked fixed, if the triage still has no trigger

#### Scenario: Design planned before this change
- **WHEN** a design has no `## Carried constraints` section because it was planned earlier
- **THEN** the review reads it as `None`, still flags stated constraints a future change could break, and does not require the design to be rewritten when there are none
