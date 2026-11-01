# Spec Delta

## ADDED Requirements

### Requirement: A GitButler project takes no in-repo skill or agent target
When the installed `openspec/specwright.yaml` selects `vcs: gitbutler`, `update.sh plan` (and `stage`, which runs it first) SHALL refuse, before any write, each `--skills` or `--agents` directory inside the code work tree: exit 1, error `refused`, a `target_in_workspace` refusal naming it. The install prompt SHALL offer only user-level targets with `vcs: gitbutler`. Other projects keep in-repo targets.

#### Scenario: In-repo target for a GitButler project
- **WHEN** `update.sh plan` runs with `--skills <code>/.claude/skills` and `<code>/openspec/specwright.yaml` has `vcs: gitbutler`
- **THEN** it exits 1 with error `refused` and a `target_in_workspace` refusal naming `<code>/.claude/skills`, and no file outside the plan's scratch directory is written

#### Scenario: User-level target
- **WHEN** the same project's update names `--skills ~/.claude/skills`
- **THEN** the plan has no `target_in_workspace` refusal

#### Scenario: Git project
- **WHEN** `vcs` is `git` and the target is `<code>/.claude/skills`
- **THEN** the plan has no `target_in_workspace` refusal

#### Scenario: Fresh install with no settings yet
- **WHEN** `<code>/openspec/specwright.yaml` does not exist and the target is `<code>/.claude/skills`
- **THEN** the plan has no `target_in_workspace` refusal, and the README install prompt's GitButler choice says the targets must be outside the repo
