## MODIFIED Requirements

### Requirement: USER_OVERRIDE follows only an escalation

Existing recorded `USER_OVERRIDE` design verdicts SHALL retain their disposition. The FULL change-design checkpoint SHALL NOT generate `USER_OVERRIDE`; when a reviewed design is unresolved, a checkpoint choice SHALL NOT convert it to a passing verdict. A deferral or an explicit pre-review waiver SHALL be recorded with its own verdict, never as `USER_OVERRIDE`.

#### Scenario: Parking change with no review rounds
- **WHEN** a parking change has had no review round and the user explains that its review is deferred to the milestone changes
- **THEN** `review.md` records `VERDICT: DEFERRED`, not `VERDICT: USER_OVERRIDE`

#### Scenario: Escalation after two REVISE rounds
- **WHEN** a previous change has a `VERDICT: USER_OVERRIDE` record from an escalation under the old two-REVISE policy
- **THEN** the change's existing passing disposition is not rewritten or invalidated by the checkpoint policy

## ADDED Requirements

### Requirement: Unresolved design review reaches an owner checkpoint

FULL change-design review SHALL stop and hand off when `review.design_max_rounds` validated reviewer passes in the current scope have not produced a passing verdict; the setting is a positive integer and defaults to 3. The handoff SHALL present the open findings and repairs made so far. A failed run SHALL NOT count. The agent SHALL NOT hand off merely because a finding count did not fall. PR feedback, pre-ship and roadmap limits SHALL remain independent.

#### Scenario: Unresolved third round
- **WHEN** the project omits the setting and round 3 is `REVISE` after two unresolved reviewer passes
- **THEN** the workflow presents open findings and repairs, leaves exactly that verdict and stops before a fourth pass or writing tasks

#### Scenario: No count-based stop
- **WHEN** round 2 is unresolved with the same or more findings than round 1 and the configured limit has not been reached
- **THEN** the workflow can make repairs and run the next reviewer pass without asking for a checkpoint decision

#### Scenario: Configured round and conditional approval
- **WHEN** `review.design_max_rounds` is 1 and the first result is `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: no`
- **THEN** the workflow hands off with the changes outstanding and does not start a recheck or write tasks before the owner chooses

#### Scenario: Approval at the limit
- **WHEN** the reviewer gives `APPROVE` or rechecks Required Changes with `APPROVE_WITH_CHANGES` and `CHANGES_APPLIED: yes` at the limit
- **THEN** the existing passing disposition applies without a checkpoint

### Requirement: The owner checkpoint records its choice without overriding the verdict

The workflow SHALL record the round and owner's choice in `review.md`: one more pass with a stated scope, a scope change with a reason, or stop. The record SHALL survive subsequent review writes. One more scoped pass permits only one current, validated result; a failed or stale result SHALL NOT consume permission. If the new result is unresolved, hand off again. A scope change SHALL require revised design artifacts and a new full review, not a waiver. Stop SHALL leave the design blocked.

#### Scenario: One scoped pass stays unresolved
- **WHEN** the owner authorizes one more scoped pass and the reviewer again returns `REVISE`
- **THEN** the choice and scope remain in `review.md`, the new verdict stays `REVISE`, and the workflow hands off again before another pass or tasks

#### Scenario: Scope change with reason
- **WHEN** the owner chooses a scope change stating why
- **THEN** the record preserves the round and reason, and the revised design needs its own passing review before tasks; the earlier unresolved verdict is not rewritten

#### Scenario: A reason alone does not restart the budget
- **WHEN** the owner records a scope-change reason but the proposal, design and spec deltas are unchanged except for Release Notes
- **THEN** a new review is refused until the artifacts change; the recorded choice and unresolved verdict are retained

#### Scenario: Stop or no choice
- **WHEN** there is no owner answer, or the owner chooses stop
- **THEN** no new reviewer is started and tasks remain blocked; an explicit stop is recorded, and silence is not recorded as a choice

#### Scenario: Failed or stale pass does not spend permission
- **WHEN** a result after a scoped-pass decision fails validation or was dispatched on an earlier record or different design inputs
- **THEN** it cannot replace the result or the decision in `review.md`, and the authorized pass still awaits a valid current result

#### Scenario: Owner details cannot add a verdict
- **WHEN** the owner supplies a scope or reason containing a line resembling a verdict
- **THEN** it is presented as part of the quoted detail, never as a second verdict or passing disposition

#### Scenario: A narrowed design cannot erase its unresolved FULL review
- **WHEN** a change with an unresolved FULL checkpoint is retiered LIGHT, including after an owner's scope-change decision
- **THEN** the LIGHT writer refuses to replace the FULL record with `SKIPPED_LIGHT`; tasks and apply still require the FULL controller's passing result
