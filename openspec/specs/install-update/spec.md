# install-update Specification

## Purpose

Defines how the install/update prompt merges a project's Specwright settings with the downloaded template, so an update keeps every setting the project uses and asks only about real differences.

## Requirements

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

### Requirement: Update stages the new version before it swaps it in
The install/update SHALL copy every new skill directory, agent file and the schema into a staging location and verify the staged copy before it changes any installed file. Until the swap starts, every installed `specwright-*` skill directory, agent file and the schema SHALL keep its previous content, so the previous version stays runnable.

#### Scenario: Update completes
- **WHEN** an update from 0.5.0 to 0.6.0 runs without interruption
- **THEN** every chosen skills directory holds exactly the 0.6.0 `specwright-*` directories, the schema matches the 0.6.0 copy, `openspec/.specwright/VERSION` reads `0.6.0`, and no staging or previous-version directory is left

#### Scenario: Interrupted before the swap
- **WHEN** an update from 0.5.0 to 0.6.0 is stopped after any step before the swap (download, staging of any skill, agent or schema, verification of the staged copy)
- **THEN** every installed skill directory, agent file and the schema are byte-identical to 0.5.0, `openspec schema validate specwright` passes, and `openspec/.specwright/VERSION` still reads `0.5.0`

#### Scenario: Staged copy fails verification
- **WHEN** a staged skill directory differs from the downloaded one (a file missing or changed)
- **THEN** the update stops before the swap, names the file, removes the staging location and leaves the installed version and `VERSION` unchanged

### Requirement: Interrupted swap resumes or rolls back
The install/update SHALL record each step in a journal, `openspec/.specwright/update.json`, before it takes the step. A run that finds a journal whose swap had started SHALL finish it (resume) when the staged copy is complete, else restore the previous version (roll back); one whose swap had not started SHALL discard the staging. It SHALL say which it did. The journal SHALL be removed only after `VERSION` is written and the previous copy is removed.

#### Scenario: Rerun after an interruption before the swap
- **WHEN** an update to 0.6.0 was stopped after staging, before any installed file was swapped, and the user reruns the update
- **THEN** the rerun deletes the old staging, reports `discarded unfinished update to 0.6.0`, and stages again from the new download

#### Scenario: Interrupted during the swap, staged copy complete
- **WHEN** an update to 0.6.0 is stopped after some skill directories were swapped and the journal names a complete, verified staged copy
- **THEN** the next run resumes: every target holds 0.6.0, `VERSION` reads `0.6.0`, the journal is gone, and the report says `resumed update to 0.6.0`

#### Scenario: Interrupted during the swap, staged copy incomplete
- **WHEN** the journal exists but the staged copy it names is missing or fails verification
- **THEN** the next run restores every swapped target from the previous copy, `VERSION` still reads the previous version, the journal is gone, and the report says `rolled back to <previous>`

#### Scenario: Journal from another version
- **WHEN** the journal records an update to 0.6.0 and the user now runs the update with a 0.6.1 download
- **THEN** the run first resumes or rolls back the 0.6.0 update as above and reports it, and only then starts the 0.6.1 update

### Requirement: Update installs a release tag by default
The install/update SHALL download the latest release tag (`v<version>`) of the repository unless the user names a version or asks for `main`, and SHALL report the ref it installed. It SHALL fall back to `main` only when no tag exists. A chosen ref older than the prompt's minimum release (0.6.0), or whose update script reports another interface than the prompt drives, SHALL be refused before staging, offering `main`.

#### Scenario: Latest tag
- **WHEN** the repository has tags `v0.5.0` and `v0.6.0` and the user names no version
- **THEN** the update installs the `v0.6.0` tree and the report names `v0.6.0`

#### Scenario: Named version has no tag
- **WHEN** the user asks for version 0.7.0 and the repository has no tag `v0.7.0`
- **THEN** the update stops before staging, names `v0.7.0` and the tags that exist, and writes no file

#### Scenario: Named version predates the update script
- **WHEN** the user asks for version 0.5.0 and the tag `v0.5.0` exists
- **THEN** the update stops before staging, says versions before 0.6.0 cannot be installed by this update, and writes no file

#### Scenario: Latest tag predates the update script
- **WHEN** the user names no version and the highest tag is `v0.5.0` (this prompt's change is merged but 0.6.0 is not yet released)
- **THEN** the update stops before staging, names `v0.5.0` and the minimum release 0.6.0, offers to install `main`, and writes no file

#### Scenario: Script interface differs from the prompt
- **WHEN** the downloaded update script reports an interface the prompt does not drive
- **THEN** the update stops before staging, names the ref and both interfaces, and writes no file

#### Scenario: No tags
- **WHEN** the repository has no release tag
- **THEN** the update installs `main` and the report says `main (no release tag)`

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

### Requirement: Update finds changes in flight on their branches
A change in flight SHALL be each change directory in the planning repo's working tree other than `archive/`, and each local `<prefix>/<change-name>` branch (any worktree) holding `<P>/changes/<change-name>/` while the planning main has no archive named `<change-name>` or `YYYY-MM-DD-<change-name>`. A change on a branch SHALL be read from that branch. A change found only on a remote-tracking ref SHALL be reported as a warning, not validated.

#### Scenario: Change in flight on its branch only
- **WHEN** the update runs from main, the working tree has no change directory, and branch `feat/add-x` holds `openspec/changes/add-x/`, which fails validation against the 0.6.0 schema
- **THEN** the update stops before the swap and names `add-x` and `feat/add-x`

#### Scenario: Branch whose change is archived
- **WHEN** branch `feat/add-z` still exists but main holds `openspec/changes/archive/2026-10-01-add-z/`
- **THEN** `add-z` is not counted as in flight and is not validated

#### Scenario: Archive of a longer name
- **WHEN** branch `feat/add-z` holds `openspec/changes/add-z/` and main holds only `openspec/changes/archive/2026-10-01-fix-add-z/`
- **THEN** `add-z` is counted as in flight and validated

#### Scenario: Change only on a remote branch
- **WHEN** `origin/feat/add-v` holds `openspec/changes/add-v/`, there is no local `feat/add-v`, and main has no archive of `add-v`
- **THEN** the workflow update does not validate `add-v`, is not refused because of it, and the report lists `add-v` on `origin/feat/add-v` as a warning: in flight elsewhere, not validated

### Requirement: Update report tells running sessions to restart
After a swap, the install/update report SHALL say that agent sessions started before the update still run the previous version's skills and must be restarted before they continue a change, naming the previous and the new version. A run that changed no installed file SHALL NOT give this notice.

#### Scenario: Version changed
- **WHEN** an update from 0.5.0 to 0.6.0 completes
- **THEN** the report says sessions started before the update run 0.5.0 and must be restarted before they continue a change on 0.6.0

#### Scenario: Refused update
- **WHEN** an update stops before the swap (a failed check or a refused workflow update)
- **THEN** the report gives no restart notice and says the installed version is unchanged
