# Proposal

## Why

The install and update path is the last workflow that still needs bash and Python. `scripts/update.sh` is about 1,000 lines of bash that drive about 2,300 lines of embedded Python. The README install prompt runs it with `bash` and checks for bash and Python 3.8+ before anything else. `scripts/install-sw.sh` and its `mise run install-sw` task are bash too. While these remain, no project can install or update Specwright without both runtimes.

This change serves M8, "Complete the native CLI migration" (#148), as change 10 of 11. It delivers the exit criterion "a fresh install and an update reach a working, checked `sw` on Linux, Windows and macOS without Python or bash, and an update keeps its recovery guarantees". It also advances three more: "`sw` starts itself only for the bounded helper and reviewer evaluation" (checking a downloaded `sw`'s version and interface stays allowed), "`sw` starts no bash or sh for its own work" and "all M8 changes are archived on main and their releases are published". All four are agent-verified: CI evals on the three platforms check them, and the milestone close re-runs them.

## What Changes

- **`sw update`** ports every `update.sh` subcommand into `sw`: `plan`, `stage`, `swap`, `note-config`, `finish`, `recover`, `pack-check`, `pack-verify`, `pack-docs` and `sw-install`. It runs in process in the target version's binary and keeps the existing guarantees: staging and SHA-256 verification before any installed file changes, the journal and its resume/rollback recovery, the update lock, the store roles and store gate lock, the changes-in-flight validation, the pack checks, the bounded downloads and the macOS quarantine rule. Its documents keep their fields and error codes. They are not byte-for-byte Python output (ADR 0033). Store VCS reads and fenced calls use `sw`'s own interfaces, and external tools (`git`, `openspec`) start through the native launcher.
- **Interface 3.** `sw update` reports `interface: 3`. It recovers a format 1 or format 2 journal that an older `update.sh` left pending.
- **BREAKING (install prompt):** the README install prompt drives `sw update` only. It no longer checks for bash or Python, and its minimum installable release becomes this change's release. An older tag is installed with that tag's own README prompt.
- **First `sw` without bash.** For a release tag, the prompt has the agent download the host's `sw` asset and `SHA256SUMS` from the tag's GitHub release with `curl` (shipped on Linux, macOS and Windows 10+). The agent checks the hash with the OS's own tool (`Get-FileHash` on Windows, `shasum -a 256` or `sha256sum` elsewhere) and runs `sw version --json`. That binary's `sw update sw-install` then downloads and verifies again, and places itself and its notice at `<home>/.specwright/bin/<version>/`. The prompt runs every later step with the placed binary.
- **`main` installs build `sw`.** An explicit `main` request builds `sw` from the downloaded tree with the pinned toolchain (`mise run install-sw`). Without mise or Dart it stops and names them, before any write.
- **`update.sh` becomes a shim** to `sw update` under ADR 0028, which resolves the download's version, until `native-cli-retire-scripts` removes it. The `evals/update` suite keeps driving it, which proves parity.
- **`scripts/install-sw.sh` is removed.** `mise run install-sw` runs the freshly built `sw` to check and place itself, with the same checks, notice placement and atomic rename.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-update`: the prompt drives `sw update` (interface 3) with no bash or Python prerequisite. A minimum release, the bootstrap of the first `sw` by the agent, `main` builds from the clone, and recovery of older journal formats. The `update.sh` requirements are restated for `sw update`, and `mise run install-sw` runs without bash.
- `native-cli`: `sw update` joins the ported commands. Its self-check of a downloaded or placed `sw` (version and interface) is one of the allowed self-launches. It starts no bash, sh or Python for its own work.

## Impact

- `cli/`: a new `update` command family (`cli/lib/src/update/`, `cli/lib/src/commands/update.dart`), its tests, and launch-site allowlist entries.
- `scripts/update.sh` becomes a shim. `scripts/install-sw.sh` is removed. The `install-sw` task in `mise.toml` changes.
- `README.md` install prompt (Steps 1, 3, 4, 5 and 7) and its prerequisites, plus `CONTRIBUTING.md` bootstrap.
- `openspec/architecture.md` rows for the install prompt, `update.sh` and `sw`. A new ADR records the bootstrap and the interface 3 contract.
- `evals/update` runs against the shim on Linux, Windows and macOS, with new cases for the agent bootstrap and for runs with failing `bash`, `sh`, `python` and `python3` first on `PATH`. `evals/suites.json` covers any new files.
- Users: an install or update needs `git`, `openspec`, `curl` and the OS hash tool, and no longer needs bash or Python. Installing a tag older than this release needs that tag's own prompt.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: The agent downloads and checks the first `sw` with curl and the OS hash tool

- **Choice:** The prompt has the agent fetch the host asset and `SHA256SUMS` with `curl`, check the SHA-256 with `Get-FileHash` (Windows) or `shasum -a 256` / `sha256sum`, run `sw version --json`, and hand placement to that binary's `sw update sw-install`. Fresh installs and updates take the same path.
- **Rejected:** an installed older `sw` fetching the new one (two bootstrap paths to document and test, and an old binary's logic would run the new install); bootstrap scripts in POSIX sh and PowerShell (new shipped interpreter scripts, against the milestone).
- **Reversal cost:** medium
- **Important:** yes, it changes behaviour users see (the install prompt's steps and prerequisites)
- **Chosen by:** user

### S2: The prompt installs only this release and later

- **Choice:** The prompt drives only `sw update` (interface 3). Its minimum installable release becomes this change's release, and older tags use their own README prompt. `sw update recover` still reads format 1 and 2 journals.
- **Rejected:** keeping a `bash update.sh` path for older tags (bash stays a prerequisite, and the prompt carries two flows).
- **Reversal cost:** medium
- **Important:** yes, it binds a contract (the prompt's interface and minimum release) and changes behaviour users see
- **Chosen by:** user

### S3: A `main` install builds `sw` from the clone

- **Choice:** On an explicit `main` request the prompt runs `mise run install-sw` in the downloaded tree. It stops before any write when mise or the pinned Dart SDK is missing.
- **Rejected:** dropping `main` installs (contributors lose the prompt path); running the latest release's `sw` against `main`'s tree (the version check would have to be loosened).
- **Reversal cost:** low
- **Important:** yes, it changes behaviour users see (`main` needs mise and Dart)
- **Chosen by:** user

### S4: `update.sh` stays as an ADR 0028 shim until `native-cli-retire-scripts`

- **Choice:** `update.sh` resolves the download's `sw` and hands over its arguments, as `release.sh` and `review-run.sh` do. The prompt calls `sw` directly, and the `evals/update` suite keeps driving the shim.
- **Rejected:** removing it now and rewriting the eval suite to call `sw` (a bigger eval rewrite in an already large change, and parity is harder to show).
- **Reversal cost:** low
- **Important:** yes, it binds future changes (the shim boundary that `native-cli-retire-scripts` removes)
- **Chosen by:** user

### S5: `scripts/install-sw.sh` is removed, not shimmed

- **Choice:** `mise run install-sw` builds `sw` and runs the built binary to check and place itself. The checks, notice placement and atomic rename stay the same. Users never call `install-sw.sh` directly.
- **Rejected:** shimming it (a shim would need bash to place the binary it resolves, which is the circular dependency this change removes).
- **Reversal cost:** low
- **Important:** no. It is contributor tooling behind an unchanged `mise` task name, and the roadmap entry already names its replacement.
- **Chosen by:** agent

## Release Notes

`sw update` replaces the Python and bash inside `update.sh`, so installing or updating Specwright no longer needs either runtime. The install prompt downloads and checks the first `sw` with `curl` and the OS's hash tool, then lets `sw` do the rest. `update.sh` stays as a shim that hands over to `sw update`, and an update interrupted under an older release is still recovered. The prompt now installs this release or later.

### Changed

- The install prompt drives `sw update` (interface 3) and no longer requires bash or Python. The agent fetches and checks the first `sw` with `curl` and the OS hash tool, and a `main` install builds `sw` with `mise run install-sw`. Older tags install with their own prompt (#148).
- `scripts/update.sh` is now a shim to `sw update`, and `sw update recover` recovers journals left by older update scripts (#148).
- An update now stops with `settings_invalid` when `openspec/specwright.yaml` holds something the settings reader refuses, such as a plain `yes`, where the old script went on. Fix the line it names, then rerun the update (#148).

### Removed

- `scripts/install-sw.sh`: `mise run install-sw` places the built `sw` without bash (#148).
- The bash and Python prerequisites of the install prompt (#148).
