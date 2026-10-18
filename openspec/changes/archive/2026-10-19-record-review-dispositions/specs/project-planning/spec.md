# Spec Delta

## ADDED Requirements

### Requirement: A parked change is never resumed
Roadmap **next** SHALL NOT offer to resume an active change whose `review.md` holds `VERDICT: DEFERRED`: it is a parked change, never applied. **next** SHALL go on to pick the milestone's next change as if the parked change were not active, and **status** SHALL list it as `parked` with its `Deferred to:` targets. Every other active change SHALL still be offered for resume.

#### Scenario: Only a parking change is active
- **WHEN** `openspec list --json` shows only `platform-backlog`, whose `review.md` holds `VERDICT: DEFERRED`, and the Now milestone's first planned change has no archive and no unmet prerequisite
- **THEN** next does not offer to resume `platform-backlog` and starts the first planned change

#### Scenario: Status shows the parked change
- **WHEN** the user runs status while `platform-backlog` is active with `VERDICT: DEFERRED` and `Deferred to: M2 changes, M3 changes`
- **THEN** status lists `platform-backlog` as `parked`, with those targets, and not as active

#### Scenario: Parking change and a change in progress
- **WHEN** `platform-backlog` is parked and `add-sync`, whose `review.md` holds `VERDICT: APPROVE`, is also active
- **THEN** next offers to resume `add-sync`, not `platform-backlog`

#### Scenario: Next run on the parking change's branch
- **WHEN** the user runs next while the checkout is on `feat/platform-backlog`, whose change is parked
- **THEN** next says the parking change is on its own branch and next starts from main once it has merged, and creates no branch and no change

#### Scenario: Active change with no review yet
- **WHEN** an active change has no `review.md`
- **THEN** next offers to resume it as before, since it is not parked

### Requirement: The baseline gate passes only a review or an escalation
Roadmap **init** SHALL write the roadmap, and **init** or **close** SHALL accept a reviewed ADR, only when `openspec/architecture-review.md` holds `VERDICT: APPROVE`, `VERDICT: APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes`, or `VERDICT: USER_OVERRIDE` after escalation. `DEFERRED`, `WAIVED` and `SKIPPED_LIGHT` SHALL NOT pass the baseline gate.

#### Scenario: Baseline passes review
- **WHEN** the baseline review returns `VERDICT: APPROVE`
- **THEN** init accepts the reviewed ADRs and writes the roadmap

#### Scenario: Baseline recorded as waived or deferred
- **WHEN** `openspec/architecture-review.md` holds `VERDICT: WAIVED` or `VERDICT: DEFERRED`
- **THEN** init writes no roadmap, every ADR stays `Status: proposed`, and the user is told the baseline needs a review
