# 0019. A GitButler workspace runs only the user-level Specwright install and the branch's committed settings

- Status: accepted
- Date: 2026-11-01
- Adds to: 0018 (does not supersede it)

## Context

ADR 0018 lets GitButler apply several branches in one shared work tree. Every applied branch can change files there. Two kinds of files in that tree steer what runs with the developer's GitHub and merge authority. The first is Specwright's own skills, agents and scripts, when they are installed inside the repository. A sibling branch can replace them, and the replaced scripts never call the real `vcs.sh`. The second is `openspec/specwright.yaml`, which sets `validate`, `merge`, `delete_branch` and the account. An edit to it that the change branch has not committed is read by every script, and the existing sibling check in `vcs.sh` never compares against the work tree. Issues #150 and #151 report these two gaps.

## Decision

- **User-level install only:** under `vcs: gitbutler`, `probe_gitbutler` stops with `scripts_in_workspace` before any `but` command when the directory of `vcs.sh` lies under the repository root. It also stops when the work tree holds `.claude/skills/specwright-*`, `.agents/skills/specwright-*`, `.claude/agents/specwright-*.md` or `.omp/agents/specwright-*.md`. The message names each path, says to install at user level, and says to remove committed copies by hand through GitButler.
- **Update refuses in-repo targets:** `update.sh plan` reads `<code>/openspec/specwright.yaml`. When it selects `vcs: gitbutler`, a `--skills` or `--agents` target under the code toplevel is refused with `target_in_workspace`.
- **Settings equal the branch's committed copy:** `pr-pair.sh` owns one comparison. It hashes the work-tree `openspec/specwright.yaml` with `git hash-object --path`, which applies the repository's filters, and compares it with the blob at the tip of `refs/heads/<branch>`. A difference, or a file on one side only, stops with `settings_not_pinned`.
- **Where it runs:** before each `pr.validate` run, read through `pr-pair.sh context --branch`; wherever the merge settings are read while the branch exists; and in `vcs.sh push`, before `but push`. After the merge, cleanup reads them through `context --after-merge --branch`. That compares against the branch tip while the branch still exists, and against GitButler's target ref otherwise. On GitButler, a read of the merge settings without `--branch` is a usage error.
- **Where it does not run:** `state --branch`, `commit`, `delete-branch` and the gate's `--only repos` read. The change can commit its own settings edit, and rollback and cleanup still see a deleted branch as gone.
- **Binding for later features:** every later GitButler feature runs Specwright's skills, agents and scripts only from outside the work tree, and acts on the settings only when they equal the change branch's committed copy.

## Consequences

GitButler users with an in-repo install must reinstall at user level and remove the copies. Git and jj are untouched. GitButler support is one release old, so few installs are affected. The README install prompt and the `specwright-branch` text say the same.

Residual risk: the OpenSpec schema, its templates and `openspec/config.yaml` stay in the work tree of a repo-local project, and the agent follows their text. They are not checked, because OpenSpec reads them and not Specwright's scripts. A sibling branch could change them. A store-backed project keeps them in the store and is not exposed. Isolating each change in a `but worktree` would close this gap. It stays out of scope here and needs a new decision. Reversal cost: medium, for the same reason as 0018.
