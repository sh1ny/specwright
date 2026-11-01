# Spec Delta

## REMOVED Requirements

### Requirement: On GitButler Specwright's scripts run from outside the work tree
**Reason**: Managing the installed skills after the install is the user's responsibility. The refusal forced a machine-wide install on every GitButler project (one Specwright version for all projects, no packs) to guard against the user's own applied branches, while `pr.validate` already runs code from the shared work tree.
**Migration**: A user-level install keeps working. To move a project to an in-repo install, first update the user-level `specwright-*` copies to 0.14.0 or later, or remove them once no other project on the machine uses them. An older user-level copy stops every call with `scripts_in_workspace`, and in Claude Code a user-level skill overrides the in-repo one of the same name (README "Where the skills live").

## ADDED Requirements

### Requirement: On GitButler Specwright runs from wherever it was installed
With `vcs: gitbutler`, `vcs.sh` SHALL run the same way whether its scripts directory and the Specwright skill and agent copies are inside the code work tree or outside it. Neither location SHALL be refused or reported as an error.

#### Scenario: Skills installed in the repo
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, and `vcs.sh probe` runs from `<repo>/.claude/skills/specwright-pr/scripts/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`

#### Scenario: Skills installed at user level beside an in-repo copy
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, `vcs.sh probe` runs from a directory outside the repo, and the work tree also holds `.claude/skills/specwright-pr/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`
