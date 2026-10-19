# Tasks

## Test map

`TestUndoPlan` lives in `evals/finish/test_undo_plan.py`. Each test builds the state as a temp git repo, runs `finish.sh undo-archive-plan`, runs the printed `script` (and `after_rerun`) with `bash`, and asserts on the resulting tree, index and refs.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| change-finish → Resume takes the newest add of the archive as its archive commit | Archive added once | evals/finish/test_undo_plan.py | TestUndoPlan.test_archive_commit_is_the_add_not_a_later_edit | green |
| change-finish → Resume takes the newest add of the archive as its archive commit | Archive reverted and archived again | evals/finish/test_undo_plan.py | TestUndoPlan.test_rearchived_targets_newest_add_only | green |
| change-finish → Resume takes the newest add of the archive as its archive commit | Archive reverted and archived again (skill text) | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_finish_archive_commit_is_the_newest_add | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Deferred archive found | evals/finish/test_undo_plan.py | TestUndoPlan.test_plan_writes_nothing | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Deferred archive found (skill text) | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_finish_step0_runs_undo_plan_and_runs_nothing | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Plan run on a dirty unrelated path in a resume on main | evals/finish/test_undo_plan.py | TestUndoPlan.test_resume_on_dirty_main_refused | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | No archive of the change | evals/finish/test_undo_plan.py | TestUndoPlan.test_no_archive_refused | green |
| change-finish → A deferred archive's undo is planned by a script that runs nothing | Branch moved after the plan | evals/finish/test_undo_plan.py | TestUndoPlan.test_guard_fails_after_branch_moved | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Uncommitted single archive | evals/finish/test_undo_plan.py | TestUndoPlan.test_uncommitted_single_archive | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Uncommitted edit in a synced main spec | evals/finish/test_undo_plan.py | TestUndoPlan.test_uncommitted_spec_edit_backed_up | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Committed archive with a later amendment | evals/finish/test_undo_plan.py | TestUndoPlan.test_committed_with_later_amendment | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Amendment survives the rerun | evals/finish/test_undo_plan.py | TestUndoPlan.test_amendment_survives_bulk_rerun | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Later commit that also changes unrelated paths | evals/finish/test_undo_plan.py | TestUndoPlan.test_unrelated_paths_kept | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Uncommitted edit in a committed archive copy | evals/finish/test_undo_plan.py | TestUndoPlan.test_uncommitted_edit_in_archive_copy_carried | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Bulk archive with a deferred member | evals/finish/test_undo_plan.py | TestUndoPlan.test_committed_bulk_undone_whole | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Uncommitted bulk archive with a deferred member | evals/finish/test_undo_plan.py | TestUndoPlan.test_uncommitted_bulk_members_found | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Resume on main with the archive on the branch | evals/finish/test_undo_plan.py | TestUndoPlan.test_resume_on_main_checks_out_branch | green |
| change-finish → The undo restores the pre-archive state without losing any edit | Saved amendment conflicts after the rerun | evals/finish/test_undo_plan.py | TestUndoPlan.test_rerun_conflict_stops_and_keeps_copies | green |
| design-review-gate → A deferred review never ships code | Apply on a deferred change | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_apply_gate_refuses_deferred_and_says_review_needed | green |
| design-review-gate → A deferred review never ships code | Archive on a deferred change | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_config_context_refuses_archive_of_deferred | green |
| design-review-gate → A deferred review never ships code | Archive ran anyway | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_finish_step0_runs_undo_plan_and_runs_nothing | green |
| design-review-gate → A deferred review never ships code | Deferred archive already committed | evals/finish/test_undo_plan.py | TestUndoPlan.test_committed_with_later_amendment (one new commit, no ref other than the branch moved) | green |
| design-review-gate → A deferred review never ships code | Bulk archive that included a deferred change | evals/finish/test_undo_plan.py | TestUndoPlan.test_committed_bulk_undone_whole | green |
| design-review-gate → A deferred review never ships code | Deferral with no target | evals/git-workflow/test_instructions.py | DesignReviewDispositions.test_tasks_precheck_stops_on_deferred_without_target | green |
| project-planning → A parking change is never a milestone change | Close with a parked change listed | evals/git-workflow/test_instructions.py | ProjectPlanning.test_close_stops_on_parked_listed_change | green |
| project-planning → A parking change is never a milestone change | Next reaches a parked listed change | evals/git-workflow/test_instructions.py | ProjectPlanning.test_next_never_starts_parked_listed_change | green |
| project-planning → A parking change is never a milestone change | Status with a parked listed change | evals/git-workflow/test_instructions.py | ProjectPlanning.test_status_lists_parked_listed_in_error | green |
| project-planning → A parking change is never a milestone change | Parking change not listed | evals/git-workflow/test_instructions.py | ProjectPlanning.test_parking_note_says_never_listed | green |
| releases → A bumped version is greater than main's before it merges | Two changes bump to the same version | evals/release/test_release.py | TestCheckMain.test_duplicate_bump_refused | green |
| releases → A bumped version is greater than main's before it merges | Main moved past the bump | evals/release/test_release.py | TestCheckMain.test_main_ahead_refused | green |
| releases → A bumped version is greater than main's before it merges | Bump still ahead | evals/release/test_release.py | TestCheckMain.test_bump_ahead_passes | green |
| releases → A bumped version is greater than main's before it merges | Version file edited without a bump | evals/release/test_release.py | TestCheckMain.test_version_file_edit_without_bump_passes | green |
| releases → A bumped version is greater than main's before it merges | Bump reverted on the branch | evals/release/test_release.py | TestCheckMain.test_bump_reverted_on_branch_passes | green |
| releases → A bumped version is greater than main's before it merges | Branch did not bump | evals/release/test_release.py | TestCheckMain.test_no_bump_passes | green |
| releases → A bumped version is greater than main's before it merges | Main was merged into the branch after the duplicate landed | evals/release/test_release.py | TestCheckMain.test_duplicate_after_main_merged_in_refused | green |
| releases → A bumped version is greater than main's before it merges | Main has no version yet | evals/release/test_release.py | TestCheckMain.test_main_without_version_passes | green |
| releases → A bumped version is greater than main's before it merges | Merge base repeats the version | evals/release/test_release.py | TestCheckMain.test_unreadable_base_dedupe_is_no_bump | green |
| releases → A bumped version is greater than main's before it merges | Bump after a repair of an unreadable version | evals/release/test_release.py | TestCheckMain.test_repair_then_bump_refused_when_behind | green |
| releases → A bumped version is greater than main's before it merges | One commit repairs and bumps | evals/release/test_release.py | TestCheckMain.test_repair_and_bump_in_one_commit_refused | green |

## 1. Undo plan script (#106)

- [x] 1.1 Check the design's assumption against a real `openspec archive`: in a scratch repo with one change that modifies and creates a main spec, archive it, then compare each file of `changes/archive/<archived>/` with the pre-archive `changes/<name>/`. Record the result in this task line ("Result: same", or "Result: differs: <files>"), not in design.md, because an edit there voids the review. If they differ, the script carries the extra diff through the base and amended copies, as the design's Risks line says. Verify: the recorded result and the command output. Result: same.
- [x] 1.2 Write `evals/finish/fixtures.py`, a temp-repo builder modelled on `evals/release/fixtures.py`. It supports: a planning prefix; a change dir with `review.md` (DEFERRED or APPROVE) and delta specs; a simulated archive (move the dir, sync each delta into its main spec, optional `specwright-change.yaml`) left uncommitted or committed as A; later commits; uncommitted edits; revert and re-archive. It also has a helper that runs `finish.sh`, then runs `script` and `after_rerun` with `bash`. Verify: a fixture smoke test passes.
- [x] 1.3 Write the failing `TestUndoPlan` tests from the test map (all `evals/finish/test_undo_plan.py` rows). Verify: `python -m unittest discover evals/finish` fails because `finish.sh` is missing.
- [x] 1.4 Implement `skills/specwright-finish/scripts/finish.sh undo-archive-plan`, a bash wrapper with embedded Python 3.8+, one JSON document, exits 0/1/2, read-only git, per design D1-D3:
  - members, uncommitted vs committed mode, and A as the newest add;
  - `script` with `set -euo pipefail`. Its guard runs before any checkout: on a resume from another branch, the guard first checks a clean tree and `rev-parse <branch>` = the planned head, then checks out, then checks again. This tightens D2 step 1 so that a failed guard leaves the checkout where it was (re-check note 2);
  - the backups that are always saved, the index-built undo commit (subject names every member), and the working-tree fix-up;
  - `after_rerun`, which merges only main specs that a non-deferred member's delta syncs again. A main spec only the deferred change synced stays saved, with a warning, and is never passed to `git merge-file` (re-check note 1);
  - the refusals `no_archive`, `dirty_tree`, `staged_changes`, `target_exists` and `backup_exists`.

  Verify: every `TestUndoPlan` test passes. Flip its rows green.
- [x] 1.5 Rewrite `skills/specwright-finish/SKILL.md`:
  - step 0: stop on `VERDICT: DEFERRED`, run `bash <specwright-finish>/scripts/finish.sh undo-archive-plan ...` (store-backed: `--dir <store toplevel>`), show `script`, `after_rerun` and `warnings`, and say to save each script and run it with `bash`. Make no commit, merge or push, and run neither script. Remove the three restore groups and the revert chain;
  - Resume's A fact: the newest add line;
  - `allowed-tools`: add `Bash(bash *)`;
  - a usage header in `finish.sh` matching the other scripts.

  Replace the step-0 wording tests in `evals/git-workflow/test_instructions.py` that pin the old prose (`test_finish_committed_archive_undone_by_revert_alone`, `test_finish_undo_moves_change_directory_back`, `test_finish_revert_includes_later_commits_on_archive_paths`, `test_finish_step0_stops_on_deferred_and_lists_restore_groups`, `test_finish_archive_commit_is_the_one_that_added_it`, `test_finish_step0_undoes_bulk_archive_as_a_whole`) with `test_finish_step0_runs_undo_plan_and_runs_nothing` and `test_finish_archive_commit_is_the_newest_add`. Keep the tests that still hold (deferred check on a committed archive, the branch's `review.md`, bulk found by path). Verify: `python -m unittest evals.git-workflow.test_instructions` passes (or the module's usual invocation), and flip those rows green.
- [ ] 1.6 Document the new script: `CONTRIBUTING.md` (run `python -m unittest discover evals/finish`), the `openspec/architecture.md` components row for `specwright-finish` (its script, one JSON document, read-only git) and the state row for `<git-dir>/specwright-undo/`. Verify: `rg -n "finish.sh|specwright-undo" CONTRIBUTING.md openspec/architecture.md` shows each.

## 2. Parked change is never a milestone change (#105)

- [x] 2.1 Write the failing `ProjectPlanning` tests from the test map: close step 1, next step 3 and status each name the parked-listed case (reported as `parked (listed in error)`, neither started nor counted done, removal is the user's planning edit, next and close stop, no roadmap edit); the parking-change note says a parking change is never listed in a milestone's Changes. Verify: they fail on the current text.
- [x] 2.2 Edit `skills/specwright-roadmap/SKILL.md` (the parking-change note, next step 3, close step 1, status) per design D4. Verify: the four tests pass and the existing parked tests (`test_roadmap_next_skips_parked_change` and the rest) still pass. Flip the rows green.

## 3. Unreadable is not absent in the release check (#103)

- [x] 3.1 Write the failing `TestCheckMain` tests: `test_unreadable_base_dedupe_is_no_bump`, `test_repair_then_bump_refused_when_behind`, `test_repair_and_bump_in_one_commit_refused`. Verify: the first fails with `version_not_ahead_of_main` on the current `release.sh`, and the others fail or pass for the reason the test names.
- [x] 3.2 Implement design D5 in `skills/specwright-release/scripts/release.sh`. `primary_at` returns `None` for absent and an `Unreadable` value with its matched versions otherwise. `check_ahead_of` and `own_bump` follow D5. A commit whose version is outside its unreadable parent's set but not greater than every semver in it is no bump, the same as a readable lowering today (re-check note 3). Update the `check` usage text in the header. Verify: `python -m unittest discover evals/release` passes, including the unchanged `TestCheckMain` rows. Flip the rows green.

## 4. Integration and release

- [ ] 4.1 Run every eval suite the milestone names: `python -m unittest discover` for `evals/finish`, `evals/git-workflow`, `evals/release`, `evals/review-routes`, `evals/pr-pair` and `evals/update`, plus `openspec validate fix-deferral-followups --strict` and `openspec schema validate specwright`. Verify: all pass.
- [ ] 4.2 `bash skills/specwright-release/scripts/release.sh bump --to 0.7.1` (a patch: fixes only, per CONTRIBUTING.md's pre-1.0 rule). Verify: `release.sh check` reports 0.7.1, and `VERSION`, the README badge and every skill `metadata.version` read 0.7.1.

## Workflow follow-up

- Archive, then finish in `pr` mode. The PR closes #106, #105 and #103.
