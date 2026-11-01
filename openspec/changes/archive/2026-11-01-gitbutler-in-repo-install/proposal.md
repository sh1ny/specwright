# Proposal

## Why

ADR 0019 (0.12.3, #150) made every GitButler project install Specwright's skills, agents and scripts at user level. `vcs.sh` refuses to run when they are in the work tree (`scripts_in_workspace`) and `update.sh plan` refuses an in-repo target (`target_in_workspace`). The aim was to stop a sibling branch from changing Specwright's scripts in the shared work tree. That guard costs too much for what it protects:

- A user-level install is one install per machine. Every project runs the same Specwright version, an update in one project updates them all, and the agent in every project sees the skills. The README states none of this.
- `pack-mechanism` (#68) would have to refuse packs in every GitButler project (`packs_user_level`), because pack skills in a shared user-level folder cannot be owned per project.
- It protects little. The shared work tree already runs code from every applied branch: `pr.validate` runs the project's tests and build scripts from it, and a sibling branch's agent has the same `gh` and git access without touching `vcs.sh`.

How installed skills are managed after the install is the user's responsibility: an edit on one branch, a stale copy on another, or a sibling branch's change in a GitButler workspace. Specwright delivers the skills into the folders the user chose and warns about these risks. It does not refuse to run because of them.

This is change 4 of milestone M6 (Packs), ahead of `pack-mechanism`, so that GitButler projects with an in-repo install can use packs. It advances the M6 exit criterion that each change ships as its own release.

## What Changes

- **In-repo install allowed on GitButler.** `vcs.sh` no longer stops with `scripts_in_workspace`, and `update.sh plan` no longer refuses an in-repo `--skills` or `--agents` directory with `target_in_workspace`. Both refusal codes are removed. **BREAKING** only for tooling that matched these codes; no install that works today stops working.
- **User-level install stays an option.** The install prompt offers in-repo and user-level targets on every backend. With `vcs: gitbutler` it says, as a warning, that every applied branch shares the work tree, so a branch that changes the installed skills changes them for every other applied branch too.
- **Settings pinning is kept.** `settings_not_pinned` (`pr-pair.sh` and `vcs.sh push`) is unchanged: it is cheap and costs no feature.
- **GitButler's own skill loads like any other.** The branch gate stops checking whether an in-repo copy of GitButler's skill differs from main before loading it. It still notes a missing or outdated skill.
- **The README documents both install locations.** A "Where the skills live" note in the install section covers in-repo and user-level installs:
  - an in-repo install is per project and per branch, and keeping it consistent across branches is the user's job;
  - a user-level install is one per machine: one Specwright version for every project, an update in one project updates all, and every project's agent sees the skills;
  - on GitButler, OpenSpec's own `openspec-*` skills and `/opsx:*` commands are always in the repo (`openspec init` has no user-level option).
- **A new ADR 0021 supersedes ADR 0019's install half.** ADR 0019 stays as written, since accepted ADRs are immutable; its settings half stays in force, and the architecture index marks its install half as superseded by 0021. The ADR records the principle that managing installed skills is the user's responsibility: warn, never refuse.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `vcs-backends`: removes "On GitButler Specwright's scripts run from outside the work tree" and adds that an in-repo install runs under `vcs: gitbutler`.
- `install-update`: removes "A GitButler project takes no in-repo skill or agent target" and adds that the install prompt offers both locations, with a warning on GitButler.

## Impact

- `skills/specwright-pr/scripts/vcs.sh`: `workspace_install`, `WORKSPACE_COPIES` and the refusal in `probe_gitbutler` are removed.
- `scripts/update.sh`: `workspace_targets`, its call in plan, and the header comment are removed. The update-script interface is unchanged; refusal codes are not part of it.
- `skills/specwright-branch/SKILL.md`: the GitButler tool guidance paragraph is rewritten, and `scripts_in_workspace` leaves step 1's error list.
- `README.md`: install prompt Step 2's GitButler bullet, Step 6's GitButler skill offer ("user level on this backend"), the GitButler section, and the new "Where the skills live" note.
- `docs/adr/0021-*.md` (new) and `openspec/architecture.md`: the decision table (rows 0019 and 0021) and the `vcs.sh` and install prompt rows.
- Evals:
  - `evals/vcs/test_gitbutler_probe.py`, `evals/update/test_update.py` and `evals/git-workflow/test_instructions.py` invert their user-level assertions.
  - `test_branch_gate_loads_only_an_unchanged_repo_copy` is replaced.
- `openspec/roadmap.md`: this change becomes M6 change 4 (0.14.0), `pack-mechanism` moves to 0.15.0 and `gamedev-pack` to 0.16.0.
- Version bump to 0.14.0.

## Release Notes

GitButler projects can install Specwright's skills and agents in the repo again, so each project keeps its own Specwright version and, from the next release, its own packs. A user-level install is an option on every backend, and the install prompt and a new README note explain what each location shares, how Claude Code picks between them, and how to move a project to an in-repo install. Managing installed skills is the user's responsibility (ADR 0021): Specwright warns and no longer refuses. GitButler settings pinning is unchanged.

### Changed

- With `vcs: gitbutler`, `vcs.sh` runs from an in-repo install, and `update.sh plan` accepts in-repo `--skills` and `--agents` targets. The install prompt offers both locations and warns that applied branches share the work tree. ADR 0021 supersedes the install half of ADR 0019 (#150).
- The branch gate loads GitButler's own skill without first comparing an in-repo copy with main (#150).

### Removed

- The `scripts_in_workspace` (`vcs.sh`) and `target_in_workspace` (`update.sh plan`) refusals (#150).
