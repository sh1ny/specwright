# Review

## Metadata

- **Round:** 2 (re-check)
- **Prior round:** round 2: APPROVE_WITH_CHANGES, 1 Moderate (M1, Claude Code skill precedence and the migration advice), 2 Suggestions promoted to Required Changes 2 and 3; CHANGES_APPLIED: no
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** round 2 review (C:/Users/bgshi/AppData/Local/Temp/specwright-gitbutler-in-repo-install/review-round2.md); openspec/changes/gitbutler-in-repo-install/design.md, specs/vcs-backends/spec.md, specs/install-update/spec.md; `openspec instructions review --change gitbutler-in-repo-install --json`; `openspec validate gitbutler-in-repo-install --strict` (valid). Re-check of the three Required Changes only, not a new full review. Installed project skills named by the request: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

Round 2 Required Changes, re-checked:

- RC1 (Claude Code precedence and migration wording): applied.
  - design.md D2 has a bullet for both locations at once. It says that in Claude Code a user-level skill overrides the in-repo one in every project, that agents resolve project over user, that the location is in effect a per-machine choice, and that a mixed install runs the user-level skills. This covers (a).
  - D2's "Moving a project from user level to in repo" bullet says either remove the copies after moving every other project that uses them, or update them to 0.14.0 or later, which no longer stops but shadows the in-repo skills. It names `scripts_in_workspace` as the symptom. This covers (b) and (c).
  - D2 keeps it a warning only (no detection, no refusal, ADR 0021), and the README "Where the skills live" note is to carry "the same points".
  - Flow & State Gaps bullet 2 no longer calls the case transitional. It says restarting sessions does not help and gives the same two ways out. Bullet 3 replaces "each agent's own loading order decides" with the Claude Code personal-over-project rule and the agents' project-over-user rule.
  - The install-update scenario "The install prompt on GitButler" now asserts the Claude Code override, removal "once no other project relies on them" or an update to 0.14.0 or later, and `scripts_in_workspace` as the symptom. It does not repeat the agents' project-over-user rule or the per-machine wording. Both follow from the asserted override and sharing statements, and D2 fixes the full prompt text, so the scenario is aligned well enough to test the obligation.
- RC2 (vcs-backends REMOVED Migration): applied. The `**Migration**` line now names the user-level copies, the update-to-0.14.0-or-remove choice, the `scripts_in_workspace` stop from an older copy and the Claude Code override. The wording matches the example.
- RC3 (SHALL for the third scenario): applied. The SHALL sentence (updating or removing the old user-level copies, which serve every project, restarting agent sessions, and the Claude Code override) is in the install-update ADDED requirements with the example's wording.
- The split into two requirements is faithful. "Every backend takes in-repo and user-level targets" keeps the `plan` acceptance, the offer of both locations and the GitButler shared-work-tree warning, and its first two scenarios test those. "The install prompt explains what a user-level install shares" holds the sharing SHALL, the migration and restart SHALL and the Claude Code override SHALL, and it now owns the third scenario. That scenario's THEN also checks the offer of both locations and the GitButler warning from the first requirement. This is redundant coverage and no obligation is left untested. No SHALL was lost or reworded in a way that changes it. Strict validation passes.

Outside the Required Changes, no action needed for this verdict: the install-update REMOVED requirement still reads `**Migration**: None needed.` RC2 targeted only the vcs-backends delta, so this does not block. The author may align it with the vcs-backends Migration line as a clarification.

### Critical (blocking)

None.

### Moderate

None open. M1 is resolved by Required Changes 1 and 3.

### Suggestions

None open. S1 and S2 are resolved as Required Changes 2 and 3.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (Round 2 RC1) Claude Code precedence and migration wording in design.md D2, Flow & State Gaps bullets 2-3, the README note and prompt wording D2 specifies, and the install-update third scenario. Applied.
2. (Round 2 RC2) vcs-backends REMOVED requirement Migration names the user-level copies. Applied.
3. (Round 2 RC3) install-update SHALL for the third scenario's obligation. Applied, in the split-out requirement "The install prompt explains what a user-level install shares".

CHANGES_APPLIED: yes

## Rebuttals
