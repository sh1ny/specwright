# Proposal

## Why

Specwright's GitHub workflows assume HTTPS, github.com, a stored `gh` account and a remote named `origin`. That blocks teams using SSH, GitHub Enterprise, token-only automation or a different remote, and ship can abort on a local planning store even when the code PR can proceed. This advances M9's adoption outcome and its push, fetch and PR exit criterion, with Linux, Windows and macOS CI coverage.

## What Changes

- Add `github.host` (default `github.com`) for repository identity, fenced HTTPS authentication, PR operations and GitHub releases on GitHub Enterprise (#167).
- Add `github.fence` (default `true`). Explicitly setting it to `false` uses the caller's Git and `gh` credentials, including SSH keys or environment tokens without a stored `gh` account. Keep the existing default protection and document the credentials and trust tradeoff (#167).
- Add `remote` and `planning_store.remote` (each default `origin`). Select one remote per repository for fetch, push, pull, PR identity and release operations; keep the mismatched-repository refusal and do not add cross-repository PRs (#168).
- Limit #260 to ship: work out expected PRs first, open the code PR when expected, and say to share the local planning branch by hand. Do not validate for publication, push, open or watch a PR for that store. In the PR workflow, watch, feedback and finish hand the store back for manual sharing and archiving instead of automating its part.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-identity`: configured GitHub host, opt-in ambient credentials and unchanged default fencing.
- `vcs-backends`: select and use the configured remote for network operations.
- `planning-stores`: select the store remote and ship only the expected PRs, including a code PR beside a local-only store.
- `releases`: use the selected code remote for tag operations and the configured GitHub host for releases.
- `native-cli`: select the code project's connection settings without switching the repository a command acts on.
- `pr-script-runtime`: bind snapshot and reply targeting to that host, including store-started commands.

## Impact

- `sw as`, VCS operations, PR identity and workflows, and release publication; skills that call those commands.
- Settings template, README, architecture decision record and cross-platform coverage.
- Target version: 0.41.0, a minor bump for new workflow settings.
- Branch gate: the pinned `sw` was bootstrapped locally; the existing feature branch was clean and exactly at the current remote default-branch tip. The linked-worktree gate was checked by hand because it refuses a non-main checkout (#258).

## Decision Making

DECISION_MAKING: important
- **Source:** setting

### S1: Keep the fence by default

- **Choice:** Keep process-scoped fencing by default; support a configured GitHub host and let projects opt in to ambient credentials for SSH and token-only automation.
- **Rejected:** Drop the fence by default or make Enterprise users change their remote transport to get past host detection.
- **Reversal cost:** high; the defaults bind authentication and deployment settings.
- **Important:** yes; changes user-facing settings and an authentication boundary.
- **Chosen by:** user

### S2: One remote per repository

- **Choice:** Select one remote per repository, keep fetch/push identity checks and leave cross-repository PRs out of scope.
- **Rejected:** Add separate PR head and base repositories in this change; that would extend discovery, creation, watch and cleanup beyond remote selection.
- **Reversal cost:** medium; the settings define the target for multiple commands.
- **Important:** yes; binds user-facing settings and the PR targeting contract.
- **Chosen by:** user

### S3: Keep the local-store fix in ship only

- **Choice:** In the round 4 checkpoint the owner chose “Cut #260 to ship only”. Ship computes the expected set first and opens the code PR when expected. It excludes the local store from publication and reports the branch to share by hand. Watch, feedback rounds and PR finish stop the store's part and report manual sharing and archiving; they do not count local store rounds, automate its archive or recover its archive on restart.
- **Rejected:** Require a store remote or a manual code PR; extend watch and feedback to derive local evidence and automate local archive and recovery.
- **Reversal cost:** medium; pushing and opening the code PR are separate from ready-to-merge and archive decisions.
- **Important:** yes; changes which operations publish or require manual work.
- **Chosen by:** user

### S4: Keep the code identity requirement for store PRs

- **Choice:** Require a usable code GitHub identity before opening a store PR, even for a planning-only change. A proven fully local change still reports no PR and manual sharing.
- **Rejected:** Open a store PR without a code GitHub identity and add a separate identity/resumption model for feedback passes.
- **Reversal cost:** medium; feedback records and PR adoption depend on a code identity.
- **Important:** yes; defines the supported store-backed publication states.
- **Chosen by:** user

## Release Notes

Use Specwright with SSH, GitHub Enterprise, token-only automation and a remote name other than `origin`, while keeping process-scoped GitHub identity fencing on by default. Ship can open the code PR even when planning stays local.

### Added

- Configure `github.host` for GitHub Enterprise and opt out of identity fencing with `github.fence: false` when SSH or environment tokens supply credentials (#167).
- Choose a named remote per code repository and planning store (#168).

### Changed

- `sw pr snapshot` and `sw pr reply` default to the selected remote. Reply checks that the item belongs to the selected PR; `sw pr policy` requires its PR coordinates.
- `sw release prove-main` binds the fetched main commit to the publication destination. Pass its receipt-backed `--proof` to `untagged` and `publish`.

### Fixed

- A local-only planning store no longer blocks the code PR; ship reports that the planning branch must be shared by hand (#260).
