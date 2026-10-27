# preship-review Specification

## Purpose

Reviews a finished change's whole diff before it reaches a PR or a local merge, decides which findings block it, and sets the rules for amending specs in response, so the review can neither be skipped silently nor rewrite a spec to fit the code.

## Requirements

### Requirement: The pre-ship review runs when every task is committed
When every task of a change is committed and `review.preship` is not `false`, `specwright-commit` SHALL run the pre-ship review over `<main>...HEAD` before it hands off to ship or suggests archive. Store-backed, the review SHALL cover the code range and the store range together. With `review.preship: false`, no pre-ship review SHALL run.

#### Scenario: Default settings
- **WHEN** the last task of a `finish: pr` change is committed and `review.preship` is not set
- **THEN** a pre-ship review of `<main>...HEAD` runs, and ship starts only after it passes

#### Scenario: Opted out
- **WHEN** the last task is committed and `review.preship` is `false`
- **THEN** no review runs, and the hand-off to ship happens as before this change

#### Scenario: Store-backed change
- **WHEN** a store-backed change completes with commits in both the code repo and the store
- **THEN** the single review covers both ranges, and its record names the code head and the store head

### Requirement: A passing review is recorded per head
A pre-ship review SHALL pass when it validates and every P0 or P1 finding in it is waived by the user. The review SHALL be recorded for the exact head it reviewed (both heads when store-backed). A later commit, other than the change's archive commit, SHALL leave the new head without a pass.

#### Scenario: Clean review
- **WHEN** a pre-ship review of head `abc123` returns only P2 and P3 findings
- **THEN** a pass is recorded for `abc123`

#### Scenario: Blocking finding
- **WHEN** a pre-ship review returns a P1 finding
- **THEN** no pass is recorded, and the P1 finding is shown to the user with the options fix or waive

#### Scenario: Fix after a blocking finding
- **WHEN** the agent commits a fix for a P1 finding on top of the reviewed head
- **THEN** the commit's subject is `<type>(<change>): address pre-ship review` with a `Preship-Round: 1` trailer, and the new head has no pass until a new pre-ship review of it passes

#### Scenario: Pre-ship fixes do not use up PR fix rounds
- **WHEN** a change has two `address pre-ship review` commits and its first PR feedback pass starts
- **THEN** that pass is PR fix round 1

### Requirement: A waiver comes only from the user
A P0 or P1 finding SHALL count as waived only when the user waives it explicitly in the session, and the waiver SHALL be recorded with the finding's id and the user's reason. The agent SHALL NOT waive a finding on its own.

#### Scenario: User waives a finding
- **WHEN** the user answers that P1 finding `f2` is accepted because it is out of scope
- **THEN** the record lists `f2` as waived with that reason, and the review passes if no other P0 or P1 is open

#### Scenario: No answer
- **WHEN** a P1 finding is open and the user has not answered
- **THEN** no pass is recorded and ship does not start

### Requirement: Ship and local merge require a pass
Before ship opens the change's first PR, and before a `finish: local` merge, Specwright SHALL check for a pass on the current head, or on a head whose only later commit is the change's archive commit. Without one, it SHALL run the pre-ship review first, unless `review.preship` is `false`.

#### Scenario: Ship with a pass on the head
- **WHEN** ship starts for a change whose current head has a pass
- **THEN** ship pushes without running another review

#### Scenario: Ship after an unreviewed commit
- **WHEN** ship starts and one commit was made after the head that has a pass, and it is not the archive commit
- **THEN** ship runs a pre-ship review before any push

#### Scenario: Local merge after archive
- **WHEN** a `finish: local` merge starts, and the only commit after the passing head is `<type>(<change>): archive change`
- **THEN** the merge proceeds without another review

#### Scenario: Store-backed local merge after archive
- **WHEN** a store-backed `finish: local` merge starts, the code head is the reviewed code head, and the only store commit after the reviewed store head is the archive commit
- **THEN** the merge proceeds without another review

#### Scenario: PR already exists
- **WHEN** ship runs for a store-backed change whose store PR is already open, to open its code PR
- **THEN** ship does not run the pass check

### Requirement: A failed review stops ship
When the pre-ship review fails (invalid output, timeout, or the reviewer could not run), ship and the local merge SHALL NOT proceed. Specwright SHALL report the reason and offer to run the review again.

#### Scenario: Invalid output
- **WHEN** the pre-ship review's output fails the findings schema
- **THEN** nothing is pushed or merged, and the report names the route and the validation error

### Requirement: Repeated blocking reviews escalate
Pre-ship fix rounds SHALL be counted from the `Preship-Round:` trailers on the change branch, in either repo. When a pre-ship review still has an unwaived P0 or P1 after round 2, Specwright SHALL stop fixing and ask the user how to proceed, listing the open findings.

#### Scenario: Blocked after the second round
- **WHEN** the branch has a commit with `Preship-Round: 2` and the next pre-ship review still returns a P1 finding
- **THEN** no further fix is committed and the user is asked, with the open findings listed

#### Scenario: New session after two rounds
- **WHEN** the review records are missing (another machine), the branch has `Preship-Round: 2`, and a new review returns a P1 finding
- **THEN** the user is asked, as after the second round, and no third round is committed

### Requirement: Spec findings are clarifications or behaviour changes
A finding that concerns a requirement or scenario SHALL be classed as a clarification (one reading fits every other scenario, and the code and tests already match it) or a behaviour change (after the edit the requirement or scenario would allow something different). The agent MAY amend a clarification itself. A behaviour change SHALL need the user's approval before any amendment.

#### Scenario: Contradictory wording
- **WHEN** a finding says a scenario's THEN contradicts another scenario, and the tests already assert the reading that fits both
- **THEN** the agent commits the edit as `<type>(<change>): amend specs` and runs a new pre-ship review

#### Scenario: Edit would change behaviour
- **WHEN** a finding proposes rewording a requirement so that the current code, which does something different, would satisfy it
- **THEN** the agent does not edit the spec, and asks the user whether to change the behaviour or the code

#### Scenario: Approved behaviour change
- **WHEN** the user approves a behaviour change to a spec in a FULL-tier change
- **THEN** the amendment follows the drift rule: an `amend specs` commit, a new design review, test and code updates, then a new pre-ship review

### Requirement: A review after the archive commit reads the archived artifacts
When a pre-ship review runs and the change's directory under `<P>/changes/<change>/` no longer exists because the archive moved it, the review SHALL be given the archived change's proposal, design, tasks and specs under `<P>/changes/archive/<archived-name>/`, on every route, CLI and subagent alike. While the active directory exists, the review SHALL use it.

#### Scenario: Recovery review after archive
- **WHEN** a `finish: local` gate reports `missing` after the archive commit (the review record is on another machine), and the recovery pre-ship review runs
- **THEN** the reviewer's input names the four artifact paths under `<P>/changes/archive/<date>-<change>/`, each of which exists, and none under `<P>/changes/<change>/`

#### Scenario: Subagent route after archive
- **WHEN** the selected route is `subagent` and the change is archived on the branch
- **THEN** the preflight output lists the archived artifact paths, and the dispatch passes those paths to the reviewer

#### Scenario: Active change
- **WHEN** a pre-ship review runs before archive, with `<P>/changes/<change>/` present
- **THEN** the input names the four artifact paths under `<P>/changes/<change>/`

#### Scenario: Several archives of the same name
- **WHEN** the active directory is gone and both `2026-09-01-<change>` and `2026-10-14-<change>` exist under the archive
- **THEN** the review is given the directory that the change's own archive commit in the reviewed range added, never the older one

#### Scenario: No artifacts anywhere
- **WHEN** neither the active directory nor any archived directory of the change exists
- **THEN** the input names the active paths as before, so the reviewer reports them as missing; no archived directory of another change is used

### Requirement: The pre-ship review checks the Release Notes section against the diff
With `release.enabled` true, the pre-ship brief SHALL ask the reviewer to check the proposal's `## Release Notes` section: a missing section, a section that breaks the format rules of the `releases` capability, or an item the diff does not ship SHALL each be a P1 `docs` finding; a user-visible change the diff ships with no item SHALL be a P2 `docs` finding. With releases off, no finding SHALL concern the section.

#### Scenario: Item the diff does not ship
- **WHEN** `release.enabled` is true, the section lists `Added: --dry-run flag (#140)` and the diff adds no such flag
- **THEN** the review returns a P1 `docs` finding naming that item, and ship waits for a fix or a waiver

#### Scenario: Shipped change with no item
- **WHEN** `release.enabled` is true and the diff adds a new `release.sh` subcommand that no item mentions
- **THEN** the review returns a P2 `docs` finding, and the review can still pass

#### Scenario: Section missing with releases on
- **WHEN** `release.enabled` is true and the proposal has no `## Release Notes` section
- **THEN** the review returns a P1 `docs` finding saying the section is missing

#### Scenario: Section breaks the format
- **WHEN** `release.enabled` is true and the section has a `### Security` heading
- **THEN** the review returns a P1 `docs` finding naming `Security` and its line, and ship waits for a fix or a waiver

#### Scenario: Releases off
- **WHEN** `release.enabled` is false and the proposal still holds a `## Release Notes` section with a stale item, or no section at all
- **THEN** no finding concerns release notes
