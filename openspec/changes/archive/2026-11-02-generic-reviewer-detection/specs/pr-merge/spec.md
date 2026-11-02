# Spec Delta

## MODIFIED Requirements

### Requirement: Agent mode archives before merging without asking
When main's `pr.merge` is `agent`, the ready head's merge policy does not differ from main's, main's required reviewers reported on it, and a change branch's PR is ready with the change not yet archived, watch SHALL run the archive workflow without asking, then watch the archive head until it is ready before merging. Otherwise (main's `pr.merge` is `user`, the policy differs or is unknown) watch SHALL keep asking before it archives, except under "Looser rules hold the archive decision".

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
The agent SHALL merge a PR only at the head watch last reported ready, with that head's SHA as a condition of the merge, using `pr.merge_method` (default `merge`), fenced for the PR's repository. A head that changed after ready SHALL NOT be merged. A head judged under the archive carry-over SHALL be merged only when it is the archive head `archive-only` judged.

#### Scenario: Merge with the configured method
- **WHEN** `pr.merge_method` is `squash` and watch reports PR #12 ready at head `abc123`
- **THEN** the merge request names method `squash` and head `abc123` and runs fenced as the run login

#### Scenario: Head moved after ready
- **WHEN** a repo-local PR #12 (or a store-backed pair before either PR merged) was reported ready at `abc123`, and someone pushes `def456` before the merge request
- **THEN** GitHub refuses the merge, the PR stays open, and watch reports that the head changed and watches `def456` instead

#### Scenario: Commit after the archive head
- **WHEN** `pr.merge` is `agent`, the archive head was judged under the archive carry-over because `archive-only` judged it archive-only, and a commit `def456` lands on the branch after the archive push
- **THEN** no merge request is sent for `def456` until every required reviewer has reported on it

#### Scenario: Invalid method
- **WHEN** `pr.merge_method` is `fast-forward`
- **THEN** watch stops before any merge request and reports that the method must be merge, squash or rebase

### Requirement: Required reviewers are those of the authorizing set
The agent SHALL merge a head only when every `required` reviewer of the authorizing reviewer set (main's, or the head's after the user confirmed a difference) reported on that head under that set's report rules, whatever reviewers or rules watch's wait started with. When they have not, watch SHALL send no merge request and SHALL wait again with the authorizing set's reviewer config.

#### Scenario: Wait started with an edited set
- **WHEN** main and the ready head both require `chatgpt-codex-connector`, the local checkout requires only `someone-else`, and `someone-else` reported on the ready head while `chatgpt-codex-connector` did not
- **THEN** no merge request is sent, and watch waits on the head with `chatgpt-codex-connector` as a required reviewer

#### Scenario: Authorizing reviewer reported
- **WHEN** the wait started with an edited set, was restarted with main's set, and `chatgpt-codex-connector` then reported on the head with nothing else outstanding
- **THEN** watch merges the PR at that head

#### Scenario: Wait started with looser rules
- **WHEN** main gives required `rev-bot` a `marker` rule, the wait ran with the work tree's settings where `rev-bot` has no `report`, and its snapshot reports `rev-bot` `reported` `by: output`
- **THEN** `policy` reports `rules_mismatch`, no merge request is sent, and watch waits on the head with main's reviewer config

#### Scenario: Archive head carry-over
- **WHEN** the archive head was judged under the archive carry-over because `archive-only` judged it archive-only, and on the ready head before the archive only `someone-else` reported while main requires `chatgpt-codex-connector`
- **THEN** no merge request is sent for the archive head until `chatgpt-codex-connector` reported

#### Scenario: Store-backed pair with main's reviewers
- **WHEN** main has `pr.merge: agent`, `planning_store.reviewers` requires `chatgpt-codex-connector`, it reported on the store PR's ready head `s1`, the code PR is ready at `c1` with its required reviewers reported, and nothing drifts
- **THEN** the store PR is merged at `s1` and then the code PR at `c1`, with no wait restarted

### Requirement: A policy difference needs the user
When the ready head's `pr.merge`, `pr.merge_method`, `pr.delete_branch`, `pr.reviewers` or `planning_store.reviewers` differ from main's, watch SHALL list each difference (key, main's value, head's value). It SHALL ask before merging only when the head's `pr.merge` is `agent` and its required reviewers reported under any report rules; a yes merges the ready head with the head's method once they reported under its rules. Otherwise, and on no, it SHALL report ready and send no merge request.

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

#### Scenario: Reviewer settings differ
- **WHEN** the head changes a required reviewer's `report`, the head has `pr.merge: agent`, and the wait ran under main's rules, so `reported.head` is not `ok` only through `rules_mismatch`
- **THEN** watch lists the difference and asks; on yes it waits again with the head's reviewer config and merges once `reported.head` is `ok`

## ADDED Requirements

### Requirement: Looser rules hold the archive decision
When main's `pr.merge` is `agent`, the policy does not differ, and `policy` reports `rules_mismatch` for main's set at the archive decision, watch SHALL archive nothing, ask nothing, and wait on the ready head with main's reviewer config.

#### Scenario: Looser rules at the archive decision
- **WHEN** main's `pr.merge` is `agent`, and at the archive decision `policy` reports `rules_mismatch` for main's set because the wait ran with the work tree's looser report rules
- **THEN** watch archives nothing yet, asks nothing, and waits on the ready head with main's reviewer config

#### Scenario: User mode keeps asking
- **WHEN** main's `pr.merge` is `user` and `policy` reports `rules_mismatch` for main's set at the archive decision
- **THEN** watch asks `Ready. Archive <change-name> on this branch now?` without another wait
