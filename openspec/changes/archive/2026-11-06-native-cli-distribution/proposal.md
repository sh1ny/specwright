# Proposal

## Why

The `native-cli-spike` change proved that `sw` builds and runs on three platforms, but only as CI artifacts. No release carries a binary, the install does not put one where ADR 0027 says skills will look (`<home>/.specwright/bin/<version>/`), and nothing yet checks that a project runs the `sw` of its installed version. The next three M7 changes (`native-cli-vcs`, `-commit`, `-finish`) switch skills to `sw`, so each release needs its binaries and each install needs a verified copy first.

This change serves **M7 - Native CLI foundation** (change 4 of 7). It advances the agent-verified exit criterion "CI builds and checks a versioned binary on Linux, Windows and macOS; distribution artifacts and checksums are verified and the install path handles a missing or incompatible binary explicitly". It also adds to "All M7 changes are archived on main and their releases are published", because from now on a published release includes its binaries. It is constrained by ADR 0027 (install root, exact version and interface check, unsigned-first stance with the macOS quarantine step, target set), ADR 0011 (staged install with a journal and recovery), ADR 0010 (tags and releases), ADR 0014 (bounds on network commands), ADR 0008 (fenced GitHub identity) and ADR 0021 (install locations are the user's to manage).

## What Changes

- **Five targets.** `sw` is built for linux-x64, linux-arm64, windows-x64, macos-arm64 and macos-x64. Each build is checked on a native runner of its platform, for pull requests and for releases.
- **Release assets.** A new release workflow runs when a GitHub release is published. It builds every target, checks each one (checksum, `sw version --json` against the tag's `VERSION`, and the macOS quarantine step), and attaches the five binaries and one `SHA256SUMS` file to the release. A manual run for a given tag re-attaches missing assets. `release.sh` still publishes the tag and the release, and it is unchanged: it ships to every project, and only this repository builds `sw`.
- **Install puts `sw` in place.** The install and update download the host platform's binary from the chosen release and check it against `SHA256SUMS` before it runs. On macOS they remove the quarantine attribute from the file they checked. They then confirm that `sw version --json` reports the installed version and the interface the skills expect, and place the binary at `<home>/.specwright/bin/<version>/sw[.exe]` (`SPECWRIGHT_HOME` overrides `<home>`). Versions sit side by side. The binary is never written into a work tree.
- **Missing or incompatible binary.** For a release tag that ships binaries, a missing platform asset, a failed or bounded download, a checksum mismatch or a wrong version or interface stops the install before any installed file changes. That includes a release whose assets are not uploaded yet: the install says to retry once they are. Installing `main`, or a tag older than the first release with binaries, installs no `sw` and says so in the report.
- **Recovery stays intact.** An interrupted install or update still discards, resumes or rolls back from its journal as before. The binary goes into its own version directory by temp file and rename, so a failed or repeated run never leaves a partial binary at the final path, and it never touches another version's binary.
- **Shared resolver.** One tested resolver derives the `sw` path from the project's `openspec/.specwright/VERSION` and runs `sw version --json`. It prints the verified path, or stops with `sw missing or mismatched: rerun the install prompt`. No skill calls it in this change: the VCS, commit and finish ports call it when they switch to `sw`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `native-cli`: the build and check matrix grows to five targets, a release workflow attaches the checked binaries and `SHA256SUMS` to each published release, and a resolver locates and checks a project's `sw`.
- `install-update`: the install and update download, check and place the host's `sw` for a tagged release, stop on a missing or incompatible binary, report an install without `sw` for `main` or older tags, and keep recovery unchanged.

## Impact

- **CI:** `.github/workflows/cli.yml` (adds the linux-arm64 and macos-x64 runners) and a new release workflow with `contents: write`, triggered by a published release.
- **Install and update:** the README install prompt (Step 3 and Step 7) and `scripts/update.sh` (download, checksum, quarantine step, version check, placement; the interface number if its subcommands change). The `install-update` evals cover these.
- **CLI:** `cli/tool/verify_artifact.py` is reused or extended for `SHA256SUMS`. The resolver is new, with its own tests.
- **Release:** `release.sh` and the `releases` capability are unchanged. The release workflow reacts to the release that `release.sh` creates.
- **Docs:** ADR 0027 is accepted and is not edited. The architecture rows for `sw` and the install are updated. `CONTRIBUTING.md` explains how to add a target.
- **Users:** after an update, each user has a `~/.specwright/bin/<version>/sw` (about 5 to 10 MB per version). Nothing removes old versions.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Release targets

- **Choice:** five targets: linux-x64, linux-arm64, windows-x64, macos-arm64 and macos-x64. Each is built and checked on a native runner.
- **Rejected:** only the spike's three, which leaves ARM Linux and Intel Mac users with no `sw` and contradicts ADR 0027's target list. Four without macOS x64, which drops Intel Macs while their runner is still supported.
- **Reversal cost:** medium (dropping a target later strands users on that platform; adding one is cheap)
- **Important:** yes (users see it: it decides which platforms can run Specwright once skills need `sw`)
- **Chosen by:** user

### S2: How binaries reach a release

- **Choice:** a release workflow, triggered when a release is published (and runnable by hand for a given tag), builds and checks every target and attaches the binaries and `SHA256SUMS`. `release.sh` is unchanged. The option as chosen also changed its report, but `release.sh` ships to every project and only this repository builds `sw`, so the window before upload is handled by the install, which stops and says to retry.
- **Rejected:** `release.sh` waiting for the upload, which makes publish slow and ties it to CI. A manual dispatch, which lets a release ship with no binaries.
- **Reversal cost:** medium (the asset names and `SHA256SUMS` become a contract the install reads)
- **Important:** yes (binds future changes: asset names and the checksum file are read by every later install)
- **Chosen by:** user

### S3: Install behaviour without a matching `sw`

- **Choice:** installing a release tag that ships binaries stops before any write when `sw` cannot be downloaded, checked or matched. Installing `main`, or a tag older than the first release with binaries, installs no `sw` and says so explicitly.
- **Rejected:** always warning and continuing, which leaves projects without `sw` just before the ports need it. Always stopping, which breaks `main` installs or makes them need a local Dart toolchain.
- **Reversal cost:** low (a policy in the install prompt and `update.sh`)
- **Important:** yes (users see it: an install can now fail on a binary)
- **Chosen by:** user

### S4: Where the skill-side check lands

- **Choice:** one shared, tested resolver that later ports call. No skill calls it in this change.
- **Rejected:** checking `sw` at every change start in the `specwright-branch` gate, which stops users over a binary no step uses yet.
- **Reversal cost:** high (every ported skill will call it; ADR 0027 rates the version check high)
- **Important:** yes (binds future changes: the VCS, commit and finish ports depend on its contract)
- **Chosen by:** user

### S5: Old binary versions

- **Choice:** out of scope. Versions stay side by side, and nothing removes old ones.
- **Rejected:** pruning on update, which could delete a binary that another project on the machine still pins.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S6: Signing

- **Choice:** out of scope. Binaries stay unsigned, as ADR 0027 decided. ADR 0027's signing trigger still applies.
- **Rejected:** signing now, before any evidence calls for it (ADR 0027).
- **Reversal cost:** low
- **Important:** no (already decided by ADR 0027)
- **Chosen by:** agent

## Release Notes

Releases now ship the `sw` native CLI. Each published release carries five checked binaries (Linux x64 and arm64, Windows x64, macOS arm64 and x64) and a `SHA256SUMS` file, and installing a release tag places the host's binary under `~/.specwright/bin/<version>/`. A tag install stops before changing anything when the binary is missing, not uploaded yet or does not match; `main` installs no binary. The binaries are unsigned: on macOS the install clears the quarantine flag only after the checksum matches. Nothing calls `sw` yet: the VCS, commit and finish ports switch to it next.

### Added

- Release binaries of `sw` for linux-x64, linux-arm64, windows-x64, macos-arm64 and macos-x64, with a `SHA256SUMS` file, built and checked by a release workflow (#148).
- The install and update download, check and place `sw` at `~/.specwright/bin/<version>/`, and stop when a release's binary is missing or does not match (#148).
- A shared resolver that finds a project's `sw` and checks its version and interface, for the upcoming ports (#148).
