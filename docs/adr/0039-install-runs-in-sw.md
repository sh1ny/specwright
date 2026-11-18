# 0039. The install runs in `sw`, and the agent fetches the first `sw`

- Status: accepted
- Date: 2026-11-17
- Supersedes: —
- Adds to: 0011 (staged updates, journal and recovery) and 0027 (one Dart binary, home layout, quarantine)

## Context

`scripts/update.sh` ran every install and update: about 1,000 lines of bash driving about 2,300 lines of embedded Python. The README install prompt checked for bash and Python 3.8+ before anything else, and `mise run install-sw` ran `scripts/install-sw.sh` with bash. While they remained, no project could install or update Specwright without both runtimes. The first `sw` on a host had to come from somewhere, and until now `update.sh sw-install` fetched it with Python.

## Decision

- **`sw update` runs the install.** Every `update.sh` subcommand (`plan`, `stage`, `swap`, `note-config`, `finish`, `recover`, `pack-check`, `pack-verify`, `pack-docs`, `sw-install`) runs in process in the target version's `sw`, with 0011's guarantees: staging and SHA-256 verification before any installed file changes, the journal and its recovery, the update lock, the store roles and gate lock. `update.sh` becomes a shim (ADR 0028) that resolves the download's version and hands over, until `native-cli-retire-scripts` removes it.
- **The journal stays format 2.** `sw update` writes the same format-2 journal, with the same fields and states, so the 0.36.0 `update.sh` can still read and recover a journal that `sw update` left. `sw update recover`, and the recovery `plan` runs first, read and recover format 1 and format 2 journals that an older `update.sh` left. A journal of any other format, or one that does not parse as a whole, is refused as `journal_unreadable` and nothing is touched.
- **The prompt drives only `sw update`, at interface 3.** `sw update interface` prints `{"ok":true,"interface":3}` and reads and writes nothing else, and `plan` reports the same number. The prompt runs `sw update interface` on the checked temporary binary before `sw-install`, recovery or any other write, and stops on another interface or a failed run. Its minimum installable release is 0.37.0, the first with `sw update`; an older tag is installed with that tag's own README prompt.
- **The agent fetches and checks the first `sw`.** For a release tag, the agent downloads the host's asset, `THIRD_PARTY_NOTICES.txt` and `SHA256SUMS` with `curl` (https only, 120 s and 64 MiB per file) and checks both files' SHA-256 with the OS's own tool. Only when both match does it make the asset executable, clear macOS quarantine and run `sw version --json`, which must report the tag's version. That binary's `sw update sw-install` downloads and checks again and places its own copy; it never moves its own running file. Every later step uses the placed binary. A `main` install builds `sw` from the clone with `mise run install-sw -- --expect-update-interface 3`, which checks the build's interface before placement.

**Rejected: an installed older `sw` fetching the new one,** because an old binary's logic would run the new install and the prompt would need two bootstrap paths. **Rejected: bootstrap scripts in POSIX sh and PowerShell,** because they are new shipped interpreter scripts, against the milestone. **Rejected: a format 3 journal,** because an older `update.sh` would refuse it as unreadable and nothing in the port needs a new field. **Rejected: keeping a `bash update.sh` path for older tags,** because bash would stay a prerequisite and the prompt would carry two flows.

## Consequences

- An install or update needs `git`, `openspec`, `curl` and the OS hash tool, and no bash or Python.
- An old interface-2 prompt run against a 0.37.0 or later tag stops before staging: the shim reports `sw_missing`, or the placed `sw` reports interface 3. The fix is the current README prompt.
- Changing the journal format, or the interface the prompt reads, is a workflow change (minor version) that must keep the older formats recoverable.
- Reversal cost: high for running the install in `sw` (the `sw update` contract binds later changes); medium for the journal format and the interface contract.
