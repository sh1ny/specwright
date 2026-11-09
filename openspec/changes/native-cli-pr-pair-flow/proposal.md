# Proposal

## Why

M8, Complete the native CLI migration (#148), now requires direct calls between ported Specwright operations. Fourteen `pr-pair.sh` commands still run embedded Python. This change ports that remaining workflow and establishes the native fence and VCS integration that the following `native-cli-internal-calls` retrofit will use.

It advances M8's agent-verified PR-operation parity, direct-call and credential/deadline exit criteria. Existing black-box evals and differential cases against the frozen script will verify results, GitHub effects and persisted state on Linux, Windows and macOS. Full script and interpreter removal is judged after the later M8 changes; this change has no user-verified exit criterion.

## What Changes

- Add native implementations of `discover`, `expected`, `ensure-pr`, `closing-check`, `closed-check`, `link`, `pair-state`, `rounds`, `pass`, `cleanup-plan`, `branch-check`, `merge`, `delete-remote` and `item-issues`. `pass` includes write, plan, done and adopt.
- Replace `pr-pair.sh`'s remaining embedded Python with an ADR 0028 shim. Keep its path and arguments. Keep JSON fields, error codes and exit statuses unless S2's documented coordinated producer/consumer change applies, and keep persisted records interoperable. With a matching `sw`, missing or unknown commands still produce the existing usage response. The fourteen newly ported commands now require that matching binary; resolution failure returns `sw_missing`, never a Python fallback.
- Call existing native settings, fence and VCS operations directly. Preserve the caller's deadline boundaries, target checkout, argument bytes and credential scope. The PR flow's bounded fenced reads share their existing budget through identity checks and execution; VCS state and planning calls retain their current unbounded behavior.
- Add the optional leading `--project <code-checkout>` prefix to `pr-pair.sh` and `as.sh`. It chooses only the project's exact-version binary; the command still starts in the caller's working directory. Update store callers and printed cleanup commands to pass it explicitly, including through the retained nested VCS fence hop.
- Keep feedback-record names, version 2 contents, ownership, legacy migration, exclusive publication and recovery behavior. Use the owner-approved SDK-exclusive lock files at the existing `.lock` path, respecting legacy directory locks, and SDK-exclusive publication fallback with documented empty/partial-record interruption recovery. Keep mutation/read-back sequencing, including one merge attempt and guarded branch deletion.
- Preserve raw POSIX feedback-directory environment values with the approved small reader using existing `ffi` and the path codec. Explicitly injected environments remain authoritative; no new package or credential-environment change is introduced.
- Extend differential and product-workflow coverage to all fourteen commands, including side effects, records and failures. The frozen oracle is evidence of the existing workflow, not a requirement to reproduce incidental Python formatting or parser quirks. Producer and consuming skills may change together when explicit contract tests prove the same workflow outcomes, safety and recovery. Record each such change and its consumer coverage rather than silently removing assertions.
- Record the direct-call and intentional isolation rule in a new ADR during apply. Retain the reviewed M8 roadmap amendment in this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-script-runtime`: complete native `pr-pair.sh` dispatch; matching-binary refusal, workflow parity, feedback-record interoperability and direct native fence/VCS calls with the existing bounds.
- `github-identity`: explicit binary-project selection for store-started fence calls, preserving the caller's target directory and authentication rules.
- `native-cli`: release and install the third-party notice file alongside binaries, preserving checksum verification, immutable release seals and installation of older releases.
- `feedback-passes`: an occupied `.lock` path may be a native lock file or a legacy lock directory; both remain `record_busy` and are never removed automatically.

## Impact

Changes will affect `cli/lib/src/commands/pr.dart`, native PR modules under `cli/lib/src/pr/`, the reusable fence boundary under `cli/lib/src/fence/`, VCS integration, the `pr-pair.sh` and `as.sh` shims, store-caller instructions, relevant PR/VCS evals and native unit tests. Apply will add ADRs 0031 and 0032, update the architecture and bump to 0.30.0. Packaging also affects `.github/workflows/sw-build.yml`, `cli/tool/attach_release.py`, `scripts/update.sh`, `scripts/install-sw.sh` and `cli/THIRD_PARTY_NOTICES.txt`. The oracle stays test-only. The user approved the Dart `html` parser package, subject to licence, build-hook and workflow checks; it compiles into `sw` and adds no separately installed runtime. Other package-adoption decisions require the user's approval.

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Finish the fourteen workflow commands together

- **Choice:** Port the fourteen commands listed in M8 change 3, with all four pass operations and their recovery behavior.
- **Rejected:** Split or reorder M8 again; the user has approved this boundary and the following retrofit and launcher changes.
- **Reversal cost:** low
- **Important:** yes, binds the scope of later M8 changes.
- **Chosen by:** user, through the approved M8 amendment and request to continue this change.

### S2: Preserve the product workflow across coordinated producer and consumer changes

- **Choice:** Preserve overall PR workflow outcomes, identity checks, mutation guards, deadlines, ownership and recovery. We control the scripts/CLI and their consuming skills, so incidental formatting, parser quirks and custom compatibility behavior need not be reproduced byte for byte. Change producers and consumers together with explicit workflow tests when that removes unnecessary custom code. Existing persisted records must remain usable for interrupted-pass recovery. Keep existing interfaces unless a concrete coordinated simplification is documented; this is not permission for unrelated rewrites or unapproved library adoption.
- **Rejected:** Treat every Python quirk or serialized byte as a product requirement, or change a producer without its consumers and workflow tests.
- **Reversal cost:** low
- **Important:** yes, changes the acceptance contract for this migration.
- **Chosen by:** user, superseding the earlier "Fields exact, messages free" choice: "we control both sides - the scripts/cli and the skills" and "the same behavior of the overall product, NOT byte for byte replica".

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

0.30.0 moves all fourteen remaining PR workflow commands and all four feedback-pass operations into `sw`, preserving identity, deadlines, ownership and recovery. Store callers select the code project's exact-version binary without changing their working directory. Closing checks use HTML5 interpretation, feedback paths preserve raw POSIX environment bytes, and binary distributions carry verified third-party notices. Bash/Python probes, the non-Git fetch fence hop and documented context/snapshot store limits remain for later M8 work.

### Changed

- The fourteen remaining `pr-pair.sh` workflow commands run in `sw`, with direct native calls and preserved identity, deadline and recovery boundaries. Every command now refuses with `sw_missing` when the matching binary is unavailable (#148).
- M8 adds an internal-call retrofit and a native launcher before the remaining ports, and explicitly covers Bash-free bootstrap and inline skill commands (#148).
- `as.sh` and `pr-pair.sh` accept a leading `--project <code-checkout>` for store-started calls. Updated store callers and cleanup plans select the code project's binary while preserving the store working directory (#148).
- Native fenced workflow reads use private per-login environments and one caller-owned budget through identity checks and execution; standalone unbounded fence calls retain their existing behavior (#148).
- Discovery, expected PR sets, creation, linking, pair state and feedback-round decisions preserve paginated reads, per-repository credentials and unknown-read mutation guards (#148).
- Closing checks use the approved HTML5 parser; merge read-back, guarded remote deletion and issue-marker lookup preserve workflow decisions (#148).
- Feedback locks use exclusive file creation while respecting legacy directory locks; interrupted records retain the existing ownership and recovery decisions (#148).
- Native feedback passes preserve owner handover and evidence-based completion across interrupted work. Direct record paths retain raw POSIX environment bytes, with the existing context and snapshot limits recorded (#148).
- Cleanup plans preserve target directories and guarded branch deletion. The retained non-Git branch check selects the code project's binary for its fenced fetch (#148).
- Releases from 0.30.0 include a checksummed third-party notice file, installed alongside `sw` without a new CLI command (#148).

### Removed

- The remaining embedded Python implementation in `pr-pair.sh`. All nineteen entry points and invalid-call usage use native dispatch; Bash and Python prerequisite probes remain until later M8 changes remove their remaining uses (#148).
