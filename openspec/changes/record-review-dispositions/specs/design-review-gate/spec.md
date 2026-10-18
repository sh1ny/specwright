# Spec Delta

## Purpose

Defines which `review.md` verdicts let a Specwright change write tasks, apply and archive, who may write each verdict, and what each one must record, so a change never ships code that skipped its design review without saying so.

## ADDED Requirements

### Requirement: The tasks precheck accepts only recorded passing dispositions
Tasks SHALL be written only when `review.md` has a whole line equal to `VERDICT: APPROVE`, `VERDICT: SKIPPED_LIGHT`, `VERDICT: USER_OVERRIDE`, `VERDICT: DEFERRED` or `VERDICT: WAIVED`, or `VERDICT: APPROVE_WITH_CHANGES` together with a whole line `CHANGES_APPLIED: yes`. A `DEFERRED` or `WAIVED` verdict SHALL pass only with the record its requirement names. Otherwise the precheck SHALL stop.

#### Scenario: Deferred parking change writes tasks
- **WHEN** a FULL-tier parking change's `review.md` holds `VERDICT: DEFERRED`, `CHANGES_APPLIED: n/a` and a `Deferred to:` line naming the changes that take its parts over
- **THEN** the tasks precheck passes and `tasks.md` may be written

#### Scenario: Waived change writes tasks
- **WHEN** `review.md` holds `VERDICT: WAIVED`, `CHANGES_APPLIED: n/a`, the user's quoted decision and the statement that no design review ran
- **THEN** the tasks precheck passes

#### Scenario: Verdict that only starts with a passing value
- **WHEN** `review.md` holds `VERDICT: DEFERRED_LATER` or `VERDICT: WAIVED?`
- **THEN** the precheck stops, because no whole line matches an accepted verdict

### Requirement: A deferred review never ships code
`VERDICT: DEFERRED` SHALL be written only when the user has declared a FULL-tier change a parking change that is never applied, and SHALL record in a `Deferred to:` line the change or milestone where each part's design review will happen. The apply gate SHALL refuse a change whose `review.md` is `DEFERRED`, and archive SHALL refuse it too.

#### Scenario: Apply on a deferred change
- **WHEN** apply starts on a change whose `review.md` holds `VERDICT: DEFERRED`
- **THEN** apply stops before any task is implemented, ticked or committed, says the change is deferred, names its `Deferred to:` targets, and says that applying it needs a design review first

#### Scenario: Archive on a deferred change
- **WHEN** the archive workflow runs on a change whose `review.md` holds `VERDICT: DEFERRED`
- **THEN** the change directory stays in `changes/`, no main spec is changed, and no archive commit is made

#### Scenario: Archive ran anyway
- **WHEN** a deferred change was moved to `changes/archive/` and finish starts
- **THEN** finish makes no archive commit, no merge and no push, runs no restore itself, and lists for the user the modified main specs (restored with `git restore`, with a warning that this discards their own uncommitted edits in those files), the created main specs (to delete) and how to restore the change directory

#### Scenario: Deferral with no target
- **WHEN** `review.md` holds `VERDICT: DEFERRED` but no `Deferred to:` line, or one that names nothing
- **THEN** the tasks precheck stops and asks for where each part's review will happen

### Requirement: A parking change lands without archive
A change whose `review.md` holds `VERDICT: DEFERRED` SHALL reach main only through the user's own merge of its branch. Watch SHALL NOT archive it before merge: it SHALL report the PR ready as a parked change, archive nothing, and send no agent merge request.

#### Scenario: Watch on a parking change's PR
- **WHEN** watch finds the PR of `platform-backlog` ready, with `finish: pr`, `pr.merge: agent`, and the change's `review.md` holds `VERDICT: DEFERRED`
- **THEN** watch reports the PR ready as a parked change for the user to merge, the change directory stays in `changes/`, no archive commit is pushed, and no merge request is sent

#### Scenario: Watch on an ordinary change
- **WHEN** watch finds a ready PR whose change's `review.md` holds `VERDICT: APPROVE`
- **THEN** archive before merge runs as before

### Requirement: A waiver records the user's decision
`VERDICT: WAIVED` SHALL be written only on an explicit user decision to apply a change without a design review, and SHALL record the user's words in a `User decision:` line and state that no design review ran. The agent SHALL NOT offer or suggest a waiver. A waiver SHALL NOT waive the pre-ship review.

#### Scenario: User waives the design review
- **WHEN** the user says to apply the change without a design review
- **THEN** `review.md` holds `VERDICT: WAIVED`, `CHANGES_APPLIED: n/a`, a `User decision:` line quoting the user, and a line saying no design review ran, and apply is allowed

#### Scenario: Waiver without the user's words
- **WHEN** `review.md` holds `VERDICT: WAIVED` with no `User decision:` line, or one with no quoted words
- **THEN** the tasks precheck and the apply gate both stop

#### Scenario: Review route unavailable
- **WHEN** no review route works for a FULL-tier change
- **THEN** the agent stops and tells the user, and offers neither a waiver nor a deferral

#### Scenario: Waived change ships
- **WHEN** a change whose design review is `WAIVED` reaches ship with `review.preship: true`
- **THEN** the pre-ship review still runs and ship waits for its pass

### Requirement: USER_OVERRIDE follows only an escalation
`VERDICT: USER_OVERRIDE` SHALL be recorded only when the user decides to proceed after 2 consecutive `VERDICT: REVISE` rounds were escalated, with the user's words and the open findings. A deferral or a waiver SHALL be recorded with its own verdict, never as `USER_OVERRIDE`.

#### Scenario: Parking change with no review rounds
- **WHEN** a parking change has had no review round and the user explains that its review is deferred to the milestone changes
- **THEN** `review.md` records `VERDICT: DEFERRED`, not `VERDICT: USER_OVERRIDE`

#### Scenario: Escalation after two REVISE rounds
- **WHEN** rounds 1 and 2 both return `VERDICT: REVISE` and the user then decides to proceed
- **THEN** `review.md` records `VERDICT: USER_OVERRIDE` with the user's words and the open findings
