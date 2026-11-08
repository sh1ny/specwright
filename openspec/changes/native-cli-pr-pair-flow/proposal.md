# Proposal

## Why

M8, Complete the native CLI migration (#148), now requires direct calls between ported Specwright operations. Fourteen `pr-pair.sh` commands still run embedded Python. This change ports that remaining workflow and establishes the native fence and VCS integration that the following `native-cli-internal-calls` retrofit will use.

It advances M8's agent-verified PR-operation parity, direct-call and credential/deadline exit criteria. Existing black-box evals and differential cases against the frozen script will verify results, GitHub effects and persisted state on Linux, Windows and macOS. Full script and interpreter removal is judged after the later M8 changes; this change has no user-verified exit criterion.

## What Changes

- Add native implementations of `discover`, `expected`, `ensure-pr`, `closing-check`, `closed-check`, `link`, `pair-state`, `rounds`, `pass`, `cleanup-plan`, `branch-check`, `merge`, `delete-remote` and `item-issues`. `pass` includes write, plan, done and adopt.
- Replace `pr-pair.sh`'s remaining embedded Python with an ADR 0028 shim. Keep its path, arguments, JSON fields, error codes, exit statuses and persisted formats. With a matching `sw`, missing or unknown commands still produce the existing usage response. The fourteen newly ported commands now require that matching binary; resolution failure returns `sw_missing`, never a Python fallback.
- Call existing native settings, fence and VCS operations directly. Preserve the caller's deadline boundaries, target checkout, argument bytes and credential scope. The PR flow's bounded fenced reads share their existing budget through identity checks and execution; VCS state and planning calls retain their current unbounded behavior.
- Add the optional leading `--project <code-checkout>` prefix to `pr-pair.sh` and `as.sh`. It chooses only the project's exact-version binary; the command still starts in the caller's working directory. Update store callers and printed cleanup commands to pass it explicitly, including through the retained nested VCS fence hop.
- Keep feedback-record names, version 2 contents, ownership, legacy migration, exclusive publication, locks and recovery behavior. Keep mutation/read-back sequencing, including one merge attempt and guarded branch deletion.
- Extend the frozen-oracle differential coverage to all fourteen commands, including side effects, records and failures. Preserve assertions except free text after stable prefixes, existing format-2 reviewer-config normalization, the intended matching-binary requirement for formerly unported/invalid calls, and the approved project-selector prefix in printed commands. Check every other command-array argument and working directory exactly.
- Record the direct-call and intentional isolation rule in a new ADR during apply. Retain the reviewed M8 roadmap amendment in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-script-runtime`: complete native `pr-pair.sh` dispatch; matching-binary refusal, workflow parity, feedback-record interoperability and direct native fence/VCS calls with the existing bounds.
- `github-identity`: explicit binary-project selection for store-started fence calls, preserving the caller's target directory and authentication rules.

## Impact

Changes will affect `cli/lib/src/commands/pr.dart`, native PR modules under `cli/lib/src/pr/`, the reusable fence boundary under `cli/lib/src/fence/`, VCS integration, the `pr-pair.sh` and `as.sh` shims, store-caller instructions, relevant PR/VCS evals and native unit tests. Apply will add ADR 0031, update the architecture and bump to 0.30.0. The oracle stays test-only, and no new runtime dependency is planned.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Finish the fourteen workflow commands together

- **Choice:** Port the fourteen commands listed in M8 change 3, with all four pass operations and their recovery behavior.
- **Rejected:** Split or reorder M8 again; the user has approved this boundary and the following retrofit and launcher changes.
- **Reversal cost:** low
- **Important:** yes, binds the scope of later M8 changes.
- **Chosen by:** user, through the approved M8 amendment and request to continue this change.

### S2: Preserve program-readable behavior

- **Choice:** Keep field names and values, statuses, stored formats and effects exact. Free messages may be reworded after stable prefixes. Retain discovered defects for parity and track them separately unless they prevent parity on a CI platform.
- **Rejected:** Fix unrelated behavior during the port or reproduce incidental Python exception wording.
- **Reversal cost:** low
- **Important:** yes, changes the acceptance contract for this migration.
- **Chosen by:** user, carrying forward the recorded M8 choice "Fields exact, messages free".

### S3: Keep later M8 work separate

- **Choice:** This change establishes direct integrations for its own callers. Retrofitting earlier ports, removing Bash transport, porting review/release/update and retiring script callers remain in their named roadmap changes.
- **Rejected:** Expand this PR to remove every runtime and wrapper at once.
- **Reversal cost:** low
- **Important:** yes, binds the remaining milestone boundaries.
- **Chosen by:** user, through the approved M8 amendment.

### S4: Explicit binary project with store working directory preserved

- **Choice:** Add a leading `--project <code-checkout>` selector to the two shims. Update store callers and emitted cleanup commands to name the code project without moving execution out of the store. The VCS fetch-main fence hop remains until the next retrofit and receives the explicit selector when needed.
- **Rejected:** Infer a code project from a shared store, or move every store command into the code checkout. A store can serve several projects; changing cwd changes what the fence checks.
- **Reversal cost:** medium
- **Important:** yes, changes a shared command interface and printed cleanup commands.
- **Chosen by:** user, "Add an explicit --project <code-checkout> prefix to the pr-pair and as shims; preserve the store working directory" and "Keep that existing nested path until the next retrofit; document and test the temporary exception".

## Release Notes

0.30.0 moves the remaining fourteen PR workflow commands into `sw`, preserving their JSON, exit codes, feedback records and recovery behavior. The PR workflow calls native settings, fence and VCS operations directly. The script remains a compatibility shim and now requires the matching installed `sw` for every command.

### Changed

- The fourteen remaining `pr-pair.sh` workflow commands run in `sw`, with direct native calls and preserved identity, deadline and recovery boundaries. Every command now refuses with `sw_missing` when the matching binary is unavailable (#148).
- M8 adds an internal-call retrofit and a native launcher before the remaining ports, and explicitly covers Bash-free bootstrap and inline skill commands (#148).
- `as.sh` and `pr-pair.sh` accept a leading `--project <code-checkout>` for store-started calls. Updated store callers and cleanup plans select the code project's binary while preserving the store working directory (#148).
- Native fenced workflow reads use private per-login environments and one caller-owned budget through identity checks and execution; standalone unbounded fence calls retain their existing behavior (#148).
- Discovery, expected PR sets, creation, linking, pair state and feedback-round decisions preserve paginated reads, per-repository credentials and unknown-read mutation guards (#148).

### Removed

- The remaining embedded Python implementation in `pr-pair.sh`; Bash and Python prerequisites remain until later M8 changes remove their remaining uses (#148).
