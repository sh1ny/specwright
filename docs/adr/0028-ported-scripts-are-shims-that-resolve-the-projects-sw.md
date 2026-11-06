# 0028. Ported scripts are shims that resolve the project's `sw`

- Status: accepted
- Date: 2026-11-06
- Adds to: 0017 (`vcs.sh` keeps its path and its JSON and exit-code contract) and 0027 (coexistence until M8; exact version, no fallback)

## Context

ADR 0027 moves the shipped scripts into one Dart binary, `sw`, port by port, and says skills keep calling the scripts until each port's own change switches them. It does not say how a port switches. Callers run scripts by path: skills, `finish.sh`, `pr-pair.sh`, `release.sh`, `review-run.sh` and `update.sh`. Changing every caller for each port would touch many files and break any caller we do not own. The ports `native-cli-vcs`, `native-cli-commit` and `native-cli-finish`, and the removal in M8, all need the same rule. No step reads an archived design for planning (ADR 0026), so the rule has to live here.

## Decision

- **A ported script stays a shim at its old path until M8.** Callers keep the command line and the output they have today. The shim holds no logic of the old implementation.
- **The shim resolves the project's `sw` through `skills/specwright-pr/scripts/sw-path.sh`.** That is the binary at `<home>/.specwright/bin/<version>/sw[.exe]` for the version in the project's `openspec/.specwright/VERSION`, checked for exact version and interface (ADR 0027).
- **The shim hands `sw` its scripts directory and its bash as the stdin header.** It runs `sw <command> --args-stdin` and writes on stdin NUL-terminated records: the scripts directory, the bash path, then the subcommand and every argument. Nothing else goes on `sw`'s command line, so paths and arguments reach `sw` as bytes and not through argv decoding. `sw` uses the directory and bash to call the scripts that are not ported yet and to name the commands it prints.
- **A failed resolution is a refusal, never a fallback.** The shim prints `sw_missing` as one JSON document on stdout (`{"ok": false, "error": "sw_missing", "message": "..."}`), copies the resolver's stderr to stderr, and exits 1. It never runs its old implementation, never uses another version's binary, and never uses an `sw` found on `PATH`.
- **Scripts not yet ported are called by `sw` as subprocesses.** A port does not need the whole tree ported first.
- **M8 removes the shims.** Callers then call `sw` directly.

**Rejected: switching every caller to `sw` in each port**, because it spreads one change over many files and leaves any caller we do not own broken. **Rejected: a fallback to the old implementation when `sw` is missing**, because it keeps two implementations alive and hides the missing binary (ADR 0027 forbids it). **Rejected: passing the scripts directory and bash as options or environment variables**, because argv is decoded lossily on POSIX and an environment contract is invisible in `sw`'s usage and leaks into child tools.

## Consequences

- A project without a matching `sw` cannot run a ported script. It stops with `sw_missing` until a tagged install or a build from the same commit places the binary.
- Each ported script costs one resolver run per call.
- `native-cli-commit`, `native-cli-finish` and M8 follow this rule. Changing the handoff form is an incompatible change to every shim and to `sw` together.
- Reversal cost: medium. The shims could return to their old bodies, but each port deletes that body.
