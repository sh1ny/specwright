# Spec Delta

## ADDED Requirements

### Requirement: PR-item issues are found in one read per pass
With `pr.after_limit: issues`, a feedback pass SHALL find the existing issues for its actionable items in one bounded read of each repository's issues (one for a repo-local pass, at most two for a store-backed one), as that repository's login, whatever the number of items. Each item is matched by its `specwright:pr-item <item id>` marker line. When the read fails or passes its bound, the pass SHALL create no issue for any item and SHALL report the lookup as not done.

#### Scenario: Several findings, some already tracked
- **WHEN** a pass past the round limit has three actionable items, and an issue with the marker of the second one already exists
- **THEN** the repository's issue list is read once, the second item is answered with that issue, and only the first and third get new issues

#### Scenario: Store-backed pass with items in both repositories
- **WHEN** a store-backed pass past the round limit has two actionable items on the code PR and one on the store PR
- **THEN** the code repository's issues are read once as the code login and the store's once as the store login, and each item is matched only in its own repository

#### Scenario: Pull requests carrying the marker
- **WHEN** a pull request's body, not an issue's, contains an item's marker
- **THEN** the pull request is not taken as that item's issue, and the item gets a new issue

#### Scenario: Issue list cannot be read
- **WHEN** the issue read fails or passes its deadline or size bound
- **THEN** no issue is created in that pass, each item is left unanswered, and the pass reports the lookup as not done with the error name
