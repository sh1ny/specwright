# Spec Delta

## ADDED Requirements

### Requirement: The merge policy comes from main
The agent merge SHALL take `pr.merge`, `pr.merge_method`, `pr.delete_branch`, `pr.reviewers` and `planning_store.reviewers` from `openspec/specwright.yaml` on the code repository's GitHub default branch, read right before the archive decision and each merge request, never from the PR branch or the local checkout, except after the user confirmed a difference. A settings file missing on main SHALL count as `pr.merge: user`. Cleanup reads `delete_branch` from main after its pull.

#### Scenario: Policy unchanged by the PR
- **WHEN** main and the ready head both have `pr.merge: agent`, `merge_method: squash` and the same `pr.reviewers`, every required reviewer reported on the ready head, and watch finds the PR ready
- **THEN** watch merges the PR with method `squash`, with no question to the user

#### Scenario: Branch turns on agent merge
- **WHEN** main has `pr.merge: user`, the ready head has `pr.merge: agent`, and watch finds the PR ready
- **THEN** no merge request is sent until the user answers, and the report names `pr.merge` with main's value `user` and the head's value `agent`

#### Scenario: Local checkout edited, remote unchanged
- **WHEN** main and the ready head have `pr.merge: user`, and only the local checkout's settings file has `pr.merge: agent`
- **THEN** watch reports ready and stops, and no merge request is sent

#### Scenario: No settings file on main
- **WHEN** main has no `openspec/specwright.yaml` and the ready head has `pr.merge: agent` with a required reviewer that reported
- **THEN** the report names `pr.merge` with main's value `user`, and no merge request is sent until the user answers

#### Scenario: Invalid method on main
- **WHEN** main has `pr.merge: agent` and `merge_method: fast-forward`
- **THEN** watch reports that the method must be merge, squash or rebase, and sends no merge request

#### Scenario: Main branch renamed in the PR
- **WHEN** the ready head sets `main_branch: attacker-branch`, and `attacker-branch` on GitHub has `pr.merge: agent` while the default branch has `pr.merge: user`
- **THEN** the policy is read from the default branch, the report names `pr.merge` with main's value `user`, and no merge request is sent before the user answers

### Requirement: Required reviewers are those of the authorizing set
The agent SHALL merge a head only when every `required` reviewer of the authorizing reviewer set (main's, or the head's after the user confirmed a difference) reported on that head, whatever reviewers watch's wait started with. When they have not, watch SHALL send no merge request and SHALL wait again with the authorizing set.

#### Scenario: Wait started with an edited set
- **WHEN** main and the ready head both require `chatgpt-codex-connector`, the local checkout requires only `someone-else`, and `someone-else` reported on the ready head while `chatgpt-codex-connector` did not
- **THEN** no merge request is sent, and watch waits on the head with `chatgpt-codex-connector` as a required reviewer

#### Scenario: Authorizing reviewer reported
- **WHEN** the wait started with an edited set, was restarted with main's set, and `chatgpt-codex-connector` then reported on the head with nothing else outstanding
- **THEN** watch merges the PR at that head

#### Scenario: Archive head carry-over
- **WHEN** the archive head was watched without reviewers because `archive-only` judged it archive-only, and on the ready head before the archive only `someone-else` reported while main requires `chatgpt-codex-connector`
- **THEN** no merge request is sent for the archive head until `chatgpt-codex-connector` reported

#### Scenario: Store-backed pair with main's reviewers
- **WHEN** main has `pr.merge: agent`, `planning_store.reviewers` requires `chatgpt-codex-connector`, it reported on the store PR's ready head `s1`, the code PR is ready at `c1` with its required reviewers reported, and nothing drifts
- **THEN** the store PR is merged at `s1` and then the code PR at `c1`, with no wait restarted

### Requirement: A policy difference needs the user
When the ready head's `pr.merge`, `pr.merge_method`, `pr.delete_branch`, `pr.reviewers` or `planning_store.reviewers` differ from main's, watch SHALL list each difference (key, main's value, head's value). It SHALL ask before merging only when the head's `pr.merge` is `agent` and the head's required reviewers reported; a yes merges at the ready head with the head's method. Otherwise, and on no, it SHALL report ready and send no merge request.

#### Scenario: Required reviewer replaced
- **WHEN** main's `pr.reviewers` has `chatgpt-codex-connector` as `required`, the ready head's has only `someone-else` as `required`, the head has `pr.merge: agent`, and `someone-else` reported
- **THEN** watch lists `pr.reviewers` with both values and asks, and no merge request is sent before the answer

#### Scenario: User confirms the difference
- **WHEN** the only difference is `merge_method` (main `merge`, head `squash`), both have `pr.merge: agent`, and the user answers yes
- **THEN** the merge request names method `squash` and the ready head

#### Scenario: User declines
- **WHEN** the policy differs, the head has `pr.merge: agent`, and the user answers no
- **THEN** watch reports the PR ready for the user to merge, and no merge request is sent

#### Scenario: Neither copy opts in
- **WHEN** main and the ready head both have `pr.merge: user` and their `pr.reviewers` differ
- **THEN** watch lists the difference, reports ready, asks no merge question, and sends no merge request

#### Scenario: PR turns agent merge off
- **WHEN** main has `pr.merge: agent` and the ready head has `pr.merge: user`
- **THEN** watch lists `pr.merge` with both values, reports ready, asks no merge question, and sends no merge request

#### Scenario: Head moves after the answer
- **WHEN** the user confirmed a difference at head `abc123`, and `def456` is pushed before the merge request
- **THEN** no merge request is sent for `def456` until its policy is read again and, if it still differs, the user answers again

#### Scenario: Formatting only
- **WHEN** the head's settings file differs from main's only in comments, key order or quoting, with the same parsed values
- **THEN** no difference is reported, and the merge goes ahead as when the files are equal

### Requirement: An unknown policy merges nothing
When main's or the ready head's settings file cannot be read from GitHub (a failed or cut-off read, a response that is not a file, a file that does not parse), or the head has no settings file, the merge policy SHALL count as unknown: watch SHALL report ready, say the policy could not be read and why, and send no merge request. Only a missing file on main SHALL be read as an empty settings file.

#### Scenario: Read fails
- **WHEN** reading main's settings file fails with a network error
- **THEN** watch reports `merge policy unknown` with the error, and no merge request is sent

#### Scenario: No settings file at the head
- **WHEN** main has `pr.merge: agent` and the ready head has no `openspec/specwright.yaml`
- **THEN** watch reports `merge policy unknown` naming the head, and no merge request is sent

#### Scenario: Read succeeds after a failure
- **WHEN** one read failed and watch reaches the merge step again, and both reads now succeed with no difference and the required reviewers reported
- **THEN** watch merges the PR

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
- **WHEN** `pr.merge` is `yes` on main and at the head, and watch finds the PR ready
- **THEN** watch reports `pr.merge: yes is not user or agent; treated as user`, reports ready, and merges nothing

#### Scenario: Local finish ignores the setting
- **WHEN** `pr.merge` is `agent` and `finish` is `local`
- **THEN** finish merges locally as before, and no GitHub merge request is sent

### Requirement: Agent mode archives before merging without asking
When main's `pr.merge` is `agent`, the ready head's merge policy does not differ from main's and main's required reviewers reported on it, and watch finds a change branch's PR ready and the change is not yet archived on the branch, watch SHALL run the archive workflow without asking, then watch the archive head until it is ready before merging. Otherwise (main's `pr.merge` is `user`, the policy differs or is unknown) watch SHALL keep asking before it archives.

#### Scenario: Ready change, not archived
- **WHEN** main's `pr.merge` is `agent`, the ready head's policy matches main's, and watch finds `feat/<change>` ready with `openspec/changes/<change>/` still present
- **THEN** watch archives the change and pushes the archive commit without asking, and sends no merge request until the archive head is ready

#### Scenario: Archive fails
- **WHEN** main's `pr.merge` is `agent` and the archive workflow fails on the ready branch
- **THEN** watch stops, reports the archive error, and sends no merge request

#### Scenario: Branch-only agent mode asks first
- **WHEN** main's `pr.merge` is `user`, the ready head's is `agent`, and watch finds `feat/<change>` ready and not archived
- **THEN** watch asks `Ready. Archive <change-name> on this branch now?` and archives nothing before the answer
