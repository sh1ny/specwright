# Spec Delta

## ADDED Requirements

### Requirement: Ship pushes every expected repo before it opens a PR
For a store-backed change, ship SHALL validate and push every repo of the expected set, the store first and then the code repo, before it finds, opens or updates a PR in either repo. When any push fails, ship SHALL open or update no PR in either repo, SHALL report which repo's push failed with its error, and SHALL NOT report the change ready.

#### Scenario: Both pushes succeed
- **WHEN** ship runs for a store-backed change, both PRs are expected and neither exists
- **THEN** both branches are pushed before the first PR is created, and both PRs exist and are linked at the end

#### Scenario: Code push rejected after the store push
- **WHEN** ship runs for a store-backed change with both PRs expected and neither existing, the store push succeeds and the code push is rejected
- **THEN** no PR exists in either repo, the report names the code repo's push and its error, and the change is not reported ready

#### Scenario: Code push rejected with an existing store PR
- **WHEN** the store PR already exists from an earlier ship, a new store commit is pushed, and the code push is rejected
- **THEN** no PR is opened in the code repo, no description, link comment or review request is added to the store PR, and the report names the code push failure

#### Scenario: Store push rejected
- **WHEN** the store push is rejected
- **THEN** the code repo is not pushed, no PR is opened or updated in either repo, and the report names the store push and its error
