# Spec Delta

## MODIFIED Requirements

### Requirement: Every platform's binary is built and checked in CI
For each pull request that touches `cli/` or the build, CI SHALL build `sw` for linux-x64, linux-arm64, windows-x64, macos-arm64 and macos-x64, each on a runner of that platform, run its tests there, and upload each binary with a SHA-256 checksum. A separate job per target SHALL download that artifact on a runner of the same platform, verify the checksum, and run `sw version --json`, checking that `version` equals `VERSION` and `interface` equals the interface the skills expect. Any mismatch SHALL fail the job.

#### Scenario: All three builds pass
- **WHEN** a pull request changes `cli/`
- **THEN** the linux-x64, windows-x64 and macos-arm64 build, test and download-and-run jobs pass as they did before linux-arm64 and macos-x64 were added

#### Scenario: All five builds pass
- **WHEN** a pull request changes `cli/`
- **THEN** each target's build, test and download-and-run jobs pass and five binaries with checksums are attached to the run

#### Scenario: Checksum does not match
- **WHEN** a downloaded binary's SHA-256 differs from its recorded checksum
- **THEN** the download-and-run job fails, naming the file, and does not run the binary

#### Scenario: Version drifts from VERSION
- **WHEN** `sw version --json` reports a version other than the `VERSION` file's
- **THEN** the download-and-run job fails, naming both versions

#### Scenario: Interface differs from the skills'
- **WHEN** `sw version --json` reports an interface other than the one the skills expect
- **THEN** the download-and-run job fails, naming both interfaces

#### Scenario: One target's runner fails
- **WHEN** the linux-arm64 build or its download-and-run job fails
- **THEN** that job fails, and the other targets' jobs still run and report their own results

## ADDED Requirements

### Requirement: Each published release carries checked binaries
When a GitHub release of this repository is published, a release workflow SHALL build `sw` for all five targets from the tagged commit, check each one as the pull-request jobs do (checksum, `version` equal to the tag's `VERSION`, `interface` equal to the skills' interface at the tag, the macOS quarantine step on both macOS targets), and only after every check passes attach the five binaries and one `SHA256SUMS` file to that release.

#### Scenario: Release published
- **WHEN** `v0.24.0` is published as a GitHub release
- **THEN** the release lists `sw-linux-x64`, `sw-linux-arm64`, `sw-windows-x64.exe`, `sw-macos-arm64`, `sw-macos-x64` and `SHA256SUMS`, and each binary reports `"version": "0.24.0"`

#### Scenario: One target fails its check
- **WHEN** the macos-x64 binary fails its download-and-run check
- **THEN** the workflow fails naming that target, and attaches no asset to the release

#### Scenario: Tag's VERSION differs from the tag
- **WHEN** the release's tag is `v0.24.0` but `VERSION` at the tagged commit reads `0.23.0`
- **THEN** the workflow fails naming both versions and attaches no asset

#### Scenario: Interface mismatch at the tag
- **WHEN** a binary built at the tag reports an interface other than the skills' interface at the tag
- **THEN** the workflow fails naming both interfaces and attaches no asset

### Requirement: Release assets have fixed names and one checksum file
The release assets SHALL be named `sw-<target>` (`sw-<target>.exe` on Windows), for the targets `linux-x64`, `linux-arm64`, `windows-x64`, `macos-arm64` and `macos-x64`. `SHA256SUMS` SHALL hold one line per binary, `<64 lowercase hex digits>  <asset name>`, and nothing else. Renaming an asset, or changing this format, is a workflow change (minor version).

#### Scenario: Checksum file content
- **WHEN** the release workflow attaches the assets of `v0.24.0`
- **THEN** `SHA256SUMS` has exactly five lines, one per binary asset name, and each hash equals the SHA-256 of that asset's bytes

#### Scenario: A malformed checksum line
- **WHEN** a consumer reads a `SHA256SUMS` line with an uppercase or short hash, a single space, or an asset name outside the five
- **THEN** the consumer treats the file as invalid and uses no hash from it

### Requirement: SHA256SUMS is uploaded last and seals the release
The workflow SHALL upload `SHA256SUMS` only after all five binaries are attached and each attached binary, read back from the release, has the hash it lists. Once a release has `SHA256SUMS`, no run SHALL replace or add any of its assets. Runs for one tag, from either trigger, SHALL never overlap. The workflow SHALL also run by hand for a named tag, and SHALL fail when the tag has no release.

#### Scenario: Re-run after a failed upload
- **WHEN** a release has `sw-linux-x64` and `sw-linux-arm64` but no `SHA256SUMS`, and the workflow is run by hand for that tag
- **THEN** all five binaries are attached from this run's build (the two existing ones replaced), then `SHA256SUMS` is attached, matching every binary

#### Scenario: Overlapping runs for one tag
- **WHEN** a manual run for `v0.24.0` starts while the release-event run for `v0.24.0` is still attaching, and the two builds differ in their bytes
- **THEN** the manual run waits until the first ends, then finds the release sealed and changes nothing, and each binary on the release has the hash `SHA256SUMS` lists for it

#### Scenario: A binary changed before the seal
- **WHEN** an attached binary read back before the seal has a hash other than the one this run built
- **THEN** the run fails naming that asset and both hashes, and uploads no `SHA256SUMS`

#### Scenario: Sealed release run again
- **WHEN** the workflow runs by hand for a release that already has `SHA256SUMS` and all five binaries
- **THEN** the run changes no asset and reports the release as already complete

#### Scenario: Sealed release missing a binary
- **WHEN** a release has `SHA256SUMS` but `sw-macos-x64` was deleted from it
- **THEN** the run fails, naming the missing asset and saying the sealed release needs the owner, and uploads nothing

#### Scenario: No release for the tag
- **WHEN** the workflow is run by hand for a tag that has no GitHub release
- **THEN** the run fails, saying that the tag has no release, and attaches nothing

### Requirement: A project's sw is found and checked before use
A shared resolver SHALL take the project's code checkout, read its `openspec/.specwright/VERSION`, and look for `sw` at `<home>/.specwright/bin/<version>/sw[.exe]` (`<home>` is `SPECWRIGHT_HOME` when set, else the user's home). It SHALL run that file's `sw version --json`. When `version` equals `VERSION` and `interface` equals the interface the installed skills were written for, it SHALL print the absolute path and exit 0.

#### Scenario: Matching binary
- **WHEN** `VERSION` reads `0.24.0` and `<home>/.specwright/bin/0.24.0/sw` reports `0.24.0` and the expected interface
- **THEN** the resolver prints that path and exits 0

#### Scenario: SPECWRIGHT_HOME override
- **WHEN** `SPECWRIGHT_HOME` names a directory holding `.specwright/bin/0.24.0/sw`
- **THEN** the resolver prints the path under `SPECWRIGHT_HOME`, not under the user's home

#### Scenario: Override set but its binary missing
- **WHEN** `SPECWRIGHT_HOME` is set, holds no `.specwright/bin/0.24.0/sw`, and the user's home does hold one
- **THEN** the resolver exits 1 with the stop message naming the path under `SPECWRIGHT_HOME`, prints nothing on stdout, and does not use the file under the user's home

#### Scenario: Project has no VERSION
- **WHEN** the code checkout has no `openspec/.specwright/VERSION`
- **THEN** the resolver exits 1 with the stop message, saying no installed version was found, and runs no binary

### Requirement: A missing or mismatched sw stops with one message
When the project has no `VERSION`, or the binary is missing, cannot run, prints anything other than one JSON object with both fields, or reports another `version` or `interface`, the resolver SHALL print `sw missing or mismatched: rerun the install prompt` and the detail (the path and what was found) on stderr, print nothing on stdout, and exit 1. It SHALL never fall back to another version's binary, or to an `sw` on `PATH`.

#### Scenario: Binary missing
- **WHEN** `VERSION` reads `0.24.0` and `<home>/.specwright/bin/0.24.0/` holds no `sw`
- **THEN** the resolver exits 1 with the stop message and the expected path, even when `<home>/.specwright/bin/0.23.0/sw` exists

#### Scenario: Interface mismatch
- **WHEN** the binary reports `"version": "0.24.0"` and an interface other than the skills' interface
- **THEN** the resolver exits 1 with the stop message, naming both interfaces

#### Scenario: Version report is not JSON
- **WHEN** the file at the path prints text that is not one JSON object, or exits non-zero
- **THEN** the resolver exits 1 with the stop message, and prints nothing on stdout
