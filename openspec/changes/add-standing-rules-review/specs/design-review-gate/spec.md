## MODIFIED Requirements

### Requirement: USER_OVERRIDE follows only an escalation

The FULL change-design owner checkpoint SHALL NOT create `USER_OVERRIDE`. Historical records SHALL retain their disposition. The separate roadmap baseline escalation is unchanged. A deferral or waiver SHALL never be recorded as `USER_OVERRIDE`.

#### Scenario: Parking change with no review rounds
- **WHEN** the owner declares a FULL-tier change parking before a design review
- **THEN** its disposition is `DEFERRED`, not `USER_OVERRIDE`

#### Scenario: Escalation after two REVISE rounds
- **WHEN** an earlier change review already recorded `USER_OVERRIDE` after the legacy two-`REVISE` escalation
- **THEN** the tasks and apply workflow recognizes that stored verdict without issuing a new override

## ADDED Requirements

### Requirement: Unresolved design review reaches an owner checkpoint

FULL change-design review SHALL pause at `review.design_max_rounds` validated rounds in the current scope while the result is `REVISE` or `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: no`. The setting SHALL be a positive integer, default 3. The author SHALL show the current open findings or Required Changes and repairs to date. Finding count SHALL NOT decide whether to stop or pass. A passing reviewer result SHALL continue under the existing verdict rules.

#### Scenario: Unresolved third round
- **WHEN** the default applies and the third validated review remains `REVISE`, even if the finding count did not change
- **THEN** the author hands off the open findings and repairs to the owner; no further review starts without the owner's choice and the verdict remains `REVISE`

#### Scenario: Configured round and conditional approval
- **WHEN** a configured checkpoint is reached with `APPROVE_WITH_CHANGES` and `CHANGES_APPLIED: no`
- **THEN** the author hands off the Required Changes and does not treat the conditional result as a pass

### Requirement: The owner checkpoint records its choice without overriding the verdict

The author SHALL record the owner's actual choice in `review.md`: one further scoped pass, a scope change with the owner's reason, or stop. The choice SHALL NOT alter the review verdict. An invalid or failed review SHALL NOT spend an authorized scoped pass. This requirement does not add a new tasks/apply gate.

#### Scenario: One scoped pass stays unresolved
- **WHEN** the owner authorizes one more pass and the next validated result is `REVISE`
- **THEN** the record retains the owner's choice and subsequent repairs and hands off again without approving; a failed attempt did not spend the choice

#### Scenario: Scope change with reason
- **WHEN** the owner chooses a scope change and provides a reason
- **THEN** the record preserves the reason and previous verdict, and the author starts a fresh budget after updating the scope

#### Scenario: Stop or no choice
- **WHEN** the owner chooses stop or has not answered at the checkpoint
- **THEN** no further review starts and the existing unresolved verdict stays in place; an explicit stop is recorded
