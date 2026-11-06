# Spec Delta

## ADDED Requirements

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
