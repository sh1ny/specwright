# 0034. sw launches tools without a shell

- Status: accepted
- Date: 2026-11-11
- Adds to: 0027 (one native binary)
- Supersedes: none

## Context

Until now `sw` started most external tools through `bash -c` with a prelude that framed the output, changed directory and set up the environment. That kept a POSIX userland, and on Windows a Git for Windows install, in the path of every internal call, and it carried non-UTF-8 bytes through a private escape codec. The `native-cli-launcher` change replaces the prelude with one native launcher, `cli/lib/src/process/launch.dart`. Its contract binds every later port and `native-cli-retire-scripts`, beyond one capability, so it is recorded here.

## Decision

- **No shell.** `sw` starts external tools without a shell (C1). A native executable starts directly with `Process.start` on the resolved path and the caller's working directory. It does not go through the `sw __exec` helper, which stays for bounded runs and batch files (C10).
- **Arguments.** On POSIX they are UTF-8. On Windows they are UTF-16, passed through Dart's native quoting.
- **Batch files.** A `.cmd` or `.bat` command runs through the `planLaunch` raw `cmd.exe` line. A captured or bounded call goes through the `sw __exec` helper. The fenced command of `sw as`, which inherits the caller's stdio, runs through `runWithCommandLine` in process. No launch gains a deadline it did not have.
- **Refusals.** Before starting anything, the launcher refuses a NUL, a lone surrogate, or on Windows a command line over 32,767 UTF-16 units, with a named `unrepresentable` result. These checks run before the batch rules of `planLaunch`.
- **MSYS paths.** A handed-over `/x/...` path converts by fixed rules from the handed-over bash: a drive letter, UNC, `/tmp` under `%TEMP%`, and anything else under the Git root. There is no `cygpath` and no fstab parsing (C4).
- **Extensionless commands.** They are not runnable on Windows. Lookup is `PATHEXT` only (C5).
- **Non-UTF-8 names.** A name or path that `sw` acts on is decoded strictly. One that is not UTF-8 stops with `not_utf8`; display text decodes with replacement.

**Rejected: starting every launch through the helper**, because it adds a second `sw` process to each of the many git and jj calls in one run. **Rejected: `CreateProcessW` with pipes in FFI**, because it means owning pipes, read loops and quoting. **Rejected: running a `#!` script through Git Bash on Windows**, because it keeps a bash dependency. **Rejected: parsing fstab or launching `cygpath`**, for the same reason.

## Consequences

- Skills and later ports launch tools through `launch`; a direct `bash -c` start for `sw`'s own work is no longer allowed. `sw run --bounded` keeps its Windows `bash -c` stdin transport for callers that ask for bash, until `native-cli-retire-scripts`.
- A Windows fake tool in an eval needs a `.cmd` wrapper beside its script.
- A name that is not UTF-8 is refused instead of carried through; the walk reports it with U+FFFD, because Dart does not expose the raw bytes.
- Reversal cost: medium. Changing the refusal rules or the lookup rule changes what users see.
