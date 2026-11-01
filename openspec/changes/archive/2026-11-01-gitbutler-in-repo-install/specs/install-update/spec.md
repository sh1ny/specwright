# Spec Delta

## REMOVED Requirements

### Requirement: A GitButler project takes no in-repo skill or agent target
**Reason**: Where the skills go and how they are kept consistent across branches is the user's choice and responsibility. Refusing in-repo targets forced a machine-wide install on GitButler projects, sharing one Specwright version across every project and blocking per-project packs.
**Migration**: None needed. Existing user-level installs keep working; rerunning the install prompt may now choose an in-repo target instead.

## ADDED Requirements

### Requirement: Every backend takes in-repo and user-level targets
`update.sh plan` SHALL accept a `--skills` or `--agents` directory inside or outside the code work tree, whatever `vcs` selects. The install prompt SHALL offer both locations on every backend. With `vcs: gitbutler` it SHALL warn before the user chooses that every applied branch shares the work tree, so a branch that changes in-repo skills changes them for every applied branch.

#### Scenario: In-repo target for a GitButler project
- **WHEN** `update.sh plan` runs with `--skills <code>/.claude/skills` and `<code>/openspec/specwright.yaml` has `vcs: gitbutler`
- **THEN** `plan` and `stage` each exit 0 with no refusal naming that directory, and `stage` stages the skills for that directory

#### Scenario: User-level target for a GitButler project
- **WHEN** the same project's update names `--skills ~/.claude/skills`
- **THEN** the plan holds no refusal for that directory

### Requirement: The install prompt explains what a user-level install shares
With any backend the install prompt SHALL say that a user-level install is shared by every project on the machine. It SHALL say that moving to an in-repo install means updating or removing the old user-level `specwright-*` copies, which serve every project on the machine, and restarting agent sessions first, and that in Claude Code a user-level skill overrides the in-repo one of the same name.

#### Scenario: The install prompt on GitButler
- **WHEN** the install prompt asks for targets and `vcs: gitbutler` is set or chosen
- **THEN** it offers the in-repo directories and the user-level ones, warns that applied branches share in-repo skills, says that a user-level install is shared by every project on the machine and, in Claude Code, overrides in-repo skills of the same name, and says that moving to an in-repo install means removing the user-level `specwright-*` copies once no other project relies on them, or updating them to 0.14.0 or later, and restarting agent sessions, with `scripts_in_workspace` from an older user-level copy as the symptom
