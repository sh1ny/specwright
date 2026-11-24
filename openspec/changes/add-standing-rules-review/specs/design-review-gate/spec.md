## MODIFIED Requirements

### Requirement: USER_OVERRIDE follows only an escalation

Existing recorded `USER_OVERRIDE` design verdicts SHALL retain their disposition. The FULL change-design checkpoint SHALL NOT generate `USER_OVERRIDE`; when a reviewed design is unresolved, a checkpoint choice SHALL NOT convert it to a passing verdict. A deferral or an explicit pre-review waiver SHALL be recorded with its own verdict, never as `USER_OVERRIDE`.

#### Scenario: Parking change with no review rounds
- **WHEN** a parking change has had no review round and the user explains that its review is deferred to the milestone changes
- **THEN** `review.md` records `VERDICT: DEFERRED`, not `VERDICT: USER_OVERRIDE`

#### Scenario: Escalation after two REVISE rounds
- **WHEN** a previous change has a `VERDICT: USER_OVERRIDE` record from an escalation under the old two-REVISE policy
- **THEN** the change's existing passing disposition is not rewritten or invalidated by the checkpoint policy

### Requirement: The tasks precheck accepts only recorded passing dispositions

Tasks SHALL require a whole `VERDICT:` line equal to `APPROVE`, `SKIPPED_LIGHT`, `USER_OVERRIDE`, `DEFERRED` or `WAIVED`. A FULL `APPROVE` SHALL also match current design inputs. `DEFERRED` and `WAIVED` SHALL carry `CHANGES_APPLIED: n/a` and the record their requirements name. Otherwise the precheck SHALL stop.

#### Scenario: Deferred parking change writes tasks
- **WHEN** a FULL-tier parking change's `review.md` holds `VERDICT: DEFERRED`, `CHANGES_APPLIED: n/a` and a `Deferred to:` line naming the changes that take its parts over
- **THEN** the tasks precheck passes and `tasks.md` may be written

#### Scenario: Waived change writes tasks
- **WHEN** `review.md` holds `VERDICT: WAIVED`, `CHANGES_APPLIED: n/a`, the user's quoted decision and the statement that no design review ran
- **THEN** the tasks precheck passes

#### Scenario: Verdict that only starts with a passing value
- **WHEN** `review.md` holds `VERDICT: DEFERRED_LATER` or `VERDICT: WAIVED?`
- **THEN** the precheck stops, because no whole line matches an accepted verdict

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
- **THEN** the workflow hands off with the changes outstanding and does not start another review or write tasks before the owner chooses

#### Scenario: Approval at the limit
- **WHEN** the reviewer gives `APPROVE` after a full round at the limit
- **THEN** the approval applies without a checkpoint

### Requirement: The owner checkpoint records its choice without overriding the verdict

The workflow SHALL record the round and owner's choice in `review.md`: one more pass with a stated scope, a scope change with a reason, or stop. The record SHALL survive subsequent review writes. One more scoped pass permits only one current, validated result; a failed or stale result SHALL NOT consume permission. If the new result is unresolved, hand off again. A scope change SHALL require revised design artifacts and a new full review, not a waiver. Stop SHALL leave the design blocked.

#### Scenario: One scoped pass stays unresolved
- **WHEN** the owner authorizes one more scoped pass and the reviewer again returns `REVISE`
- **THEN** the choice and scope remain in `review.md`, the new verdict stays `REVISE`, and the workflow hands off again before another pass or tasks

#### Scenario: Scope change with reason
- **WHEN** the owner chooses a scope change stating why
- **THEN** the record preserves the round and reason, and the revised design needs its own passing review before tasks; the earlier unresolved verdict is not rewritten

#### Scenario: A reason alone does not restart the budget
- **WHEN** the owner records a scope-change reason but the proposal, design and spec deltas are unchanged
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

### Requirement: Any edit to FULL design inputs voids the pass

Any edit to a FULL change's proposal, design, spec deltas or standing rule inputs SHALL void a pass. This includes Release Notes and Required Changes. Each subsequent round SHALL use the whole checklist. Only a fresh `APPROVE` SHALL pass; `APPROVE_WITH_CHANGES` remains unresolved, and `CHANGES_APPLIED: yes` SHALL NOT be accepted as a new result.

#### Scenario: Release Notes item added during apply
- **WHEN** a task adds a `### Fixed` item to the proposal's `## Release Notes` section of a FULL change and changes no other design inputs
- **THEN** the earlier pass is void and apply requires a new full review

#### Scenario: Required Changes are applied
- **WHEN** the author edits the design after `APPROVE_WITH_CHANGES`
- **THEN** only a fresh full `APPROVE` passes; a limited confirmation cannot advance the change

## REMOVED Requirements

### Requirement: Release Notes edits keep the design review verdict

**Reason:** A FULL review now covers every byte of the proposal, without a Release Notes exemption.
**Migration:** Run the full review after Release Notes edits before continuing apply.
