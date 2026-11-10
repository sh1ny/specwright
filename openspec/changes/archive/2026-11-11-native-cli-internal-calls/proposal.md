# Proposal

## Why

`sw` still launches parts of itself as if they were separate programs. `sw vcs` reaches the identity fence by running the `as.sh` shim (`cli/lib/src/vcs/scripts.dart:128-166`). That shim resolves `sw` again and starts `sw as`. `sw pr snapshot` probes for a Python interpreter it never uses and checks the reviewer config in a child `sw` process (`cli/lib/src/pr/snapshot.dart:143-150`, `:234-245`). Each hop costs a process, needs bash and a resolvable binary, and leaves two known store gaps open. ADR 0031 records them as C11 (store network calls through `sw vcs` stop with `sw_missing` from a store without `VERSION`) and S-1 (`pr-snapshot.sh` and `pr-reply.sh` cannot select the code project's binary from a store).

This change serves M8, Complete the native CLI migration (#148). It is change 5 of the milestone, after `native-cli-library-foundations`, and it lands before `native-cli-launcher` so that the launcher change starts from a known, checked set of launch sites. It advances two exit criteria:

- `sw` starts itself only for the bounded helper and reviewer evaluation, and never starts a shipped script or Python for its own work. This change adds the launch-site allowlist and black-box evals with sentinel scripts and failing `python`/`python3` on `PATH`.
- Direct fence evals pass on the three CI platforms for exact argument bytes, per-call token scope, target-repository checks, refusal mapping and each existing deadline, and `sw vcs` fenced commands gain no new deadline.

Every exit criterion is agent-verified; none is user-verified.

## What Changes

- `sw vcs` on Git, jj and GitButler calls the fence's Dart interface in process for login resolution and for each fenced network command. It no longer runs `as.sh`. Each fenced command still runs in the target repository with the verified per-call token, the gh lookups keep their own bounds, the command stays unbounded, and a refusal keeps its exit 3 and `fence_failed` or command-exit mapping. This removes the temporary non-Git `branch-check` fetch hop (ADR 0031 C9), including the `--project` forwarding, and closes C11: a store without `VERSION` no longer stops these calls with `sw_missing`.
- `sw pr snapshot` drops its Python probe and the `no_python` stop. The `pr-snapshot.sh` shim keeps its own prerequisite check until `native-cli-retire-scripts`. The reviewer config check runs in process instead of in a child `sw pr reviewers --check-config`. Its stderr line, exit 2 and the rule that it runs before any gh call stay the same.
- The reviewer evaluator stays a separately killable child under the poll deadline (ADR 0022). Its limit line becomes the fixed `bounded: <limit>: reviewers.py python3` and no longer depends on a probed interpreter. Snapshot reads the evaluator's document by parsing it, which closes the C12 regex readers in `cli/lib/src/pr/text.dart`.
- `pr-snapshot.sh` and `pr-reply.sh` accept one optional leading `--project <code-checkout>` selector, as `as.sh` and `pr-pair.sh` do. It selects only the binary, never cwd, repository or login. The skills' store-started snapshot and reply calls pass it, which closes S-1.
- A launch-site allowlist test over `cli/lib/src` lists every call to a process runner and every caller of the runners. It refuses an unlisted launch, a self-launch other than the `__exec` helper and the reviewer evaluator, and a shipped script name in launch arguments. Printed command documents (`sw vcs plan`, cleanup plans, undo scripts) are data, not launches.
- Black-box evals run the retrofitted paths with recording `as.sh` and `vcs.sh` sentinels in the handoff scripts directory and failing `python` and `python3` first on `PATH`. They prove that neither sentinel runs and that no interpreter starts. They cover argument bytes, credentials, target repositories, unchanged deadlines and error mapping. They fail on `main` before the retrofit.
- C13 (the jj and GitButler guards that `sw finish undo-archive-plan` prints match `vcs.sh state` output as text) moves to `native-cli-retire-scripts`, which replaces every printed `bash vcs.sh` command. Only the recorded owner changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `vcs-backends`: `sw vcs` fences network commands through the fence in process, not through `as.sh`. Store network calls no longer need a resolvable binary in the store.
- `pr-script-runtime`: the snapshot drops the Python probe, checks the reviewer config in process, reads evaluator documents by parsing and prints a fixed limit line. The non-Git `branch-check` fence-hop exception ends. `pr-snapshot.sh` and `pr-reply.sh` gain the `--project` selector.
- `native-cli`: `sw` starts itself only for the bounded helper and reviewer evaluation, which the launch-site allowlist enforces. The document-reader exception narrows to C13, now owned by `native-cli-retire-scripts`.

## Impact

Touches `cli/lib/src/vcs/{scripts,git_common,jj_backend,gitbutler_backend}.dart`, `cli/lib/src/commands/vcs.dart`, `cli/lib/src/pr/{snapshot,context,text,reviewers,workflow}.dart`, `cli/lib/src/fence/` (a captured-output entry beside `runFence`), the `pr-snapshot.sh` and `pr-reply.sh` shims, `skills/specwright-pr/SKILL.md` and `skills/specwright-finish/SKILL.md` (the S-1 and C11 notes and the store snapshot and reply calls), `cli/lib/src/finish/undo_plan.dart` and `evals/cli/test_option_callers.py` (C13's owner), new Dart tests under `cli/test/`, new or extended evals under `evals/vcs`, `evals/pr-pair` and `evals/cli`, and `evals/suites.json`. ADR 0031 stays unchanged; design decides whether the allowlist needs its own ADR. There are no new dependencies. `interface` stays 1.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Fixed evaluator limit line

- **Choice:** Print `bounded: <limit>: reviewers.py python3` whatever interpreter exists, with no probe.
- **Rejected:** `reviewers.py` alone; naming `sw pr`, which breaks the prefix that the evals and watch read.
- **Reversal cost:** low
- **Important:** yes, changes behaviour users see.
- **Chosen by:** user, chose "Fixed `reviewers.py python3`".

### S2: Allowlist as a Dart test

- **Choice:** A `dart test` file in `cli/test` scans `cli/lib/src` against a checked-in allowlist and runs on three OSes in `cli.yml`.
- **Rejected:** A Python eval in `evals/cli`.
- **Reversal cost:** low
- **Important:** yes, binds future changes: launcher, review, release and update register their launches in it.
- **Chosen by:** user, chose "Dart test in cli/test".

### S3: Interpreter-absent evals now, for the retrofitted paths

- **Choice:** Add failing `python`/`python3` PATH evals for `sw pr snapshot` and the `sw vcs` fenced paths, run through `sw`. Shim prerequisite probes stay until retire-scripts.
- **Rejected:** Leave all interpreter-absent evals to `native-cli-retire-scripts`.
- **Reversal cost:** low
- **Important:** yes, binds future changes (exit criterion evidence).
- **Chosen by:** user, chose "Yes, for retrofitted paths".

### S4: Close S-1 with a `--project` selector

- **Choice:** `pr-snapshot.sh` and `pr-reply.sh` take the same optional leading `--project <code-checkout>` as `as.sh` and `pr-pair.sh`, and the skills pass it on store-started calls.
- **Rejected:** Defer to `native-cli-retire-scripts`.
- **Reversal cost:** low
- **Important:** yes, changes behaviour users see (shim arguments).
- **Chosen by:** user, chose "Fix here: add --project".

### S5: C13 moves to retire-scripts

- **Choice:** The printed undo guards keep their compact-text match. `native-cli-retire-scripts` replaces them along with every printed `bash vcs.sh` command.
- **Rejected:** A new `sw vcs` check subcommand for the printed guard now.
- **Reversal cost:** low
- **Important:** yes, binds future changes.
- **Chosen by:** user, chose "Move to retire-scripts".

### S6: C12 closes here

- **Choice:** Snapshot parses the evaluator's document instead of matching it with regexes.
- **Rejected:** Keep the regex readers until retire-scripts.
- **Reversal cost:** low
- **Important:** no. The boundary is internal to `sw`, and the roadmap and the library-foundations design already assign it here.
- **Chosen by:** agent

### S7: The shell transport stays

- **Choice:** External tools still start through the existing `bash -c 'exec "$@"'` transport, and `sw as`'s inherited-stdio launch keeps its bash prelude. `native-cli-launcher` replaces both.
- **Rejected:** Replacing launches here.
- **Reversal cost:** low
- **Important:** no. This follows the roadmap order.
- **Chosen by:** agent

## Release Notes

0.32.0 stops `sw` from starting scripts and Python for its own work. `sw vcs` runs the GitHub identity fence in process, so store network calls work from a store without its own Specwright version. `sw pr snapshot` checks the reviewer config in process, no longer looks for Python, and parses the reviewer evaluator's output instead of matching its text. `pr-snapshot.sh` and `pr-reply.sh` accept `--project` for store-started calls. A new test lists every place `sw` starts a process, so a later change cannot add a script or Python launch unnoticed.

### Added

- `pr-snapshot.sh` and `pr-reply.sh` accept a leading `--project <code-checkout>` to select the code project's `sw` from a planning store (#148).

### Changed

- `sw vcs` runs fenced fetch, pull and push in process instead of through `as.sh`. Outputs, refusals and exit codes are unchanged (#148).
- The reviewer evaluator's limit line always reads `reviewers.py python3` (#148).

### Fixed

- Store network operations through `vcs.sh`, including the jj store pull that cleanup prints, no longer stop with `sw_missing` from a store without `openspec/.specwright/VERSION` (#148).

### Removed

- `sw pr snapshot`'s Python probe and its `no_python` stop. The `pr-snapshot.sh` shim keeps its own check until the scripts retire (#148).
