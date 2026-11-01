# 0021. Installed skills are the user's to manage

- Status: accepted
- Date: 2026-11-01
- Supersedes: 0019 (its user-level install decision and the install part of its binding clause; the settings decision, and the binding that later GitButler features act on the settings only when they equal the change branch's committed copy, stay in force)

## Context

ADR 0019 made every GitButler project install Specwright's skills, agents and scripts at user level. `vcs.sh` stopped with `scripts_in_workspace` when they were in the work tree, and `update.sh plan` refused an in-repo target with `target_in_workspace`. The aim was to stop a sibling branch from changing Specwright's scripts in the shared work tree.

The guard cost more than it protected. A user-level install is one per machine: every project runs the same Specwright version, an update from one project updates them all, and every project's agent sees the skills. Pack skills in a shared user-level folder cannot be owned per project, so packs would have to be refused in every GitButler project. And the guard closed one path of many: the shared work tree already runs code from every applied branch through `pr.validate`, and a sibling branch's agent has the same `gh` and Git access without touching `vcs.sh`.

## Decision

- Specwright installs its skills and agents into the directories the user chooses, in the repo or at user level, on every backend. `scripts_in_workspace` and `target_in_workspace` are removed.
- After the install, keeping the skills consistent across branches, worktrees and a shared GitButler work tree is the user's responsibility: an edit on one branch, a stale copy on another, or a sibling branch's change.
- Specwright warns where the risk is chosen, in the install prompt and the README, and never refuses to run because of where or how the skills are installed. The branch gate loads GitButler's own skill without comparing an in-repo copy with main.
- Settings pinning stays: ADR 0019's `settings_not_pinned` decision and its binding for later GitButler features are unchanged.

## Consequences

GitButler projects can install in the repo, per project and per branch, and can use packs. A user-level install stays available for anyone who wants the old isolation; it is shared by every project on the machine.

In Claude Code a user-level skill overrides the in-repo skill of the same name in every project (personal over project), while agents resolve project over user. For Claude Code users the skills' location is in effect a per-machine choice, and a mixed install runs the user-level skills. Moving a project from user level to in repo means updating the user-level copies to 0.14.0 or later, or removing them once no other project on the machine uses them, and restarting agent sessions. An older user-level `vcs.sh` stops every call with `scripts_in_workspace` once in-repo copies exist; that message is the symptom. Specwright detects none of this.

A sibling branch that changes in-repo skills on GitButler changes them for every applied branch. This is accepted. Reversal cost: low; the removed checks are in Git history.
