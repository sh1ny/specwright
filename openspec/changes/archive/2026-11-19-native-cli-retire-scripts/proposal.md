# Proposal

## Why

M8's outcome is that Specwright needs neither bash nor Python for its own work (#148). Every shipped script is now a thin shim in front of `sw`, but the shims still need bash, eight of them still check for Python 3.8+, `sw-path.sh` runs `bounded.py` to check the binary, and the skills hand the agent `bash <dir>/scripts/<x>.sh` commands plus inline bash (the store gate lock). This is the last M8 change (11 of 11). It advances these M8 exit criteria:

- **No shipped skill calls a script:** no shipped skill calls a bash or Python script or gives the agent a command that needs bash syntax; the ported scripts, their shims and the `bounded.py` copies are removed; the docs list no Python or bash prerequisite for Specwright's own work.
- **No interpreter launches:** `sw` starts itself only for the bounded helper and reviewer evaluation, with black-box evals that run the ported commands with shipped scripts absent and failing `python`/`python3` first on `PATH` on Linux, Windows and macOS.
- **No shell launches:** `sw` starts no bash or sh for its own work, checked with failing `bash` and `sh` first on `PATH`.
- **Everything shipped:** all M8 changes are archived on main and their releases are published.

Every M8 criterion is agent-verified; this change checks its share in PR CI on the three platforms.

## What Changes

- **Direct entry:** skills call `sw <command> ...` with ordinary arguments. A new ADR (0040), the successor to ADR 0028, defines the entry and its UTF-8 argument contract. Arguments `sw` cannot represent are refused before any work: with the `bad_argument` document on Windows, and on Linux and macOS by the Dart runtime itself (non-zero exit, empty stdout), which `sw` cannot see past (C6). **BREAKING** for anything that calls the scripts by path.
- **Resolution without a script:** skills name `sw` as `<home>/.specwright/bin/<project VERSION>/sw[.exe]`. Every `sw` command that works on a project checks that project's `openspec/.specwright/VERSION` against its own version and stops with `sw_mismatch` when they differ. `sw-path.sh` goes.
- **Gate lock in `sw`:** the store gate lock, which `specwright-branch` and `specwright-roadmap` now describe as inline bash (`mkdir`, `printf`, `date`, `rm -r`), becomes `sw` commands with the same lock directory, owner record and refusal rules.
- **Skills, schema, agents and README:** each `bash <...>/scripts/<x>.sh` becomes `sw <command>`, including the `[vcs]` and `[as]` shorthands, and script-existence checks go. Commands that `sw` prints for the agent or the user to run (undo-archive plans, `vcs` plans, cleanup steps) name `sw` instead of a script.
- **Undo plan as steps:** `sw finish undo-archive-plan` prints an ordered list of commands (`steps`, `after_rerun_steps`) instead of a bash script; its guards and backups become `sw finish` steps. **BREAKING** for the plan's `script` field.
- **`GH_REPO`:** `sw as` and `sw pr` keep an inherited `GH_REPO` out of their `gh` calls and the fenced command, which the shims and the skills' `env -u GH_REPO` did in bash.
- **Interface 2:** `sw version --json` reports interface 2, because the command-line contract changed.
- **Reference files in the binary:** the review brief and the findings schema, which `sw` read through the shim's script directory, are built into `sw`.
- **Removed (BREAKING):** the twelve bash scripts (`vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `scripts/update.sh`), `bounded.py`, the `--args-stdin`/`--args-file` handoff, `sw`'s own MSYS path conversion and the scripts-directory and bash records.
- **Evals:** the eval runner gets its own process helper instead of loading `bounded.py`; the suites stop driving shims and call `sw` through a shared helper, and new black-box evals run the commands with no shipped scripts and with failing `python`, `python3`, `bash` and `sh` first on `PATH`.
- **Docs:** the README, CONTRIBUTING and architecture list no bash or Python prerequisite for Specwright's own work. Evals stay Python and remain a contributor-only tool.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `native-cli`: the direct entry and its argument contract, project version self-check, a name map from retired scripts to `sw` commands, embedded reference files; the script resolver requirements are removed.
- `pr-script-runtime`: shim, `sw_missing` and Python prerequisite requirements are removed or rewritten for `sw` called directly; prerequisites list no bash or Python.
- `planning-stores`: the gate lock is taken, shown and released through `sw`.
- `vcs-backends`, `github-identity`, `task-commits`, `change-finish`, `review-routes`, `releases`, `install-update`: requirements about a shim, its handoff, its `sw_missing` output or a printed script command change to `sw` called directly.
- `eval-runner`: suites call `sw` directly; script-absent and interpreter-absent evals.

## Impact

- `cli/`: new entry dispatch and refusal, version self-check, gate-lock commands, embedded references, printed commands, removal of the stdin/file handoff and MSYS conversion.
- `skills/*/SKILL.md`, `skills/*/references`, `schemas/specwright/schema.yaml`, `agents/`, `README.md`, `CONTRIBUTING.md`, `templates/`, `openspec/architecture.md`, `docs/adr/0040-*`.
- All twelve scripts and `bounded.py` deleted; `evals/` retargeted (about 96 files) and the suite map updated.
- Users: a project updated to this version calls `sw` only. A person who scripted `bash .../vcs.sh` by hand must switch to `sw vcs`. Each binary is versioned, so an older project keeps its own `sw`. When user-level skills of this version serve an older project, the skill stops before any command and says to update that project.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: How skills find and check `sw`

- **Choice:** a pinned path, `<home>/.specwright/bin/<project VERSION>/sw[.exe]`, plus a self-check. Every project command compares the project's `VERSION` with its own and stops with `sw_mismatch`.
- **Rejected:** a stable launcher on `<home>/.specwright/bin/sw` (adds a self-launch and a cross-version contract); a per-project copy of the binary (about 10 MB per project, more install writes).
- **Reversal cost:** medium
- **Important:** yes, binds future changes (the way every skill names `sw`)
- **Chosen by:** user

### S2: Where the review reference files come from

- **Choice:** build `brief.md` and `findings.schema.json` into `sw`.
- **Rejected:** a `--skill-dir` argument on every review call (one more argument for the agent to get wrong).
- **Reversal cost:** low
- **Important:** yes, changes a boundary (`sw` no longer reads skill files)
- **Chosen by:** user

### S3: The old handoff

- **Choice:** remove `--args-stdin`, `--args-file`, the scripts-directory and bash records, and `sw`'s MSYS conversion. Git Bash already converts POSIX paths when it starts a Windows executable.
- **Rejected:** keeping them as a hidden entry (dead code and two entry surfaces).
- **Reversal cost:** medium
- **Important:** yes, binds future changes (the CLI's argument contract)
- **Chosen by:** user

### S4: One change

- **Choice:** keep the roadmap's single change. Group the tasks so the evals move to `sw` before anything is deleted.
- **Rejected:** splitting into a direct-entry change and a removal change (a new roadmap entry and a branch rename).
- **Reversal cost:** low
- **Important:** yes, high reversal cost once started
- **Chosen by:** user

### S5: How specs are updated

- **Choice:** one native-cli requirement maps each retired script name to its `sw` command, so existing requirement text keeps its meaning. Only requirements whose behaviour changes get MODIFIED or REMOVED deltas. A follow-up issue tracks the wording sweep.
- **Rejected:** rewriting every requirement that names a script (about 150 deltas).
- **Reversal cost:** low
- **Important:** yes, binds future changes (how specs read)
- **Chosen by:** user

### S6: Evals and CI tools stay Python

- **Choice:** `evals/` and `cli/tool/*.py` stay Python. They are contributor and CI tools, not shipped to projects, and fall outside "Specwright's own work".
- **Rejected:** porting the eval harness to Dart (a separate project, no user-visible gain).
- **Reversal cost:** low
- **Important:** no
- **Chosen by:** agent

## Release Notes

This release finishes the move to the native `sw` binary: Specwright's own work no longer needs bash or Python. Skills run the project's `sw` directly and check it with `sw version --json` (interface 2), and every project command checks that `sw` and the project are at the same version. The shell scripts, their `sw-path.sh` resolver and `bounded.py` are gone, the store gate lock is taken through `sw`, and the undo-archive plan lists `sw` steps instead of a bash script. Projects update with the install prompt, whose check now requires interface 2.

### Changed

- Skills call `sw <command>` directly at `<home>/.specwright/bin/<VERSION>/sw`. A project command run by an `sw` of another version stops with `sw_mismatch` (#148).
- The store gate lock is taken, shown and released with `sw` commands instead of inline shell (#148).
- Commands that `sw` prints for you to run (cleanup steps) name `sw` instead of a script (#148).
- The undo-archive plan lists its commands as `steps` you can run from any shell, instead of a bash `script` (#148).
- `sw as` keeps an inherited `GH_REPO` out of the command it fences (#148).
- User-level skills of this version stop in a project still on an older version and ask you to update that project first (#148).

### Removed

- The shipped bash scripts (`vcs.sh`, `as.sh`, `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh`, `sw-path.sh`, `task-cover.sh`, `fit-subject.sh`, `finish.sh`, `review-run.sh`, `release.sh`, `scripts/update.sh`) and `bounded.py`. Call `sw` instead (#148).
- The bash and Python prerequisites for Specwright's own work (#148).
