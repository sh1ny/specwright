# Proposal

## Why

Every Specwright step that reads a branch or writes to version control goes through `skills/specwright-pr/scripts/vcs.sh`: about 1,250 lines of Python inside a bash heredoc, covering the Git, jj and GitButler backends (ADRs 0017 and 0018). ADR 0027 moves shipped tooling into the Dart `sw` binary. The `native-cli-spike` and `native-cli-distribution` changes delivered that binary, its install and the version-checked resolver (`sw-path.sh`). The VCS boundary is the first script to move.

This change serves **M7 - Native CLI foundation** (change 5 of 7, #148). It advances the exit criterion "VCS, commit and finish operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms" for the VCS part. Commit and finish follow in `native-cli-commit` and `native-cli-finish`. The criterion is agent-verified, and the `evals/vcs` suite run against `sw` in CI checks it.

## What Changes

- `sw` gains a `vcs` command with the same subcommands, arguments, JSON documents and exit codes as `vcs.sh` today: `state`, `branch-create`, `switch`, `commit`, `merge`, `delete-branch`, `fetch-main`, `pull`, `push`, `plan` and the rest of the existing surface. It covers all three backends: Git, jj and GitButler.
- `vcs.sh` keeps its path and its command line but drops its Python body. It becomes a shim that resolves the project's `sw` through `sw-path.sh` and execs `sw vcs <sub> ...`. A missing or mismatched `sw` stops with `sw missing or mismatched: rerun the install prompt`. There is no fallback to the old Python. **BREAKING** for projects whose `sw` is not installed: the install prompt has installed it since `native-cli-distribution`.
- Names keep their bytes as with `vcs.sh`: arguments reach `sw` on stdin, directory walks read raw names, and a file name that is not valid UTF-8 round-trips through the JSON and the next tool call.
- The skills, `finish.sh`, `pr-pair.sh`, `release.sh` and `review-run.sh` keep calling `vcs.sh` unchanged; `update.sh` changes only its jj-store read (below). M8 removes the shim once the callers move to `sw`.
- `sw vcs` keeps reading settings through `pr-pair.sh vcs`/`context` and keeps fencing network operations through `as.sh`, from the scripts directory of the `vcs.sh` that started it, until M8 ports those scripts. Like `vcs.sh`, it runs `git`, `jj`, `but` and those scripts with no deadline of its own: adding bounds would be a behaviour change, outside this port.
- `update.sh` reads a jj store's branch with the download's own `sw` (the download's `VERSION`), not the project's installed one. Without a binary for that version, the update refuses the store with `sw_missing`.
- A new `mise run install-sw` builds `sw` from a checkout and places it for that checkout's version. When the installed `vcs.sh` runs `sw` and no matching binary resolves after the install, the install report says that VCS steps stop until a tagged install or this task places the binary.
- The `evals/vcs` suite, and the other suites that drive `vcs.sh`, run against the `sw` built from the tree on Linux, Windows and macOS. Their assertions do not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `install-update`: when the installed version's VCS steps need `sw` and none matches, the install report says so; `mise run install-sw` places a tree-built one.
- `vcs-backends`: the backend operations are carried out by `sw vcs`, which `vcs.sh` runs, with `vcs.sh`'s output and exit-code contract. A missing or mismatched `sw` stops every VCS operation with `sw_missing`, and nothing falls back. Settings and the identity fence still come from `pr-pair.sh` and `as.sh`. The existing requirements keep naming `vcs.sh`, which stays the entry point. The update's jj-store branch read uses the download's `sw`.

## Impact

- New Dart code under `cli/lib/src/vcs/` and a `vcs` command in `cli/lib/src/cli.dart`, with Dart unit tests under `cli/test/`.
- `skills/specwright-pr/scripts/vcs.sh` is reduced to the shim.
- `scripts/update.sh` (`jj_store_branch`), `mise.toml` (`install-sw`), the README install prompt's Step 8, `.github/workflows/evals.yml` (`sw` built for every suite), a new ADR 0028 and `openspec/architecture.md`.
- `evals/vcs/vcs_test_support.py` and the evals that run `vcs.sh` need an installed `sw` that the shim can find. CI already builds `sw` (`SPECWRIGHT_SW` in `.github/workflows/evals.yml`), and running the vcs evals locally now needs that build too.
- Runtime prerequisites do not change for users until M8: bash and Python stay for the other scripts and for the settings and fence calls.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Callers reach `sw vcs` through a `vcs.sh` shim

- **Choice:** `vcs.sh` keeps its path and command line, drops its Python body, resolves `sw` through `sw-path.sh` and execs `sw vcs`. No caller changes, and M8 removes the shim.
- **Rejected:** calling `sw vcs` directly from every skill and script and deleting `vcs.sh` now (touches 8 skills and 5 scripts, and agents would have to carry the binary path between tool calls). A shim for skills plus direct calls from scripts (two call styles until M8).
- **Reversal cost:** low
- **Important:** yes: binds future changes (the call boundary M8 removes)
- **Chosen by:** user

### S2: Settings and the identity fence stay in `pr-pair.sh` and `as.sh` until M8

- **Choice:** `sw vcs` runs `pr-pair.sh vcs`/`context` and `as.sh` as subprocesses under the contracts `vcs.sh` uses today.
- **Rejected:** porting the YAML settings read and the gh-token fence into `sw` now. That needs a YAML parser beyond ADR 0027's two dependencies and duplicates logic `pr-pair.sh` keeps until M8.
- **Reversal cost:** medium
- **Important:** yes: binds future changes (M8 ports these scripts)
- **Chosen by:** user

### S3: All three backends move in one change

- **Choice:** Git, jj and GitButler move together in task groups, and the shim switches over once, at the end.
- **Rejected:** splitting GitButler into a later change, which would keep a mixed Python/Dart dispatcher in the meantime.
- **Reversal cost:** low
- **Important:** yes: high reversal cost for the roadmap split, and it changes the size of the PR the user reviews
- **Chosen by:** user

### S4: Port for parity only

- **Choice:** the port keeps every JSON field, error code, exit code and command `vcs.sh` runs, and changes no eval assertion. Any defect or improvement found while porting is filed as an issue unless it blocks parity on a CI platform.
- **Rejected:** fixing or reshaping behaviour during the port, which would make "the evals pass unchanged" no longer prove parity.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

Version-control work now runs in the native `sw` binary. Every branch read and version-control write goes through `sw vcs`, with the same JSON, exit codes and Git, jj and GitButler behaviour as before, and `vcs.sh` is a shim around it. Each project needs an `sw` matching its installed version: a tagged install places it, and a checkout of this repository places it with `mise run install-sw` and the bootstrap in `CONTRIBUTING.md`.

### Added

- `mise run install-sw` builds `sw` from the tree, checks it and places it under `~/.specwright/bin/<version>/`.
- `CONTRIBUTING.md` describes how to bootstrap a checkout of this repository from its own tree, ending with `mise run install-sw`.

### Changed

- `vcs.sh` now runs `sw vcs`, the Dart port of its Git, jj and GitButler backends, with unchanged JSON documents and exit codes. A missing or mismatched `sw` stops with `sw missing or mismatched: rerun the install prompt`, with no fallback to the old Python (#148).
- The update reads a jj planning store's branch with the downloaded version's `sw`, and refuses with `sw_missing` when none is installed.
- The install prompt's Step 8 warns when no matching `sw` is installed, so VCS steps would stop with `sw_missing`.

### Fixed

- `sw-path.sh` accepts only a version (`x.y.z`, with an optional pre-release or build suffix) from `openspec/.specwright/VERSION`, so a committed VERSION can no longer point the `sw` lookup at a binary outside `~/.specwright/bin/`.
