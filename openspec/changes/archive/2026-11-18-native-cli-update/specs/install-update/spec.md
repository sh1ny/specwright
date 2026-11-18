# Spec Delta

## ADDED Requirements

### Requirement: sw update carries every update subcommand
`sw update <subcommand>` SHALL provide `plan`, `stage`, `swap`, `note-config`, `finish`, `recover`, `pack-check`, `pack-verify`, `pack-docs` and `sw-install` with the options, JSON fields, error and refusal codes, exit codes and file effects that the requirements of this capability give for `update.sh`. Each such requirement SHALL apply to `sw update` as written, messages included. Only the order of fields MAY differ.

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
- **THEN** each subcommand returns the document it returns without them, `VERSION` is stamped after `finish`, and no recorder ran

#### Scenario: Interrupted swap recovered with failing interpreters
- **WHEN** a `sw update swap` is killed after its first rename, and `sw update recover` runs with the same recorders first on `PATH`
- **THEN** recover reports `resumed update to <to>` or `rolled back to <from>` as the staged copy decides, and no recorder ran

#### Scenario: A jj store read in process
- **WHEN** an owner's swap checks a `planning_store.vcs: jj` store that is busy with a change bookmark
- **THEN** the swap stops with `store_busy` naming the bookmark, and no `vcs.sh` or `as.sh` ran

### Requirement: sw update refuses settings the shared reader refuses
`sw update` SHALL read `openspec/specwright.yaml` only through `sw`'s shared settings reader. When that reader refuses the file, `plan` and every subcommand that reads it SHALL stop before any write with `settings_invalid`, naming the file, the line and the problem, and saying to fix the file and rerun the update. A missing file SHALL read as no settings.

#### Scenario: A plain yes in the settings
- **WHEN** `openspec/specwright.yaml` sets `review.preship` to a plain `yes` and the prompt runs `sw update plan`
- **THEN** `plan` exits 1 with `settings_invalid`, names the file, the line and that `yes` must be written `true`, and no file is written

#### Scenario: No settings file
- **WHEN** the code checkout has no `openspec/specwright.yaml` (a fresh install)
- **THEN** `plan` reads no `main_branch`, `vcs` or `planning_store` setting, detects the main branch, and continues

### Requirement: update.sh hands over to the download's sw
Until scripts are retired, `scripts/update.sh` SHALL be a shim that resolves `sw` for the download's `VERSION` at `<home>/.specwright/bin/<version>/` and hands every argument to `sw update` unchanged. When no matching `sw` is found it SHALL print `sw_missing` JSON and exit 1. It SHALL never run another implementation, another version or an `sw` from `PATH`.

#### Scenario: Shim with the download's sw placed
- **WHEN** `bash <download>/scripts/update.sh plan --code <project>` runs, and the download's `VERSION` is 0.37.0 with `<home>/.specwright/bin/0.37.0/sw` placed
- **THEN** it prints the document that `sw update plan --code <project> --download <download>` prints, with the same exit status

#### Scenario: Shim with no matching sw
- **WHEN** the shim runs and `<home>/.specwright/bin/0.37.0/` holds no `sw`, or one that reports another version
- **THEN** it prints `{"ok":false,"error":"sw_missing",...}`, exits 1, and no file is written

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

## MODIFIED Requirements

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

### Requirement: An install whose VCS steps need a missing sw says so
After the install, the Step 8 report SHALL run the resolver for the project. When it finds no matching `sw`, the report SHALL say that every branch, commit and finish step stops with `sw_missing` until one is placed, and SHALL name a tagged install and the contributor bootstrap in `CONTRIBUTING.md`. Otherwise it SHALL add no such warning.

#### Scenario: main install with no binary
- **WHEN** a `main` install built `sw`, and the version directory was emptied before Step 8
- **THEN** the Step 8 report says VCS steps stop with `sw_missing`, and names a tagged install and the `CONTRIBUTING.md` bootstrap

#### Scenario: main install with a matching binary already placed
- **WHEN** the user installs `main` and the resolver accepts the built `sw`
- **THEN** the Step 8 report holds no `sw_missing` warning

#### Scenario: Older tag whose scripts need no sw
- **WHEN** the user asks for `v0.23.0`, whose `vcs.sh` runs no `sw`
- **THEN** the prompt stops under the minimum-release rule before Step 8, so no `sw_missing` warning is reported

#### Scenario: Tagged install with sw placed
- **WHEN** a release tag's `sw-install` returns `installed`, `replaced` or `kept`
- **THEN** the Step 8 report holds no `sw_missing` warning

### Requirement: Contributors place a tree-built sw with one task
`mise run install-sw` in a Specwright checkout SHALL build `sw` from the tree and run the built binary to place it at `<home>/.specwright/bin/<tree VERSION>/sw[.exe]` (`<home>` as the resolver finds it), with no bash. It SHALL place it only after the built binary reports the tree's `VERSION` and the skills' interface, SHALL place the notice before the binary, and SHALL replace an existing file there only by a rename. It SHALL print the placed path.

#### Scenario: Build placed
- **WHEN** `mise run install-sw` runs in a checkout whose `VERSION` reads `0.37.0`
- **THEN** `<home>/.specwright/bin/0.37.0/sw[.exe]` exists with `THIRD_PARTY_NOTICES.txt` beside it, `sw-path.sh --code <a project at 0.37.0>` prints it, and the task prints that path

#### Scenario: Build fails the check
- **WHEN** the built binary reports another version or interface than the tree's
- **THEN** the task exits non-zero, names the mismatch, and leaves any existing file under `<home>/.specwright/bin/0.37.0/` unchanged

#### Scenario: No bash on PATH
- **WHEN** on Windows `mise run install-sw` runs with no `bash` on `PATH`
- **THEN** the build is placed as above

## REMOVED Requirements

### Requirement: The install prompt drives update-script interface 2
**Reason**: The prompt now drives `sw update`, which reports interface 3. It installs only releases that have `sw update`, so interface 1 and interface 2 downloads are out of its range.
**Migration**: Install a release older than 0.37.0 with that tag's own README prompt. The new requirement "The install prompt drives sw update interface 3" replaces this one, and a pending format 1 or 2 journal is still recovered.
