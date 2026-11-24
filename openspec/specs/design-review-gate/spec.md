# design-review-gate Specification

## Purpose

Defines which `review.md` verdicts let a Specwright change write tasks, apply and archive, who may write each verdict, and what each one must record, so a change never ships code that skipped its design review without saying so.

## Requirements

### Requirement: The tasks precheck accepts only recorded passing dispositions
Tasks SHALL be written only when `review.md` has a whole line equal to `VERDICT: APPROVE`, `VERDICT: SKIPPED_LIGHT` or `VERDICT: USER_OVERRIDE`, or `VERDICT: APPROVE_WITH_CHANGES` together with a whole line `CHANGES_APPLIED: yes`, or `VERDICT: DEFERRED` or `VERDICT: WAIVED` together with a whole line `CHANGES_APPLIED: n/a`. A `DEFERRED` or `WAIVED` verdict SHALL pass only with the record its requirement names. Otherwise the precheck SHALL stop.

#### Scenario: Deferred parking change writes tasks
- **WHEN** a FULL-tier parking change's `review.md` holds `VERDICT: DEFERRED`, `CHANGES_APPLIED: n/a` and a `Deferred to:` line naming the changes that take its parts over
- **THEN** the tasks precheck passes and `tasks.md` may be written

#### Scenario: Waived change writes tasks
- **WHEN** `review.md` holds `VERDICT: WAIVED`, `CHANGES_APPLIED: n/a`, the user's quoted decision and the statement that no design review ran
- **THEN** the tasks precheck passes

#### Scenario: Verdict that only starts with a passing value
- **WHEN** `review.md` holds `VERDICT: DEFERRED_LATER` or `VERDICT: WAIVED?`
- **THEN** the precheck stops, because no whole line matches an accepted verdict

### Requirement: A disposition record counts only when filled in
A `Deferred to:`, `User decision:` or `No design review ran.` line SHALL count toward the tasks precheck only outside an HTML comment and only with a real value, never the template's placeholder. A record that fails this SHALL count as missing.

#### Scenario: Record left inside a template comment
- **WHEN** `review.md` holds `VERDICT: DEFERRED` or `VERDICT: WAIVED` with `CHANGES_APPLIED: n/a`, but its `Deferred to:` or `User decision:` line sits inside an `<!-- ... -->` comment or still reads `<changes or milestones>` or `"<the user's words>"`
- **THEN** the tasks precheck stops, because the record is missing

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
- **THEN** finish makes no archive commit, no merge and no push, runs no restore itself, and shows the commands printed by `sw finish undo-archive-plan`

#### Scenario: Deferred archive already committed
- **WHEN** finish resumes where a deferred change's archive is already committed on the branch but not yet on main
- **THEN** finish runs the deferred check before any merge, ship or push, stops, and shows the plan's undo, which is one new commit on the branch, never a reset or a force-push

#### Scenario: Bulk archive that included a deferred change
- **WHEN** a bulk archive moved a deferred change together with an ordinary change whose delta updated the same main spec
- **THEN** finish stops, and the plan undoes the whole bulk archive and says to run it again without the deferred change, never restoring only the deferred change's files

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

The FULL change-design owner checkpoint SHALL NOT create `USER_OVERRIDE`. Historical records SHALL retain their disposition. The separate roadmap baseline escalation is unchanged. A deferral or waiver SHALL never be recorded as `USER_OVERRIDE`.

#### Scenario: Parking change with no review rounds
- **WHEN** the owner declares a FULL-tier change parking before a design review
- **THEN** its disposition is `DEFERRED`, not `USER_OVERRIDE`

#### Scenario: Escalation after two REVISE rounds
- **WHEN** an earlier change review already recorded `USER_OVERRIDE` after the legacy two-`REVISE` escalation
- **THEN** the tasks and apply workflow recognizes that stored verdict without issuing a new override

### Requirement: Release Notes edits keep the design review verdict
An edit that changes only the proposal's `## Release Notes` section SHALL NOT void the change's design review verdict. Any edit outside that section, in the proposal, specs or design, SHALL void it as before.

#### Scenario: Release Notes item added during apply
- **WHEN** a task commit during apply adds a `### Fixed` item to the proposal's `## Release Notes` section and changes no other line of proposal, specs or design
- **THEN** the review's verdict still holds, and apply continues without a new design review

#### Scenario: Edit outside the section
- **WHEN** the same commit also rewords a line of the proposal's `## What Changes`
- **THEN** the verdict is void, and the drift rule's new review step applies

### Requirement: Unresolved design review reaches an owner checkpoint

FULL change-design review SHALL pause at `review.design_max_rounds` validated rounds in the current scope while the result is `REVISE` or `APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: no`. The setting SHALL be a positive integer, default 3. The author SHALL show the current open findings or Required Changes and repairs to date. Finding count SHALL NOT decide whether to stop or pass. A passing reviewer result SHALL continue under the existing verdict rules.

#### Scenario: Unresolved third round
- **WHEN** the default applies and the third validated review remains `REVISE`, even if the finding count did not change
- **THEN** the author hands off the open findings and repairs to the owner; no further review starts without the owner's choice or an owner-raised limit above the current round, and the verdict remains `REVISE`

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
- **THEN** the existing unresolved verdict stays in place. An explicit stop is recorded and blocks review even if the owner raises the limit. Without a recorded choice, a cap-only handoff can reopen only if the owner raises the limit above the current round.
