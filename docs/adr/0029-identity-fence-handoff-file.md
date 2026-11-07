# 0029. The identity fence hands its arguments over in a private file

- Status: accepted
- Date: 2026-11-07
- Adds to: 0028 (ported scripts are shims that hand `sw` their records on stdin)

## Context

ADR 0028 has every shim write its records (scripts directory, bash, then every argument) to `sw`'s stdin. That suits a script whose own stdin means nothing. `as.sh` is different: it ends by running the fenced command, and that command reads `as.sh`'s stdin. `git credential fill` reads the credential request there, and any future `gh ... --input -` caller would read its body there. With the stdin handoff, `sw as` would consume the records and the fenced command would read EOF instead of the caller's input, a silent behaviour change. `native-cli-pr-io` ports `as.sh` to `sw as`, so the fence needs another way to hand its records over.

## Decision

- **`as.sh` alone hands its records to `sw as` in a private file.** The shim writes the ADR 0028 records (scripts directory, bash, then every argument, each ending in NUL) to a file from `mktemp`, which only the current user can read, and runs `sw as --args-file <path>`. Stdin stays the caller's.
- **`sw as` deletes the file before any `gh` call or command.** It reads the whole file, deletes it, and only then parses the records. A file it cannot read or delete stops it with exit 3 and `as.sh: handoff: <reason>`, and nothing runs.
- **The file holds arguments, never a token.** The token is read after the file is gone and lives only in memory and in the fenced command's environment.
- **The fenced command keeps the caller's stdin.** It reads what `as.sh` was given, as before the port.
- **Every other shim keeps ADR 0028's stdin handoff.** Only the fence hands its stdin to another command, so only `as.sh` needs the exception.

**Rejected: ADR 0028's stdin handoff for `as.sh`**, because the fenced command would read EOF instead of the caller's input. **Rejected: an extra file descriptor (`3< <(...)`)**, because native Windows processes started from Git Bash do not inherit it. **Rejected: the arguments on `sw`'s command line**, because ADR 0028 rejected argv for its lossy decoding on POSIX and the Git Bash length limit on Windows.

## Consequences

- `sw as` has a handoff form no other `sw` command has: `--args-file <path>`, not `--args-stdin`.
- A `sw as` killed between the shim's write and its own delete leaves one file in `TMPDIR` holding arguments only. Deleting it is the first thing `sw as` does, so the window is one read.
- When M8 switches callers to `sw as` directly, the direct argv form replaces the file, and this exception ends with the shim.
- Reversal cost: medium. Returning to the stdin handoff changes what the fenced command reads.
