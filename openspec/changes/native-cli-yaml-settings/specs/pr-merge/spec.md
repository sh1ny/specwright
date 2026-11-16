# Spec Delta

## MODIFIED Requirements

### Requirement: Merging is opt-in
Specwright SHALL merge a pull request only when `finish` is `pr` and either `pr.merge` is `agent` on the default branch, or the user confirmed a policy difference whose head has `pr.merge: agent`. With main's `pr.merge` absent, `user` or any other value and no such confirmation, no skill or script SHALL merge a PR, and watch SHALL report ready and stop as before. An unrecognised `pr.merge` value SHALL be reported as treated like `user`.

#### Scenario: Default project never merges
- **WHEN** `openspec/specwright.yaml` has no `pr.merge` key on main or at the head, `finish` is `pr`, and watch finds the archived change's PR ready
- **THEN** watch reports ready and stops, and no merge request is sent to GitHub

#### Scenario: Opted-in project merges
- **WHEN** `pr.merge` is `agent` on main and at the head, `finish` is `pr`, and watch finds the archived change's PR ready
- **THEN** watch merges the PR, and GitHub shows it MERGED

#### Scenario: Unrecognised value
- **WHEN** `pr.merge` is `automatic` on main and at the head, and watch finds the PR ready
- **THEN** watch reports `pr.merge: automatic is not user or agent; treated as user`, reports ready, and merges nothing

#### Scenario: Local finish ignores the setting
- **WHEN** `pr.merge` is `agent` and `finish` is `local`
- **THEN** finish merges locally as before, and no GitHub merge request is sent

### Requirement: An unknown policy merges nothing
When main's or the ready head's settings file cannot be read from GitHub (a failed or cut-off read, a response that is not a file, a file the settings reader refuses, a plain `yes` or `no` value, a section of the wrong shape), or the head has no settings file, the merge policy SHALL count as unknown: watch SHALL report ready, say the policy could not be read and why, and send no merge request. Only a missing file on main SHALL be read as an empty settings file.

#### Scenario: Read fails
- **WHEN** reading main's settings file fails with a network error
- **THEN** watch reports `merge policy unknown` with the error, and no merge request is sent

#### Scenario: No settings file at the head
- **WHEN** main has `pr.merge: agent` and the ready head has no `openspec/specwright.yaml`
- **THEN** watch reports `merge policy unknown` naming the head, and no merge request is sent

#### Scenario: Read succeeds after a failure
- **WHEN** one read failed and watch reaches the merge step again, and both reads now succeed with no difference and the required reviewers reported
- **THEN** watch merges the PR

#### Scenario: Duplicate key at the head
- **WHEN** main has `pr.merge: agent` and the ready head's settings give `merge:` twice under `pr:`, once `user` and once `agent`
- **THEN** `policy` exits 3 with `lookup_failed` naming the line, watch reports `merge policy unknown`, and no merge request is sent

#### Scenario: A yes boolean on main
- **WHEN** main's settings hold `delete_branch: yes` under `pr:` and watch reaches the merge step
- **THEN** watch reports `merge policy unknown` naming the line and `true`/`false`, and no merge request is sent

#### Scenario: Wrong shape at the head
- **WHEN** the ready head's settings hold `pr:` as a list instead of a mapping
- **THEN** `policy` exits 3 with `lookup_failed`, and no merge request is sent

#### Scenario: A store reviewer set that is not a mapping
- **WHEN** `policy --store` runs, `pr.merge` is `agent` with a required code reviewer, and `planning_store.reviewers` on main and at the head is a list, written as a block sequence or as a flow sequence
- **THEN** `policy` exits 3 with `lookup_failed` naming `planning_store.reviewers`, writes no reviewer config, and the code reviewers authorize no store merge; an absent `planning_store.reviewers` still inherits the code set

#### Scenario: A reviewer entry that is not a mapping
- **WHEN** `pr.merge` is `agent` on main and at the head, and both write a required reviewer as a list (`guard:` then `- role: required` with a `report.check`)
- **THEN** `policy` exits 3 with `lookup_failed` naming `pr.reviewers.guard`, and no merge request is sent

#### Scenario: A non-finite number
- **WHEN** the ready head's settings hold `delete_branch: .nan`, `merge_method: .inf` or a reviewer `timeout: -.inf`
- **THEN** `policy` exits 3 with `lookup_failed` naming the line, and never stops with `internal_error`

#### Scenario: Valid YAML the old reader refused
- **WHEN** main writes a reviewer as `{ role: required }` and the head writes the same reviewer as `{ role: required, }` (a trailing flow comma), or as a block mapping
- **THEN** `policy` reads both as the same reviewer set, reports no difference, and authorizes as it would for identical files
