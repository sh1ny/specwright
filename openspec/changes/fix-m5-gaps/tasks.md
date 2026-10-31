# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| releases → The release skill names the proposal in the planning repo | Store-backed project | evals/release/test_skill_text.py | TestReleaseSkill.test_notes_check_names_proposal_in_planning_repo | red |
| releases → The release skill names the proposal in the planning repo | A hardcoded path comes back | evals/release/test_skill_text.py | TestReleaseSkill.test_no_skill_passes_a_fixed_proposal_path | red |
| task-commits → A repeated task id stops the coverage check | Ticked line followed by a draft line with the same id | evals/git-workflow/test_task_cover.py | TaskCover.test_repeated_task_id_exits_2 | red |
| task-commits → A repeated task id stops the coverage check | Unique ids | evals/git-workflow/test_task_cover.py | TaskCover (existing coverage tests, unchanged) | green |
| task-commits → A repeated task id stops the coverage check | Repeated id in an untracked line | evals/git-workflow/test_task_cover.py | TaskCover.test_repeated_id_in_plain_bullet_is_not_a_task | red |
| eval-grading → Store-group pair evidence names the trailers it checks | Only the trailers fail | evals/git-workflow/test_grade.py | StoreGroupRecovery.test_store_group_code_half_without_trailers_fails (extended with the evidence assertion) | red |
| eval-grading → Store-group pair evidence names the trailers it checks | Trailers present | evals/git-workflow/test_grade.py | StoreGroupRecovery.test_store_group_pair_evidence_lists_tasks | red |
| eval-grading → The fake gh state file is replaced whole | Reader during a write | evals/pr-pair/test_fake_gh.py | StateFile.test_reader_never_sees_a_partial_state | red |
| eval-grading → The fake gh state file is replaced whole | Rename held off | evals/pr-pair/test_fake_gh.py | StateFile.test_held_rename_fails_after_bound_and_keeps_state | red |
| eval-grading → A fake gh read never rewrites the state | Watcher polls while the test mutates | evals/pr-pair/test_fake_gh.py | StateFile.test_read_call_leaves_state_file_untouched | red |
| eval-grading → A fake gh read never rewrites the state | A mutation still saves | evals/pr-pair/test_fake_gh.py | StateFile.test_mutation_still_saves | red |
| eval-grading → Every seeded PR body for an issue check has a recorded rendering | Finish fixtures' body | evals/pr-pair/test_pr_pair.py | ClosingRecordings.test_finish_fixture_body_closed_check_reads_issue_state | red |
| eval-grading → Every seeded PR body for an issue check has a recorded rendering | A new fixture body without a recording | evals/pr-pair/test_pr_pair.py | ClosingRecordings.test_every_closing_body_has_a_recording (bodies now include the fixture bodies) | red |
| eval-runner → A stopped test file's nested sessions are stopped too | Timed-out file with a nested bounded session | evals/runner/test_run.py | test_a_timed_out_file_nested_bounded_session_is_stopped | red |
| eval-runner → A stopped test file's nested sessions are stopped too | Interrupted run | evals/runner/test_run.py | test_an_interrupt_stops_a_nested_bounded_session | red |
| eval-runner → A stopped test file's nested sessions are stopped too | Outside the runner | evals/pr-pair/test_bounded.py | test_spawn_records_nothing_without_spawn_dir | red |
| vcs-backends → On GitButler Specwright's scripts run from outside the work tree | Skills installed in the repo | evals/vcs/test_gitbutler_probe.py | test_scripts_in_work_tree_stop_before_but | red |
| vcs-backends → On GitButler Specwright's scripts run from outside the work tree | Skills installed at user level | evals/vcs/test_gitbutler_probe.py | test_scripts_outside_work_tree_probe_continues | red |
| vcs-backends → On GitButler Specwright's scripts run from outside the work tree | A sibling branch adds a skill copy | evals/vcs/test_gitbutler_probe.py | test_specwright_copy_in_work_tree_stops | red |
| vcs-backends → On GitButler Specwright's scripts run from outside the work tree | Git project with in-repo skills | evals/vcs/test_probe.py | test_git_backend_ignores_in_repo_scripts | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Unassigned edit before ship | evals/pr-pair/test_pr_pair.py | ContextPin.test_unassigned_settings_edit_stops_context | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Watch reads merge settings | evals/pr-pair/test_pr_pair.py | ContextPin.test_merge_settings_not_reported_when_unpinned | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Push with an unpinned edit | evals/vcs/test_gitbutler_push.py | test_unassigned_settings_edit_stops_push | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Context without the branch | evals/pr-pair/test_pr_pair.py | ContextPin.test_gitbutler_context_without_branch_is_usage_error | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Feedback or CI fix push in a repo-local project | evals/git-workflow/test_instructions.py | test_gitbutler_validate_read_from_pinned_context | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup after the merge | evals/pr-pair/test_pr_pair.py | ContextPin.test_after_merge_without_branch_ref_compares_target_ref | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup with an unpinned edit | evals/pr-pair/test_pr_pair.py | ContextPin.test_after_merge_unpinned_edit_stops | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Cleanup after a skipped pull | evals/pr-pair/test_pr_pair.py | ContextPin.test_after_merge_with_branch_still_present_compares_tip | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Settings never committed on the branch | evals/pr-pair/test_pr_pair.py | ContextPin.test_settings_missing_at_tip_stops | red |
| vcs-backends → On GitButler the settings are those the change branch committed | The change commits its own settings edit | evals/vcs/test_gitbutler_commit.py | test_own_settings_edit_commits_then_context_passes | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Branch already deleted | evals/vcs/test_gitbutler_delete.py | test_state_of_deleted_branch_has_no_pin_stop | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Pinned settings | evals/pr-pair/test_pr_pair.py | ContextPin.test_pinned_settings_report_as_before | red |
| vcs-backends → On GitButler the settings are those the change branch committed | Git backend | evals/pr-pair/test_pr_pair.py | ContextPin.test_git_backend_never_pins | red |
| install-update → A GitButler project takes no in-repo skill or agent target | In-repo target for a GitButler project | evals/update/test_update.py | test_gitbutler_project_refuses_in_repo_target | red |
| install-update → A GitButler project takes no in-repo skill or agent target | User-level target | evals/update/test_update.py | test_gitbutler_project_accepts_user_level_target | red |
| install-update → A GitButler project takes no in-repo skill or agent target | Git project | evals/update/test_update.py | test_git_project_keeps_in_repo_target | red |
| install-update → A GitButler project takes no in-repo skill or agent target | Fresh install with no settings yet | evals/update/test_update.py + evals/git-workflow/test_instructions.py | test_fresh_install_has_no_workspace_refusal + test_readme_gitbutler_choice_names_user_level_targets | red |

The GitButler tests in `evals/vcs/test_gitbutler_*.py` need a real `but`. It runs only on the Linux CI job (`SPECWRIGHT_REQUIRE_BUT=1`), and they skip on this Windows machine. Their red step is shown by running the module where `but` exists (WSL only with the user's OK, else the PR's Linux job), and the task says which was used. Per AGENTS.md, run only the module being written locally, red then green, and never a whole suite.

## 1. ADR 0019 and architecture

- [ ] 1.1 Write `docs/adr/0019-gitbutler-workspace-runs-only-the-user-level-install.md`: Status accepted, today's date, adds to 0018 (does not supersede it). Its Decision records D7 and D8 from design.md. Its Consequences name the residual risk of the schema, templates and `config.yaml` in the work tree, and `but worktree` as the fix that would close it. Add its row to the in-force index in `openspec/architecture.md`, and amend the `vcs.sh` and Install prompt rows (`scripts_in_workspace`, `settings_not_pinned` through `pr-pair.sh context --branch`/`--after-merge`, `target_in_workspace`). Verify: `python -m unittest evals/runner/test_suite_map.py` passes (add a `suites.json` rule or `no_eval` entry if it fails).

## 2. Release skill names the proposal by role (#133)

- [ ] 2.1 Add `test_notes_check_names_proposal_in_planning_repo` and `test_no_skill_passes_a_fixed_proposal_path` to `evals/release/test_skill_text.py` (`TestReleaseSkill`). Run the module and see both fail on `skills/specwright-release/SKILL.md:48`.
- [ ] 2.2 Rewrite the notes check in `skills/specwright-release/SKILL.md` (`## Release notes`) to `release.sh notes --proposal <proposal.md>`, saying it is the change's `<P>/changes/<change>/proposal.md` in the planning repo, in the store when store-backed. Verify: `python -m unittest evals/release/test_skill_text.py` passes, and flip both rows green.

## 3. Repeated task ids stop task-cover (#143)

- [ ] 3.1 Add `test_repeated_task_id_exits_2` (`- [x] 1.1` then `- [~] 1.1 draft`: exit 2, `error: duplicate_task_ids`, message names `1.1`, no `uncovered`) and `test_repeated_id_in_plain_bullet_is_not_a_task` to `evals/git-workflow/test_task_cover.py`. Run the module: the first fails.
- [ ] 3.2 In `skills/specwright-commit/scripts/task-cover.sh`, collect ids seen on more than one tracked line and `stop("duplicate_task_ids", ..., 2)` before coverage is built. Document the error in the header's exit-code block. Verify: `python -m unittest evals/git-workflow/test_task_cover.py` passes (existing tests included), and flip the rows green.

## 4. Store-group evidence shows the trailers (#144)

- [ ] 4.1 Extend `StoreGroupRecovery.test_store_group_code_half_without_trailers_fails` in `evals/git-workflow/test_grade.py` to assert the evidence shows each commit's empty task list. Add `test_store_group_pair_evidence_lists_tasks` for the passing case (`['1.1', '1.2', '1.3']`, both pair checks). Run the module and see them fail.
- [ ] 4.2 Change the evidence of `eval-store-group-code-half` and `eval-store-group-store-half` in `evals/git-workflow/grade.py` to `(subject, tasks)` pairs, as `eval-store-apply-groups` already does. Verify: `python -m unittest evals/git-workflow/test_grade.py -k StoreGroup` passes, and flip the rows green.

## 5. Fake gh state written whole, reads never write (#134)

- [ ] 5.1 Add class `StateFile` to `evals/pr-pair/test_fake_gh.py` with four tests:
  - `test_reader_never_sees_a_partial_state`: a reader thread loops while 200 writes run, and every read parses and equals a written state.
  - `test_held_rename_fails_after_bound_and_keeps_state`: patch `os.replace` to raise `PermissionError`, and use a short bound through a module constant.
  - `test_read_call_leaves_state_file_untouched`: the file's mtime and bytes are unchanged after a read call.
  - `test_mutation_still_saves`.

  Run the module and see them fail.
- [ ] 5.2 Add `write_state` and `read_state` to `evals/fakes/gh.py`:
  - `write_state` writes a temp file in the same directory, flushes, fsyncs and `os.replace`s it, retrying `PermissionError` every 20 ms for up to 5 s, then raises `OSError` naming the file and removes the temp file.
  - `read_state` retries `PermissionError` on open for 5 s.
  - `save()` and `load()` use them.
  - `main()` saves only when the state's JSON changed during the call.

  Switch `evals/pr-pair/snapfix.py` (`mutate`, `st`) and the helper scripts at `test_pr_snapshot.py` (fakesleep, FAKE_SLEEP_PATCH, steps) and `test_pr_reply.py` (pend.py) to `gh.write_state` and `gh.read_state`. Verify: `python -m unittest evals/pr-pair/test_fake_gh.py` passes, then `python -m unittest evals/pr-pair/test_pr_snapshot.py` and `evals/pr-pair/test_pr_reply.py` pass (the modules this group edits). Flip the rows green.

## 6. Runner stops nested sessions (#136)

- [ ] 6.1 Write the three tests, then run them:
  - In `evals/runner/test_run.py`, `test_a_timed_out_file_nested_bounded_session_is_stopped`: a hang file loads `skills/specwright-pr/scripts/bounded.py` by path, `bounded.spawn`s a sleeper, writes both pids and sleeps; with `--timeout 4`, both pids are dead after the runner exits.
  - In the same file, `test_an_interrupt_stops_a_nested_bounded_session`.
  - In `evals/pr-pair/test_bounded.py`, `test_spawn_records_nothing_without_spawn_dir`.

  On Windows the nested pair already dies, so the red step for the two runner tests is shown on POSIX: WSL with the user's OK, else the PR's Linux and macOS jobs. Record which in the task commit.
- [ ] 6.2 Add the `SPECWRIGHT_TEST_SPAWN_DIR` hook to `skills/specwright-pr/scripts/bounded.py`. On POSIX only, after a successful `spawn`, create `<dir>/<pid>` for the directory in `os.environ`, and also for the one in the child's `env=` when it is different; ignore `OSError`. List the hook in the header (lines 12-14), then copy the file byte-identically to `skills/specwright-release/scripts/bounded.py` and `skills/specwright-review/scripts/bounded.py`.
- [ ] 6.3 In `evals/run.py`, give each file `<workdir>/spawns/<n>/` through `env={**os.environ, SPECWRIGHT_TEST_SPAWN_DIR: dir}`. After every `bounded.kill(p)` (timeout, interrupt, `finally`, `stop_all`), `killpg(pid, SIGKILL)` each recorded pid, ignoring `ProcessLookupError` and `PermissionError`. Correct the comments at lines 5-6 and 264. Verify: `python -m unittest evals/runner/test_run.py` and `evals/pr-pair/test_bounded.py` (including `test_bounded_copies_identical`) pass, and flip the rows green.

## 7. Finish fixture PR body recorded (#146)

- [ ] 7.1 In `evals/git-workflow/fixtures.py`, export the merged-PR bodies the finish fixtures seed as `MERGED_PR_BODIES` and use the constant at both seeding sites. Have `evals/pr-pair/closing_bodies.collect_bodies()` append them. Add `ClosingRecordings.test_finish_fixture_body_closed_check_reads_issue_state`: `pr-pair.sh closed-check` against a fake `gh` seeded like the finish fixture exits with the issue's state and does not say `no recorded rendering`. Run `python -m unittest evals/pr-pair/test_pr_pair.py -k ClosingRecordings`: both tests fail.
- [ ] 7.2 Record the rendering. The orchestrator, not an implementer, runs `python evals/pr-pair/record_markdown.py`. It makes one read-only `POST /markdown` as KintsugiBot through `as.sh`. Check the diff of `evals/pr-pair/fixtures/markdown.json`: only new keys, no entries dropped. Verify: `python -m unittest evals/pr-pair/test_pr_pair.py -k ClosingRecordings` passes, and flip both rows green.

## 8. GitButler runs only an install outside the repo (#150)

- [ ] 8.1 Write the failing tests, then run each module and see them fail:
  - In `evals/vcs/test_gitbutler_probe.py`: `test_scripts_in_work_tree_stop_before_but`, `test_scripts_outside_work_tree_probe_continues` and `test_specwright_copy_in_work_tree_stops`. Each logs that no `but` ran on a stop.
  - In `evals/vcs/test_probe.py`: `test_git_backend_ignores_in_repo_scripts`.
  - In `evals/update/test_update.py`: `test_gitbutler_project_refuses_in_repo_target`, `test_gitbutler_project_accepts_user_level_target`, `test_git_project_keeps_in_repo_target` and `test_fresh_install_has_no_workspace_refusal`.
- [ ] 8.2 In `skills/specwright-pr/scripts/vcs.sh` `probe_gitbutler`, before `but --version`, stop with `scripts_in_workspace` (exit 1) in either of two cases:
  - the resolved `VCS_DIR` is under the resolved repo root;
  - any of `.claude/skills/specwright-*`, `.agents/skills/specwright-*`, `.claude/agents/specwright-*.md` or `.omp/agents/specwright-*.md` exists in the work tree.

  The message names each path, says to install at user level, and says to remove committed copies by hand through GitButler. Verify: the 8.1 vcs modules pass (GitButler ones where `but` exists, see the note under the test map), and flip their rows green.
- [ ] 8.3 In `scripts/update.sh` plan, read `<code>/openspec/specwright.yaml`. When it selects `vcs: gitbutler`, add a `target_in_workspace` refusal for each `--skills` or `--agents` directory under the code toplevel, and document it in the header. Verify: `python -m unittest evals/update/test_update.py` passes, and flip its rows green.
- [ ] 8.4 Add `test_readme_gitbutler_choice_names_user_level_targets` to `evals/git-workflow/test_instructions.py` and see it fail. Then edit:
  - `README.md`: the install prompt's GitButler choice names user-level targets for Specwright's skills and agents. Reword the line about GitButler's own skill (README.md:307-308) so the two rules are not confused.
  - `skills/specwright-branch/SKILL.md`: the GitButler paragraph says the same.

  Verify: the test passes, and flip the README part of the "Fresh install" row green.

## 9. GitButler settings pinned where they are used (#151)

- [ ] 9.1 Add class `ContextPin` to `evals/pr-pair/test_pr_pair.py` with the nine `context` tests in the test map. Each runs in a git repo with `vcs: gitbutler` settings and `gitbutler.project.targetRef` set; no `but` is needed for `pr-pair.sh`. Run `python -m unittest evals/pr-pair/test_pr_pair.py -k ContextPin` and see them fail.
- [ ] 9.2 In `skills/specwright-pr/scripts/pr-pair.sh`:
  - Add `settings_pinned(code, ref)`, which compares `git hash-object --path=openspec/specwright.yaml` of the work-tree file with `git rev-parse <ref>:openspec/specwright.yaml`. A difference, or a file on one side only, is `settings_not_pinned`; a git failure is `git_error`.
  - Add `context --branch <b>` and `--after-merge`, which use the tip of `refs/heads/<b>` while it exists, else `gitbutler.project.targetRef`. The message names the ref, and for `--after-merge` it says `but pull` or undo the edit.
  - On GitButler, a merge-settings `context` without `--branch` is exit 2 usage.
  - Document all of this in the header.

  Verify: the `ContextPin` tests pass, the existing `Context` tests still pass, and flip the rows green.
- [ ] 9.3 Write the three tests and see them fail:
  - In `evals/vcs/test_gitbutler_push.py`: `test_unassigned_settings_edit_stops_push`.
  - In `evals/vcs/test_gitbutler_commit.py`: `test_own_settings_edit_commits_then_context_passes`.
  - In `evals/vcs/test_gitbutler_delete.py`: `test_state_of_deleted_branch_has_no_pin_stop`.

  Switch the GitButler fixture (`evals/vcs/test_gitbutler_branch.py:14-16` and any shared helper) from hiding `openspec/specwright.yaml` in `.git/info/exclude` to committing it on main.
- [ ] 9.4 Make `vcs.sh` `gitbutler_push` call `pr-pair.sh context --code <code> --only repos --branch <b>` before `but push`, and stop on its error. Leave `state` and `commit` unpinned. Verify: the 9.3 modules and the edited GitButler modules pass where `but` exists (see the note under the test map), and flip the rows green.
- [ ] 9.5 Add `test_gitbutler_validate_read_from_pinned_context` to `evals/git-workflow/test_instructions.py` and see it fail. It checks the `specwright-pr` push rule (SKILL.md:53), the `context` calls at :67 and :128, cleanup at :156-159, and `specwright-finish` :93-94. Then edit those skill lines:
  - on GitButler, read `validate` from `pr-pair.sh context --code <code> --branch <branch>` right before each run;
  - watch, ship and finish pass `--branch <branch>`;
  - cleanup uses `--after-merge --branch <branch>` after its pull.

  Verify: the test passes, the existing skill-text tests in that module still pass, and flip the row green.

## 10. Release 0.12.3

- [ ] 10.1 Run `python -m unittest evals/runner/test_suite_map.py` for the files this change adds (ADR 0019 and any new test helper), and add a `suites.json` rule or `no_eval` entry where it fails. Then run `bash skills/specwright-release/scripts/release.sh bump --to 0.12.3` and rewrite the summary of this proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `bash skills/specwright-release/scripts/release.sh notes --proposal openspec/changes/fix-m5-gaps/proposal.md`, both exit 0.

## Workflow follow-up

- Push the branch and open the PR with `specwright-pr` ship. The pre-ship review runs first. CI runs every suite on Linux, Windows and macOS, and every job must pass (M6 exit criterion). The GitButler and POSIX-only red steps noted above are confirmed there.
- After the merge, publish 0.12.3 (`specwright-release` publish) and confirm #133, #134, #136, #143, #144, #146, #150 and #151 are closed by the merged PR.
