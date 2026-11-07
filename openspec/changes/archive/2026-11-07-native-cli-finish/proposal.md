# Proposal

## Why

`specwright-finish` plans the undo of a deferred (or user-waiting) archive through `skills/specwright-finish/scripts/finish.sh undo-archive-plan`, about 560 lines of Python inside a bash heredoc. ADR 0027 moves shipped tooling into the Dart `sw` binary, and ADR 0028 says how a port switches: the script stays a shim at its old path, resolves the project's `sw` and hands it the command line. `native-cli-vcs` and `native-cli-commit` ported `vcs.sh`, `task-cover.sh` and `fit-subject.sh` that way. `finish.sh` is the last script of M7's scope.

This change serves **M7 - Native CLI foundation** (change 7 of 7, #148). It advances the exit criterion "VCS, commit and finish operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms" for the finish part. With it merged and released, the criterion "All M7 changes are archived on main and their releases are published" can be checked at the close. Both criteria are agent-verified. The `evals/finish` suite, which covers Git and jj, runs against the `sw` built from the tree in CI on Linux, Windows and macOS. The `evals/vcs` GitButler undo tests run on Linux only, because GitButler publishes no standalone `but` for the other platforms (#154). A differential eval compares `sw`'s output byte for byte with a frozen copy of the old `finish.sh`.

## What Changes

- `sw` gains a `finish` command with one subcommand, `undo-archive-plan`. It takes `finish.sh`'s arguments (`--dir`, `--change`, `--archived-name`, `--prefix`, `--main`, `--branch`, `--type`, `--code`) and keeps its whole contract. That covers the JSON keys, the refusal codes and exit codes (0, 1, 2), the uncommitted and committed modes, and the member, main-spec, amendment and carried-edit rules. It also covers the Git, jj and GitButler guards, and the exact `script` and `after_rerun` texts it prints.
- The plan stays read-only and runs no network command. The `sw finish` code is held to the same rule as `finish.sh`: only local `git` reads, and no `fetch`, `pull`, `push`, `ls-remote` or `gh`.
- `finish.sh` keeps its path and command line and drops its body. It becomes an ADR 0028 shim. It finds the project from `--code` when given (store-backed runs already pass it), else from `--dir` or the current directory. It resolves `sw` through `specwright-pr/scripts/sw-path.sh` and runs `sw finish --args-stdin`. A missing or mismatched `sw` prints `sw_missing` JSON and exits 1, with no fallback.
- The scripts the plan prints still call `bash <specwright-pr>/scripts/vcs.sh` by path, as they do today, so a user who runs them needs nothing new.
- `specwright-finish` treats a `sw_missing` answer from the undo plan as a stop with the install message. It is never shown as an undo script, and finish still makes no commit, merge or push.
- The `evals/finish` tests and the `evals/vcs` GitButler undo tests run against the tree-built `sw` through a test home, as the commit port's evals do. Their assertions do not change.
- A new differential eval runs a frozen, test-only copy of the old `finish.sh` and the shim on the same repos: committed, uncommitted and bulk archives, on Git and jj, and on GitButler where `but` is installed. It asserts equal stdout bytes and exit codes. M8 removes the copy together with the shim.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-finish`: `sw finish undo-archive-plan`, which `finish.sh` runs, now builds the undo plan under `finish.sh`'s output and exit-code contract. A missing or mismatched `sw` stops the plan with `sw_missing`, nothing falls back, and finish stops on it. The no-network requirement extends to the `sw finish` source. The existing requirements keep naming `finish.sh`, which stays the entry point.

## Impact

- New Dart code under `cli/lib/src/finish/`, a `finish` command in `cli/lib/src/cli.dart` and its usage text, and Dart unit tests under `cli/test/finish/`.
- `skills/specwright-finish/scripts/finish.sh` is reduced to a shim. `skills/specwright-finish/SKILL.md` gets the `sw_missing` stop.
- `evals/finish/fixtures.py` (or the test modules) and `evals/vcs/test_gitbutler_undo.py` gain the `sw` test home and a stamped project. The no-network scan in `evals/finish` also covers `cli/lib/src/finish/**`. `evals/finish/oracle/finish.sh` is the frozen copy for the differential eval in `evals/finish/test_parity.py`, and `evals/vcs/test_gitbutler_parity.py` runs its GitButler cases in the Linux `vcs` job, where `but` is installed. `evals/suites.json` gains rules for `cli/lib/src/finish/**`. The `finish` and `vcs` CI jobs build `sw` if they do not already.
- ADR 0012's known exception for `finish.sh` (no bounds, #111) carries over to `sw finish` unchanged. ADR 0014's "finish runs no network command" now covers the Dart code too. Neither ADR is edited.
- Runtime prerequisites do not change: bash and Python stay for `sw-path.sh` and the scripts not yet ported, and `jj` or `but` only where the repo uses them.
- Version 0.27.0. Installs need `sw` 0.27.0 placed.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: `finish.sh` becomes a shim under ADR 0028

- **Choice:** `finish.sh` keeps its path and command line, resolves `sw` through `sw-path.sh` and hands it the arguments on stdin. M8 removes it.
- **Rejected:** switching `specwright-finish` and the evals to `sw` directly now. ADR 0028 rejects that for every port.
- **Reversal cost:** low
- **Important:** no: accepted ADR 0028 already decides it
- **Chosen by:** agent

### S2: The `sw` command is `sw finish undo-archive-plan`

- **Choice:** one `finish` command for the ported skill, with the subcommand named after `finish.sh`'s own, reached through `--args-stdin` as `sw vcs` and `sw commit` are.
- **Rejected:** a top-level `sw undo-archive-plan`, which breaks the one-command-per-skill pattern.
- **Reversal cost:** medium
- **Important:** yes: binds future changes (M8 callers call this name directly)
- **Chosen by:** user

### S3: Port for parity only

- **Choice:** the port keeps every JSON key, error code, exit code, message, warning and printed script byte for byte. It runs the same `git` reads with no deadline of its own and changes no eval assertion. A defect found while porting is filed as an issue unless it blocks parity on a CI platform.
- **Rejected:** fixing or reshaping the plan during the port, for example adding bounds (#111) or printing `sw` commands in the scripts. Either would stop "the evals pass unchanged" from proving parity.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S4: "Finish operations" means `finish.sh`

- **Choice:** the finish part of the M7 criterion is `finish.sh`, the only script `specwright-finish` owns. The merges, pushes, branch deletes and state reads that finish runs already go through `vcs.sh` (ported by `native-cli-vcs`), `task-cover.sh` (ported by `native-cli-commit`) or `as.sh`, `pr-pair.sh` and `release.sh`, which M8 ports.
- **Rejected:** also porting the PR and release scripts that finish calls. M8's outcome already covers them.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S5: The shim finds the project from the existing `--code`, then `--dir`

- **Choice:** no new argument. The shim walks up to the first `.git` entry from `--code` when it is given and is a directory, else from `--dir`, else from the current directory. Store-backed finish already passes `--code <code toplevel>` with `--dir <store>`.
- **Rejected:** adding a separate project option as `task-cover.sh` needed, which `finish.sh` does not need because it already has `--code`.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

Undo plans for deferred archives now run in the native `sw` binary. `finish.sh` is a shim around the new `sw finish undo-archive-plan`, with unchanged JSON, exit codes and printed scripts. With it, every script in M7's scope (`vcs.sh`, `task-cover.sh`, `fit-subject.sh` and `finish.sh`) runs in `sw`. Installs at 0.27.0 need `sw` 0.27.0 placed.

### Changed

- `finish.sh undo-archive-plan` now runs `sw finish undo-archive-plan`, the Dart port of the undo plan, with unchanged JSON, refusals, exit codes and printed `script` and `after_rerun` texts on Git, jj and GitButler. A missing or mismatched `sw` stops it with `sw_missing`, and finish stops with the install message (#148).
