# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 ended APPROVE_WITH_CHANGES, its changes re-checked as applied. M1-M7 and N1-N3 were fixed and accepted, and S1-S8 were applied or folded into tasks. An apply-time amendment to D1 ("Windows argument transport") and a new Risks entry voided that verdict.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** proposal.md, design.md (the whole file, with the focus on `git diff` of D1's new "Windows argument transport" bullet and the new Risks entry), specs/pr-script-runtime/spec.md (grep for Windows, argument, stdin and file wording), tasks.md and review.md (round 1) of `bound-pr-scripts`. Code: skills/specwright-pr/scripts/bounded.py (working tree), the pr-snapshot.sh diff (the shared header, the uncommitted `SW_JQ` workaround in `query_pr`, the `norm`/`scan` backslash rewrites and the SHAPE heredoc at :187-391), pr-pair.sh :66-78, `net` :157-167, `git_net` :213-230, `gh` :235-245 and `token_for` :258-271, as.sh :69-119 and :215, pr-reply.sh :36-48 and its `gh` call sites, the evals/pr-pair/test_bounded.py diff, and evals/fakes/gh.py (its stdin and encoding handling). CPython's `Popen._communicate` on Windows, as installed (3.14.4). Local bash: GNU bash 5.3.15 (Git Bash).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The prelude runs the command even when the argument list arrived incomplete.**
The prelude is `mapfile -d "" -t __sw_argv; set -- "${__sw_argv[@]}"; …`. It runs the script on whatever reached EOF, and `mapfile -t` also keeps a final element that has no NUL after it. This causes two concrete failures:
- **The runner dies mid-write.** If the runner is killed while it writes (the Failure table already accepts "bounded runner killed itself (the parent died)", and on Windows the child outlives it), bash reads EOF early. It then executes `gh` with a prefix of the arguments, and the last of them may be cut. These scripts issue writes (`gh pr create`, the merge PUT, reply posts and resolves; design T6). A shortened argv can run as a different command, for example one with a trailing flag dropped. The window is real only when the arguments exceed the pipe buffer, as the 14 KB filter does.
- **A bash without `mapfile -d`.** On bash older than 4.4, `mapfile -d` fails with "invalid option" and leaves the array empty. Every call then runs bare `gh`, which prints its help and exits 0. Callers read that output as data. For example, as.sh's `help=$(gh auth token --help)` gets the general help and refuses with "upgrade gh", and `gh api user --jq .login` returns help text as the login. Git Bash ships 5.x, so this is unlikely, but the failure is silent and misleading.

The fix is one line and fails closed in both cases: the runner writes an end sentinel as the last NUL-terminated element, and the prelude checks for it and drops it before `set --`, or exits non-zero with a clear stderr line.

**M2. D1 does not fix the encoding of the transported arguments or what the writer does when the pipe breaks.**
- **Encoding.** On the command-line path, MSYS turns the UTF-16 command line into UTF-8. Over stdin, the bytes are whatever the runner encodes. The real snapshot filter is not ASCII: the SHAPE heredoc (pr-snapshot.sh:187-391) contains `…` (:190) and the 👍/👎/👀 emoji in jq comments (:209-212). Two plausible implementations break every snapshot on Windows:
  - `Popen(..., text=True)` or `universal_newlines` encodes with the locale code page (cp1252 without UTF-8 mode, and bounded.py runs as `-I` without `-X utf8`). That raises `UnicodeEncodeError` on the emoji.
  - Any non-UTF-8 encoding would hand gh bytes it cannot parse.
- **Broken pipe.** If the child exits or is killed before it reads everything, Windows raises `OSError` (EINVAL or EPIPE) in the writer. Unless the daemon thread catches it, Python prints an `Exception in thread …` traceback to the runner's stderr. That traceback lands on the script's stderr, next to the `bounded: deadline_exceeded: …` line that callers and tests match.

D1 should state that the runner writes `"\0".join(args) + "\0"` encoded as UTF-8 to a binary pipe. It should also state that the writer closes stdin when done and ignores `OSError`/`ValueError` from a pipe the child has closed. The Risks test should include a non-ASCII argument.

**M3. Nothing in tasks.md implements or tests the amendment, and the workaround it replaces stays in place.**
- Task 3.2 (bounded.py) is ticked, and no open task changes bounded.py for the transport.
- No task adds the `test_bounded.py` round-trip case that the new Risks entry promises (long argument with spaces, a newline, quotes, backslashes).
- No task removes the uncommitted `SW_JQ` path in `query_pr`. It bypasses the shared `gh()` function: it duplicates the bounded.py invocation and drops `${SW_SECRET:+--secret}`, so the file has two call paths with different flags. It also contradicts D1's rejected alternative "passing a large argument through an environment variable at each call site".
- The backslash rewrites in the SHAPE filter (`norm` as `rtrimstr("[bot]")`, `scan("Reviewed commit:[*][*] …")`) are equivalent and can stay. Their comment ("bash.exe halves it in an argument") becomes false once the transport lands.

As things stand, the apply phase can finish with the design amended and the code still on the env-var workaround.

### Suggestions

**S1. Secret mode's no-hang claim rests on its input being small. Say so.**
D1 says that `communicate(input=...)` in secret mode means "a child that never reads cannot hold the runner past its deadline". The CPython installed here (3.14) writes input from a daemon writer thread and honours the timeout. Older CPython releases inside the project's 3.8+ floor write stdin on the calling thread in Windows `_communicate`, before the timeout applies. The claim still holds today, because every secret-mode command (`gh auth token --hostname github.com --user <login>`, under 100 bytes) fits in the pipe buffer, so the write never blocks. State that dependency in D1, or use the same daemon writer in both modes and pass no `input` to `communicate`. That keeps the claim true if a larger secret-mode command is ever added.

**S2. Specify where the rewrite happens.** The transport should rewrite the command inside `_file_backed`/`_secret` (or `_run`), not in `main`. `main` names the limit from the original `cmd[3:5]` (bounded.py:176-177, and `test_limit_line_names_the_command_inside_bash_c`). If the rewritten command reaches `main`, the `bounded: <limit>: gh api` line still works only by accident, through `$0` and the first argument. The command-line form has no first argument.

**S3. Scope note.** `git_net` runs `[BASH, as.sh, login, git, …]` with no `-c`, so it keeps the command-line path. Its arguments are short today (`ls-remote`/`fetch` refs), so this is fine. One line saying so ("as.sh as a script file is not covered; its arguments are refs") would stop a later reader from assuming every bash hop is covered.

### Answers to the focus questions

- **Bash version.** `mapfile -d` needs 4.4+. The transport applies only when `os.name == "nt"`, where the bash in use is the script's own `$BASH` (Git Bash or MSYS2, 5.x; 5.3.15 locally). MSYS or Cygwin Python reports `os.name == "posix"` and keeps the command line, which is correct for an MSYS-to-MSYS hop. M1's sentinel makes an older bash fail visibly instead of silently.
- **Deadlock.** In file-backed mode the writer is a daemon thread, the deadline clock starts at `Popen` as before, and `kill_tree` closes the read end, which unblocks the writer. A survivor of `taskkill` leaves only a blocked daemon thread, which ends with the process. In secret mode, see S1.
- **Secret mode on disk.** Nothing reaches disk: the arguments go over a pipe. That holds.
- **`$0`.** It is preserved, because the prelude is prepended to the script and `$0` stays `cmd[3]`. See S2 for the limit line.
- **Scripts that read stdin.** After the prelude, `exec </dev/null` gives `gh` the same empty stdin it had with `DEVNULL`. No call site uses `--input -` or `@-`: pr-reply.sh passes bodies with `-F body=@"$tmp"` and `--body-file`. The `while … done <<<"$batches"` loop in pr-snapshot.sh is unaffected, because the runner never reads its own inherited stdin.
- **Specs and other decisions.** No scenario in the five delta specs depends on how arguments are passed. The amendment contradicts no other decision and no in-force ADR (0002, 0007, 0008). pr-pair.sh's `gh()` and `token_for` gain the same transport through `run_bounded`. That is a fix for their GraphQL queries, not a regression.
- **Rejected alternatives.** Both rejections are sound. An environment variable per call site fixes one argument and leaves the rest exposed. An argument file breaks secret mode's no-disk rule. A uniform stdin path is also simpler to test than a "long arguments only" switch.

### Re-check (after the author's edits)

Re-read: `git diff -- design.md tasks.md` (D1's "Windows argument transport" bullets, the new Risks entry, new task 3.3).

- **RC1 (M1): applied.** The runner writes an end marker `__SW_ARGV_END__` followed by a NUL. The prelude checks that the last element is the marker and drops it before `set --`. On a missing marker it prints `bounded: argument transport failed` and exits 126 without running the command. D1 names both causes it covers: a runner that died mid-write, and a bash older than 4.4. The wording differs from the request (`argument transport failed` / 126, not `incomplete arguments` / non-zero), which is equivalent. An empty original argument still round-trips, because `mapfile` keeps empty NUL-terminated elements and only the marker is dropped. Task 3.3 tests that case.
- **RC2 (M2): applied.** D1 now specifies UTF-8 bytes on a binary pipe, and a daemon writer thread in both modes that ignores `OSError`/`ValueError` and closes stdin afterwards. The Risks test covers non-ASCII text and the missing marker. Task 3.3 adds the case of a child that closes stdin early and prints no traceback.
- **RC3 (M3): applied.** Task 3.3 is open and written test-first. It covers the round trip (9,000 characters, spaces, a newline, quotes, doubled backslashes, `…`, 👍, an empty argument), the missing marker (exit 126, command not run), the early-close case, and Windows-only skips. It then implements the transport inside the run functions, removes `SW_JQ` from `query_pr` in favour of the shared `gh()`, and fixes the `norm` comment. Putting those last two in 3.3 rather than 5.2/5.5 is fine: 3.3 is where the transport they depend on lands, and its Verify runs `test_pr_snapshot.py`.
- **S1: applied.** Both modes use the daemon writer, so secret mode's no-hang claim no longer depends on the CPython version or on the input size.
- **S2: applied.** The rewrite happens inside the run functions, and the CLI's limit line names the original wrapped command.
- **S3: applied.** D1 says that `git_net` starts `as.sh` as a script file and keeps its short arguments on the command line.

The edits introduced no Critical or Moderate defect. Two minor notes for apply, neither blocking:

- **S4. Secret mode: keep `communicate` from writing stdin as well.** With the daemon writer in both modes, secret mode's `communicate(timeout=…)` must not also own `p.stdin`. On CPython 3.13+ (3.14 here), `communicate` starts its own writer thread whenever `p.stdin` is set and closes stdin on a `None` input. That races the runner's writer and can cut the argument stream, which the end marker then turns into exit 126 on a valid call. Hand `p.stdin` to the runner's thread and set `p.stdin = None` before calling `communicate`, or read stdout and stderr with the runner's own reader threads.
- **S5. as.sh and exit 126.** as.sh's `limit_stop` maps only 124 and 125. Exit 126 falls through to its existing messages: "upgrade gh" (`--help`), "no active gh account" or "no gh credential". Several of those calls discard stderr (`2>/dev/null`), so the `bounded: argument transport failed` line is lost. It still fails closed (exit 3, fenced command not run), but the cause is misreported. Mapping 126 in `limit_stop` to `as.sh: argument transport failed: <command>` would fix that.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

None outstanding. The re-check found RC1-RC3 applied (see Findings). The list was:

1. **D1, Windows argument transport (M1).** Add an end sentinel. The runner writes a fixed final element after the arguments, NUL-terminated. The prelude checks that the last array element is the sentinel and removes it before `set --`. Otherwise it writes `bounded: incomplete arguments` to stderr and exits non-zero without running the script. State that this covers both a runner that dies mid-write and a bash without `mapfile -d`. *(applied)*
2. **D1, Windows argument transport (M2).** State that the runner writes `"\0".join(args) + "\0"` (plus the sentinel) as UTF-8 bytes to a binary stdin pipe. State that the writer closes stdin afterwards and ignores `OSError`/`ValueError` from a pipe the child closed, so nothing beyond the runner's own limit line reaches stderr. In the Risks entry, add a non-ASCII character to the round-trip test argument and a truncated-input case that asserts the script does not run. *(applied)*
3. **tasks.md (M3).** Add an open task with failing-test-first wording: write the `test_bounded.py` cases (round trip of a long argument with spaces, a newline, quotes, backslashes and non-ASCII; truncated input does not run; Windows only, skipped elsewhere), then implement the transport in bounded.py. Extend task 5.2 or 5.5 to replace the `SW_JQ` call in `query_pr` with a plain `gh api graphql … --jq "$CFG…$SHAPE"` through the shared `gh()`. In the same task, correct or remove the "bash.exe halves it" comment on `norm`. *(applied)*

CHANGES_APPLIED: yes

## Rebuttals
- **M1:** fixed. D1 adds the end marker `__SW_ARGV_END__`. On a missing marker the prelude prints `bounded: argument transport failed` and exits 126 without running the command, and D1 names the mid-write death and old-bash causes. *(accepted by reviewer)*
- **M2:** fixed. D1 specifies UTF-8 bytes on a binary pipe and a daemon writer in both modes that ignores `OSError`/`ValueError` and closes stdin. The Risks test adds non-ASCII text and the missing-marker case. *(accepted by reviewer)*
- **M3:** fixed. New open task 3.3 is written test-first, covers the transport in `bounded.py`, removes `SW_JQ` from `query_pr` and fixes the `norm` comment. *(accepted by reviewer)*
- **S1:** applied. The daemon writer runs in both modes. *(accepted by reviewer; see S4 for an implementation note)*
- **S2:** applied. The rewrite is inside the run functions. *(accepted by reviewer)*
- **S3:** applied. D1 scopes out `git_net`'s as.sh hop. *(accepted by reviewer)*
