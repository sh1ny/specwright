# Spec Delta

## MODIFIED Requirements

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
- **THEN** finish makes no archive commit, no merge and no push, runs no restore itself, and shows the commands printed by `finish.sh undo-archive-plan`

#### Scenario: Deferred archive already committed
- **WHEN** finish resumes where a deferred change's archive is already committed on the branch but not yet on main
- **THEN** finish runs the deferred check before any merge, ship or push, stops, and shows the plan's undo, which is one new commit on the branch, never a reset or a force-push

#### Scenario: Bulk archive that included a deferred change
- **WHEN** a bulk archive moved a deferred change together with an ordinary change whose delta updated the same main spec
- **THEN** finish stops, and the plan undoes the whole bulk archive and says to run it again without the deferred change, never restoring only the deferred change's files

#### Scenario: Deferral with no target
- **WHEN** `review.md` holds `VERDICT: DEFERRED` but no `Deferred to:` line, or one that names nothing
- **THEN** the tasks precheck stops and asks for where each part's review will happen
