# Proposal

## Why

The M8 ports moved every script into `sw` at parity, so they kept the old scripts' defects byte for byte, and their reviews found a few new gaps that went past the fix-round limit. Ten issues now track them, and two of them make Windows CI fail intermittently. This change serves **M9 - Adoption and configuration** (change 1). It advances the exit criterion "The defects kept or found by the M8 ports (#206, #209, #214, #215, #223, #224, #227, #231, #232, #235) are fixed or closed with a reason, with evals on the three CI platforms" (agent-verified). It runs first so the later M9 changes start from a sound `sw`.

## What Changes

- **#206** `sw vcs commit` on GitButler no longer stops with `commit_mismatch` when the message file has CRLF line endings. jj normalises the message to LF before the commit. GitButler keeps passing the file to `but commit -F`, now by its path resolved where `sw` runs, so `but` no longer reads it relative to the repo, and its read-back check reads line endings as LF on both sides, so a CRLF file no longer reports a mismatch; `sw` makes no promise about the line endings `but` stores. Git is unchanged: under its default cleanup it already strips the CRs, a test now pins that, and a configured `commit.cleanup` mode is honoured as before.
- **#209** `sw finish undo-archive-plan`:
  - a resume's `dirty_tree` keeps the first character of the first path;
  - a usage error from the state read exits 2, not 1;
  - a staged rename's source record is read whole by the shared `-z` record reader, which the carried-edits read also uses; on Git a staged rename reaches the planner only on resume, as a `dirty_tree` record with both paths;
  - the undo refuses more cases it used to run into, each before it writes: at planning, with no script printed, a sparse checkout (`git_env`), ignored content in the archive root (`git_env`), a checkout filter or committed symlink on a rerun input (`unsupported_filter`), a submodule, type change, link or case alias on a path the undo writes or moves (`unsupported_entry`), and a failed Git read (`vcs_error`); after a resume's checkout, a restored decision file that differs from the tip, an untracked file in the archive or an occupied restore destination stops the steps before any backup or index write, with the archive branch left checked out.
- **#214** `sw pr snapshot`:
  - a non-numeric `--timeout` is a usage error;
  - a leading zero is read as decimal (`08` is 8 seconds);
  - a material file that cannot be written is named on stderr, with the reason.
  - Item 4 (the `$0` name in messages) is closed as moot: the scripts are retired and `sw` prints one fixed name.
- **#215** `sw pr snapshot --logs` merges the failed job's stdout and stderr in the order their output arrived before it takes the 80-line tail.
- **#223** On Windows, the command-line limit check counts the bounded helper's prefix, so an over-long line is refused before anything starts. A direct launch reports it as `Unrepresentable`; a bounded launch reports a line the old checks admitted as the failed helper start it gave before, so callers keep their results.
- **#224** On POSIX, `PATH` lookup skips a file the current user cannot execute and goes on down `PATH`, as the bash launcher did.
- **#227, #231** Windows eval flakes:
  - On Windows, a feedback record replace that fails while another process has the record open, as an adopt call's existence check can, is retried briefly. A failure that persists is still reported as it is.
  - `test_parity` names each subtest folder by the case's ordinal instead of by `hash()`, so no two cases share one.
  - The lock-race test checks the record the winner leaves and prints every call's result when it fails.
- **#235** `sw-install` cleans up its part files on a best-effort basis: a part file that is still locked never replaces the install's own result or error.
- **#232** is closed with a reason and changes no code (S1).
- **Interface 3:** several of these fixes change exit codes or results callers could rely on, so `sw version --json` reports `interface` 3 and the skills require it (S5).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `vcs-backends`: a commit message file with CRLF line endings commits and verifies on every backend.
- `change-finish`: the undo planner reports dirty and carried paths whole and keeps usage exits at 2.
- `pr-script-runtime`:
  - snapshot `--timeout` parsing;
  - a write failure names the file;
  - `--logs` keeps stream order;
  - feedback-record replacement on Windows retries a replace that another call's read refuses, briefly, under the record's lock and only while its temporary source exists.
- `native-cli`:
  - the Windows command-line check includes the helper prefix;
  - command lookup takes only files the current user can execute.
- `install-update`: part-file cleanup never replaces the install's own result.

## Impact

- **Code:**
  - `cli/lib/src/vcs/` (GitButler and jj commit; Git checked by a test only), and a `vcs` suite rule for it in `evals/suites.json`;
  - `cli/lib/src/finish/undo_plan.dart`;
  - `cli/lib/src/pr/snapshot.dart`;
  - `cli/lib/src/pr/feedback_record.dart` (and doc comments in `cli/lib/src/pr/feedback_record_files.dart`);
  - `cli/lib/src/process/` (`command_line.dart`, `bounded_run.dart`, `resolve.dart`, `launch.dart`);
  - `cli/lib/src/update/sw_install.dart`.
- **Evals:**
  - `evals/pr-pair/test_parity.py` and `evals/pr-pair/test_workflow_records.py`;
  - PR parity cases whose frozen oracle records change become explicit differences with their own outcome tests; the finish evals are outcome tests already and are strengthened directly; a new failed-log outcome case covers `--logs`, beside the unchanged `--logs` parity fixture;
  - new Dart tests beside each fix.
  - CI runs them on Linux, Windows and macOS.
- **Skills:** the `<sw>` paragraph of each skill that runs `sw` (`specwright-branch`, `-commit`, `-debug`, `-finish`, `-pr`, `-release`, `-review`, `-roadmap`) requires interface 3, and `specwright-pr`'s `interface` line reads 3; no setting or install layout changes.
- **Release:** minor 0.39.0 with `interface` 3 (S5).

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: #232 is closed with a reason, not fixed

- **Choice:** close #232 with a reason and change no code. The gaps need either a stale unlock the user confirms by hand or a failure partway through the undo plan. The owner chose parity there after two design rounds, and review found that the unlock and ownerless-lock fixes each add a race of their own.
- **Rejected:** making only the undo plan resumable (item 3), which is a design of its own for a rare failure; moving #232 to Later, which would need a roadmap edit to the exit criterion.
- **Reversal cost:** low. The issue can be reopened, or planned as its own change.
- **Important:** yes. It decides the scope of an exit criterion.
- **Chosen by:** user

### S2: #223 and #224 are fixed

- **Choice:** fix both. Each is a regression from the bash launcher (#221), and each fix is small: count the helper prefix in the limit check, and check whether the current user can execute a file during lookup.
- **Rejected:** closing both as corner cases; fixing #224 only.
- **Reversal cost:** low.
- **Important:** yes. Both change behaviour users see (which `git` runs, and which error an over-long line gives).
- **Chosen by:** user

### S3: every parity-kept defect is fixed, each as an explicit oracle difference

- **Choice:** fix #206, #209 items 1-3, #214 items 1-3 and #215. Each case whose frozen record changes becomes an explicit difference with its own outcome test, and the records themselves stay untouched. Close #214 item 4 as moot.
- **Rejected:** fixing only #206 and #215 and closing the rest, which would leave known wrong output in place.
- **Reversal cost:** low.
- **Important:** yes. Exit codes and output that users and skills read change.
- **Chosen by:** user

### S4: the Windows flakes are fixed in `sw` and in the tests

- **Choice:**
  - `sw`: retry a failed feedback record replace on Windows (at most 5 retries, each after a requested 20 ms pause, under the record's lock, only while its temporary source exists; the older publication-rollback window is left to #239), and report a failure that persists as it is (design D3, chosen by the user over retrying the lock create, which a Windows probe showed does not fail in this race);
  - `sw-install`: make part-file cleanup best effort;
  - tests: name the parity subtest folders stably, and print the documents when the lock-race assertion fails.
- **Rejected:** test-side tolerance only, which would hide a real `record_busy` mismatch that users can hit.
- **Reversal cost:** low.
- **Important:** yes. It changes an error code users can see.
- **Chosen by:** user

### S5: one minor release with interface 3

- **Choice:** release the whole change as 0.39.0 and raise `sw`'s `interface` from 2 to 3, as ADR 0027 and ADR 0040 require when a command's arguments, exit codes or JSON output change incompatibly. This change makes several such changes for callers that relied on the old results, among them: strict `--timeout` validation; exit 2 instead of 1 for a `usage` stop of `undo-archive-plan`; route selection skipping an over-long `omp.cmd` probe instead of `internal_error`; `sw pr snapshot --logs` reporting `response_too_large` and exiting 1 when the merged streams pass the shared cap; `sw as` exiting 2 instead of 127 for an `Unrepresentable` `.cmd` line; `download_failed` for a final HTTP 200 with a non-identity `Content-Encoding`, and before any request when the partial file cannot be created; and Git 2.40 or later for a Git resume undo. The skills of this release require interface 3, so a project updates its skills and its `sw` together, as every update already does; a project left at 0.38.x with skills of this release stops with "update this project".
- **Rejected:** a patch with interface 2 and a closed list of exceptions, which three review rounds in a row found incomplete.
- **Reversal cost:** low.
- **Important:** yes.
- **Chosen by:** user

## Release Notes

0.39.0 fixes gaps the M8 native-CLI ports kept or found. Some fixes change exit codes or results, so `sw` reports interface 3 and these skills require it: update each project's skills and `sw` together. GitButler accepts CRLF message files, the archive undo reports paths whole and refuses what it cannot undo safely, `sw pr snapshot` checks `--timeout` and keeps log order, `PATH` lookup skips files the user cannot run, and Windows command-line, record and install-cleanup handling is fixed. Downloads must be unencoded; a Git resume undo needs Git 2.40.

### Fixed

- GitButler `sw vcs commit` accepts a message file with CRLF line endings instead of stopping with `commit_mismatch`, and jj stores such a message with LF line endings (#206). On GitButler a relative `--message-file` is read where `sw` runs.
- `sw finish undo-archive-plan` keeps the first character of dirty paths, reports both paths of a staged rename, and exits 2 on a usage error from the state read (#209).
- The archive undo stops at planning, printing no steps, on a sparse checkout or ignored archive content (`git_env`), a filtered or linked rerun input (`unsupported_filter`), a submodule, type change, link, case alias or file/directory clash on a path it writes or moves (`unsupported_entry`), a failed Git read (`vcs_error`), and a commit too long for one command line (`plan_too_large`) (#209).
- A resume undo whose restored files, archive directory or restore destinations are wrong after its checkout stops before any backup or index write, and leaves the archive branch checked out (#209).
- `sw pr snapshot` refuses a non-numeric `--timeout`, reads `08` as decimal, and names a material file it cannot write (#214).
- `sw pr snapshot --logs` merges stdout and stderr in arrival order before taking the tail (#215).
- The Windows command-line check counts the bounded helper's prefix, so an over-long line is refused cleanly (#223).
- `PATH` lookup skips files the current user cannot execute (#224).
- On Windows, a feedback record replacement that races another call's read of the record is retried briefly instead of failing at once (#227), and the `pr-pair` evals no longer collide on temp folders (#231).
- A Windows part file that is still locked no longer replaces `sw-install`'s own result (#235).

### Changed

- `sw version --json` reports `interface` 3, and the skills require it; a project still on 0.38.x stops with "update this project" when served by these skills.
- `sw pr snapshot --logs` reports `response_too_large` and exits 1 when its merged stdout and stderr pass the shared cap, where two separate per-stream caps used to let it succeed.
- `sw as` exits 2, not 127, for a `.cmd` command line it cannot represent.
- When the version directory cannot hold the partial download, `sw update sw-install` stops with `download_failed` before any request, even for a release whose assets are not uploaded yet.
- `sw finish undo-archive-plan` exits 2, not 1, when its state read stops with `usage`.
- `sw review run` route selection skips `omp` when an `omp.cmd` probe line is over the batch limit and tries the next route, instead of failing with `internal_error`.
- `sw update sw-install` asks for and requires unencoded downloads: a release asset or `SHA256SUMS` whose final HTTP 200 response has a `Content-Encoding` such as gzip now stops with `download_failed` naming the encoding, where it used to be decoded. GitHub serves release assets unencoded; a mirror or proxy that compresses them must stop doing so. A non-200 answer, such as a compressed 404 for a release not uploaded yet, is reported as before if it ends within the download's byte and time limits.
- `sw pr snapshot --timeout` now takes decimal digits from 0 to 9223372036854775807 only and exits 2, with no document and no `gh` call, on any other value such as `+5`, `0x10`, `soon` or `9223372036854775808`, which it accepted before.
- An archive undo on Git that resumes from the archive branch now needs Git 2.40 or later, to read the archive branch's attributes; on an older Git it stops with `tool_too_old` naming the minimum and the version found. No other command needs a newer Git.
- On a download, redirect and error response bodies now share the download byte budget with the asset: a mirror's oversized redirect or 404 body stops `sw update sw-install` with `response_too_large`.
