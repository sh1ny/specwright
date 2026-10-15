# Spec Delta

## ADDED Requirements

### Requirement: Install checks the OpenSpec version against the pin
Before it writes any file, the install prompt SHALL compare the version that `openspec --version` reports with the downloaded copy's `OPENSPEC_VERSION` and SHALL require an exact match. A different version, newer patch releases included, and output with no version number in it SHALL count as a mismatch.

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

#### Scenario: Downloaded copy has no pin file
- **WHEN** the downloaded copy has no `OPENSPEC_VERSION` file, or it is empty
- **THEN** the install stops before Step 4, says the downloaded copy names no pinned OpenSpec version, and writes no file

#### Scenario: Root check fails on an unpinned OpenSpec
- **WHEN** `openspec --version` prints `1.13.0`, the README's pin is `1.14.1`, and `openspec list --json` reports no root
- **THEN** the install stops in Step 1, names `1.13.0` and `npm i -g @fission-ai/openspec@1.14.1`, does not suggest `openspec init`, and writes no file

#### Scenario: OpenSpec missing
- **WHEN** `openspec --version` fails
- **THEN** the install stops in Step 1 and tells the user to run `npm i -g @fission-ai/openspec@<pin>`, with the pin from the README's own install command

### Requirement: Explicit override of the OpenSpec pin
On a version mismatch the install SHALL continue only when the user has said in their own words to continue with the found version, naming that version (for example `continue with OpenSpec 1.15.0`), in the request or in a reply. The install SHALL NOT offer the override as a default or a recommendation, and SHALL NOT infer it from a general confirmation.

#### Scenario: Override stated
- **WHEN** `openspec --version` prints `1.15.0`, the pin is `1.14.1`, and the user's request says `continue with OpenSpec 1.15.0`
- **THEN** the install completes and stamps `openspec/.specwright/VERSION`, and the report shows `OpenSpec 1.15.0 (pinned 1.14.1, override)`

#### Scenario: General confirmation is not an override
- **WHEN** the install has stopped on a mismatch (`1.15.0` found, `1.14.1` pinned) and the user replies `yes, go ahead`
- **THEN** the install still does not write any file, and it asks the user to install `1.14.1` or to state the override with the found version

#### Scenario: Override names another version
- **WHEN** `openspec --version` prints `1.15.0` and the user's request says `continue with OpenSpec 1.16.0`
- **THEN** the install stops before Step 4 as on a mismatch, and the message names `1.15.0` as the version found

### Requirement: Public install commands name the pinned version
Every OpenSpec install command in the README (the prerequisites and install Step 1) and in `CONTRIBUTING.md` SHALL install `@fission-ai/openspec@<pin>`, and the README's OpenSpec badge SHALL show `<pin>`, where `<pin>` is the content of `OPENSPEC_VERSION`. The README SHALL NOT describe a later OpenSpec version as supported.

#### Scenario: Commands match the pin
- **WHEN** `OPENSPEC_VERSION` holds `1.14.1`
- **THEN** the README prerequisites, install Step 1 and `CONTRIBUTING.md` each contain `npm i -g @fission-ai/openspec@1.14.1`, no unversioned `npm i -g @fission-ai/openspec` remains, and the badge reads `OpenSpec-1.14.1`

#### Scenario: Pin bumped in one place only
- **WHEN** `OPENSPEC_VERSION` is changed to `1.15.0` while the README still names `@1.14.1`
- **THEN** the regression test in `evals/git-workflow` fails and names the README line that disagrees
