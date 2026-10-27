# 0014. Bounded runs share one process module, copied per skill

- Status: accepted
- Date: 2026-10-26
- Supersedes: 0012

## Context
ADR 0012 bounded every network command of the PR scripts through `skills/specwright-pr/scripts/bounded.py` and every reviewer run through `review-run.sh`'s own `capture` and `kill_tree`. It listed exceptions: `release.sh`, `finish.sh` and `update.sh` stayed unbounded (#111). M4 closed with more gaps in the same area. Both runners learned of a command's exit only at their next poll, so a command that exited just before its deadline while a child held its pipe was reported as a timeout (#114). On Windows `taskkill /T` walks the tree from the parent PID, so a child whose parent had exited survived the kill, and the tests skipped that assert (#116). Codex's answer was read from the `-o` file the CLI writes itself, which was only size-polled, so it escaped the bound while codex wrote it (#113). The two runners had the same spawn, kill and loop rules in two diverging copies, and fixing #114 and #116 in each, plus a third runner for `release.sh`, would have made three. ADR 0012 rejected importing `bounded.py` across skill folders, because each skill folder is installed independently; `update.sh` copies every `skills/specwright-*` folder whole.

## Decision
ADR 0012's bounds stand unchanged: 120 s per command, 300 s for a paginated read, 32 MiB each of stdout and stderr, the reviewer stream bounds, limits named `deadline_exceeded`, `response_too_large` or `output too large`, and a cut-off write decided by a read-back, never retried in a script. Its exceptions are removed.

- **One process module, an identical copy in each skill that runs bounded processes.** `bounded.py` is the only implementation of spawn, exit watching, tree kill and the bounded run. Byte-identical copies live in `skills/specwright-pr/scripts/`, `skills/specwright-release/scripts/` and `skills/specwright-review/scripts/`; the PR copy is the one edited, and a test fails when the copies differ. Each caller loads its own folder's copy by path, so no skill imports from another.
- **`review-run.sh` takes spawn, kill and the exit watcher from its copy.** Its `capture` keeps its own loop (file-backed output, per-stream limits, a held pipe fails the run) and drops its own `kill_tree`.
- **Windows trees are held by a job object.** `spawn` creates the process suspended, assigns it to a job object (without kill-on-close) and resumes it, so every process it starts is in the job, also after the parent exits; `kill` terminates the job. When the job cannot be created or assigned, the run falls back to `taskkill /T /F` by PID and says so: `bounded.py` writes `bounded: no job object: <reason>` on stderr, and the review receipt has `process_group: none` with the reason. POSIX is unchanged (`start_new_session`, `killpg`).
- **The exit is observed by a watcher thread.** It blocks in `wait()`, records the exit time and wakes the loop. An exit recorded before the deadline gets the 2 s grace and keeps the command's own result; one recorded at or after the deadline is a timeout.
- **Codex's answer is read from its `--json` event stream**: the text of the last completed `agent_message` item, under the 2 MiB answer bound. No route's answer comes from a file the CLI writes itself, so the stream bound covers everything a reviewer writes while it runs.
- **`release.sh` and `update.sh` are bounded.** `release.sh` runs `git ls-remote`, `fetch`, `push` and every `gh` call through its copy, the closed-PR read as a paginated read; a cut-off tag push or release creation is read back (`ls-remote`, `gh release view`) and the existing tag-conflict and tag-mismatch stops still apply. `update.sh` loads the download's PR copy only for its release-tag lookup, at `min(60 s, the resolved deadline)`, and a limit or a missing module becomes the reason in its `store_version` refusal.
- **`finish.sh` runs no network command.** Its network steps are the agent's, through `as.sh`. An eval scans the script and fails on a `git` network command or `gh` call.

**Rejected: fixing #114 and #116 separately in each runner, and a third inline runner in `release.sh`**, because three copies of a Windows job-object routine would drift, as 0012's two copies already had. **Rejected: one shared file outside the skill folders**, because it breaks independent installation. **Rejected: assigning the job after an unsuspended spawn**, because a child started before the assignment escapes it. **Rejected: kill-on-job-close**, because it would also kill the detached helpers of a command that finished normally. **Rejected: a FIFO or OS size limit for codex's `-o` file**, because Windows has neither. **Rejected: one outer deadline around a whole `release.sh` run**, because it cannot tell which call hung, cannot bound bytes, and could kill a publish between its tag push and its read-back.

## Consequences
- No script in the skills runs an unbounded network command, and #111's exceptions are gone.
- A command that exits before its deadline is judged by that exit within scheduler latency, not a poll interval. A starved runner can still see an exit late and report a timeout, deliberately.
- On Windows a child left holding a pipe is stopped with the tree. `NtResumeProcess` is undocumented; its use is confined to `spawn`, and a failure ends the run as a spawn failure.
- The codex route depends on codex's documented `exec --json` event shape. A shape change fails the run closed (`invalid`), never accepts a wrong answer.
- Three copies of `bounded.py` ship, kept identical by a test.
- A runner itself killed by SIGKILL can still leave a hung child behind, as ADR 0012 accepted.
- Reversal cost: low. Callers go through `spawn`, `kill`, the exit watcher, one bounded-run function and one CLI.
