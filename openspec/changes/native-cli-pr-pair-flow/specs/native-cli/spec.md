## MODIFIED Requirements

### Requirement: Release assets have fixed names and one checksum file
Binary assets SHALL keep the five `sw-<target>` names and Windows `.exe` suffix. From 0.30.0, releases SHALL also carry `THIRD_PARTY_NOTICES.txt`. `SHA256SUMS` SHALL hold one `<64 lowercase hex digits>  <asset name>` line per required asset, with no unknown or duplicate names. Older releases retain their five-binary manifest. Renaming an asset, or changing this format, is a workflow change (minor version).

#### Scenario: Checksum file content
- **WHEN** the release workflow attaches the assets of `v0.24.0`
- **THEN** `SHA256SUMS` has exactly five lines, one per binary asset name, and each hash equals the SHA-256 of that asset's bytes

#### Scenario: A malformed checksum line
- **WHEN** a consumer reads a `SHA256SUMS` line with an uppercase or short hash, a single space, an unknown name or a duplicate name
- **THEN** the consumer treats the file as invalid and uses no hash from it

### Requirement: SHA256SUMS is uploaded last and seals the release
The workflow SHALL upload `SHA256SUMS` only after every asset required for that release (the five binaries and, from 0.30.0, the notice) is attached and each, read back from the release, has the hash it lists. Once a release has `SHA256SUMS`, no run SHALL replace or add any of its assets. Runs for one tag, from either trigger, SHALL never overlap. The workflow SHALL also run by hand for a named tag, and SHALL fail when the tag has no release.

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
- **WHEN** the workflow runs by hand for a release that already has `SHA256SUMS` and every asset required for its version
- **THEN** the run changes no asset and reports the release as already complete

#### Scenario: Sealed release missing a binary
- **WHEN** a release has `SHA256SUMS` but `sw-macos-x64` was deleted from it
- **THEN** the run fails, naming the missing asset and saying the sealed release needs the owner, and uploads nothing

#### Scenario: No release for the tag
- **WHEN** the workflow is run by hand for a tag that has no GitHub release
- **THEN** the run fails, saying that the tag has no release, and attaches nothing

## ADDED Requirements

### Requirement: Third-party notices accompany new sw distributions
From 0.30.0, builds, releases and installs SHALL include `THIRD_PARTY_NOTICES.txt` alongside the binary. Release upload SHALL verify the notice by read-back before sealing; sealed assets SHALL never change. Downloaded binary and notice hashes SHALL be verified before the binary runs. Failed notice verification or placement SHALL report failure without replacing an existing binary. Reruns SHALL repair missing or incorrect notices even when keeping the binary.

#### Scenario: New release carries a verified notice before sealing
- **WHEN** the 0.30.0 release is attached
- **THEN** it contains five binaries, the notice and `SHA256SUMS`, the notice hash matches its bytes, and the seal is uploaded only after all six assets pass read-back

#### Scenario: Sealed new release lacks its notice
- **WHEN** a release from 0.30.0 has its checksum seal but lacks its notice
- **THEN** attachment fails naming the missing notice and changes no release asset

#### Scenario: Download installs the notice beside the binary
- **WHEN** the tagged installer installs a release from 0.30.0
- **THEN** it verifies the notice and binary before running the downloaded binary and installs the notice in the binary's version directory

#### Scenario: Notice failure preserves the existing binary
- **WHEN** the new release notice is missing, corrupt or cannot be placed
- **THEN** `sw-install` returns `ok: false` with `sums_invalid`, `asset_missing`, `checksum_mismatch` or `notice_write_failed`, its message names the notice and the release, the install stops before staging, the downloaded binary did not run before notice verification, and any existing binary is byte-identical

#### Scenario: Kept binary gets its notice repaired
- **WHEN** a new-release install rerun keeps a matching binary but its installed notice is missing or incorrect
- **THEN** installation repairs the notice before reporting success

#### Scenario: Source-build install includes notices
- **WHEN** the local source-build installer places a checked binary
- **THEN** it places the source notice beside that binary and does not report success if required notice placement fails

#### Scenario: Older release needs no retrospective notice
- **WHEN** the tagged installer or attachment tool handles a release before 0.30.0 with its original five-binary manifest
- **THEN** the old release remains usable without adding a notice or modifying a sealed release

#### Scenario: Build artifacts carry identical notices
- **WHEN** a ref at 0.30.0 or later is built for the five targets
- **THEN** each artifact holds the same notice bytes and a matching checksum file, and a missing source notice fails the build

#### Scenario: Older tag builds without a notice
- **WHEN** the current build workflow runs for a tag below 0.30.0
- **THEN** it requires no notice and a sealed release reports complete without any asset change

#### Scenario: Notice read-back differs before the seal
- **WHEN** the notice read back from an unsealed 0.30.0 release differs from the built notice
- **THEN** attachment fails naming the notice and both hashes, and uploads no `SHA256SUMS`
