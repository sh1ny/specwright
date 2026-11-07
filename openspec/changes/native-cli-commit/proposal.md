# Proposal

## Why

`specwright-commit` reads task evidence through `skills/specwright-commit/scripts/task-cover.sh`, about 290 lines of Python inside a bash heredoc. It fits commit subjects through `fit-subject.sh`, an awk program in bash. `specwright-finish` (the user-task check after archive) and `specwright-pr` watch (user tasks at the ready head) run `task-cover.sh` too. ADR 0027 moves shipped tooling into the Dart `sw` binary, and ADR 0028 fixes how a port switches: the script stays a shim at its old path that resolves the project's `sw` and hands it the command line. `native-cli-vcs` ported `vcs.sh` that way. The commit scripts come next.

This change serves **M7 - Native CLI foundation** (change 6 of 7, #148). It advances the exit criterion "VCS, commit and finish operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms" for the commit part. `native-cli-finish` follows. The criterion is agent-verified: the `evals/git-workflow` tests of both scripts, and the `evals/vcs` test that reads coverage after a jj commit, run against the `sw` built from the tree in CI on Linux, Windows and macOS.

## What Changes

- `sw` gains a `commit` command with two subcommands, `task-cover` and `fit-subject`. Each takes the arguments of the script it replaces and has the same output and exit codes. `task-cover` keeps every JSON key, error code, bound (`TASK_COVER_MAX_COMMITS` included) and the exact evidence rules of ADRs 0016 and 0024. `fit-subject` keeps the 72-character limit counted in characters, the in-place rewrite of line 1 that leaves every other byte alone, the printed subject and the stderr messages.
- `task-cover.sh` and `fit-subject.sh` keep their paths and command lines and drop their bodies. Each becomes a shim under ADR 0028: it resolves the project's `sw` through `specwright-pr/scripts/sw-path.sh`, hands over its scripts directory, bash and the arguments as NUL-terminated stdin records, and runs `sw commit <sub> --args-stdin`. A missing or mismatched `sw` prints `sw_missing` JSON and exits 1, with no fallback.
- `specwright-commit` tells a `sw_missing` stop apart from `fit-subject`'s own exit 1 ("no word fits") by the `sw_missing` document on stdout, and stops apply with the install message instead of skipping the task.
- `task-cover.sh` takes an optional `--code <code toplevel>` that only picks the project whose `sw` runs: a store has no installed `VERSION`, so the commit, finish and watch skills pass it in store-backed runs.
- Otherwise the skills, `finish.sh` and the evals keep calling the scripts unchanged. `finish.sh` keeps its own user-task read until `native-cli-finish`.
- The `evals/git-workflow` tests of both scripts run against the tree-built `sw` through a test home, as `evals/vcs` does. Their assertions do not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `task-commits`: the coverage check and subject fitting are carried out by `sw commit task-cover` and `sw commit fit-subject`, which the scripts run, under the scripts' output and exit-code contracts. A missing or mismatched `sw` stops them with `sw_missing`, nothing falls back, and `specwright-commit` stops apply on it. The existing requirements keep naming the scripts, which stay the entry points.

## Impact

- New Dart code under `cli/lib/src/commit/`, a `commit` command in `cli/lib/src/cli.dart` and its usage text, and Dart unit tests under `cli/test/commit/`.
- `skills/specwright-commit/scripts/task-cover.sh` and `fit-subject.sh` are reduced to shims. `skills/specwright-commit/SKILL.md` gets the `sw_missing` stop, and it, `specwright-finish` and `specwright-pr` pass `--code` to `task-cover.sh` when store-backed.
- `evals/git-workflow/test_task_cover.py`, `test_fit_subject.py` and `test_user_tasks.py` (if it runs the script) gain the `sw` test home. `evals/suites.json` gains rules for `cli/lib/src/commit/**`. The `git-workflow` CI job already builds `sw` (`SPECWRIGHT_SW`).
- `docs/adr/0016` and `0024` are unchanged: the contracts they name stay with the scripts.
- Runtime prerequisites do not change: bash and Python stay for `sw-path.sh` and the scripts not yet ported.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: The scripts become shims under ADR 0028

- **Choice:** `task-cover.sh` and `fit-subject.sh` keep their paths and command lines, resolve `sw` through `sw-path.sh` and hand it their arguments on stdin. M8 removes them.
- **Rejected:** switching the callers (two skills, the watch step and the evals) to `sw` directly now. ADR 0028 rejects that for every port.
- **Reversal cost:** low
- **Important:** no: accepted ADR 0028 already decides it
- **Chosen by:** agent

### S2: The `sw` commands are `sw commit task-cover` and `sw commit fit-subject`

- **Choice:** one `commit` command per ported skill, with subcommands named after the scripts, reached through `--args-stdin` as `sw vcs` is.
- **Rejected:** top-level `sw task-cover` and `sw fit-subject` (two entries for one skill); a domain group `sw tasks cover` (names that match no script).
- **Reversal cost:** medium
- **Important:** yes: binds future changes (M8 callers call these names directly)
- **Chosen by:** user

### S3: Port for parity only

- **Choice:** the port keeps every JSON key, error code, exit code, bound and message, runs the same `git` reads with no deadline of its own, and changes no eval assertion. A defect found while porting is filed as an issue unless it blocks parity on a CI platform.
- **Rejected:** fixing or reshaping behaviour during the port, which would stop "the evals pass unchanged" from proving parity.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

### S4: `finish.sh` keeps its own user-task read

- **Choice:** `finish.sh`'s in-script read of unticked user tasks stays as it is; `native-cli-finish` ports it with the rest of `finish.sh`.
- **Rejected:** routing it through `sw commit task-cover` now, which edits the finish script one change before its own port.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

Task coverage and commit-subject fitting now run in the native `sw` binary. `task-cover.sh` and `fit-subject.sh` are shims around `sw commit task-cover` and `sw commit fit-subject`, with unchanged output and exit codes.

### Changed

- `task-cover.sh` and `fit-subject.sh` now run `sw commit task-cover` and `sw commit fit-subject`, the Dart ports of their evidence and subject rules, with unchanged JSON, output and exit codes. A missing or mismatched `sw` stops them with `sw_missing`, and apply stops with the install message (#148).
