# project-planning Specification

## Purpose
Defines how `specwright-roadmap` records architecture decisions, reviews the project baseline, and commits roadmap edits, so project-level planning never needs a manual rescue.

## Requirements

### Requirement: ADRs stay proposed until the review gate passes
Roadmap **init** SHALL write baseline ADRs, and **close** any superseding ADR, with `Status: proposed`. Each SHALL be changed to `Status: accepted` with the acceptance date only after the baseline review gate passes for the content being accepted. The architecture's in-force ADR index SHALL list only accepted ADRs. An accepted ADR SHALL NOT be edited once it is on main; a later decision change SHALL be a new superseding ADR.

#### Scenario: Baseline passes review
- **WHEN** init writes ADRs 0001-0004 and the baseline review returns `VERDICT: APPROVE`
- **THEN** the committed ADRs read `Status: accepted` with that day's date, the roadmap is written only after that, and no further review round runs because of the acceptance edit

#### Scenario: Review asks to change a decision
- **WHEN** the baseline review returns `VERDICT: REVISE` with a finding against ADR 0002
- **THEN** ADR 0002 is edited in place while it still reads `Status: proposed`, and no superseding ADR is created

#### Scenario: Close supersedes an accepted ADR
- **WHEN** close finds that the decision in ADR 0003, accepted and on main, no longer holds
- **THEN** close writes a new ADR with `Status: proposed` and `Supersedes: 0003`, reviews it as the baseline is reviewed, accepts it only after that gate passes, and leaves ADR 0003's file unchanged

### Requirement: Baseline review rounds follow the schema's escalation rule
The baseline review SHALL escalate to the user after 2 consecutive `VERDICT: REVISE` rounds, and SHALL have no lifetime round cap. A pass covers only the content reviewed: a later edit to strategy, architecture or ADRs voids it and SHALL get a new round. The acceptance edit (a reviewed ADR's status set to accepted with its date, plus its in-force index row) is part of passing and does not void it. A pass ends a run of REVISE rounds.

#### Scenario: Two consecutive revise verdicts
- **WHEN** rounds 1 and 2 of the baseline review both return `VERDICT: REVISE`
- **THEN** roadmap stops and asks the user, and writes no roadmap until the user decides (recorded as `VERDICT: USER_OVERRIDE` if they choose to proceed)

#### Scenario: Edit after a passing verdict
- **WHEN** round 2 approved the baseline and a PR fix round then edits `openspec/architecture.md`
- **THEN** a round 3 review of the edited content runs without asking the user, and a REVISE in round 3 alone does not escalate

### Requirement: Gap-closing roadmap edit is committed on the new change's branch
When no planned change of the Now milestone is left and an exit criterion fails, as found by roadmap **close** or reported by the user, roadmap **next** SHALL leave the roadmap untouched until the branch gate has created the gap-closing change's branch. It SHALL then add the change to the roadmap and commit only the roadmap file by name on that branch, before any planning artifact commit. Main SHALL stay unchanged.

#### Scenario: Criterion fails with no change left
- **WHEN** every change of M1 is done, close finds the agent-verified criterion "evals/pr-pair passes" failing, and the user accepts the proposed change `fix-pr-pair-suite`
- **THEN** branch `bugfix/fix-pr-pair-suite` holds a commit that changes only the roadmap file and adds `fix-pr-pair-suite` to M1, main has no new commit, and the branch gate did not stop on a dirty tree

#### Scenario: Branch gate stops
- **WHEN** the branch gate for the gap-closing change stops, for example because main is not clean
- **THEN** the roadmap file is unchanged and no roadmap commit exists on any branch

#### Scenario: No criterion shown failing
- **WHEN** every change of M1 is done and neither close nor the user has shown an exit criterion failing
- **THEN** next proposes no gap-closing change and offers close instead

### Requirement: A milestone end offers close, not a new change
When every change of the Now milestone is done, roadmap **next** SHALL report a milestone end, offer **close** and start no change, create no branch and edit no file, unless an exit criterion was shown failing by **close** or reported failing by the user: then the gap-closing requirement applies. **next** SHALL start only changes of the Now milestone. A change that is not done keeps the milestone open: next reports what it waits for.

#### Scenario: All changes done, criteria not yet walked
- **WHEN** every change of M1 is done, M1 has a user-verified exit criterion with no recorded result, and the user runs next
- **THEN** next reports that M1 is at its end and offers close, no branch or change directory is created, and the roadmap file is unchanged

#### Scenario: Next milestone already split
- **WHEN** every change of M1 is done and Next (M2) lists agreed changes, and the user runs next
- **THEN** next offers close and does not start M2's first change

#### Scenario: Last change archived but code pending
- **WHEN** M1's last change is archived on the store's main but its code PR is still open
- **THEN** next does not offer close: it reports the change as planning merged, code pending, and names the code PR it waits for

#### Scenario: Close found a criterion failing
- **WHEN** every change of M1 is done, close found an exit criterion failing and routed to next
- **THEN** next proposes a gap-closing change instead of offering close again, and follows the gap-closing requirement

### Requirement: Status names a milestone end
Roadmap **status** SHALL name `milestone end: run close` as what **next** would do when every change of the Now milestone is done, unless an exit criterion was shown failing by **close** or reported failing by the user: then it SHALL name the gap-closing change next would propose. Otherwise it SHALL name the change next would start, or what next waits for when no change is ready to start.

#### Scenario: Status at a milestone end
- **WHEN** every change of M1 is done and the user asks for roadmap status
- **THEN** status reports each change as done and names `milestone end: run close` as what next would do, instead of a change

#### Scenario: Status after close found a criterion failing
- **WHEN** every change of M1 is done, close found an exit criterion failing, and the user asks for roadmap status
- **THEN** status names the gap-closing change next would propose, not `milestone end: run close`

#### Scenario: Status with a change left
- **WHEN** M1 has a planned change whose prerequisites are done and the user asks for roadmap status
- **THEN** status names that change as what next would start and does not report a milestone end

#### Scenario: Status while a change's code is pending
- **WHEN** M1's only change left is archived on main but its code PR is still open, and the user asks for roadmap status
- **THEN** status names the code PR next waits for, names no change to start, and does not report a milestone end

### Requirement: Finish offers close after the milestone's last change
When the roadmap exists and a change reaches main, `specwright-finish` SHALL offer roadmap **close** when every change of the Now milestone is then done, and **next** otherwise. It SHALL NOT offer both as alternatives.

#### Scenario: Last change of the milestone merged
- **WHEN** the PR of M1's last planned change is merged and finish cleans up
- **THEN** finish offers close for M1 and does not offer next

#### Scenario: Changes left in the milestone
- **WHEN** the PR of M1's first of three changes is merged and finish cleans up
- **THEN** finish offers next and does not offer close

### Requirement: An agreed Next split is recorded
Roadmap **init** and **close** SHALL split only the Now milestone into changes, unless the author explicitly agrees a split for Next. A Next milestone with an agreed split SHALL list its changes and record the agreement with its date in a `Split agreed: <YYYY-MM-DD>` line, which close drops when it promotes that milestone to Now.

#### Scenario: Author agrees a Next split at init
- **WHEN** during init the author explicitly agrees that M2 is split into three named changes
- **THEN** the roadmap's Next (M2) lists those three changes and a `Split agreed:` line with that day's date

#### Scenario: Close records a split agreed for the new Next
- **WHEN** close promotes M2 to Now and the author explicitly agrees that M3, the new Next, is split into two named changes
- **THEN** the closed roadmap's Next (M3) lists those two changes and a `Split agreed:` line with that day's date

#### Scenario: Init without an agreed Next split
- **WHEN** init writes a roadmap and the author did not agree a split for Next
- **THEN** only Now lists changes, and Next is a paragraph with no `Split agreed:` line

### Requirement: Close keeps an agreed Next split
When **close** promotes a Next milestone with a `Split agreed:` line, it SHALL keep those changes, their names and their order, and SHALL propose any amendment the finished milestone suggests to the user instead of applying it. Close SHALL ask the user before re-splitting a Next that lists changes without that line. A Next without changes SHALL be split as before.

#### Scenario: Close promotes an agreed split
- **WHEN** M1 is done, its exit criteria pass, and Next (M2) lists five changes with `Split agreed: 2026-10-01`
- **THEN** after close, Now is M2 with the same five changes in the same order and with the same names and no `Split agreed:` line, and M1 is in Done

#### Scenario: Close finds a reason to amend the agreed split
- **WHEN** M1 taught that one of M2's agreed changes is no longer needed
- **THEN** close proposes removing it and asks the user; without the user's agreement the roadmap keeps all five changes

#### Scenario: Next without a split
- **WHEN** Next (M2) is one paragraph with no changes
- **THEN** close splits M2 into changes when it promotes it, as before

#### Scenario: Next lists changes without a recorded agreement
- **WHEN** Next (M2) lists four changes but has no `Split agreed:` line
- **THEN** close asks the user whether that split is agreed; on yes Now is M2 with those four changes in the same order, and on no close splits M2 as before

### Requirement: Close offers untagged releases
With `release.enabled` true, roadmap **close** SHALL list the versions `release.sh untagged` lists (run fenced with the run login; a version is published when its tag is on origin, or with no origin remote a local tag), and offer to publish them oldest first. It SHALL NOT publish without the user's yes, and a refused or failed publish SHALL NOT block the close.

#### Scenario: Versions left untagged
- **WHEN** close runs, `v0.5.0` is the latest tag on origin and main's version history reads 0.5.0, 0.5.1, 0.6.0 with no tag on origin for the last two
- **THEN** close lists 0.5.1 and 0.6.0 and offers to publish them in that order

#### Scenario: Everything tagged
- **WHEN** every version since the latest published tag has its tag on origin, and no local tag is missing from origin
- **THEN** close offers no release

#### Scenario: No tag yet
- **WHEN** close runs in a project with no tag on origin and none locally, and main's version is 0.3.0
- **THEN** close offers to publish 0.3.0 only

#### Scenario: User declines
- **WHEN** close offers 0.6.0 and the user declines
- **THEN** no tag is created and close continues with the milestone move

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false
- **THEN** close lists no versions and offers no release
