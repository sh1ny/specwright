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
The `git ls-remote --tags` that `update.sh` runs to name the highest release tag SHALL run under a 60-second deadline and read at most 32 MiB. When it passes a bound, its process tree SHALL be stopped and the tag SHALL be reported as not named, with the limit (`deadline_exceeded` or `response_too_large`) and the command in the reason. The refusal it belongs to SHALL still be made, and nothing SHALL be written.

#### Scenario: Tags listed in time
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin lists `v0.6.0` and `v0.6.2` within the deadline
- **THEN** the `store_version` refusal names `v0.6.2`

#### Scenario: Hung tag lookup
- **WHEN** another project's update would leave the store's 0.6 version, and the download's origin never answers `git ls-remote`
- **THEN** `update.sh plan` exits 1 within 60 seconds plus 10 seconds with the `store_version` refusal, whose message says the highest 0.6 release could not be named and names `deadline_exceeded` and `git ls-remote`, no file is written, and no process it started is still running

#### Scenario: Oversized tag list
- **WHEN** the download's origin answers `git ls-remote` with more than 32 MiB
- **THEN** the `store_version` refusal names `response_too_large` and `git ls-remote` as the reason, and no tag is named from a partial list

### Requirement: Every backend takes in-repo and user-level targets
`update.sh plan` SHALL accept a `--skills` or `--agents` directory inside or outside the code work tree, whatever `vcs` selects. The install prompt SHALL offer both locations on every backend. With `vcs: gitbutler` it SHALL warn before the user chooses that every applied branch shares the work tree, so a branch that changes in-repo skills changes them for every applied branch.

#### Scenario: In-repo target for a GitButler project
- **WHEN** `update.sh plan` runs with `--skills <code>/.claude/skills` and `<code>/openspec/specwright.yaml` has `vcs: gitbutler`
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
The install SHALL pass each pack enabled in `specwright.yaml` to `update.sh` (`--pack <name>`). `plan` SHALL run the pack checks on them, and `stage` and `swap` SHALL stage, verify and swap each pack skill directory into every chosen skills directory with the same journal and recovery as the `specwright-*` directories.

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
The config merge SHALL remove each `[pack:<name>] ` line whose `<name>` is enabled now or in `packs_previous` (below), then add each enabled pack's lines once as double-quoted YAML scalars, keeping and reporting every other `[pack:` line. `update.sh pack-verify` SHALL confirm through `openspec instructions` in a scratch root that each line reaches its target once, that no line of a pack enabled before and not now does, and that every core context line is still delivered.

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

### Requirement: The install prompt drives update-script interface 2
`update.sh` SHALL report `interface: 2` and SHALL write journal format 2; a format-1 journal is still recovered, and an older download refuses a format-2 journal as unreadable. The install prompt SHALL accept interface 2, and interface 1 only when `specwright.yaml` enables no pack and the installed `packs.json`, if any, lists no enabled pack; otherwise it SHALL stop before any write, naming the interface found and the one needed.

#### Scenario: Matching interface
- **WHEN** the prompt runs a download whose `plan` reports `interface: 2`
- **THEN** the install continues to `stage`

#### Scenario: An older download without packs
- **WHEN** the prompt installs 0.12.3 (`interface: 1`) in a project with no `packs:` key and no enabled pack in `packs.json`
- **THEN** the install continues as before this change and writes no pack state

#### Scenario: An older download with packs enabled
- **WHEN** the prompt runs a download whose `plan` reports `interface: 1`, and `packs:` enables `web` or the installed `packs.json` still lists `web` as enabled
- **THEN** the prompt stops before `stage`, says that download predates packs (remove the packs with a 0.16.0 or later release first) and names interfaces 1 and 2, and no file changes

### Requirement: Pack documents are created by an idempotent step after the stamp
`update.sh pack-docs` SHALL create each missing pack document from its template, never overwrite one, and report each as `created` or `kept`. It SHALL depend on no journal, so a rerun after an interruption completes it; the prompt SHALL run it after the stamp.

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
When the downloaded copy offers the `sw` install step and the installed ref is a release tag, the install/update SHALL download the host's binary asset and `SHA256SUMS` from that tag's GitHub release, check the binary's SHA-256 against its line before the file runs, then confirm that `sw version --json` reports the tag's version and the skills' interface. Only then SHALL it place the file at `<home>/.specwright/bin/<version>/sw[.exe]`.

#### Scenario: Install of a tag with binaries on Linux x64
- **WHEN** the install of `v0.24.0` runs on a linux-x64 host and the release carries `sw-linux-x64` and a `SHA256SUMS` line that matches it
- **THEN** `<home>/.specwright/bin/0.24.0/sw` exists and is executable, `sw version --json` there reports `0.24.0`, and the report names that path

#### Scenario: SPECWRIGHT_HOME set
- **WHEN** `SPECWRIGHT_HOME` names a directory during the install
- **THEN** the binary is placed under `<SPECWRIGHT_HOME>/.specwright/bin/<version>/`, and nothing is written under the user's home

#### Scenario: Host on a platform with no target
- **WHEN** the install of a tag with binaries runs on a host that is none of the five targets (for example windows-arm64)
- **THEN** the install stops before any installed file changes, naming the host platform and the five targets

### Requirement: The macOS install clears quarantine only on the file it checked
On macOS the install SHALL remove the `com.apple.quarantine` attribute only from the downloaded file whose SHA-256 it has just checked, before it runs that file. A file whose checksum did not match SHALL never have the attribute removed and SHALL never run.

#### Scenario: Quarantined download on macOS arm64
- **WHEN** the downloaded `sw-macos-arm64` carries `com.apple.quarantine` and its SHA-256 matches its `SHA256SUMS` line
- **THEN** the attribute is removed, `sw version --json` exits 0, and the binary is placed

#### Scenario: Mismatched file is left quarantined
- **WHEN** the downloaded macOS binary's SHA-256 differs from its line
- **THEN** the install stops, the attribute is not removed, the file is not run, and the download is deleted

### Requirement: A missing or incompatible sw stops a tagged install before any change
For a release tag whose downloaded copy offers the `sw` install step, any failure to get a matching `sw` (asset or `SHA256SUMS` missing or invalid, download failed or bounded, checksum differs, version report fails or mismatches) SHALL stop the install/update before staging. Installed files, `VERSION` and every binary under `<home>/.specwright/bin/` SHALL stay unchanged, and the report SHALL name the cause, the asset and the release.

#### Scenario: Release assets not uploaded yet
- **WHEN** `v0.24.0` was just published and the release workflow has not attached its assets
- **THEN** the install stops before staging, says the release's binaries are not uploaded yet and to rerun the install once they are, and no file changes

#### Scenario: Checksum mismatch
- **WHEN** the downloaded binary's SHA-256 differs from its `SHA256SUMS` line
- **THEN** the install stops before staging, naming the asset and both hashes, the file is not run, and nothing is placed

#### Scenario: Wrong interface
- **WHEN** the checked binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the install stops before staging, naming both interfaces, and nothing is placed

### Requirement: The sw download is bounded
Each download of a release asset or `SHA256SUMS` SHALL run under a 120-second deadline and read at most 64 MiB. A download that passes a bound SHALL be stopped, its partial file deleted, and reported with the limit (`deadline_exceeded` or `response_too_large`) and the asset name.

#### Scenario: Download completes in time
- **WHEN** the asset is 9 MiB and the server answers within the deadline
- **THEN** the download completes and the checksum check runs on the whole file

#### Scenario: Server stalls
- **WHEN** the release download never completes
- **THEN** the install stops within 120 seconds plus 10 seconds, names `deadline_exceeded` and the asset, and no partial file is left

#### Scenario: Oversized answer
- **WHEN** the server sends more than 64 MiB for an asset
- **THEN** the install stops naming `response_too_large` and the asset, and no partial file is left

### Requirement: An install without release binaries says so
When the installed ref is `main`, or the downloaded copy does not offer the `sw` install step (a release older than the first with binaries), the install/update SHALL install no `sw`, change nothing under `<home>/.specwright/bin/`, continue, and say in its report that no `sw` was installed and why.

#### Scenario: Install of main
- **WHEN** the user installs `main`
- **THEN** the install completes, places no binary, and the report says `sw not installed: main has no release binaries`

#### Scenario: Install of an older tag
- **WHEN** the user installs `v0.23.0`, whose downloaded copy has no `sw` install step
- **THEN** the install completes as before this change, places no binary, and the report says that release ships no `sw`

#### Scenario: Existing binaries stay untouched on main
- **WHEN** the user installs `main` and `<home>/.specwright/bin/0.24.0/sw` exists
- **THEN** that file's bytes, mode and timestamps are unchanged, and no other file under `<home>/.specwright/bin/` is created or removed

### Requirement: Placing sw is atomic and keeps other versions
The install SHALL write the binary into its version directory under a temporary name and rename it to `sw[.exe]` only after the checks pass, so the final path never holds a partial or unchecked file. It SHALL never change another version's directory. A file already at the final path SHALL be kept only when it has the release's SHA-256 and passes the resolver's check. Any other file there SHALL be replaced by that rename.

#### Scenario: Rerun with the binary already placed
- **WHEN** the install of `v0.24.0` runs again and `<home>/.specwright/bin/0.24.0/sw` already matches the release's hash
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
- **WHEN** two projects on one machine install `v0.24.0` at the same time
- **THEN** both installs succeed, the final file has the release's SHA-256, and neither run deletes the other's temporary file

#### Scenario: Rename blocked by a running binary
- **WHEN** on Windows the rename to the final path fails because another process is running that file
- **THEN** the install checks the final file again: when it has the release's SHA-256 and passes the resolver's check, the install succeeds and reports it kept; otherwise it stops with `sw_in_use` naming the path, and nothing else changes

#### Scenario: A temporary file left by a killed run
- **WHEN** the version directory holds a temporary file last modified more than one hour ago
- **THEN** the next install of that version deletes it; a temporary file modified within the last hour is left alone

### Requirement: Recovery leaves placed binaries in place
A rollback or a discarded update SHALL leave every file under `<home>/.specwright/bin/` as it is. The previous version's binary is never touched by the update, and a new version's binary placed before the rollback stays for a later update to that version.

#### Scenario: Rollback after the binary was placed
- **WHEN** an update from 0.24.0 to 0.25.0 placed `bin/0.25.0/sw`, was interrupted during the swap, and the next run rolls back
- **THEN** `VERSION` reads `0.24.0`, `bin/0.24.0/sw` is unchanged, and `bin/0.25.0/sw` is still present

#### Scenario: Previous version had no binary
- **WHEN** a project on 0.23.0 (no `sw`) updates to 0.24.0 and the update rolls back
- **THEN** `VERSION` reads `0.23.0`, and the report says no `sw` serves 0.23.0, which no 0.23.0 skill needs

### Requirement: An install whose VCS steps need a missing sw says so
When the installed version's `vcs.sh` runs `sw` (0.25.0 or newer) and, after the install, the resolver finds no matching `sw` for the project, the Step 8 report SHALL say that every branch, commit and finish step stops with `sw_missing` until one is placed, and SHALL name a tagged install and the contributor bootstrap in `CONTRIBUTING.md`. Otherwise it SHALL add no such warning.

#### Scenario: main install with no binary
- **WHEN** the user installs `main` at 0.25.0 or newer, and `<home>/.specwright/bin/<that version>/` holds no matching `sw`
- **THEN** the Step 8 report holds `sw not installed: main has no release binaries`, says VCS steps stop with `sw_missing`, and names a tagged install and the `CONTRIBUTING.md` bootstrap

#### Scenario: main install with a matching binary already placed
- **WHEN** the user installs `main` and the resolver accepts an `sw` already placed for that version
- **THEN** the Step 8 report holds no `sw_missing` warning

#### Scenario: Older tag whose scripts need no sw
- **WHEN** the user installs `v0.23.0`, which ships no `sw` and whose `vcs.sh` does not run one
- **THEN** the install completes as before and the Step 8 report holds no `sw_missing` warning

#### Scenario: Tagged install with sw placed
- **WHEN** a release tag's `sw-install` returns `installed`, `replaced` or `kept`
- **THEN** the Step 8 report holds no `sw_missing` warning

### Requirement: Contributors place a tree-built sw with one task
`mise run install-sw` in a Specwright checkout SHALL build `sw` from the tree and place it at `<home>/.specwright/bin/<tree VERSION>/sw[.exe]` (`<home>` as the resolver finds it), only after `sw-path.sh --file <built binary> --version <tree VERSION>` accepts the build, and SHALL replace an existing file there only by a rename. It SHALL print the placed path.

#### Scenario: Build placed
- **WHEN** `mise run install-sw` runs in a checkout whose `VERSION` reads `0.25.0`
- **THEN** `<home>/.specwright/bin/0.25.0/sw[.exe]` exists, `sw-path.sh --code <a project at 0.25.0>` prints it, and the task prints that path

#### Scenario: Build fails the check
- **WHEN** the built binary reports another version or interface than the tree's
- **THEN** the task exits non-zero, names the mismatch, and leaves any existing file under `<home>/.specwright/bin/0.25.0/` unchanged
