# Spec Delta

## MODIFIED Requirements

### Requirement: Every backend takes in-repo and user-level targets
`sw update plan` SHALL accept a `--skills` or `--agents` directory inside or outside the code work tree, whatever `vcs` selects. The install prompt SHALL offer both locations on every backend. With `vcs: gitbutler` it SHALL warn before the user chooses that every applied branch shares the work tree, so a branch that changes in-repo skills changes them for every applied branch.

#### Scenario: In-repo target for a GitButler project
- **WHEN** `sw update plan --download <tree>` runs with `--skills <code>/.claude/skills` and `<code>/openspec/specwright.yaml` has `vcs: gitbutler`
- **THEN** `plan` and `stage` each exit 0 with no refusal naming that directory, and `stage` stages the skills for that directory

#### Scenario: User-level target for a GitButler project
- **WHEN** the same project's update names `--skills ~/.claude/skills`
- **THEN** the plan holds no refusal for that directory

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

### Requirement: Pack documents are created by an idempotent step after the stamp
`sw update pack-docs` SHALL create each missing pack document from its template, never overwrite one, and report each as `created` or `kept`. It SHALL depend on no journal, so a rerun after an interruption completes it; the prompt SHALL run it after the stamp.

#### Scenario: Documents after a finished install
- **WHEN** the stamp is written and `docs/game/gdd.md` does not exist
- **THEN** pack-docs creates it from the gamedev template and reports `created`

#### Scenario: Interrupted document creation
- **WHEN** pack-docs stops after creating one of two documents and is run again
- **THEN** the first is reported `kept` with its content unchanged and the second `created`

### Requirement: An install whose VCS steps need a missing sw says so
Step 8 SHALL check that `<home>/.specwright/bin/<project VERSION>/sw[.exe]` exists and its `version --json` exits 0 in 10 s with that version and the installed skills' interface (`specwright-pr`'s `interface <n>` line, or an older tag's `SW_INTERFACE=`). On a failure it SHALL warn that branch, commit and finish steps stop until a matching `sw` is placed, that another version's `sw` stops with `sw_mismatch`, and name a tagged install and the `CONTRIBUTING.md` bootstrap; otherwise no warning.

#### Scenario: A binary of the right version and an old interface
- **WHEN** the installed skills require interface 2 and the pinned binary reports the project's version but interface 1
- **THEN** the Step 8 report gives the same warning as for a missing binary and does not report the install ready

#### Scenario: An older supported tag
- **WHEN** the new install prompt selects `v0.37.0`, whose installed skills pin interface 1 in `sw-path.sh`, its `sw-install` returns `installed`, and at Step 8 the pinned binary exits 0 reporting `0.37.0` and interface 1
- **THEN** the Step 8 report gives no missing-binary warning

#### Scenario: The interface named in prose and on its own line
- **WHEN** the installed `specwright-pr/SKILL.md` says in a paragraph that an older `sw` reported interface 2, holds the line `interface 3` on its own, and the pinned binary reports the project's version and interface 3
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

## ADDED Requirements

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
Step 4 SHALL ask about each `specwright-*` skill directory among the current plan's `orphans` that this update does not install, and remove those the user agrees to remove, after a new `swap` or, when the plan shows a completed swap and Step 4 skips `stage` and `swap`, once that swap is confirmed. It SHALL do so before Step 5. Other `orphans` entries, such as agent files and pack skills, are outside this rule.

#### Scenario: A rerun that removes an orphan kept before
- **WHEN** the prompt is run again after a swap that kept `specwright-old`, the plan lists it among `orphans` with the swap already completed, and the user now agrees to remove it
- **THEN** Step 4 removes `specwright-old` before Step 5, Step 7's skills check passes, and with every other Step 7 check passing `VERSION` is stamped

#### Scenario: A rerun that keeps it again
- **WHEN** the same rerun's user declines the removal again
- **THEN** `specwright-old` stays, Step 7's skills check passes, and Step 8 lists it as an orphan kept
