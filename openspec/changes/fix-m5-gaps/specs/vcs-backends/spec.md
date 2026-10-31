# Spec Delta

## ADDED Requirements

### Requirement: On GitButler Specwright's scripts run from outside the work tree
With `vcs: gitbutler`, every `vcs.sh` subcommand SHALL stop with `scripts_in_workspace` before any `but` command or write when its own scripts directory lies inside the code work tree, or a Specwright skill or agent copy (`specwright-*` under `.claude/skills`, `.agents/skills`, `.claude/agents`, `.omp/agents`) exists there. The message SHALL name each path, say to install outside the repo, and say to remove committed copies by hand through GitButler. Git and jj are unaffected.

#### Scenario: Skills installed in the repo
- **WHEN** `vcs` is `gitbutler` and `vcs.sh state` runs from `<repo>/.claude/skills/specwright-pr/scripts/`
- **THEN** it exits 1 with `error: scripts_in_workspace` naming that directory, and no `but` command ran

#### Scenario: Skills installed at user level
- **WHEN** `vcs` is `gitbutler`, `vcs.sh` runs from a directory outside the repo and the work tree holds no `specwright-*` skill or agent copy
- **THEN** the probe continues as before

#### Scenario: A sibling branch adds a skill copy
- **WHEN** `vcs` is `gitbutler`, `vcs.sh` runs from outside the repo, and an applied sibling branch has added `.claude/skills/specwright-pr/`
- **THEN** it exits 1 with `scripts_in_workspace` naming `.claude/skills/specwright-pr`, and no `but` command ran

#### Scenario: Git project with in-repo skills
- **WHEN** `vcs` is `git` and `vcs.sh` runs from `<repo>/.claude/skills/specwright-pr/scripts/`
- **THEN** it runs as before

### Requirement: On GitButler the settings are those the change branch committed
With `vcs: gitbutler`, the settings SHALL be read only from `pr-pair.sh context --branch <b>` right before each use (each `pr.validate` run, the merge settings), and `vcs.sh push` SHALL check again. Each SHALL stop with `settings_not_pinned` when the work-tree `openspec/specwright.yaml` differs from the file at the tip of `<b>` (after the merge, with `--after-merge`: that tip while `<b>` exists, else GitButler's target ref), or exists on one side only. Branch reads and commits are not pinned.

#### Scenario: Unassigned edit before ship
- **WHEN** the change branch `feat/add-c` has the settings committed, an unassigned work-tree edit changes `pr.validate`, and ship runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned` naming the file, no validate command runs, and ship does not push

#### Scenario: Watch reads merge settings
- **WHEN** an unassigned edit changes `pr.merge` and watch runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`, and no merge setting is reported

#### Scenario: Push with an unpinned edit
- **WHEN** an unassigned edit of the settings exists and `vcs.sh push --branch feat/add-c` runs
- **THEN** it exits 1 with `settings_not_pinned`, and nothing is pushed

#### Scenario: Context without the branch
- **WHEN** `vcs` is `gitbutler` and `pr-pair.sh context` runs for the merge settings without `--branch`
- **THEN** it exits 2 with a usage error naming `--branch`, and no merge setting is reported

#### Scenario: Feedback or CI fix push in a repo-local project
- **WHEN** a repo-local GitButler project's feedback pass (or watch's CI fix) is about to run `pr.validate` before its push, and an unassigned edit changed `pr.validate`
- **THEN** the skill reads `validate` from `pr-pair.sh context --branch feat/add-c`, which exits 1 with `settings_not_pinned`, and the edited validate command never runs

#### Scenario: Cleanup after the merge
- **WHEN** the PR of `feat/add-c` merged, cleanup has pulled, the local branch is gone, and the work-tree settings equal the file at GitButler's target ref
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` reports `merge` and `delete_branch`, and the remote-branch deletion follows them

#### Scenario: Cleanup with an unpinned edit
- **WHEN** after the merge an unassigned edit sets `delete_branch: true` that the target ref does not have
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` exits 1 with `settings_not_pinned`, and no remote branch is deleted

#### Scenario: Cleanup after a skipped pull
- **WHEN** `feat/add-c` committed an edit of `openspec/specwright.yaml` and its PR merged, another branch is applied, `vcs.sh pull --branch feat/add-c` returned `pull_skipped`, and `delete-branch` returned `left_applied`
- **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` reports `merge` and `delete_branch` with no `settings_not_pinned` stop, and the remote-branch deletion follows them

#### Scenario: Settings never committed on the branch
- **WHEN** `openspec/specwright.yaml` exists in the work tree but not at the tip of `feat/add-c`, and ship runs `pr-pair.sh context --branch feat/add-c`
- **THEN** it exits 1 with `settings_not_pinned`

#### Scenario: The change commits its own settings edit
- **WHEN** a task of `feat/add-c` edits `openspec/specwright.yaml` and `specwright-commit` runs `vcs.sh state --branch feat/add-c` and `vcs.sh commit --branch feat/add-c -- openspec/specwright.yaml`
- **THEN** neither stops with `settings_not_pinned`, the edit is committed on `feat/add-c`, and a following `context --branch feat/add-c` passes

#### Scenario: Branch already deleted
- **WHEN** finish cleanup or a gate rollback runs `vcs.sh state --branch feat/add-c` after the branch was deleted
- **THEN** it reports the branch as gone, as before, with no `settings_not_pinned` stop

#### Scenario: Pinned settings
- **WHEN** the work-tree settings equal the file at the tip of `feat/add-c`
- **THEN** `push` and `context --branch` run as before

#### Scenario: Git backend
- **WHEN** `vcs` is `git` and the settings file has an uncommitted edit
- **THEN** no `settings_not_pinned` stop is raised
