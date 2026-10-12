# Spec Delta

## ADDED Requirements

### Requirement: The archive head gets no new review round
With `pr.review_after_archive` `false` (the default), after a change's archive commit is pushed, watch SHALL post no review request and SHALL count each required reviewer's report on the previous head as valid for the archive head, provided the archive commit is the only commit after that head and touches only the change's archive paths and the main specs it synced.

#### Scenario: Archive pushed after a clean review
- **WHEN** Codex reported on head `h1` with no findings, and watch pushes the archive commit `h2` whose parent is `h1`
- **THEN** no `@codex review` comment is posted on `h2`, and readiness of `h2` does not wait for Codex, only for CI, mergeability and new feedback

#### Scenario: Setting turned on
- **WHEN** `pr.review_after_archive` is `true` and watch pushes the archive commit
- **THEN** review requests are posted again on the archive head and watch waits for the required reviewers, as in 0.1.13

#### Scenario: Archive commit touches other files
- **WHEN** the archive commit also changes a file outside `<P>/changes/archive/<archived-name>/` and the synced main specs
- **THEN** reports on the previous head do not carry over, and review requests are posted on the archive head

#### Scenario: Another commit after the reviewed head
- **WHEN** a fix commit sits between the last reviewed head and the archive commit
- **THEN** reports do not carry over, and the fix is reviewed as after any fix push

#### Scenario: Branch protection wants a fresh approval
- **WHEN** reports carried over to the archive head, CI passed, and the head is short of ready only because `merge_state` is BLOCKED with `review_decision` `REVIEW_REQUIRED`
- **THEN** watch reports `archive head needs a fresh approval` and asks once whether to post the review requests, and does not keep waiting without asking

#### Scenario: Store-backed archive
- **WHEN** a store-backed change's archive commit is pushed to the store PR, and the store PR's required reviewers reported on its previous head
- **THEN** the same rule applies to the store PR: no request is posted and their reports carry over
