# pr-merge Specification

## Purpose

Decides when Specwright merges a pull request itself, which happens only when the project opts in and the PR is ready, and how the merge is made, checked and cleaned up, so the agent never merges without consent or merges an unreviewed head.

## Requirements

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

### Requirement: An agent merge needs a required reviewer
With `pr.merge: agent`, the agent SHALL merge a PR only when its repository's reviewer set (`pr.reviewers`; for the store PR, `planning_store.reviewers`) has at least one `required` reviewer. Otherwise watch SHALL report ready, state `agent merge needs a required reviewer in pr.reviewers`, and merge nothing.

#### Scenario: Required reviewer configured
- **WHEN** `pr.merge` is `agent`, `pr.reviewers` has `chatgpt-codex-connector` with `role: required`, and watch finds the archived change's PR ready after that reviewer reported
- **THEN** watch merges the PR

#### Scenario: No required reviewer
- **WHEN** `pr.merge` is `agent`, `pr.reviewers` is absent and `review_request.body` is `@codex review`, and watch finds the PR ready
- **THEN** watch reports ready with `agent merge needs a required reviewer in pr.reviewers`, and no merge request is sent

#### Scenario: Store without a required reviewer
- **WHEN** `pr.merge` is `agent`, the code PR has a required reviewer, and `planning_store.reviewers` is `{}`
- **THEN** neither PR is merged, and the report names the store's reviewer set

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

### Requirement: Only the ready head is merged
The agent SHALL merge a PR only at the head watch last reported ready, with that head's SHA as a condition of the merge, using `pr.merge_method` (default `merge`), fenced for the PR's repository. A head that changed after ready SHALL NOT be merged. A head watched without reviewers SHALL be merged only when it is the archive head `archive-only` judged.

#### Scenario: Merge with the configured method
- **WHEN** `pr.merge_method` is `squash` and watch reports PR #12 ready at head `abc123`
- **THEN** the merge request names method `squash` and head `abc123` and runs fenced as the run login

#### Scenario: Head moved after ready
- **WHEN** a repo-local PR #12 (or a store-backed pair before either PR merged) was reported ready at `abc123`, and someone pushes `def456` before the merge request
- **THEN** GitHub refuses the merge, the PR stays open, and watch reports that the head changed and watches `def456` instead

#### Scenario: Commit after the archive head
- **WHEN** `pr.merge` is `agent`, the archive head was watched without reviewers because `archive-only` judged it archive-only, and a commit `def456` lands on the branch after the archive push
- **THEN** no merge request is sent for `def456` until every required reviewer has reported on it

#### Scenario: Invalid method
- **WHEN** `pr.merge_method` is `fast-forward`
- **THEN** watch stops before any merge request and reports that the method must be merge, squash or rebase

### Requirement: A refused merge stops
When GitHub refuses a merge (branch protection, a merge queue, a method the repository disallows, a conflict or a changed head), the agent SHALL stop with GitHub's message and leave the PR open. It SHALL NOT retry with another method, use administrator rights, enable auto-merge, add the PR to a merge queue or dismiss a review.

#### Scenario: Method disallowed
- **WHEN** the repository allows only squash merges and `pr.merge_method` is `merge`
- **THEN** watch reports GitHub's refusal, the PR stays open, and no second merge request with another method is sent

#### Scenario: Merge queue required
- **WHEN** the base branch requires a merge queue
- **THEN** watch reports that GitHub refused the direct merge and that the user merges this PR, and neither enables auto-merge nor queues the PR

### Requirement: The merge is confirmed before cleanup
After a merge request, the agent SHALL read the PR back from GitHub and run cleanup only when it is MERGED. When the read fails, the merge state SHALL count as unknown: no branch is deleted, and the user is told to check the PR.

#### Scenario: Merge confirmed
- **WHEN** the merge request succeeds and the PR reads back as MERGED
- **THEN** watch runs Cleanup after merge for the PR

#### Scenario: Read-back fails
- **WHEN** the merge request returns but reading the PR back fails
- **THEN** watch reports the merge state as unknown, deletes no local or remote branch, and stops

### Requirement: Cleanup after an agent merge
After a confirmed agent merge, the agent SHALL run the existing Cleanup after merge (check out main, fenced `pull --ff-only`, local branch deletion only under the branch-check rule, the issues-left-open backstop), then offer one `specwright-roadmap` mode: **close** when the Now milestone is then done, else **next**.

#### Scenario: Squash merge cleans up
- **WHEN** a squash merge of `feat/<change>` is confirmed and main pulls cleanly
- **THEN** the repo is on an up-to-date main, `feat/<change>` is deleted locally because its tip is the merged PR's head, and **next** or **close** is offered

#### Scenario: Pull fails after the merge
- **WHEN** the merge is confirmed but `git pull --ff-only` on main fails
- **THEN** cleanup stops with the pull error, no local or remote branch is deleted, and the PR stays merged

### Requirement: The remote branch is deleted only at the merged head
With `pr.merge: agent` and `pr.delete_branch` true (the default), Cleanup after merge SHALL delete a merged PR's remote branch only while it still points at the merged head and no open PR uses it as a base, whoever merged the PR. Otherwise it SHALL keep the branch and say why. With `pr.delete_branch` false or `pr.merge: user` it SHALL NOT delete it.

#### Scenario: Remote branch deleted
- **WHEN** PR #12 from `feat/<change>` merged at `abc123`, the remote branch is at `abc123`, and no open PR is based on it
- **THEN** the remote branch `feat/<change>` no longer exists on GitHub

#### Scenario: Remote branch moved
- **WHEN** the remote branch was pushed to `def456` after the merge of `abc123`
- **THEN** the remote branch is kept at `def456`, and the report names the commit the merge did not include

#### Scenario: Another PR is based on the branch
- **WHEN** an open PR has `feat/<change>` as its base
- **THEN** the remote branch is kept, and the report names that PR

#### Scenario: User mode keeps remote branches
- **WHEN** `pr.merge` is `user`, the user merged PR #12 and cleanup runs
- **THEN** the remote branch `feat/<change>` still exists on GitHub

#### Scenario: Already deleted by GitHub
- **WHEN** the repository deletes head branches on merge and `feat/<change>` is already gone
- **THEN** the remote deletion counts as done, and nothing is reported as failed

### Requirement: Store-backed changes merge as a pair
For a store-backed change, the agent SHALL merge only when watch reports every expected PR of the change ready in the same check, merging the store PR first and then the code PR. When the second merge ends other than merged (refused, head changed, unknown), it SHALL stop, report `planning merged, code pending` and clean up only the store; a later watch stops too, and the user merges the code PR.

#### Scenario: Both merge
- **WHEN** the store and code PRs are both ready
- **THEN** the store PR is merged, then the code PR, and cleanup runs in both repos

#### Scenario: Code merge refused
- **WHEN** the store PR merges and GitHub refuses the code PR's merge, by policy or because the code head changed after ready
- **THEN** watch reports `planning merged, code pending` with GitHub's message, cleans up only the store, leaves the code PR and branch as they are, and does not watch the code PR again

#### Scenario: Watch after a split
- **WHEN** the store PR is merged, the code PR is still open, and watch starts again
- **THEN** watch stops with the split hand-off and sends no merge request; after the user merges the code PR, Cleanup after merge runs for the code repo

#### Scenario: Only one PR ready
- **WHEN** the code PR is ready and the store PR still has pending checks
- **THEN** no PR is merged, and watch keeps waiting

### Requirement: Roadmap branches merge like changes
With `pr.merge: agent`, a roadmap branch (`docs/project-baseline`, `docs/close-<milestone>`) that watch reports ready SHALL be merged and cleaned up the same way, with nothing to archive first. Other branches that are neither a change branch nor a roadmap branch SHALL NOT be merged.

#### Scenario: Close branch merges
- **WHEN** `pr.merge` is `agent` and watch reports `docs/close-m2` ready
- **THEN** the PR is merged at its ready head, main is pulled and the local branch deleted under the branch-check rule

#### Scenario: Unknown branch
- **WHEN** `pr.merge` is `agent` and watch reports a PR from `experiment/foo` ready
- **THEN** watch reports ready and stops without merging

### Requirement: Finish hands a PR to watch in agent mode
With `pr.merge: agent`, after `specwright-finish` ships the archive commit, it SHALL continue in watch with the run login, instead of reporting `Ready to merge on GitHub` and offering watch. With `pr.merge: user` the finish report SHALL stay as it is.

#### Scenario: Archive outside watch
- **WHEN** `pr.merge` is `agent` and the user runs the archive workflow, so finish ships the archive commit
- **THEN** finish starts watch on the PR with the run login, and does not print `Ready to merge on GitHub`

#### Scenario: Ship fails
- **WHEN** `pr.merge` is `agent` and the archive commit's push fails
- **THEN** finish stops with the push error and starts no watch

### Requirement: Watch offers a release after an agent merge
With `release.enabled` true, after a confirmed agent merge and its cleanup, watch SHALL read `release.sh untagged` and offer `specwright-release` publish for each listed version oldest first, or with `release.auto` publish them oldest first, stopping at the first failure, before the roadmap offer. A publish failure SHALL NOT undo the merge or the cleanup.

#### Scenario: Unattended agent merge with auto release
- **WHEN** `pr.merge` is `agent`, `release.auto` is true, the merged PR moved `VERSION` to 0.5.0, and cleanup finished
- **THEN** watch runs publish, `v0.5.0` is on origin at the merge commit, and the roadmap mode is then offered

#### Scenario: Offer without auto
- **WHEN** `release.auto` is false and the merged version has no tag
- **THEN** watch offers publish for that version and creates no tag until the user accepts

#### Scenario: An earlier version was left untagged
- **WHEN** `release.auto` is true, 0.5.0 was never published and the agent merge moved `VERSION` to 0.5.1
- **THEN** watch publishes `v0.5.0`, then `v0.5.1`

#### Scenario: Cleanup stopped
- **WHEN** cleanup stops because `git pull --ff-only` on main failed
- **THEN** no release is offered or run, because cleanup did not finish

#### Scenario: Publish fails after the merge
- **WHEN** `release.auto` is true and publish exits non-zero
- **THEN** the PR stays merged, the report names the publish error and says a re-run of publish resumes it

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
