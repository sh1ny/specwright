# 0027. Shipped tooling is one Dart binary, installed per user by version

- Status: accepted
- Date: 2026-11-05
- Supersedes: 0002
- Adds to: 0014 (its bounds and process rules stay; its Python-specific parts end with M8)

## Context

ADR 0002 put Specwright's mechanical work into small scripts that use only bash, a POSIX userland, `git`, `gh` and the Python standard library. That tooling grew into bash wrapped around about 7,000 lines of Python heredocs, plus three byte-identical copies of `bounded.py` (ADR 0014). It needs two runtimes and per-script interpreter lookup, and it has no linting, types or unit tests below the black-box evals. Issue #148 fixed the replacement language: one compiled Dart executable, `sw`. The open questions were how it is built, where it is installed, how skills know they run the right binary, how an unsigned binary fares with macOS Gatekeeper and antivirus, and how the Windows process-tree guarantee of ADR 0014 survives the move. The `native-cli-spike` change proved the build, the bounded runner and the CI artifacts on Linux, Windows and macOS before any skill depends on `sw`.

## Decision

- **One single-file executable per platform**, built with `dart compile exe` from `cli/`. `cli/` depends on no package with build hooks (`package:args` and `package:ffi` only; Win32 and libc calls are its own lookups), and a test fails when a hook package enters `pubspec.lock`. The toolchain is pure Dart pinned in `mise.toml`.
- **Install root.** `sw` is installed at `<home>/.specwright/bin/<version>/sw[.exe]` on every OS (`%USERPROFILE%` on Windows), overridable by `SPECWRIGHT_HOME` for tests. Versions sit side by side. A skill derives the path from the project's installed `openspec/.specwright/VERSION`. No binary lands in a work tree.
- **Exact version and interface.** `sw version --json` prints `{"version": "<x.y.z>", "interface": <n>}`; the version is compiled in from `VERSION`, and a build without it reports `0.0.0-dev`. A skill runs only the binary at its project's installed version, and only when the reported `version` equals that version and `interface` equals the interface the skills were written for; otherwise it stops with `sw missing or mismatched: rerun the install prompt`. The skill-side check lands with `native-cli-distribution`.
- **Unsigned first, measured.** Builds are unsigned. On macOS the documented install step is `xattr -d com.apple.quarantine <sw>`, run by the install on the file it just checked by SHA-256; CI sets the quarantine attribute on the downloaded binary, logs whether it ran as-is, applies the step and requires success. On Windows the owner checks a CI-built binary under Malwarebytes. **Signing trigger:** if the macOS step does not unblock the binary, or antivirus blocks or quarantines it, signing (and on macOS notarisation) becomes the next decision; an antivirus exclusion is never the answer.
- **Process trees through a self-spawned helper.** `sw run --bounded` keeps ADR 0014's bounds and contract. The parent starts itself as a helper (`sw __exec`), which joins a job object without kill-on-close on Windows, or calls `setsid()` on POSIX, writes an internal ready frame, and starts the command only after the parent's go byte. This replaces `bounded.py`'s `CREATE_SUSPENDED` plus the undocumented `NtResumeProcess`. A limit before the go kills the helper by PID; a limit after it terminates the job or kills the group.
- **Coexistence until M8.** Skills keep calling the bash and Python scripts until each port's own change switches them to `sw`. `bounded.py` and its three copies stay, kept identical by ADR 0014's test, until M8 removes them. Until then both runners keep the same command-line contract.
- **Targets.** This change publishes CI artifacts only, with SHA-256 checksums, for linux-x64, windows-x64 and macos-arm64. Release assets, the install download, linux-arm64 and macOS x64 belong to `native-cli-distribution`.

**Rejected: a per-project, gitignored binary** (#148's suggestion), because it puts an executable in every work tree, GitButler's shared one included, and a fresh clone lacks it. **Rejected: accepting any installed binary whose interface matches** (newest wins), because same-interface versions can differ in behaviour and the evals prove only the version they ran on. **Rejected: `dart build cli` bundles**, because they allow native-asset packages but make the install a directory swap and the download a bundle instead of one file. **Rejected: signing and notarising from day one**, because it needs certificates, an Apple developer account and CI secrets before any evidence says they are needed. **Rejected: `CreateProcessW` suspended plus `ResumeThread` from Dart**, because it means owning pipes, read loops and Windows quoting in FFI for the same guarantee; it stays the fallback if the helper cannot join an inherited job.

## Consequences

- Skills and the install will depend on one path rule and one JSON report. Changing either is a workflow change (minor version); an incompatible command change bumps `interface`.
- A parent `sw` itself killed by SIGKILL or a task kill can leave its helper and command running: the job has no kill-on-close and the POSIX session is not tied to the parent, as ADR 0012 and 0014 accepted for `bounded.py`. The eval harness closes this for tests only: with `SPECWRIGHT_TEST_SPAWN_DIR` set, `sw` records each session it starts, and `evals/run.py`'s sweep stops recorded groups when it stops a test file. Production has no such record.
- Contributors need mise and the pinned Dart SDK to work on `cli/`; users need nothing new until `native-cli-distribution` installs the binary.
- Until M8 two runners implement ADR 0014's contract; the `evals/cli` suite checks `sw` against the same cases as `bounded.py`'s.
- Reversal cost: high for the install root and the version check (every skill will call them), medium for the build form and the helper, low for the rest.
