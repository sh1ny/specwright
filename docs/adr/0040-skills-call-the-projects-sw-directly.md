# 0040. Skills call the project's `sw` directly

- Status: accepted; its interface-2 pin is amended to 3 by 0042, and its entry check for `sw finish undo-archive-plan` by 0043
- Date: 2026-11-19
- Supersedes: 0028 (ported scripts are shims that resolve the project's `sw`) and 0029 (the identity fence hands its arguments over in a private file); replaces the MSYS-paths clause of 0034
- Adds to: 0027 (one native binary, exact version, no fallback) and 0031 (direct native calls, `--project`)

## Context

After M8's ports every shipped script was a shim: it resolved `sw` through `sw-path.sh`, checked for Python 3.8+, and handed `sw` its scripts directory, its bash path and the caller's arguments as NUL records on stdin (ADR 0028), or, for the fence, in a private file (ADR 0029). The shims kept bash in front of every call, `sw-path.sh` ran `bounded.py` for its version probe, and `sw` converted MSYS paths itself because the stdin handoff skipped Git Bash's own conversion (ADR 0034). M8's outcome is that Specwright needs neither bash nor Python for its own work, so the shims, the handoff and the resolver go, and the skills call `sw` themselves.

## Decision

- **Direct argument entry.** Every `sw` command takes its arguments as the process's own argument list. There is no stdin or file handoff, no scripts-directory or bash record, and `sw` converts no MSYS path: a path reaches a command as the caller's shell passed it. Git Bash already converts `/c/...` and `/tmp/...` when it starts a native executable.
- **UTF-8 argument contract.** An argument that is not well-formed Unicode as it reached the process is refused before any work. On Windows (a lone surrogate) `sw` prints one `bad_argument` document naming the argument's position, exit 2. On Linux and macOS (bytes that are not UTF-8) the Dart runtime refuses the argument list before `main`: non-zero exit, empty stdout, no work, its exit code and text unspecified (C6). When execution reaches `sw`, it checks the raw list itself (`/proc/self/cmdline` on Linux, `_NSGetArgv` on macOS, `GetCommandLineW` on Windows) to tell a malformed argument from a valid one that holds U+FFFD. ADR 0034's launch-time refusals stay as a second line.
- **Version-pinned resolution with an entry check.** Skills name `sw` as `<home>/.specwright/bin/<project VERSION>/sw[.exe]`, after checking that `VERSION` is a version. Every project command (`vcs`, `pr`, `as`, `commit`, `finish`, `review`, `release`, `gate`) checks the project's `openspec/.specwright/VERSION` against its own version once at the entry and stops with `sw_mismatch` naming the expected binary path when they differ. `version`, `run --bounded`, `update` and `pr reviewers` check no project version.
- **A global leading `--project <code checkout>`.** It selects only the `VERSION` to check, so a store-started call passes the check; it changes neither the working directory, the targets nor the login.
- **Interface 2.** `sw version --json` reports interface 2, because the command-line contract changed. Before its first other command a skill runs `<sw> version --json` and stops unless it reports the project's version and interface 2, so an older project served by newer skills stops with "update this project", never with an unknown-option error.
- **The Windows `bash -c` transport stays for caller-requested shells.** `sw run --bounded` keeps the stdin transport it uses on Windows when the caller asks for `bash -c`, which ADR 0034 left to this change. It is never used for `sw`'s own work, which starts no shell.

**Rejected: a stable launcher at `<home>/.specwright/bin/sw`,** because it adds a self-launch and a cross-version contract. **Rejected: a per-project copy of the binary,** at about 10 MB per project. **Rejected: keeping `--args-stdin` as a hidden entry,** because no shipped caller remains and two entry surfaces drift. **Rejected: refusing a malformed argument only where it is used,** because that scatters error names and allows partial work before the stop.

## Carried constraints

- **No fallback (C2).** `sw` never falls back to an `sw` on `PATH` or to another version's binary. The version check is the only resolution: a mismatch stops, it does not search.
- **No leading slash in `gh api` paths (C3).** Skills write `gh api repos/...`, never `gh api /repos/...`. Git Bash converts any leading-slash argument it hands to a native executable, not only paths, and `sw` no longer undoes that.
- **Argument detection on each OS (C6).** A compiled-binary probe on Linux, Windows and macOS (run https://github.com/sh1ny/specwright/actions/runs/44410098089) settled what `sw` can see. On Windows it passes: `sw` reads the raw command line, tells a lone surrogate apart from a valid U+FFFD, and prints `bad_argument` with exit 2. On Linux and macOS `sw` cannot see a non-UTF-8 argument: the Dart runtime refuses the argument list before `main` runs, exiting 255 with `Dart_NewStringFromUTF8 expects argument 'str' to be valid UTF-8.` on stderr and nothing on stdout. That loss is accepted: there the runtime's refusal (non-zero exit, empty stdout, nothing started or written) stands in for the `bad_argument` document, and evals check only that, not the runtime's exit code or text. `sw` still checks the raw list on Linux and macOS, so a runtime that ever passes such bytes through gets the document.
- **The probe keeps its deadline, not its output cap (C8).** The skill's version probe keeps the 10-second deadline `sw-path.sh` applied, carried by the agent's tool timeout. It drops the 1 MiB output cap that `bounded.py` gave `sw-path.sh`: the probed binary is the one the install placed after a checksum check, and the agent's tool already limits what it captures.

## Consequences

- Specwright's own work needs neither bash nor Python. `sw` starts itself only for its process helper and the reviewer evaluator.
- A person who scripted `bash .../vcs.sh` by hand must call `sw vcs`. The name map in the native-cli spec gives the `sw` command for each retired script.
- A project on an older version keeps its own `sw`; newer user-level skills stop in it until it is updated.
- Changing the argument contract or the interface number is a workflow change (minor version).
- Reversal cost: medium. Restoring shims would need a handoff entry in every command and bash back as a prerequisite.
