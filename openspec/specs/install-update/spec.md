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
- **THEN** every chosen skills directory holds every 0.6.0 `specwright-*` directory with the 0.6.0 content and no other `specwright-*` directory than the orphans the user chose in Step 4 to keep, the schema matches the 0.6.0 copy, `openspec/.specwright/VERSION` reads `0.6.0`, and no staging or previous-version directory is left

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
The install/update SHALL download the latest release tag (`v<version>`) of the repository unless the user names a version or asks for `main`, and SHALL report the ref it installed. It SHALL fall back to `main` only when no tag exists. A ref older than the minimum release (0.37.0, the first with `sw update`), or whose `sw update interface` is not the prompt's, SHALL be refused before any write, naming the tag's own README prompt, and offering `main` when the latest tag predates the minimum.

#### Scenario: Latest tag
- **WHEN** the repository has tags `v0.36.0` and `v0.37.0` and the user names no version
- **THEN** the update installs the `v0.37.0` tree and the report names `v0.37.0`

#### Scenario: Named version has no tag
- **WHEN** the user asks for version 0.38.0 and the repository has no tag `v0.38.0`
- **THEN** the update stops before staging, names `v0.38.0` and the tags that exist, and writes no file

#### Scenario: Named version predates the update script
- **WHEN** the user asks for version 0.36.0 and the tag `v0.36.0` exists
- **THEN** the update stops before staging, says versions before 0.37.0 cannot be installed by this prompt and that the `v0.36.0` README prompt installs it, and writes no file

#### Scenario: Latest tag predates the update script
- **WHEN** the user names no version and the highest tag is `v0.36.0` (this prompt's change is merged but 0.37.0 is not yet released)
- **THEN** the update stops before staging, names `v0.36.0` and the minimum release 0.37.0, offers to install `main`, and writes no file

#### Scenario: Script interface differs from the prompt
- **WHEN** the checked temporary `sw`'s `sw update interface` reports an interface the prompt does not drive
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

### Requirement: The release-tag lookup is bounded
The `git ls-remote --tags` that `sw update plan` runs to name the highest release tag SHALL run under a 60-second deadline and read at most 32 MiB. When it passes a bound, its process tree SHALL be stopped and the tag SHALL be reported as not named, with the limit (`deadline_exceeded` or `response_too_large`) and the command in the reason. The refusal it belongs to SHALL still be made, and nothing SHALL be written.

#### Scenario: Tags listed in time
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin lists `v0.6.0` and `v0.6.2` within the deadline
- **THEN** the `store_version` refusal names `v0.6.2`

#### Scenario: Hung tag lookup
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin never answers `git ls-remote`
- **THEN** `sw update plan` exits 1 within 60 seconds plus 10 seconds with the `store_version` refusal, whose message says the highest 0.6 release could not be named and names `deadline_exceeded` and `git ls-remote`, no file is written, and no process it started is still running

#### Scenario: Oversized tag list
- **WHEN** the download's origin answers `git ls-remote` with more than 32 MiB
- **THEN** the `store_version` refusal names `response_too_large` and `git ls-remote` as the reason, and no tag is named from a partial list

### Requirement: Every backend takes in-repo and user-level targets
`sw update plan` SHALL accept a `--skills` or `--agents` directory inside or outside the code work tree, whatever `vcs` selects. The install prompt SHALL offer both locations on every backend. With `vcs: gitbutler` it SHALL warn before the user chooses that every applied branch shares the work tree, so a branch that changes in-repo skills changes them for every applied branch.

#### Scenario: In-repo target for a GitButler project
- **WHEN** `sw update plan --download <tree>` runs with `--skills <code>/.claude/skills` and `<code>/openspec/specwright.yaml` has `vcs: gitbutler`
- **THEN** `plan` and `stage` each exit 0 with no refusal naming that directory, and `stage` stages the skills for that directory

#### Scenario: User-level target for a GitButler project
- **WHEN** the same project's update names `--skills ~/.claude/skills`
- **THEN** the plan holds no refusal for that directory

### Requirement: The install prompt explains what a user-level install shares
With any backend the install prompt SHALL say that a user-level install is shared by every project on the machine. It SHALL say that moving to an in-repo install means updating or removing the old user-level `specwright-*` copies, which serve every project on the machine, and restarting agent sessions first, and that in Claude Code a user-level skill overrides the in-repo one of the same name.

#### Scenario: The install prompt on GitButler
- **WHEN** the install prompt asks for targets and `vcs: gitbutler` is set or chosen
- **THEN** it offers the in-repo directories and the user-level ones, warns that applied branches share in-repo skills, says that a user-level install is shared by every project on the machine and, in Claude Code, overrides in-repo skills of the same name, and says that moving to an in-repo install means removing the user-level `specwright-*` copies once no other project relies on them, or updating them to 0.14.0 or later, and restarting agent sessions, with `scripts_in_workspace` from an older user-level copy as the symptom

### Requirement: Enabled packs' skills are installed with Specwright's own
The install SHALL pass each pack enabled in `specwright.yaml` to `sw update` (`--pack <name>`). `plan` SHALL run the pack checks on them, and `stage` and `swap` SHALL stage, verify and swap each pack skill directory into every chosen skills directory with the same journal and recovery as the `specwright-*` directories.

#### Scenario: A pack's skills are installed
- **WHEN** `packs:` enables `web` with skills `web-ux` and `web-a11y`, and the user chose `.claude/skills` and `.agents/skills`
- **THEN** after the install both skill directories exist in both skills directories with the download's content, and the report lists them under pack `web`

#### Scenario: An interrupted pack install is recovered
- **WHEN** the swap stops after `web-ux` is swapped and before `web-a11y` is
- **THEN** the next run's `recover` resumes or rolls back both pack skills with the `specwright-*` targets, and no staging directory or journal is left

#### Scenario: An interrupted pack removal is recovered
- **WHEN** the swap stops after a removed pack's skill was moved to `old/` and before the next install item
- **THEN** `recover` counts the swap as started and either resumes it (the removal stays done, the rest is swapped) or rolls it back (the removed skill and the previous `packs.json` are restored)

#### Scenario: A pack that fails its checks installs nothing
- **WHEN** an enabled pack fails pack-check
- **THEN** plan exits 1 with the pack-check refusals, and no installed file changes

### Requirement: The install records which skills belong to which pack
A finished install SHALL leave `openspec/.specwright/packs.json` in the code checkout listing each enabled pack with the Specwright version, its skill names, document paths and init questions, plus a catalogue (name, description, requires, signals) of every pack in the download. It SHALL be written in the swap, after the skill renames and under the journal, and a rollback SHALL restore the previous record or its absence.

#### Scenario: The record matches the installed packs
- **WHEN** an install enables `gamedev` and `ui-prototyping` at 0.18.0
- **THEN** `packs.json` lists both packs with version `0.18.0` and each pack's skill names, and no other pack

#### Scenario: A rollback restores the old record
- **WHEN** an update that enables `web` is rolled back with `recover --rollback`
- **THEN** `packs.json` holds its previous content, or is absent when it was absent before

### Requirement: A pack that is no longer enabled is removed
When `packs.json` lists a pack that `specwright.yaml` no longer enables, the swap SHALL remove that pack's recorded skill directories from every chosen skills directory (kept in the staging `old/` until finish), and the config merge SHALL remove every line starting with `[pack:<name>] `. The pack's documents SHALL be kept.

#### Scenario: Removing a pack
- **WHEN** `web` is recorded and the user deletes it from `packs:` and reruns the install
- **THEN** `web-ux` and `web-a11y` are gone from every chosen skills directory, `config.yaml` has no `[pack:web] ` line, the project's web documents are unchanged and `packs.json` no longer lists `web`

#### Scenario: A removal that would break a requirement
- **WHEN** the user removes `ui-prototyping` while `gamedev`, which requires it, stays enabled
- **THEN** plan stops before any write with refusal `pack_requires` naming both packs

### Requirement: The install never touches a skill it did not install
A skill directory named like an enabled pack's skill, not recorded in `packs.json` for that pack, SHALL be adopted when its content equals the download's byte for byte, and otherwise SHALL make `plan` stop before any write with refusal `unmanaged_skill`, naming the directory. A recorded pack skill whose name the download no longer ships SHALL be listed in `orphans`, as `specwright-*` orphans are.

#### Scenario: A hand-copied skill with a pack skill's name
- **WHEN** `.claude/skills/gamedev-design/` exists, was copied by hand, and `gamedev` is enabled for the first time
- **THEN** plan exits 1 with refusal `unmanaged_skill` naming `.claude/skills/gamedev-design`, and the directory is unchanged

#### Scenario: A clone without the record
- **WHEN** a fresh clone has committed `.claude/skills/web-ux/`, identical to the download's, and no `packs.json`
- **THEN** plan adopts it, reports it as adopted, and the install records it for `web`

#### Scenario: A hand copy of a pack that is not enabled
- **WHEN** `.claude/skills/gamedev-design/` was copied by hand, the catalogue has `gamedev`, the project does not enable it and no record lists it
- **THEN** plan does not list it in `orphans` and the install leaves it unchanged

#### Scenario: A user's unrelated skill
- **WHEN** `.claude/skills/my-tool/` exists and no enabled pack ships `my-tool`
- **THEN** the install neither lists nor changes it

### Requirement: Pack lines are merged by prefix and verified through OpenSpec
The config merge SHALL remove each `[pack:<name>] ` line whose `<name>` is enabled now or in `packs_previous` (below), then add each enabled pack's lines once as double-quoted YAML scalars, keeping and reporting every other `[pack:` line. `sw update pack-verify` SHALL confirm through `openspec instructions` in a scratch root that each line reaches its target once, that no line of a pack enabled before and not now does, and that every core context line is still delivered.

#### Scenario: Lines reach their artifacts
- **WHEN** `gamedev` has two `rules.proposal` lines and one `operations.apply` line and the merge ran
- **THEN** pack-verify reports `"ok": true`, having found each line once in `openspec instructions proposal` and `openspec instructions apply` output

#### Scenario: A missing, duplicated or stale line
- **WHEN** a gamedev line is missing, appears twice, or a `[pack:web] ` line is left after `web` was removed from `packs:`
- **THEN** pack-verify exits 1 naming each line, its artifact or operation and `missing`, `duplicate` or `not_enabled`, and the install does not stamp `VERSION`

#### Scenario: A removed pack's lines after a rerun past the swap
- **WHEN** the user removed `web` from `packs:`, the swap finished, the run stopped before Step 5, and the next run skips `stage` and `swap`
- **THEN** plan reports `packs_previous` with `web` from the journal, Step 5 removes every `[pack:web] ` line, and pack-verify reports any line left as `not_enabled`

#### Scenario: Hand-written lines of a pack the project never enabled
- **WHEN** `config.yaml` holds hand-written `[pack:gamedev] ` rules, the catalogue may or may not have `gamedev`, the project does not enable it and no record lists it
- **THEN** the merge keeps them, the report lists them as not managed (enable `gamedev` to have Specwright manage them), and pack-verify passes

### Requirement: The settings merge treats packs as user data
The install's settings merge SHALL treat every key under `packs.` in `openspec/specwright.yaml` as user data, like `pr.reviewers.`: never compared with the template, never added and never listed as removed.

#### Scenario: Enabled packs survive an update
- **WHEN** `specwright.yaml` has `packs.gamedev.documents.gdd` and the template has only a commented `packs:` example
- **THEN** the settings merge lists no `packs.` key as removed and leaves the entry unchanged

#### Scenario: A template key under packs
- **WHEN** a later template adds an uncommented example key under `packs:`
- **THEN** the merge does not add it to the user's file

### Requirement: Pack documents are created by an idempotent step after the stamp
`sw update pack-docs` SHALL create each missing pack document from its template, never overwrite one, and report each as `created` or `kept`. It SHALL depend on no journal, so a rerun after an interruption completes it; the prompt SHALL run it after the stamp.

#### Scenario: Documents after a finished install
- **WHEN** the stamp is written and `docs/game/gdd.md` does not exist
- **THEN** pack-docs creates it from the gamedev template and reports `created`

#### Scenario: Interrupted document creation
- **WHEN** pack-docs stops after creating one of two documents and is run again
- **THEN** the first is reported `kept` with its content unchanged and the second `created`

### Requirement: The previously enabled packs come from the start of the update
`stage` SHALL write the enabled packs of `packs.json` as it was before the update into the journal as `prev_packs`, and `plan` SHALL report `packs_previous`: from a pending journal when there is one, else from `packs.json`. Step 5 and `pack-verify` SHALL use `packs_previous`, never the `packs.json` the swap wrote.

#### Scenario: An uninterrupted update that removes a pack
- **WHEN** `packs.json` lists `web` enabled, the user removes `web` from `packs:` and runs the install
- **THEN** plan reports `packs_previous` `["web"]`, and after the swap Step 5 still removes the `[pack:web] ` lines although the new `packs.json` no longer lists `web`

#### Scenario: No previous record
- **WHEN** a project updates from 0.13.0, which wrote no `packs.json`
- **THEN** plan reports `packs_previous` as an empty list, and Step 5 removes no `[pack:` line of a pack that is not enabled now

### Requirement: A tagged install places a checked sw for the host
When the installed ref is a release tag, `sw update sw-install` SHALL download the host's binary asset and `SHA256SUMS` from that tag's GitHub release, check the binary's SHA-256 against its line before the file runs, then confirm that `sw version --json` reports the tag's version and the interface of the running `sw`. Only then SHALL it place the file at `<home>/.specwright/bin/<version>/sw[.exe]`. The binary it runs from MAY be the agent's checked temporary copy.

#### Scenario: Install of a tag with binaries on Linux x64
- **WHEN** the install of `v0.37.0` runs on a linux-x64 host and the release carries `sw-linux-x64` and a `SHA256SUMS` line that matches it
- **THEN** `<home>/.specwright/bin/0.37.0/sw` exists and is executable, `sw version --json` there reports `0.37.0`, and the report names that path

#### Scenario: SPECWRIGHT_HOME set
- **WHEN** `SPECWRIGHT_HOME` names a directory during the install
- **THEN** the binary is placed under `<SPECWRIGHT_HOME>/.specwright/bin/<version>/`, and nothing is written under the user's home

#### Scenario: Host on a platform with no target
- **WHEN** the install of a tag with binaries runs on a host that is none of the five targets (for example windows-arm64)
- **THEN** the install stops before any installed file changes, naming the host platform and the five targets

#### Scenario: Run from the agent's temporary copy
- **WHEN** `sw update sw-install` runs from the checked copy in the temporary directory
- **THEN** it places a separately downloaded and checked file at the final path, never moves or renames its own running file, and the temporary copy is left for the prompt to delete

### Requirement: The macOS install clears quarantine only on the file it checked
On macOS the install SHALL remove the `com.apple.quarantine` attribute only from the downloaded file whose SHA-256 it has just checked, before it runs that file. A file whose checksum did not match SHALL never have the attribute removed and SHALL never run.

#### Scenario: Quarantined download on macOS arm64
- **WHEN** the downloaded `sw-macos-arm64` carries `com.apple.quarantine` and its SHA-256 matches its `SHA256SUMS` line
- **THEN** the attribute is removed, `sw version --json` exits 0, and the binary is placed

#### Scenario: Mismatched file is left quarantined
- **WHEN** the downloaded macOS binary's SHA-256 differs from its line
- **THEN** the install stops, the attribute is not removed, the file is not run, and the download is deleted when it can be; when it cannot, it is left in place and the install still stops with the checksum error

### Requirement: A missing or incompatible sw stops a tagged install before any change
For a release tag whose downloaded copy offers the `sw` install step, any failure to get a matching `sw` (asset or `SHA256SUMS` missing or invalid, download failed or bounded, checksum differs, version report fails or mismatches) SHALL stop the install/update before staging. Installed files, `VERSION` and every binary under `<home>/.specwright/bin/` SHALL stay unchanged, and the report SHALL name the cause, the asset and the release.

#### Scenario: Release assets not uploaded yet
- **WHEN** `v0.24.0` was just published, the release workflow has not attached its assets, and the request for them is sent and answered 404 with a response that completes within the remaining byte and time budgets (a 404 that passes a bound reports that bound instead)
- **THEN** the install stops before staging, says the release's binaries are not uploaded yet and to rerun the install once they are, and no file changes

#### Scenario: Checksum mismatch
- **WHEN** the downloaded binary's SHA-256 differs from its `SHA256SUMS` line
- **THEN** the install stops before staging, naming the asset and both hashes, the file is not run, and nothing is placed

#### Scenario: Wrong interface
- **WHEN** the checked binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the install stops before staging, naming both interfaces, and nothing is placed

#### Scenario: Unattached assets and an unwritable version directory
- **WHEN** the release has no assets yet and the partial file cannot be created in the version directory
- **THEN** no request is sent and the install stops with `download_failed` naming the partial file, since a failed open comes before any HTTP outcome

### Requirement: The sw download is bounded
Each download of a release asset or `SHA256SUMS` SHALL accept at most 64 MiB in all, redirects and error bodies included, under a 120-second deadline that stops HTTP(S) and refuses a late `file://` copy. A final HTTP 200 response SHALL be judged in order: expired deadline (`deadline_exceeded`), non-identity encoding (`download_failed`), size (`response_too_large`). The first bound passed SHALL be reported with the asset within 10 s of the stop, cleanup aside.

#### Scenario: Download completes in time
- **WHEN** the server answers an uncompressed 9 MiB asset, and its write and close settle before the deadline
- **THEN** the download completes and the checksum check runs on the whole file

#### Scenario: A partial file that is slow to open
- **WHEN** opening the partial file on the destination filesystem stalls
- **THEN** the 120-second deadline starts only once the file is open; the stalled open itself is not bounded

#### Scenario: A partial file that cannot be created
- **WHEN** the partial file cannot be created in the version directory, for a release whose asset would answer 404
- **THEN** no request is sent and the install stops with `download_failed` naming the partial file and the operating system's reason, not `assets_not_uploaded`

#### Scenario: Server stalls
- **WHEN** an HTTP(S) release download is still pending at the deadline with no outcome recorded
- **THEN** the download stops within 120 seconds plus 10 seconds, and once its cleanup returns the install reports `deadline_exceeded` and the asset; when the partial file can be deleted, no partial file is left

#### Scenario: A file mirror that finishes after the deadline
- **WHEN** the release URL is a `file://` mirror whose copy of an asset under 64 MiB finishes after the deadline
- **THEN** the install stops naming `deadline_exceeded` and the asset, and nothing is placed

#### Scenario: A file mirror
- **WHEN** the release URL is a `file://` mirror whose asset is over 64 MiB and the copy passes 64 MiB before the deadline
- **THEN** the install stops naming `response_too_large` and the asset, and nothing is placed

#### Scenario: Oversized answer
- **WHEN** before the deadline the server sends more than 64 MiB for an uncompressed asset
- **THEN** the install stops naming `response_too_large` and the asset, and, when the partial file can be deleted, no partial file is left

#### Scenario: An oversized error or redirect body
- **WHEN** before the deadline the server answers a redirect, a 404 or another error status with a body over 64 MiB
- **THEN** the install accepts no more than 64 MiB of it, stops reading, and stops naming `response_too_large` and the asset

#### Scenario: Bodies that fit alone but not together
- **WHEN** before the deadline a download follows a redirect whose body is 40 MiB to an uncompressed asset of 40 MiB
- **THEN** the install stops naming `response_too_large` and the asset, and nothing is placed

#### Scenario: The partial file cannot be closed after an oversized answer
- **WHEN** before the deadline an uncompressed download passes 64 MiB, and closing its partial file then fails or does not finish before the deadline
- **THEN** the download stops within 120 seconds plus 10 seconds, and once its cleanup returns the install reports `response_too_large` and the asset, and nothing is placed

#### Scenario: The deadline passes before an oversized chunk is read
- **WHEN** the deadline has passed by the time the download reads a chunk that would take it past 64 MiB
- **THEN** the install stops naming `deadline_exceeded` and the asset

#### Scenario: An oversized length with a stalled body
- **WHEN** before the deadline the server answers with an uncompressed HTTP 200, advertises a length over 64 MiB, and then sends no body
- **THEN** the downloader latches `response_too_large` when it reads the header, before the deadline, and returns it within ten seconds of that latch, not `deadline_exceeded`; once its cleanup returns, the install reports `response_too_large` naming the asset

#### Scenario: A write failure while the body stalls
- **WHEN** before the deadline the partial file's write fails while the server has stopped sending, and closing the file then runs past the deadline
- **THEN** the download stops reading at once, and after its bounded shutdown and cleanup the install reports `download_failed` and the asset, not `deadline_exceeded`

#### Scenario: A connection failure after the deadline
- **WHEN** the deadline has passed by the time the download's connection or file write fails
- **THEN** the install stops naming `deadline_exceeded` and the asset, not `download_failed`

#### Scenario: A compressed answer
- **WHEN** before the deadline the server answers the asset with HTTP 200 and a `Content-Encoding` other than `identity`, with or without a length header, an oversized one included
- **THEN** the install stops naming `download_failed`, the asset and the encoding, and nothing is placed

#### Scenario: A partial answer
- **WHEN** before the deadline the server answers the asset with an identity-encoded HTTP 206 whose body ends within the remaining byte budget and before the deadline
- **THEN** the install stops with `download_failed` naming the status, as before this change, and nothing of the body is kept

#### Scenario: A compressed 404
- **WHEN** the server answers `SHA256SUMS` with a small gzip-encoded 404 whose response, redirects included, completes within the remaining byte and time budgets
- **THEN** the downloader latches the missing asset when the drain completes and returns it within ten seconds of that latch even while closing the partial file is still held, so a close that fails or stalls cannot replace it; once its cleanup returns, the install reports the missing asset as before this change, not `download_failed`; a 404 that passes a bound first reports that bound

#### Scenario: A compressed answer handled after the deadline
- **WHEN** the deadline has passed by the time a compressed answer's headers are handled
- **THEN** the install stops naming `deadline_exceeded` and the asset, not `download_failed`

#### Scenario: An answer of exactly 64 MiB
- **WHEN** with no redirect or error body counted, the server sends an uncompressed asset of exactly 64 MiB with no length header, and its write and close settle before the deadline
- **THEN** the download completes and the checksum check runs on the whole file

#### Scenario: A body that ends in time with a close that settles late
- **WHEN** over HTTP(S) an uncompressed asset of exactly 64 MiB ends before the deadline but its partial file's close settles after it, even after the grace period
- **THEN** the downloader latches `deadline_exceeded` at the deadline and returns it by the end of the grace period; once its cleanup returns, the install reports `deadline_exceeded` naming the asset, the partial file is closed exactly once, and no checksum check runs

#### Scenario: The partial file is held
- **WHEN** a download passes its deadline and its partial file cannot be deleted
- **THEN** the install stops naming `deadline_exceeded` and the asset, not a file-operation error, and the partial file remains

### Requirement: An install without release binaries says so
When the installed ref is `main`, `sw update sw-install` SHALL place no binary and SHALL report `skipped` with a message, changing nothing under `<home>/.specwright/bin/`. The `main` install's `sw` comes from its build, and the report SHALL say that `sw` was built from the clone.

#### Scenario: Install of main
- **WHEN** `sw update sw-install` runs with `--ref main`
- **THEN** it reports `action: skipped`, places no binary, and no file under `<home>/.specwright/bin/` is created, changed or removed

#### Scenario: Install of an older tag
- **WHEN** the user asks for `v0.23.0`, which ships no `sw`
- **THEN** the prompt stops before any write under the minimum-release rule, and nothing under `<home>/.specwright/bin/` changes

#### Scenario: Install of main reports the build
- **WHEN** the user installs `main` and `mise run install-sw` placed `sw`
- **THEN** the report says `sw built from main` with the placed path

#### Scenario: Existing binaries stay untouched on main
- **WHEN** `sw update sw-install --ref main` runs and `<home>/.specwright/bin/0.36.0/sw` exists
- **THEN** that file's bytes, mode and timestamps are unchanged

### Requirement: Placing sw is atomic and keeps other versions
The install SHALL write the binary into its version directory under a temporary name and rename it to `sw[.exe]` only after the checks pass, so the final path never holds a partial or unchecked file. It SHALL never change another version's directory. A file already at the final path SHALL be kept only when it has the release's SHA-256 and its `sw version --json` reports the release's version and interface. Any other file there SHALL be replaced by that rename.

#### Scenario: Rerun with the binary already placed
- **WHEN** the install of `v0.24.0` runs again and `<home>/.specwright/bin/0.24.0/sw` already matches the release's hash and passes the version and interface check
- **THEN** the file is kept unchanged and the report says it was already installed

#### Scenario: Interrupted before the rename
- **WHEN** the install is stopped after the download and before the rename
- **THEN** no file exists at `<home>/.specwright/bin/0.24.0/sw`, `<home>/.specwright/bin/0.23.0/sw` is unchanged, and the next run downloads and checks again

#### Scenario: A stale file at the final path
- **WHEN** `<home>/.specwright/bin/0.24.0/sw` exists but its SHA-256 differs from the release's
- **THEN** the checked download replaces it by rename, and the report says it was replaced

#### Scenario: Matching hash but not runnable
- **WHEN** `<home>/.specwright/bin/0.24.0/sw` has the release's SHA-256 but its executable bit was removed
- **THEN** the checked download replaces it, `sw version --json` at the final path exits 0, and the report says it was replaced

#### Scenario: Two installs of one version at once
- **WHEN** two projects on one machine install `v0.24.0` at the same time, each finishes within an hour so neither loses a live part to the other's age sweep, and no running process holds the final file
- **THEN** both succeed, one placing the binary and the other placing it or reporting it kept after checking the winner's file, the final file has the release's SHA-256, and neither run deletes the other's temporary file while it is younger than an hour

#### Scenario: Rename blocked by a running binary
- **WHEN** on Windows the rename to the final path fails because another process is running that file
- **THEN** the install checks the final file again: when it has the release's SHA-256 and its `sw version --json` reports the release's version and interface, the install succeeds and reports it kept; otherwise it stops with `sw_in_use` naming the path; the existing binary and other versions are unchanged, the checked notice may already be in place, and the part file may remain

#### Scenario: The final file cannot be read after a blocked rename
- **WHEN** the rename to the final path fails and the final file disappears or cannot be opened while it is being checked
- **THEN** the install stops with `sw_in_use` naming the path, not a file-operation error, and makes no further placement attempt

#### Scenario: A temporary file left by a killed run
- **WHEN** the version directory holds a temporary file last modified more than one hour ago
- **THEN** the next install of that version deletes it when it can, and leaves it without an error when it cannot; a temporary file modified within the last hour is left alone

### Requirement: Recovery leaves placed binaries in place
A rollback or a discarded update SHALL leave every file under `<home>/.specwright/bin/` as it is. The previous version's binary is never touched by the update, and a new version's binary placed before the rollback stays for a later update to that version.

#### Scenario: Rollback after the binary was placed
- **WHEN** an update from 0.24.0 to 0.25.0 placed `bin/0.25.0/sw`, was interrupted during the swap, and the next run rolls back
- **THEN** `VERSION` reads `0.24.0`, `bin/0.24.0/sw` is unchanged, and `bin/0.25.0/sw` is still present

#### Scenario: Previous version had no binary
- **WHEN** a project on 0.23.0 (no `sw`) updates to 0.24.0 and the update rolls back
- **THEN** `VERSION` reads `0.23.0`, and the report says no `sw` serves 0.23.0, which no 0.23.0 skill needs

### Requirement: An install whose VCS steps need a missing sw says so
Step 8 SHALL check that `<home>/.specwright/bin/<project VERSION>/sw[.exe]` exists and its `version --json` exits 0 in 10 s with that version and the skills' interface (`specwright-pr`'s standalone `interface <n>` line, or an older tag's `SW_INTERFACE=`). On a failure it SHALL warn that branch, commit and finish steps stop until a matching `sw` is placed, that another version's `sw` stops with `sw_mismatch`, and name a tagged install and the `CONTRIBUTING.md` bootstrap; otherwise no warning.

#### Scenario: A binary of the right version and an old interface
- **WHEN** the installed skills require interface 2 and the pinned binary reports the project's version but interface 1
- **THEN** the Step 8 report gives the same warning as for a missing binary and does not report the install ready

#### Scenario: An older supported tag
- **WHEN** the new install prompt selects `v0.37.0`, whose installed skills pin interface 1 in `sw-path.sh`, its `sw-install` returns `installed`, and at Step 8 the pinned binary exits 0 reporting `0.37.0` and interface 1
- **THEN** the Step 8 report gives no missing-binary warning

#### Scenario: The interface named in prose and on its own line
- **WHEN** the installed `specwright-pr/SKILL.md` says in a paragraph that an older `sw` reported interface 2, holds the line `interface 3` on its own, and the pinned binary exists and its `version --json` exits 0 in 10 s with the project's version and interface 3
- **THEN** the Step 8 report holds no missing-`sw` warning and reports no `sw_mismatch`

#### Scenario: main install with no binary
- **WHEN** a `main` install built `sw`, and the version directory was emptied before Step 8
- **THEN** the Step 8 report says VCS steps stop until a matching `sw` is placed, and names a tagged install and the `CONTRIBUTING.md` bootstrap

#### Scenario: Binary of another version at the path
- **WHEN** the file at `<home>/.specwright/bin/<project VERSION>/sw[.exe]` reports another version in `sw version --json`
- **THEN** the Step 8 report holds the missing-`sw` warning and says that VCS steps stop with `sw_mismatch`

#### Scenario: main install with a matching binary already placed
- **WHEN** the user installs `main` and the built `sw` at the project's version path passes the final check: it reports that version and the interface the installed skills require
- **THEN** the Step 8 report holds no missing-`sw` warning

#### Scenario: Older tag whose scripts need no sw
- **WHEN** the user asks for `v0.23.0`, whose `vcs.sh` runs no `sw`
- **THEN** the prompt stops under the minimum-release rule before Step 8, so no missing-`sw` warning is reported

#### Scenario: Tagged install with sw placed
- **WHEN** a release tag's `sw-install` returns `installed`, `replaced` or `kept`, and the final check of the placed binary passes
- **THEN** the Step 8 report holds no missing-`sw` warning

#### Scenario: Tagged install whose binary then fails the final check
- **WHEN** a release tag's `sw-install` returns `installed`, and before Step 8 the placed file is removed
- **THEN** the Step 8 report holds the missing-`sw` warning

### Requirement: Contributors place a tree-built sw with one task
`mise run install-sw` in a Specwright checkout SHALL build `sw` from the tree and place it at `<home>/.specwright/bin/<tree VERSION>/sw[.exe]` (`<home>`: `SPECWRIGHT_HOME`, else the user's home), with no bash, only after the built binary reports the tree's `VERSION` and a workflow interface equal to the tree's skill pin (`skills/specwright-pr/SKILL.md`'s `interface` line), never its own constant. It SHALL place the notice first, replace a file only by rename, and print the placed path.

#### Scenario: Build placed
- **WHEN** `mise run install-sw` runs in a checkout whose `VERSION` reads `0.38.0`
- **THEN** `<home>/.specwright/bin/0.38.0/sw[.exe]` exists with `THIRD_PARTY_NOTICES.txt` beside it, `sw vcs state --repo <p> --role code` run with it in a project at 0.38.0 passes the version check, and the task prints that path

#### Scenario: Build fails the check
- **WHEN** the built binary reports another version or interface than the tree's
- **THEN** the task exits non-zero, names the mismatch, and leaves any existing file under `<home>/.specwright/bin/0.38.0/` unchanged

#### Scenario: Update interface passes, workflow interface differs from the skill pin
- **WHEN** the built binary reports `0.38.0`, update interface 3 and workflow interface 1, while the tree's `specwright-pr` skill pins interface 2, and `<home>/.specwright/bin/0.38.0/` already holds `sw[.exe]` and `THIRD_PARTY_NOTICES.txt`
- **THEN** the task exits non-zero naming both interfaces, and both existing files are unchanged

#### Scenario: No bash on PATH
- **WHEN** on Windows `mise run install-sw` runs with no `bash` on `PATH`
- **THEN** the build is placed as above

### Requirement: sw update carries every update subcommand
`sw update <subcommand>` SHALL provide `plan`, `stage`, `swap`, `note-config`, `finish`, `recover`, `pack-check`, `pack-verify`, `pack-docs` and `sw-install` with the options, JSON fields, error and refusal codes, exit codes and file effects that the requirements of this capability give for each subcommand. Each such requirement SHALL apply to `sw update` as written, messages included. Only the order of fields MAY differ.

#### Scenario: A workflow update through sw update
- **WHEN** an update from 0.36.0 to 0.37.0 runs `sw update plan`, `stage`, `swap`, `note-config` and `finish` with the prompt's options
- **THEN** `plan` reports `kind: workflow` and the changes in flight with their results, every target holds the 0.37.0 copy after `swap`, and after the stamp `finish` leaves no staging directory, `old/` copy or journal

#### Scenario: A refusal keeps its code
- **WHEN** `sw update plan` finds a change in flight that fails validation against the new schema
- **THEN** it exits 1 with `"error": "refused"`, a `change_invalid` refusal naming the change, and `"unchanged": true`, and writes no file outside its scratch directory

#### Scenario: A usage error
- **WHEN** `sw update` runs with no subcommand, or with `--rollback` on `plan`
- **THEN** it prints one JSON document with `"error": "usage"` and exits 2, and nothing is written

### Requirement: sw update needs no bash or Python
`sw update` SHALL do its own work without starting `bash`, `sh` or a Python interpreter. It SHALL copy, rename and remove files with its own operations, read the store's VCS state and run fenced calls through `sw`'s own interfaces, and start `git` and `openspec` directly through the native launcher.

#### Scenario: Install and update with failing interpreters first on PATH
- **WHEN** on Linux, Windows and macOS a fresh install and a workflow update run every `sw update` subcommand with recording `bash`, `sh`, `python` and `python3` that exit 1 placed first on `PATH`
- **THEN** each subcommand returns the document it returns without them, `VERSION` is stamped before `finish`, and no recorder ran

#### Scenario: Interrupted swap recovered with failing interpreters
- **WHEN** a `sw update swap` is killed after its first rename, and `sw update recover` runs with the same recorders first on `PATH`
- **THEN** recover reports `resumed update to <to>` or `rolled back to <from>` as the staged copy decides, and no recorder ran

#### Scenario: A jj store read in process
- **WHEN** an owner's swap checks a `planning_store.vcs: jj` store that is busy with a change bookmark
- **THEN** the swap stops with `store_busy` naming the bookmark, and no separate `sw vcs` or `sw as` process ran

### Requirement: sw update refuses settings the shared reader refuses
`sw update` SHALL read `openspec/specwright.yaml` only through `sw`'s shared settings reader. When that reader refuses the file, `plan` and every subcommand that reads it SHALL stop before any write with `settings_invalid`, naming the file, the line and the problem, and saying to fix the file and rerun the update. A missing file SHALL read as no settings.

#### Scenario: A plain yes in the settings
- **WHEN** `openspec/specwright.yaml` sets `review.preship` to a plain `yes` and the prompt runs `sw update plan`
- **THEN** `plan` exits 1 with `settings_invalid`, names the file, the line and that `yes` must be written `true`, and no file is written

#### Scenario: No settings file
- **WHEN** the code checkout has no `openspec/specwright.yaml` (a fresh install)
- **THEN** `plan` reads no `main_branch`, `vcs` or `planning_store` setting, detects the main branch, and continues

### Requirement: sw update recovers journals that older update scripts left
`sw update recover`, and the recovery `plan` runs first, SHALL read and recover a pending journal of format 1 or format 2 written by an older `update.sh`, with the same outcomes as for its own journal. A journal of an unknown format, or one that does not parse as a whole, SHALL be refused as `journal_unreadable`, and nothing SHALL be touched.

#### Scenario: A format-2 journal from update.sh
- **WHEN** an update by the 0.36.0 `update.sh` was interrupted mid-swap with a complete staged copy, and the 0.37.0 prompt then runs `sw update plan`
- **THEN** `plan` reports `recovered` with `resumed update to <to>` and then plans the 0.37.0 update

#### Scenario: Unknown journal format
- **WHEN** the journal reads `"format": 9`
- **THEN** `plan` refuses with `journal_unreadable`, `"unchanged": true`, and every installed file and the journal are unchanged

### Requirement: The install prompt drives sw update interface 3
`sw update interface` SHALL print `{"ok":true,"interface":3}` and read or write nothing else. `sw update plan` SHALL also report `interface: 3`, and `sw update` SHALL write journal format 2. The prompt SHALL drive only `sw update`, and SHALL run `sw update interface` on the checked temporary binary before `sw-install`, recovery or any other write. A failing run or another interface SHALL stop the prompt, naming the ref, the interface found or that there is none, and interface 3.

#### Scenario: Matching interface
- **WHEN** the prompt runs `sw update interface` with the checked temporary 0.37.0 `sw`
- **THEN** it prints `interface: 3` and the install continues to `sw-install`

#### Scenario: Interface mismatch
- **WHEN** the checked temporary `sw` reports another interface, or has no `update` command, while `<home>/.specwright/bin/<version>/` holds an `sw` and its notice and the project holds a pending journal
- **THEN** the prompt stops before `sw-install`, names the ref and both interfaces, deletes the temporary directory, and the placed binary, the notice, the journal and every installed file are unchanged

### Requirement: The install prompt needs no bash or Python
The install prompt SHALL check `openspec`, `git`, `curl` and the host's SHA-256 tool (`Get-FileHash` on Windows, `shasum -a 256` or `sha256sum` elsewhere) and SHALL NOT check for or run bash or Python. Every step SHALL be given as a command the agent can run in the host's own shell, with no bash syntax. A missing tool SHALL stop the prompt before any write, naming the tool.

#### Scenario: Windows host without Git Bash or Python
- **WHEN** the prompt runs on Windows with `git`, `openspec` and `curl.exe` on `PATH`, PowerShell's `Get-FileHash`, and no `bash` or `python`
- **THEN** a tagged install completes, `VERSION` is stamped, and the report names the placed `sw`

#### Scenario: No SHA-256 tool
- **WHEN** on Linux neither `sha256sum` nor `shasum` is found
- **THEN** the prompt stops before any download is run, names both tools, and writes no file

### Requirement: The agent fetches and checks the first sw before any write
For a release tag, the agent SHALL fetch the host's `sw` asset, `THIRD_PARTY_NOTICES.txt` and `SHA256SUMS` into the temporary directory with `curl` and check both files' SHA-256. Only when both match SHALL it make the asset executable (POSIX), clear macOS quarantine and run `sw version --json`, which SHALL report the tag's version. Then `sw update interface` and `sw update sw-install` run, and every later step uses the placed binary.

#### Scenario: Fresh install on macOS arm64
- **WHEN** the prompt installs `v0.37.0` on macOS arm64 with no `sw` placed, starting from a download without the executable bit
- **THEN** the agent's check passes, the file is made executable before it runs, `sw update sw-install` reports `installed` with `<home>/.specwright/bin/0.37.0/sw`, and `plan`, `stage` and `swap` run from that path

#### Scenario: Hash mismatch at the bootstrap
- **WHEN** the downloaded asset's SHA-256 differs from its `SHA256SUMS` line
- **THEN** the prompt stops before any write, names the asset and both hashes, deletes the file without running it, and nothing under `<home>/.specwright/bin/` changes

#### Scenario: Missing or corrupt notice at the bootstrap
- **WHEN** the release has no `THIRD_PARTY_NOTICES.txt`, or its SHA-256 differs from its line
- **THEN** the prompt stops before any write, names the notice and the release, and the temporary binary is never made executable and never run

#### Scenario: Version report differs from the tag
- **WHEN** the checked binary's `sw version --json` reports another version than the tag's
- **THEN** the prompt stops before any write, naming both versions, and nothing is placed

### Requirement: The bootstrap downloads are bounded and https only
Each `curl` fetch of the bootstrap SHALL accept only https, on the first URL and on every redirect, and SHALL be bounded to 120 seconds and 64 MiB. A fetch that fails or passes a bound SHALL stop the prompt before any write, naming the file and the cause, and its partial file SHALL be deleted.

#### Scenario: Bootstrap downloads in time
- **WHEN** the asset, the notice and `SHA256SUMS` arrive over https within the bounds, through GitHub's redirect to its https asset host
- **THEN** the hash checks run on the whole files

#### Scenario: Stalled, oversized or downgraded bootstrap download
- **WHEN** a bootstrap download does not finish within 120 seconds, exceeds 64 MiB, or redirects to a URL that is not https
- **THEN** `curl` fails, the prompt stops before any write naming the file and the cause, deletes the partial file, and runs nothing

### Requirement: A main install builds sw from the clone
A `main` install SHALL build `sw` from the downloaded tree with `mise run install-sw -- --expect-update-interface 3`, and SHALL run every `sw update` step with the placed binary. The task SHALL check the build's `sw update interface` before placing it. A missing `mise`, a failed build or a failed check SHALL stop the prompt before any write, naming the tool or the failure.

#### Scenario: main install with mise
- **WHEN** the user asks for `main` and `mise` with the pinned Dart SDK is available
- **THEN** `sw` is placed at `<home>/.specwright/bin/<main's VERSION>/`, the install completes, and the report names `main` and that path

#### Scenario: main install without mise
- **WHEN** the user asks for `main` and `mise` is not on `PATH`
- **THEN** the prompt stops before any write in the project, says a `main` install builds `sw` with `mise run install-sw` and names `mise`, and no file under the project or `<home>/.specwright/bin/` changes

#### Scenario: main build reports another interface
- **WHEN** the user asks for `main`, the build's `sw update interface` reports another interface or fails, `<home>/.specwright/bin/<main's VERSION>/` already holds an `sw` and its notice, and the project holds a pending journal
- **THEN** the task stops before placement and the prompt stops, naming `main`, the interface found or that there is none, and interface 3, and the placed binary, the notice, the journal and every installed file are unchanged

### Requirement: Part-file cleanup never replaces the install's result
Every deletion of a temporary part file or `.stage` directory during `sw update sw-install` SHALL be best effort. A part file it cannot delete SHALL be left in place and SHALL NOT change the install's exit status, document or error; where another requirement says no file changes, a leftover temporary part and an old part removed by the existing age-based sweep are the only exceptions; installed files, binaries and `VERSION` never are.

#### Scenario: A locked binary part after a notice write failure
- **WHEN** on Windows the install stops with `notice_write_failed` and its `.part.exe` cannot be deleted because it is still locked
- **THEN** the document's error is `notice_write_failed`, not `file_operation_failed`, the existing binary is unchanged, and the part file remains

#### Scenario: A locked part after a rename lost to a concurrent install
- **WHEN** a concurrent install places the release's binary at the final path after this install's first check, this install's rename then fails, and deleting its part fails
- **THEN** the install reports `kept`, as when the delete succeeds, and the part file remains

#### Scenario: A locked part after a rename that fails otherwise
- **WHEN** this install's rename fails, the final path does not hold the release's binary, and deleting its part fails
- **THEN** the install stops with `sw_in_use`, not a file-operation error, and the part file remains

#### Scenario: A part left when the release has no SHA256SUMS
- **WHEN** a tagged install stops because `SHA256SUMS` is missing and deleting the partial download fails
- **THEN** installed files, `VERSION` and every binary under `<home>/.specwright/bin/` are unchanged and the stop is reported as before; the temporary part file remains, and the existing age-based sweep may already have removed old parts from the version directory; these two are the only exceptions to that stop's "no file changes"

#### Scenario: A version directory that cannot be listed
- **WHEN** the version directory can be written but not listed when the install sweeps old parts
- **THEN** the sweep is skipped and the install goes on as if no old part were there

#### Scenario: A source build whose stage cannot be deleted
- **WHEN** an install from source ends and its `.stage` directory cannot be deleted
- **THEN** the install's result and document are those of the build, and the `.stage` directory remains

#### Scenario: Cleanup succeeds
- **WHEN** the install succeeds and every part file it created can be deleted
- **THEN** none of this run's part files or its source-build `.stage` directory remain, another run's part file younger than an hour is left untouched, and the document reports the install as before

#### Scenario: A later run meets the leftover
- **WHEN** a later install in the same version directory finds a part file older than an hour
- **THEN** it tries to delete it, and leaves it without an error when it is still held

### Requirement: The settings merge treats version-file entries as user data
The settings merge SHALL treat every key under `release.version_files.` as user data, like `pr.reviewers.` and `packs.`: never compared, merged into an existing mapping or listed as removed, and kept in order. `release.version_files` itself SHALL stay a compared key: when the project lacks it and the template sets it, Step 6 offers the template's mapping as one unit, in order, as a default the user may decline. Step 7 SHALL check it like any compared key, and none of its entries.

#### Scenario: A project's own version files survive an update
- **WHEN** `specwright.yaml` has `release.version_files.VERSION`, `release.version_files.README.md` and `release.version_files."skills/*/SKILL.md"` in that order, and the template names only `VERSION`
- **THEN** Step 6 lists none of them as removed, asks nothing about them, and leaves all three values and their order unchanged

#### Scenario: A project without the template's entry
- **WHEN** the project's `release.version_files` names only `package.json` and the template's names `VERSION`
- **THEN** Step 6 adds no `release.version_files.VERSION` key, Step 7's key check passes without it, and with every other Step 7 check passing `VERSION` is stamped

#### Scenario: A project without version_files accepts the default
- **WHEN** the project's `release:` block has no `version_files` key, the template's has one, and the user keeps the default
- **THEN** Step 6 adds `release.version_files` with the template's entries in the template's order and lists it as added, and Step 7's key check passes

#### Scenario: A project without version_files declines the default
- **WHEN** the project's `release:` block has no `version_files` key and the user declines the template's default in Step 6
- **THEN** no `release.version_files` key is added, and Step 7's key check passes, as for any key the user chose not to add

### Requirement: The settings merge never rewrites a comment
The install's settings merge SHALL keep the user's values and the comments of every key it keeps as they are: when it adds a missing key the template sets and the user keeps its default, it SHALL copy the template's comment with it, and it SHALL never rewrite, add or remove a comment on a key the user's file keeps. A key removed with the user's consent MAY take its comment with it. The install prompt SHALL say so in Step 6.

#### Scenario: A stale comment on a kept key
- **WHEN** the user's file has `cheap_tier.enabled` under the comment `# Cheap tier (add-cheap-tier)` and the template's comment for that key reads `# Cheap tier`
- **THEN** after the update the user's comment still reads `# Cheap tier (add-cheap-tier)`, Step 6 asks nothing about it and Step 7's key check passes

#### Scenario: A missing key is added with its comment
- **WHEN** the template sets a key the user's file lacks, with a comment above it, and the user keeps its default
- **THEN** Step 6 adds that key with the template's default and comment, and lists it as added

#### Scenario: A key removed upstream still needs consent
- **WHEN** the user's file sets a key with a comment attached, the template no longer has that key at all, and the user declines its removal
- **THEN** the key and its comment stay unchanged, and Step 8 lists it neither as added nor as removed

### Requirement: Step 7 checks only Specwright's skill directories
Step 7's skills check SHALL pass for a chosen skills directory when every downloaded `specwright-*` file is there with the same content and no installed `specwright-*` directory with a downloaded counterpart holds a file the download lacks. A `specwright-*` orphan (no downloaded counterpart) SHALL pass only when the user chose in Step 4 to keep it. Other directories (OpenSpec's `openspec-*`, `gitbutler`, the user's own, pack skills) SHALL NOT count.

#### Scenario: OpenSpec skills beside Specwright's
- **WHEN** a chosen skills directory holds the downloaded `specwright-*` directories with the same content and twelve `openspec-*` directories
- **THEN** Step 7's skills check passes and reports nothing about the `openspec-*` directories

#### Scenario: An extra file inside a Specwright directory
- **WHEN** an installed `specwright-pr` directory holds a file the downloaded `specwright-pr` lacks
- **THEN** Step 7's skills check fails naming that file, and `VERSION` is not stamped

#### Scenario: An orphan the user kept
- **WHEN** a chosen skills directory holds `specwright-old`, which the download has no counterpart for, and the user declined its removal in Step 4
- **THEN** Step 7's skills check passes, and Step 8 lists `specwright-old` as an orphan kept

#### Scenario: An orphan the user agreed to remove is still there
- **WHEN** the user agreed in Step 4 to remove `specwright-old`, and it is still in the skills directory at Step 7
- **THEN** Step 7's skills check fails naming `specwright-old`, and `VERSION` is not stamped

### Requirement: Step 4 settles the plan's orphans on every path
Step 4 SHALL ask about each `specwright-*` skill directory among the current plan's `orphans` that this update does not install, and remove those the user agrees to remove, after a new `swap` or, when the plan shows a completed swap and no refusal and Step 4 skips `stage` and `swap`, once that swap is confirmed. It SHALL do so before Step 5. Other `orphans` entries, such as agent files and pack skills, are outside this rule.

#### Scenario: A rerun that removes an orphan kept before
- **WHEN** the prompt is run again after a swap that kept `specwright-old`, the plan lists it among `orphans` with the swap already completed and lists no refusals, and the user now agrees to remove it
- **THEN** Step 4 removes `specwright-old` before Step 5, Step 7's skills check passes, and with every other Step 7 check passing `VERSION` is stamped

#### Scenario: A rerun that keeps it again
- **WHEN** the same refusal-free rerun's user declines the removal again
- **THEN** `specwright-old` stays, Step 7's skills check passes, and Step 8 lists it as an orphan kept

#### Scenario: A rerun whose plan also lists a refusal
- **WHEN** the plan shows the completed swap and lists `specwright-old` among `orphans`, and also lists a refusal
- **THEN** Step 4 removes nothing, asks no orphan question and handles the refusal first

