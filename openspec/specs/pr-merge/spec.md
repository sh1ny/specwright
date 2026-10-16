# pr-merge Specification

## Purpose

Decides when Specwright merges a pull request itself, which happens only when the project opts in and the PR is ready, and how the merge is made, checked and cleaned up, so the agent never merges without consent or merges an unreviewed head.

## Requirements

### Requirement: Merging is opt-in
Specwright SHALL merge a pull request only when `pr.merge` is `agent` and `finish` is `pr`. With `pr.merge` absent, `user` or any other value, no skill or script SHALL merge a PR, and watch SHALL report ready and stop as before. An unrecognised `pr.merge` value SHALL be reported as treated like `user`.

#### Scenario: Default project never merges
- **WHEN** `openspec/specwright.yaml` has no `pr.merge` key, `finish` is `pr`, and watch finds the archived change's PR ready
- **THEN** watch reports ready and stops, and no merge request is sent to GitHub

#### Scenario: Opted-in project merges
- **WHEN** `pr.merge` is `agent`, `finish` is `pr`, and watch finds the archived change's PR ready
- **THEN** watch merges the PR, and GitHub shows it MERGED

#### Scenario: Unrecognised value
- **WHEN** `pr.merge` is `yes` and watch finds the PR ready
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
With `pr.merge: agent`, when watch finds a change branch's PR ready and the change is not yet archived on the branch, watch SHALL run the archive workflow without asking, then watch the archive head until it is ready before merging. With `pr.merge: user` watch SHALL keep asking before it archives.

#### Scenario: Ready change, not archived
- **WHEN** `pr.merge` is `agent` and watch finds `feat/<change>` ready with `openspec/changes/<change>/` still present
- **THEN** watch archives the change and pushes the archive commit without asking, and sends no merge request until the archive head is ready

#### Scenario: Archive fails
- **WHEN** `pr.merge` is `agent` and the archive workflow fails on the ready branch
- **THEN** watch stops, reports the archive error, and sends no merge request

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
