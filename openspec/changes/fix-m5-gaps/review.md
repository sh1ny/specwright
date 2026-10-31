# Review

## Metadata

- **Round:** 3
- **Prior round:** REVISE: unpinned validate in repo-local ship/feedback/CI fix; post-merge cleanup settings unpinnable; user chose to revise
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:** openspec/changes/fix-m5-gaps/proposal.md, design.md, review.md (round 2), round 1 copy (by its round-2 summary); specs/{releases,task-commits,eval-grading,eval-runner,vcs-backends,install-update}/spec.md; source: skills/specwright-pr/scripts/vcs.sh (get_settings 120-149, gitbutler_managed/probe_gitbutler 161-193, gitbutler_state 443-494, require_settings_pinned 496-512, fenced_but_pull/gitbutler_pull 627-672, gitbutler_push 674-688, gitbutler_delete 690-718, jj_fetch_main 1067-1076), skills/specwright-pr/scripts/pr-pair.sh (load_settings 540, repo_ctx 558-579, contexts 591-615, cmd_context 726-738, cmd_vcs, cmd_cleanup 2123-2172, the internal contexts() callers), skills/specwright-review/scripts/review-run.sh (settings header, load_settings), evals/pr-pair/snapfix.py (env 121-132); skill text: skills/specwright-pr/SKILL.md (27, 43, 49, 53, 67, 83-85, 108, 128, 150-160), skills/specwright-finish/SKILL.md (93-94); a grep of every `pr-pair.sh context` caller in skills, scripts, schemas and README. ADRs 0014, 0016, 0017, 0018 by the design's citations (unchanged since round 2).
- **Re-check:** 2026-11-01, fresh-context subagent. Re-checked only Required Changes 1-4 against design.md (D8 bullets at lines 131-132, Flow & State Gaps line 240), specs/vcs-backends/spec.md (requirement at line 25, scenarios at lines 38-57) and proposal.md (#151 bullet, line 27). Also ran `openspec validate fix-m5-gaps` (exit 0, one warning) and `--strict` (exit 1), and read evals/git-workflow/test_specs_strict.py, schemas/specwright/schema.yaml:127 and the openspec validator (`MAX_REQUIREMENT_TEXT_LENGTH = 500`, applied to ADDED requirements). Result: items 1, 2 and 4 are applied exactly. Item 3 is applied word for word, but its prescribed wording takes the requirement description to 525 characters, which breaks the strict gate. See Rebuttals. The changes-applied flag stays no.
- **Second re-check:** 2026-11-01, fresh-context subagent. Re-checked only Required Changes 1-5 against design.md (131, 132, 179-181, 240), specs/vcs-backends/spec.md (25, 40, 46-57) and proposal.md (27). Ran `openspec validate fix-m5-gaps --strict` (exit 0, `--json` shows no issues). Result: all five items are applied. The changes-applied flag is now yes. See Rebuttals.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Round 2 findings

- **C1 (unpinned `pr.validate` in repo-local ship, feedback, CI fix): resolved.** D8 now attaches the rule to the general sentence at specwright-pr/SKILL.md:53, which covers every push site (ship 4a.2 at :84, feedback step 7 at :108, watch's CI-fix push), repo-local and store-backed. On GitButler, `validate` is read from `pr-pair.sh context --branch` immediately before it runs, never from an earlier read. That closes the pre-ship-review window. The value comes from `repo_ctx` (`pr.validate` for code, `planning_store.validate` for the store, both in the code repo's settings file, pr-pair.sh:567,574), so one work-tree comparison of the code repo's file covers both. The vcs-backends delta has "Unassigned edit before ship" and "Feedback or CI fix push in a repo-local project", and both assert that the edited command never runs.
- **C2 (post-merge cleanup cannot pin): partly resolved.** D8 adds `context --after-merge`, which compares against GitButler's target ref, and names both call sites (specwright-pr/SKILL.md:156-159, specwright-finish/SKILL.md:94). The scenarios "Cleanup after the merge" and "Cleanup with an unpinned edit" are added. This holds when `but pull` ran. It does not hold on the skipped-pull path, which is the usual one on GitButler. See M1.
- **S1 (committed copies block their own removal): resolved.** D7 and the vcs-backends requirement have the message say to remove committed copies by hand through GitButler. The proposal's Release Notes say the same under Changed.
- **Round 1 findings not reopened.** `state --branch` and `commit` still do not pin (D8, scenario "The change commits its own settings edit"). `state --branch` for a deleted branch still reports it gone ("Branch already deleted"). M2 (D4 saves only on change), M3 (ADR 0019 residual risk) and S2 (README wording) are unchanged.

### Critical (blocking)

None.

### Moderate

**M1. `--after-merge` fails on a skipped pull, so cleanup stops for any merged change that committed its own settings edit while another branch is applied.**
D8 says cleanup "calls `context --after-merge` after its pull, which compares against GitButler's target ref (... origin's main just fetched by the pull). The merged settings are on that ref, and the workspace has just been updated to it." On GitButler that is only true when the pull runs:
- `gitbutler_pull` skips `but pull` whenever any other branch is applied or a linked worktree exists, and returns `pulled: false, reason: pull_skipped` (vcs.sh:650-660). The skill treats this as a normal result to "report and go on from" (specwright-pr/SKILL.md:158). Several applied branches is the reason to use GitButler at all, so this is the common path.
- The target ref then stays stale. The skill says so itself ("the local target lags a skipped pull"). `fetch-main` cannot update it, because it fetches with `--refmap=` into FETCH_HEAD only (vcs.sh:1067-1076).
- The merged branch stays applied. `gitbutler_delete` returns `left_applied` when the workspace base does not hold the merge yet (vcs.sh:709-714). So the work tree still holds the branch's committed edits.

Consequence: the change commits its own settings edit, which D8 and the scenario "The change commits its own settings edit" explicitly support, and it merges while a sibling is applied. The work-tree `openspec/specwright.yaml` (stale target plus the still-applied merged branch) then differs from the stale target ref, and `context --after-merge` exits 1 with `settings_not_pinned`. Per the scenarios, the remote-branch deletion does not run. The cleanup also stops before finish:94's `closed-check` step. The D8 message tells the user to "commit the edit on `<b>`", but the edit is already committed and merged, so that advice is wrong. This is not a safety hole, because it fails closed. But a supported flow stops with misleading advice on the main GitButler path. The fix is mechanical. The branch is still there exactly when the target is stale, and its tip holds the settings that were merged.

### Suggestions

None.

## Verdict

Round 2's C1 and S1 are resolved. C2 is resolved for the path where the pull runs. No round 1 finding reopens. The remaining Moderate is a precise, local correction to the post-merge pin source. It needs no new design decision: pin against the branch tip while the branch still exists, otherwise against the target ref.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **design.md, D8, bullet "Merge settings after the merge":** replace the sentence from "It calls `context --after-merge` after its pull" to the end of the bullet with the following. "It calls `context --after-merge --branch <branch>` after its pull and delete. While `refs/heads/<branch>` still exists (the pull returned `pull_skipped` or the delete returned `left_applied`, vcs.sh:658,714), the comparison is against that branch's tip, which holds the settings that were merged. Otherwise it compares against GitButler's target ref (`gitbutler.project.targetRef`), which the pull has just updated. On a mismatch the `settings_not_pinned` message names the reference compared against and says to run `but pull` or undo the work-tree edit, not to commit on `<branch>`." In the next bullet, change "with neither `--branch` nor `--after-merge`" to "without `--branch`".
2. **design.md, Flow & State Gaps:** add the entry "**Skipped pull after the merge.** Another branch is applied, so `pull` returns `pull_skipped`, the target ref lags, and the merged branch stays applied (`left_applied`). `context --after-merge --branch` then compares against the branch's tip, so a change that merged its own settings edit still cleans up."
3. **specs/vcs-backends/spec.md, requirement "On GitButler the settings are those the change branch committed":** change "`pr-pair.sh context --branch <b>` (or `--after-merge`)" to "`pr-pair.sh context --branch <b>` (after the merge, with `--after-merge`)". Change "(after merge: GitButler's target ref)" to "(after merge: the tip of `<b>` while that branch exists, else GitButler's target ref)". In the scenarios "Cleanup after the merge" and "Cleanup with an unpinned edit", change `pr-pair.sh context --after-merge` to `pr-pair.sh context --after-merge --branch feat/add-c`. In "Context without the branch", change "with neither `--branch` nor `--after-merge`" to "without `--branch`". Add this scenario:
   "#### Scenario: Cleanup after a skipped pull
   - **WHEN** `feat/add-c` committed an edit of `openspec/specwright.yaml` and its PR merged, another branch is applied, `vcs.sh pull --branch feat/add-c` returned `pull_skipped`, and `delete-branch` returned `left_applied`
   - **THEN** `pr-pair.sh context --after-merge --branch feat/add-c` reports `merge` and `delete_branch` with no `settings_not_pinned` stop, and the remote-branch deletion follows them"
   **Amended at the re-check (supersedes the two requirement-text edits above; the scenario edits stand as applied):** the requirement description must stay at or under 500 characters. Replace the whole description paragraph (the line after `### Requirement: On GitButler the settings are those the change branch committed`) with exactly this text (497 characters):
   "With `vcs: gitbutler`, the settings SHALL be read only from `pr-pair.sh context --branch <b>` right before each use (each `pr.validate` run, the merge settings), and `vcs.sh push` SHALL check again. Each SHALL stop with `settings_not_pinned` when the work-tree `openspec/specwright.yaml` differs from the file at the tip of `<b>` (after the merge, with `--after-merge`: that tip while `<b>` exists, else GitButler's target ref), or exists on one side only. Branch reads and commits are not pinned."
   Then `openspec validate fix-m5-gaps --strict` must exit 0 with no warning for this requirement.
4. **proposal.md, What Changes, the #151 bullet:** change "Cleanup after the merge uses `--after-merge`, which compares against GitButler's target ref." to "Cleanup after the merge uses `--after-merge`, which compares against the merged branch's tip while it is still applied, else GitButler's target ref."
5. **Added at the re-check. design.md, Diagrams, the T4/T6 flowchart:** change `CTXM[pr-pair.sh context --after-merge]` to `CTXM[pr-pair.sh context --after-merge --branch b]` and `PIN3{work tree == target ref?}` to `PIN3{work tree == tip of b while it exists, else target ref?}`. As things stand, the diagram still shows the round-2 rule that item 1 replaced.

CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

**Re-check note (reviewer, 2026-11-01).**
- Item 1: applied exactly (design.md:131, and :132 now reads "without `--branch`"). It is consistent with D8's "It does not run on ... `delete-branch`" paragraph (:135) and with the scenario "Branch already deleted".
- Item 2: applied exactly (design.md:240).
- Item 3: every edit is applied word for word (spec.md:25, 40, 49, 53, and the new scenario at 55-57). The new scenario is assertable and matches design.md:131. But the prescribed wording takes the requirement description to 525 characters. This matters, and not only as a cosmetic warning. (a) The schema's spec rule (schemas/specwright/schema.yaml:127) requires a description of at most 500 characters and states that `--strict` fails on a longer one. `openspec validate fix-m5-gaps --strict` does exit 1 now. (b) The CI test evals/git-workflow/test_specs_strict.py archives every active change into a scratch copy and asserts that `openspec validate --specs --strict` exits 0. Main specs pass strict today (exit 0), so this change's PR would turn that CI test red, and the overlong requirement would land in the main vcs-backends spec on archive. The defect is in the reviewer's item 3 wording, not in how it was applied. Item 3 now carries an amended text of 497 characters with the same meaning. Applying it is applying a Required Change, so it does not void the verdict.
- Item 4: applied exactly (proposal.md:27).
- Item 5 is new and minor. It brings the T4/T6 diagram in line with item 1, since the author is editing again anyway.
- Nothing else in the edits contradicts the other artifacts. The general message wording at design.md:126 ("saying to commit the edit on `<b>`") is overridden for the post-merge case by the item 1 text, which says so explicitly.
- After items 3 (amended) and 5 are applied, a new re-check run can mark the changes applied.

**Second re-check note (reviewer, 2026-11-01).**
- Item 3 (amended): applied exactly. The description at specs/vcs-backends/spec.md:25 is byte-identical to the amended text, 497 characters. The scenario edits still stand (spec.md:40, 49, 53, and "Cleanup after a skipped pull" at 55-57).
- Item 5: applied exactly (design.md:179 reads `CTXM[pr-pair.sh context --after-merge --branch b] --> PIN3{work tree == tip of b while it exists, else target ref?}`, and the `PIN3` edges at :180-181 are unchanged).
- Items 1, 2 and 4 are still in place (design.md:131, :132, :240; proposal.md:27).
- `openspec validate fix-m5-gaps --strict` exits 0. The `--json` output reports `valid: true` with no issues, so the requirement has no length warning.
- All Required Changes are applied. CHANGES_APPLIED is set to yes, and the verdict stays APPROVE_WITH_CHANGES.
