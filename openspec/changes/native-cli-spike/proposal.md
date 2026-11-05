# Proposal

## Why

Specwright's shipped tooling is bash wrapped around about 7,000 lines of Python heredocs, plus three byte-identical copies of `bounded.py` (#148). It needs two runtimes and per-script interpreter lookup, and it has no linting, types or unit tests below the black-box evals. #148 replaces it with one Dart executable, `sw`. The language is fixed there. The expensive and uncertain parts are not the ports: they are holding a Windows process tree from Dart, building and delivering a binary on three platforms, and how an unsigned binary fares with macOS Gatekeeper and antivirus. This change proves those parts before any script depends on `sw`.

It serves **M7 - Native CLI foundation**, change 3 of 7. It advances three exit criteria:
- the reviewed architecture decision on distribution, installation and the interface-version contract, which records what it supersedes (ADR 0002, parts of 0014);
- bounded processes that keep deadlines, output bounds, secret handling and process-tree cleanup on Windows and POSIX, with regression coverage;
- CI that builds and checks a versioned binary on Linux, Windows and macOS. This change builds and checks CI artifacts with checksums. Publishing them and the install path belong to `native-cli-distribution`.

The milestone's exit criteria are all agent-verified. The Malwarebytes check is a `[user]` task in this change, because it can only run on the owner's machine.

## What Changes

- A Dart package in `cli/` with the `sw` entry point, pinned through a `mise.toml` (pure Dart, not Flutter), with lints, `dart_test.yaml` tags and mise tasks for test, analyze and format.
- `sw version --json` reports the binary version and an interface version: the contract skills and the install will check before using a binary.
- `sw run --bounded [--paged] [--secret] -- <cmd...>` runs one command under ADR 0014's rules: deadline, byte bounds, named limits, secret mode, exit observed when it happens, and the whole process tree stopped. On Windows the command is born inside a job object, through `sw` starting itself as a helper, which the parent assigns to the job before the helper may start the command. On POSIX the command runs in its own process group. The rules and regression tests from #114 and #116 carry over.
- A CI workflow that builds `sw` on Linux, Windows and macOS, runs the Dart tests and the process-tree tests on each, and uploads each binary with a SHA-256 checksum. A separate job per OS downloads the artifact, checks its checksum and runs it.
- A new ADR records that shipped tooling becomes one Dart binary. It covers the versioned install at user level, the interface-version contract, the build and distribution shape, the unsigned-first stance, and what it supersedes: ADR 0002, plus 0014's Python-specific parts. Nothing in the skills calls `sw` yet, and every script stays as it is.
- An eval suite drives `sw` as a black box, and `evals/suites.json` maps `cli/**`.

## Capabilities

### New Capabilities
- `native-cli`: the `sw` executable. Covers its version and interface-version report, its bounded process runner, its toolchain pin and the CI build, checksum and download-and-run check on three platforms.

### Modified Capabilities
- `eval-runner`: the CI workflow builds and checks `sw` on every OS. The suite map covers the Dart sources, and contributors run Dart tests locally through mise, only for the module being written.

## Impact

- New: `cli/` (Dart package), `mise.toml`, a CI workflow or job for the binary, an eval suite for `sw`, `docs/adr/0027-*.md` and its row in `openspec/architecture.md`.
- Changed: `.github/workflows/`, `evals/suites.json`, `AGENTS.md` and `CONTRIBUTING.md` (Dart test rules), `.gitignore` (build outputs).
- Unchanged: every shipped script and skill, `bounded.py` and its copies, the install prompt and `update.sh`. No project receives a binary from this change.
- Dependencies: Dart SDK through mise (version from the owner's other projects), `package:args`, `package:ffi` and possibly `package:win32`. CI uses `jdx/mise-action` pinned to mise 2026.10.12.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: `sw` is installed at user level, by version

- **Choice:** the ADR fixes a user-level versioned location (for example `~/.specwright/bin/<version>/sw[.exe]`). The project's installed version picks which binary runs, so no binary lands in a work tree, including GitButler's shared one.
- **Rejected:** a per-project gitignored binary (#148's suggestion). It puts an executable in every work tree, and a fresh clone lacks it. Deferring the location to `native-cli-distribution` was also rejected, because it leaves the M7 ADR criterion open.
- **Reversal cost:** high
- **Important:** yes (binds future changes: the install path skills call)
- **Chosen by:** user

### S2: The spike's code is the foundation, not a throwaway

- **Choice:** `cli/`, `sw version`, `sw run --bounded` and the CI build stay, and later changes build on them. No skill calls `sw` in this change.
- **Rejected:** a throwaway prototype, which would repeat the same work in `native-cli-distribution`.
- **Reversal cost:** low
- **Important:** yes (binds future changes)
- **Chosen by:** user

### S3: Unsigned binaries, measured first

- **Choice:** the builds stay unsigned. The spike checks the macOS quarantine path in CI, and the owner checks a downloaded Windows build with Malwarebytes (a `[user]` task). The ADR names signing and notarisation as the response if either check shows a block.
- **Rejected:** signing from day one, which needs certificates, an Apple developer account and CI secrets before any evidence says they are needed.
- **Reversal cost:** medium
- **Important:** yes (changes what users run and see)
- **Chosen by:** user

### S4: Pure Dart pinned through mise

- **Choice:** a `mise.toml` pins `dart` (no Flutter), with mise tasks for test, analyze and format. CI uses `jdx/mise-action` pinned to mise 2026.10.12, as the owner's other Dart projects do. Locally, only the Dart test module being written runs, through `mise exec -- dart test`.
- **Rejected:** pinning Flutter like the app repos (a heavier download, and `sw` has no UI); `dart-lang/setup-dart` without mise (it diverges from the owner's other projects).
- **Reversal cost:** low
- **Important:** yes (binds future changes: contributor toolchain)
- **Chosen by:** user

### S5: A straight port, not engine-shaped

- **Choice:** `sw` ports the scripts behind their existing JSON and exit-code contracts. The existing evals prove each step, and engine-shaped work stays in the separate engine project.
- **Rejected:** shaping `sw`'s commands and internals for the engine now, which widens M7 and leaves its criteria uncheckable.
- **Reversal cost:** medium
- **Important:** yes (binds future changes)
- **Chosen by:** user

### S6: CI artifacts only, nothing published

- **Choice:** the spike builds each binary with its checksum as a CI artifact, and a fresh job per OS downloads and runs it. Release assets, the install download and the version check in skills are for `native-cli-distribution`.
- **Rejected:** publishing release assets in the spike, before the ADR and the process runner are proven.
- **Reversal cost:** low
- **Important:** no (set by the roadmap's change split)
- **Chosen by:** agent

### S7: Each runner OS's native architecture only

- **Choice:** build and test on `ubuntu-24.04` (x64), `windows-latest` (x64) and `macos-latest` (arm64), the runners the eval matrix already uses. The ADR lists the target set (adding linux-arm64 and macOS x64) for `native-cli-distribution`.
- **Rejected:** the full target matrix now, which adds runner minutes before the delivery path is known to work.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S8: A minor release, 0.23.0

- **Choice:** bump to 0.23.0. The change adds a component, a CI workflow and contributor tooling, even though projects receive nothing new.
- **Rejected:** a patch bump, because this is not a fix.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

Starts the native CLI migration (#148) with `sw`, a Dart executable that CI builds and checks on Linux, Windows and macOS. `sw version --json` reports its version and interface. `sw run --bounded` runs a command under `bounded.py`'s limits and exit codes and stops the whole process tree on a limit: a job object on Windows, a process session on Linux and macOS. A new `cli` eval suite checks `sw` against the same cases as `bounded.py`. Nothing in the skills uses `sw` yet. ADR 0027 decides how it will be installed (per user, by version) and supersedes ADR 0002.

### Added
- `cli/`: the `sw` Dart executable with `sw version --json` and `sw run --bounded`, pinned through mise, with process-tree regression tests on three platforms (#148).
- A CI build of `sw` on Linux, Windows and macOS, with SHA-256 checksums and a download-and-run check on each OS (#148).
- ADR 0027: shipped tooling becomes one Dart binary, installed per user by version, with an interface-version contract. It supersedes ADR 0002 (#148).
