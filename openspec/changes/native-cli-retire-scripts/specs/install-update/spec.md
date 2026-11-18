# Spec Delta

## MODIFIED Requirements

### Requirement: Placing sw is atomic and keeps other versions
The install SHALL write the binary into its version directory under a temporary name and rename it to `sw[.exe]` only after the checks pass, so the final path never holds a partial or unchecked file. It SHALL never change another version's directory. A file already at the final path SHALL be kept only when it has the release's SHA-256 and its `sw version --json` reports the release's version. Any other file there SHALL be replaced by that rename.

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
- **THEN** the install checks the final file again: when it has the release's SHA-256 and its `sw version --json` reports the release's version, the install succeeds and reports it kept; otherwise it stops with `sw_in_use` naming the path, and nothing else changes

#### Scenario: A temporary file left by a killed run
- **WHEN** the version directory holds a temporary file last modified more than one hour ago
- **THEN** the next install of that version deletes it; a temporary file modified within the last hour is left alone

### Requirement: An install whose VCS steps need a missing sw says so
After the install, the Step 8 report SHALL check `<home>/.specwright/bin/<project VERSION>/sw[.exe]`: the file exists and its `sw version --json` exits 0 within 10 seconds reporting that version and the interface the installed skills require: the `interface` line of the installed `specwright-pr` skill, or for a tag older than this change the `SW_INTERFACE=` line of its installed `sw-path.sh`. When the check fails, the report SHALL say that every branch, commit and finish step stops until a matching `sw` is placed, and that an `sw` of another version stops with `sw_mismatch`. It SHALL name a tagged install and the contributor bootstrap in `CONTRIBUTING.md`. Otherwise it SHALL add no such warning.

#### Scenario: A binary of the right version and an old interface
- **WHEN** the installed skills require interface 2 and the pinned binary reports the project's version but interface 1
- **THEN** the Step 8 report gives the same warning as for a missing binary and does not report the install ready

#### Scenario: An older supported tag
- **WHEN** the new install prompt selects `v0.37.0`, whose installed skills pin interface 1 in `sw-path.sh`, its `sw-install` returns `installed`, and at Step 8 the pinned binary exits 0 reporting `0.37.0` and interface 1
- **THEN** the Step 8 report gives no missing-binary warning

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
`mise run install-sw` in a Specwright checkout SHALL build `sw` from the tree and run the built binary to place it at `<home>/.specwright/bin/<tree VERSION>/sw[.exe]` (`<home>` is `SPECWRIGHT_HOME` when set, else the user's home), with no bash. It SHALL place it only after the built binary reports the tree's `VERSION` and a workflow interface equal to the tree's skill pin (the `interface` line of `skills/specwright-pr/SKILL.md`), never the running binary's own constant, SHALL place the notice before the binary, and SHALL replace an existing file there only by a rename. It SHALL print the placed path.

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

## REMOVED Requirements

### Requirement: update.sh hands over to the download's sw
**Reason**: `scripts/update.sh` is removed. The README install prompt already runs the download's checked `sw update` directly, with no bash or Python.
**Migration**: Run the README install prompt, or run `<sw> update <subcommand> ... --download <download>` with the same arguments in place of `bash <download>/scripts/update.sh <subcommand> ...`. See "The install prompt drives sw update interface 3" and native-cli's "Retired script names map to sw commands".
