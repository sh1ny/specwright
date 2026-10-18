# Spec Delta

## MODIFIED Requirements

### Requirement: Install checks the OpenSpec version against the pin
Before it writes any file, the install prompt SHALL compare the version that `openspec --version` reports with the downloaded copy's `OPENSPEC_VERSION` and SHALL require an exact match. A different version, newer patch releases included, and output with no version number in it SHALL count as a mismatch. A version token directly followed by another version character (a digit, letter, `.`, `+` or `-`) SHALL count as output with no version number.

#### Scenario: Pinned version installed
- **WHEN** `openspec --version` prints `1.14.1` and the downloaded `OPENSPEC_VERSION` is `1.14.1`
- **THEN** the install continues to Step 4, and the report shows `OpenSpec 1.14.1 (pinned)`

#### Scenario: Newer patch release installed
- **WHEN** `openspec --version` prints `1.14.2` and the downloaded `OPENSPEC_VERSION` is `1.14.1`, and the user has not stated the override
- **THEN** the install stops before Step 4, and the message names `1.14.2`, `1.14.1` and `npm i -g @fission-ai/openspec@1.14.1`
- **AND** no skill, agent, schema, `config.yaml` or `specwright.yaml` file is created or changed, and `openspec/.specwright/VERSION` keeps its previous content (or stays absent)

#### Scenario: Pre-release of the pinned version installed
- **WHEN** `openspec --version` prints `1.14.1-beta.1` and the downloaded `OPENSPEC_VERSION` is `1.14.1`
- **THEN** the install stops before Step 4 as on a mismatch, and the message names `1.14.1-beta.1` as the version found

#### Scenario: Build of the pinned version installed
- **WHEN** `openspec --version` prints `1.14.1+vendor.1` and the downloaded `OPENSPEC_VERSION` is `1.14.1`
- **THEN** the install stops before Step 4 as on a mismatch, and the message names `1.14.1+vendor.1` as the version found

#### Scenario: Version output has no version number
- **WHEN** `openspec --version` exits 0 but its output contains no `<major>.<minor>.<patch>` number
- **THEN** the install stops before Step 4 as on a mismatch, showing the output it could not read

#### Scenario: Version token runs into other version characters
- **WHEN** `openspec --version` prints `1.14.1.0` or `1.14.1vendor` and the downloaded `OPENSPEC_VERSION` is `1.14.1`
- **THEN** the install stops before Step 4 as on output with no version number, showing that output, and writes no file

#### Scenario: Root check reads a run-on version token
- **WHEN** `openspec --version` prints `1.14.1vendor` and `openspec list --json` reports no root
- **THEN** the install stops in Step 1 treating the version as unreadable, names the pin `1.14.1` and `npm i -g @fission-ai/openspec@1.14.1`, does not suggest `openspec init`, and writes no file

#### Scenario: Downloaded copy has no pin file
- **WHEN** the downloaded copy has no `OPENSPEC_VERSION` file, or it is empty
- **THEN** the install stops before Step 4, says the downloaded copy names no pinned OpenSpec version, and writes no file

#### Scenario: Root check fails on an unpinned OpenSpec
- **WHEN** `openspec --version` prints `1.13.0`, the README's pin is `1.14.1`, and `openspec list --json` reports no root
- **THEN** the install stops in Step 1, names `1.13.0` and `npm i -g @fission-ai/openspec@1.14.1`, does not suggest `openspec init`, and writes no file

#### Scenario: OpenSpec missing
- **WHEN** `openspec --version` fails
- **THEN** the install stops in Step 1 and tells the user to run `npm i -g @fission-ai/openspec@<pin>`, with the pin from the README's own install command

### Requirement: Workflow update validates changes in flight
An update whose major or minor version differs from the installed one, or with no installed `VERSION`, is a workflow update. It SHALL validate every change in flight (as found by the rule below) against the new schema when it plans, and again at the swap. A failure, or a set of changes that differs at the swap, SHALL stop it before the swap, naming the change and the error, and write no file. A patch update SHALL skip this check.

#### Scenario: Changes in flight still validate
- **WHEN** an update from 0.5.0 to 0.6.0 runs with change `add-x` in flight, and `add-x` validates against the 0.6.0 schema
- **THEN** the update completes and the report lists `add-x` as validated against 0.6.0

#### Scenario: A change in flight fails
- **WHEN** an update from 0.5.0 to 0.6.0 runs with change `add-x` in flight, and `add-x` fails validation against the 0.6.0 schema
- **THEN** the update stops before the swap, names `add-x` and the validation error, and every installed file and `VERSION` are unchanged

#### Scenario: Change started after planning
- **WHEN** a 0.5.0 → 0.6.0 update has planned with no change in flight, and before its swap a session creates branch `feat/add-w` holding `openspec/changes/add-w/`
- **THEN** the swap collects `add-w`, stops before any rename because the set differs from the plan, names `add-w`, and leaves every installed file unchanged

#### Scenario: Patch update with a change in flight
- **WHEN** a repo-local project updates from 0.6.0 to 0.6.1 with change `add-x` in flight
- **THEN** the update completes without validating `add-x` against the new schema

## ADDED Requirements

### Requirement: A refused change is also checked against the installed schema
When a change in flight fails validation against the target version, at the plan or at the swap, the update SHALL also validate it against the schema installed on disk, labelled with that schema's version. Only when that schema itself validates and the change fails against it SHALL the refusal say the change already fails on that version, name that error, and say the update did not cause it. The refusal itself SHALL stay unchanged.

#### Scenario: Change already incomplete on the installed version
- **WHEN** an update from 0.4.2 to 0.6.0 runs with change `platform-backlog` in flight, whose `tasks.md` exists while `review.md` does not, and it fails `openspec status` against both schemas
- **THEN** the update stops before the swap as before, and the message names `platform-backlog`, says it already fails on 0.4.2 with the same check, and says the update to 0.6.0 did not cause it

#### Scenario: Change fails only on the target
- **WHEN** an update from 0.5.0 to 0.6.0 runs with change `add-x` in flight, and `add-x` validates against the installed 0.5.0 schema but fails against 0.6.0
- **THEN** the refusal names `add-x` and the 0.6.0 error, and does not say the change already fails on 0.5.0

#### Scenario: Installed schema fails under the current OpenSpec
- **WHEN** an update from 0.4.2 to 0.6.0 refuses change `add-x`, and the installed 0.4.2 schema itself fails `openspec schema validate` under the OpenSpec now installed
- **THEN** the refusal names `add-x` and the 0.6.0 error, and makes no claim that `add-x` already fails on 0.4.2

#### Scenario: OpenSpec fails during the installed check
- **WHEN** an update from 0.5.0 to 0.6.0 refuses change `add-x`, and `openspec validate` exits non-zero without a validation result when run against the installed 0.5.0 schema
- **THEN** the refusal names `add-x` and the 0.6.0 error, and makes no claim that `add-x` already fails on 0.5.0

#### Scenario: No installed schema to compare with
- **WHEN** a workflow update with no installed `VERSION` refuses change `add-x`
- **THEN** the refusal names `add-x` and the target's error, makes no claim about an installed version, and the update writes no file
