# Spec Delta

## Purpose

Defines how the install/update prompt merges a project's Specwright settings with the downloaded template, so an update keeps every setting the project uses and asks only about real differences.

## ADDED Requirements

### Requirement: Keys commented out in the template are optional
The install prompt SHALL compare settings by dotted key path, and SHALL treat a path that appears only commented out in the downloaded template as optional and still supported: never listed as removed, never added, and not required by Step 7. Entries under `pr.reviewers` and `planning_store.reviewers` SHALL be treated as user data, never compared.

#### Scenario: Project sets an optional key
- **WHEN** the project's `openspec/specwright.yaml` sets `pr.reviewers` and `pr.request_as`, and the downloaded template has both only as commented-out lines
- **THEN** Step 6 lists neither key as missing from the template and asks no question about them, and the file keeps both values

#### Scenario: Project lacks an optional key
- **WHEN** the project's file has no `planning_store:` block and the template has it only commented out
- **THEN** Step 6 adds no `planning_store:` key, and Step 7's key check passes

#### Scenario: Reviewer entries are user data
- **WHEN** the project's file sets `pr.reviewers.kody-ai` and `pr.reviewers.chatgpt-codex-connector`, which the template does not name
- **THEN** Step 6 lists neither as removed and asks nothing about them

#### Scenario: Same name at two paths
- **WHEN** the template has `github.login` uncommented and `planning_store.login` only commented out, and the project's file sets `github.login` but not `planning_store`
- **THEN** Step 6 reports no missing key and adds no `planning_store.login`

#### Scenario: Key really removed upstream
- **WHEN** the project's file has a key that appears in the downloaded template neither as a key nor as a commented-out key
- **THEN** Step 6 lists that key and asks before removing it
