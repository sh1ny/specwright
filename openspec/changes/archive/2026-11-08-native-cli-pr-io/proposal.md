# Proposal

## Why

Every GitHub call Specwright makes goes through three scripts in `skills/specwright-pr/scripts/`. `as.sh` is the identity fence: it resolves and checks the token, sets the transport rules and refuses userinfo URLs. `pr-snapshot.sh` reads a PR's state, threads, comments and reviews, and runs the watch loop. `pr-reply.sh` posts replies, reactions and resolutions. Each one needs bash and Python 3.8+, because `bounded.py` puts a deadline and a size limit on every `gh` call. ADR 0027 moves shipped tooling into the Dart `sw` binary, and M7 ported `vcs.sh`, the commit helpers and `finish.sh` behind ADR 0028 shims. These three scripts are leaves that pr-pair, review, release and update depend on, so they move first.

This change serves **M8 - Complete the native CLI migration** (change 1 of 6, #148). It advances the exit criterion "The PR, review, release and update operations use `sw`; their existing JSON, exit-code and workflow contracts are covered by the corresponding black-box evals on the three CI platforms" for the fence and PR I/O part. It also moves toward "No shipped skill calls a bash or Python script": the skills keep calling the shims until `native-cli-retire-scripts`. Both criteria are agent-verified. The `evals/pr-pair` tests of the three scripts, run against `sw` in CI, check this change's part. It also carries #202.

## What Changes

- `sw` gains `sw as`, the identity fence, with `as.sh`'s refusals, exit codes, environment rules and transport settings, for `as.sh <login> <command...>` and `as.sh --resolve`. Its own `gh` lookups keep their deadline and size bound, and the token never reaches a file.
- `sw` gains `sw pr snapshot` and `sw pr reply`, with the scripts' command lines, JSON documents, exit codes, markers, watch ownership and state files of `pr-snapshot.sh` and `pr-reply.sh`. Every `gh` call keeps its deadline and size bound, now enforced by `sw`'s own bounded runner instead of `bounded.py`.
- `as.sh`, `pr-snapshot.sh` and `pr-reply.sh` keep their paths and command lines and become ADR 0028 shims. In this change the three `sw` commands take only the shim handoff (`sw as --args-file`, `sw pr ... --args-stdin`), as `sw vcs` does. A direct argv form arrives with `native-cli-retire-scripts`, when callers switch to `sw`. A missing or mismatched `sw` stops them with `sw_missing`, and nothing falls back to the old code. **BREAKING** for a project with no matching `sw`: every tagged install has placed one since `native-cli-distribution`.
- The `as.sh` shim hands its arguments to `sw` without using stdin, so the fenced command keeps the caller's stdin as it does today. A new ADR records this one exception to ADR 0028's stdin handoff.
- `sw pr snapshot` keeps running `reviewers.py` as a bounded subprocess, as `pr-snapshot.sh` does. `native-cli-pr-pair` ports it.
- `sw`'s own callers of the fence (`sw vcs` network operations) keep the same behaviour and exit codes.
- #202: `sw run --bounded`, and every command `sw` resolves on `PATH`, keeps an empty POSIX `PATH` entry as the current directory, in its position, as the shell and `execvp` do.
- The `evals/pr-pair` tests of the three scripts run against the `sw` built from the tree on Linux, Windows and macOS. Their assertions do not change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-identity`: the fence is carried out by `sw as`, which `as.sh` runs with the same contract. A missing or mismatched `sw` stops every fenced call, with no fallback, and the fenced command keeps the caller's stdin.
- `pr-script-runtime`: `pr-snapshot.sh` and `pr-reply.sh` run `sw pr snapshot` and `sw pr reply`. Their `gh` calls and `as.sh`'s lookups stay bounded by `sw`'s runner, with the same deadlines, size bounds and messages. Python is no longer needed for these three scripts' own work.
- `native-cli`: `sw` resolves commands on `PATH` with empty POSIX entries meaning the current directory (#202).

## Impact

- New Dart code under `cli/lib/src/fence/` and `cli/lib/src/pr/`, new `as` and `pr` commands in `cli/lib/src/cli.dart`, and Dart unit tests under `cli/test/`. `cli/lib/src/process/resolve.dart` changes for #202.
- `skills/specwright-pr/scripts/as.sh`, `pr-snapshot.sh` and `pr-reply.sh` are reduced to shims. `bounded.py` stays, because `pr-pair.sh`, `reviewers.py` runs and the other scripts still use it.
- The callers (skills, `pr-pair.sh`, `release.sh`, `review-run.sh`, `update.sh`, `sw vcs`) keep their command lines.
- `evals/pr-pair` tests that run the three scripts need an installed `sw` that the shims can find. CI already builds one for every suite. `evals/suites.json` gains rules for the new Dart paths.
- A new ADR (the `as.sh` handoff exception) and `openspec/architecture.md`'s index.
- Users' prerequisites do not change until `native-cli-retire-scripts`: bash and Python stay for the scripts not yet ported.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: The three scripts become ADR 0028 shims

- **Choice:** `as.sh`, `pr-snapshot.sh` and `pr-reply.sh` keep their paths and command lines, resolve `sw` through `sw-path.sh` and run it. No caller changes, and `native-cli-retire-scripts` removes the shims.
- **Rejected:** switching every caller to `sw` now. ADR 0028 settles this for every M8 port.
- **Reversal cost:** low
- **Important:** no: ADR 0028 already decided it
- **Chosen by:** agent

### S2: Command names `sw as`, `sw pr snapshot` and `sw pr reply`

- **Choice:** the fence is `sw as` at top level, because VCS, release and update operations use it as well as the PR steps. PR I/O goes under a `sw pr` group, which `native-cli-pr-pair` extends.
- **Rejected:** `sw pr as` (the fence is not PR-specific). Flat `sw pr-reply` and `sw pr-snapshot` (they copy the file names and leave no group for pr-pair).
- **Reversal cost:** medium
- **Important:** yes: binds future changes (the names the M8 callers and skills will use)
- **Chosen by:** user

### S3: The fenced command keeps the caller's stdin

- **Choice:** the `as.sh` shim passes its handoff records to `sw as` in a private temp file, which `sw as` reads and deletes before it does anything else. Stdin stays free for the fenced command. A new ADR adds this exception to ADR 0028.
- **Rejected:** ADR 0028's stdin handoff as it stands. The fenced command would read EOF instead of the caller's input, a silent behaviour change that no current caller notices but any future `--input -` caller would hit.
- **Reversal cost:** medium
- **Important:** yes: binds future changes (a second handoff form beside ADR 0028) and changes behaviour users see
- **Chosen by:** user

### S4: `reviewers.py` stays a subprocess until `native-cli-pr-pair`

- **Choice:** `sw pr snapshot` runs `reviewers.py` (`--check-config` and the evaluation) as a bounded subprocess from the shim's scripts directory, under the same contract and deadline `pr-snapshot.sh` uses.
- **Rejected:** porting `reviewers.py` here. It belongs with `pr-pair.sh`, which writes its config, and moving it would push this change well past one PR.
- **Reversal cost:** low
- **Important:** yes: binds future changes (change 2 ports it)
- **Chosen by:** user

### S5: Port for parity only, with #202 as the one fix

- **Choice:** the port keeps every JSON field, error code, exit code, message, marker and state file, and changes no eval assertion. #202, carried by the roadmap, is the one behaviour fix. Any other defect found while porting is filed as an issue unless it blocks parity on a CI platform.
- **Rejected:** fixing or reshaping behaviour during the port, which would stop the unchanged evals from proving parity.
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

The GitHub identity fence and the PR snapshot and reply tools now run in the native `sw` binary. `as.sh`, `pr-snapshot.sh` and `pr-reply.sh` keep their command lines and output, and each is a shim around `sw as`, `sw pr snapshot` and `sw pr reply`. A project needs the `sw` that matches its installed version, which every tagged install places.

### Changed

- `as.sh` now runs `sw as`, the Dart port of the identity fence, with the same refusals, exit codes and transport rules. The fenced command keeps the caller's stdin. A missing or mismatched `sw` stops with `sw missing or mismatched: rerun the install prompt` (#148).
- `pr-snapshot.sh` and `pr-reply.sh` now run `sw pr snapshot` and `sw pr reply`, with unchanged JSON, markers, watch ownership and exit codes. Their `gh` calls are bounded by `sw` instead of `bounded.py` (#148).

### Fixed

- `sw` treats an empty entry in a POSIX `PATH` as the current directory, in its position, as the shell does (#202).
- In a UTF-8 locale, `sw vcs` no longer exits 126 with `vcs: argument transport failed` when an argument ends in a byte that starts a multibyte character. It reads its argument records with `LC_ALL=C`, and the tool still gets the caller's `LC_ALL`.
