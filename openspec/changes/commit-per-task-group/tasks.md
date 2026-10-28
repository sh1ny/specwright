# Tasks

## Test map

Agent-behaviour scenarios are proven twice: an instruction test pins the rule in `skills/specwright-commit/SKILL.md` (or the schema), and a `git-workflow` eval case (`evals.json`, run with skill-creator) is graded by a `grade.py` check whose own logic is unit-tested in `test_grade.py` on synthetic repos. The grader matches evidence with its own code, never through `task-cover.sh` (review S3).

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| task-commits → Task subjects fit 72 characters | Long task text with backticks | evals/git-workflow/test_fit_subject.py | existing long-text tests | green |
| task-commits → Task subjects fit 72 characters | Subject exactly at the limit | evals/git-workflow/test_fit_subject.py | existing exact-limit test | green |
| task-commits → Task subjects fit 72 characters | Store-backed task pair | evals/git-workflow/test_grade.py | existing store per-task check (eval-store-apply) | green |
| task-commits → Task subjects fit 72 characters | Long group heading | evals/git-workflow/test_fit_subject.py | `test_group_subject_cut_at_word` | green |
| task-commits → Unfittable subject stops the commit | Prefix plus first word too long | evals/git-workflow/test_fit_subject.py | existing unfittable test | green |
| task-commits → Unfittable subject stops the commit | Group prefix plus first word too long | evals/git-workflow/test_fit_subject.py | `test_group_prefix_unfittable_exits_1` | green |
| task-commits → Commit granularity is a project setting | Setting unset | evals/git-workflow/test_grade.py, test_instructions.py | `test_task_mode_run_has_no_trailers`, `test_commit_reads_granularity_task_default` | green |
| task-commits → Commit granularity is a project setting | Unknown value | evals/git-workflow/test_instructions.py | `test_commit_stops_on_unknown_granularity` | green |
| task-commits → A group is committed once at its boundary | Two groups | evals/git-workflow/test_grade.py | `test_group_apply_two_commits_pass`, `test_group_apply_per_task_commits_fail` (eval-apply-groups) | green |
| task-commits → A group is committed once at its boundary | Shared file within a group | evals/git-workflow/test_grade.py | `test_group_apply_split_group_fails` (eval-apply-groups) | green |
| task-commits → A group is committed once at its boundary | Unowned edits present | evals/git-workflow/test_grade.py | `test_group_apply_swept_scratch_fails` (eval-apply-groups) | green |
| task-commits → A group is committed once at its boundary | Interrupted before the group is complete | evals/git-workflow/test_instructions.py | `test_commit_group_waits_for_every_task` | green |
| task-commits → One group is pending at a time | Groups run in parallel | evals/git-workflow/test_instructions.py | `test_commit_one_group_pending_at_a_time` | green |
| task-commits → One group is pending at a time | Group 1 commit fails | evals/git-workflow/test_instructions.py | `test_commit_one_group_pending_at_a_time` | green |
| task-commits → Group membership is exact | Group 1 and group 10 | evals/git-workflow/test_task_cover.py, test_grade.py | `test_group_ten_is_not_group_one`, `test_group_ten_tick_in_group_one_fails` (eval-apply-groups-ten) | green |
| task-commits → Group membership is exact | Missing heading | evals/git-workflow/test_task_cover.py | `test_group_without_heading_is_reported` | green |
| task-commits → Task evidence is a subject or a trailer | Exact match | evals/git-workflow/test_task_cover.py | `test_trailer_match_is_exact` | green |
| task-commits → Task evidence is a subject or a trailer | Task ID inside other text | evals/git-workflow/test_task_cover.py | `test_task_id_inside_text_is_not_evidence` | green |
| task-commits → Task evidence is a subject or a trailer | Task covered twice | evals/git-workflow/test_task_cover.py | `test_task_covered_twice_names_both` | green |
| task-commits → Task evidence is a subject or a trailer | Trailer outside its group | evals/git-workflow/test_task_cover.py | `test_cross_group_trailer_reported` | green |
| task-commits → An interrupted group resumes without loss | Resume in a fresh session | evals/git-workflow/test_grade.py | `test_group_resume_one_commit_pass` (eval-apply-groups-resume) | green |
| task-commits → An interrupted group resumes without loss | Group already partly committed | evals/git-workflow/test_task_cover.py, test_grade.py | `test_pending_excludes_covered_tasks`, `test_group_switch_mixed_pass` (eval-apply-groups-switch) | green |
| task-commits → An interrupted group resumes without loss | Two groups pending | evals/git-workflow/test_task_cover.py, test_instructions.py | `test_two_pending_groups_reported`, `test_commit_two_pending_groups_ask` | green |
| task-commits → A resumed red step is re-verified by its test | Red step ticked before the interruption | evals/git-workflow/test_grade.py, test_instructions.py | `test_group_resume_body_names_red_step` (eval-apply-groups-resume), `test_commit_resumed_red_step_rule` | green |
| task-commits → A resumed red step is re-verified by its test | Named test missing | evals/git-workflow/test_instructions.py | `test_commit_resumed_red_step_rule` | green |
| task-commits → Pending ticks wait for their group commit | Resume with a pending group and a planning edit | evals/git-workflow/test_grade.py | `test_group_resume_planning_commit_without_ticks` (eval-apply-groups-resume) | green |
| task-commits → Pending ticks wait for their group commit | First planning commit with ticks | evals/git-workflow/test_instructions.py | `test_commit_pending_ticks_wait_for_group` | green |
| task-commits → Grouping never rewrites history | Switching to group mode mid-change | evals/git-workflow/test_grade.py | `test_group_switch_mixed_pass`, `test_group_switch_rewritten_task_commit_fails` (eval-apply-groups-switch) | green |
| task-commits → Grouping never rewrites history | PR feedback after group commits | evals/git-workflow/test_instructions.py | `test_commit_never_regroups` | green |
| task-commits → End-of-apply check uses task evidence | Group mode complete | evals/git-workflow/test_grade.py | `test_completion_accepts_task_work_wording` (eval-apply-groups report) | green |
| task-commits → End-of-apply check uses task evidence | Lost coverage | evals/git-workflow/test_task_cover.py | `test_uncovered_ticked_task_reported` | green |
| planning-stores → Planning commits go to the store | Planning artifacts committed before the first task | evals/git-workflow/test_grade.py | existing eval-store-apply checks | green |
| planning-stores → Planning commits go to the store | Task commit for a store-backed change | evals/git-workflow/test_grade.py | existing eval-store-apply checks | green |
| planning-stores → Planning commits go to the store | Group commit for a store-backed change | evals/git-workflow/test_grade.py | `test_store_group_pair_pass`, `test_store_group_message_mismatch_fails` (eval-store-apply-groups) | green |
| planning-stores → Planning commits go to the store | Group with no code | evals/git-workflow/test_grade.py | `test_store_group_nocode_store_only_pass` (eval-store-group-noop) | green |
| planning-stores → Planning commits go to the store | Store on the wrong branch | evals/git-workflow/test_grade.py | existing eval-store-apply-wrong-branch checks | green |
| planning-stores → Task commit pairs are reconciled before new work | Normal code task | evals/git-workflow/test_grade.py | existing eval-store-apply checks | green |
| planning-stores → Task commit pairs are reconciled before new work | Store commit failed, apply resumes | evals/git-workflow/test_grade.py | existing eval-store-apply-reconcile checks | green |
| planning-stores → Task commit pairs are reconciled before new work | Group store half failed, apply resumes | evals/git-workflow/test_grade.py | `test_store_group_store_half_pass`, `test_store_group_store_half_duplicate_code_fails` (eval-store-group-store-half) | green |
| planning-stores → Task commit pairs are reconciled before new work | Group code half interrupted, apply resumes | evals/git-workflow/test_grade.py | `test_store_group_code_half_pass`, `test_store_group_code_half_lost_tick_fails` (eval-store-group-code-half) | green |
| planning-stores → Task commit pairs are reconciled before new work | Reconciliation cannot isolate the tick | evals/git-workflow/test_grade.py | existing eval-store-apply-multi-gap checks | green |
| planning-stores → A tick without a code commit is confirmed | Restart before a task's code commit | evals/git-workflow/test_grade.py | existing eval-store-apply-orphan-tick checks | green |
| planning-stores → A tick without a code commit is confirmed | No-op task's store commit failed | evals/git-workflow/test_grade.py | existing eval-store-apply-noop-gap checks | green |
| planning-stores → A tick without a code commit is confirmed | Group ticked, code tree clean | evals/git-workflow/test_grade.py | `test_store_group_noop_asks_first` (eval-store-group-noop) | green |
| planning-stores → Completion check covers both repos | All tasks committed in both repos | evals/git-workflow/test_grade.py | `test_completion_accepts_task_work_wording` plus existing eval-store-apply checks | green |
| planning-stores → Completion check covers both repos | Store has uncommitted tasks.md | evals/git-workflow/test_grade.py | existing eval-store-complete-gap checks | green |
| planning-stores → Completion check covers both repos | Group pair complete | evals/git-workflow/test_grade.py | `test_store_group_pair_pass` (eval-store-apply-groups report) | green |

## 1. ADR and architecture

- [x] 1.1 Write `docs/adr/0016-task-evidence-and-group-commits.md` (MADR-short, `Status: accepted`, today's date): task evidence is a subject starting `<type>(<change>): task X.Y ` or an exact `Specwright-Task:` trailer read by Git's parser; group commits at the boundary, one group pending at a time, never by rewriting history; rejected squash and subject ranges (design D1, D2). Add its row to the in-force index in `openspec/architecture.md`, add `task-cover.sh` to the `specwright-commit` component row, and add a Commits entry to the formats-parsed-by-later-runs list (`commit_granularity`, the trailer, the `group N` subject; changing them is a minor version). Verify `python evals/run.py --changed main` passes the map test and `grep -n 0016 openspec/architecture.md` shows the row.

## 2. Task evidence script

- [x] 2.1 Write failing tests in `evals/git-workflow/test_task_cover.py`, each on a scratch git repo with a `tasks.md`: every `test_task_cover.py` row of the test map, plus `tasks.md` over 1 MiB → exit 2 `tasks_too_large` and a range over 10 000 commits → exit 1 `range_too_large` (bound patched low by environment for the test). Verify they fail because `task-cover.sh` does not exist.
- [x] 2.2 Implement `skills/specwright-commit/scripts/task-cover.sh --repo <dir> --range <a>..<b> --tasks <tasks.md> --change <name>`: bash entry finding Python 3.8+ as `pr-pair.sh:68-72` does, one JSON document (`tasks` with id, group, ticked, commits {sha, form}; `groups` with heading; `pending_groups`; `uncovered`; `duplicates`; `cross_group`; `missing_headings`), exit 0/1/2/3, read-only git (`git log -z --format=%H%x00%s%x00%(trailers:key=Specwright-Task,valueonly,separator=%x2C)`), bounds from design Resource Bounds. Subject evidence only on the `<type>(<change>): task X.Y ` prefix. Verify the 2.1 tests pass and flip their rows green.

## 3. Group subjects

- [x] 3.1 Write failing tests `test_group_subject_cut_at_word` and `test_group_prefix_unfittable_exits_1` in `evals/git-workflow/test_fit_subject.py`. Verify they fail on today's exit 2.
- [x] 3.2 Extend `skills/specwright-commit/scripts/fit-subject.sh` to accept `<type>(<scope>): group N ` alongside the task prefix (header comment and exit 2 message updated). Verify all of `test_fit_subject.py` passes and flip the two rows green.

## 4. Commit rules, schema and docs

- [x] 4.1 Write failing instruction tests in `evals/git-workflow/test_instructions.py` for every `test_instructions.py` row of the test map: setting read once with `task` default and unknown-value stop; group commit at the boundary with trailers in the final trailer block before `Co-authored-by`; one group pending at a time; pending ticks kept out of planning and amendment commits; resume of one pending group, two pending groups asked; red-step re-verification; no amend/squash/regroup and mixed groups reported; `task-cover.sh` used in Reconcile and the end check; store group pair code first with one message file and `Code-Changes: none`. Also the schema apply instruction no longer says only "commit task by task". Verify they fail.
- [x] 4.2 Rewrite `skills/specwright-commit/SKILL.md` sections 1-3 and Reconcile for both modes (design D1-D7, Flow & State Gaps), keeping task mode's per-task text and subjects unchanged, and its completion report as `<N> tasks, <M> task-work commits, tree clean`. Update the description line, `schemas/specwright/schema.yaml` apply instruction ("commit per the configured granularity"), `templates/openspec/specwright.yaml` (commented `commit_granularity: task`), `README.md` (feature line, apply rows, commit-message table with the group subject and trailer, config section), and `CONTRIBUTING.md`. Run `openspec schema validate specwright`. Verify the 4.1 tests pass and flip their rows green.

## 5. Evals for group apply and recovery

- [x] 5.1 Write failing grader tests in `evals/git-workflow/test_grade.py` for every `test_grade.py` row of the test map, on synthetic repos built from new fixtures in `evals/git-workflow/fixtures.py`: a groups change (1.1-1.3 sharing `greet.py`, 2.1-2.2), a groups-and-ten change (groups 1 and 10), a resume state (1.1 red step and 1.2 ticked, uncommitted, plus an uncommitted `design.md` edit), a switch state (1.1 committed per task), and store states (code half interrupted, store half failed, group 3 no code with a clean code tree). The grader matches evidence with its own parsing of `git log` subjects and `git interpret-trailers --parse`, not `task-cover.sh`. Update `completion_by_repo` to accept `task-work commit` as well as `task commit`. Verify they fail.
- [x] 5.2 Add the eval cases to `evals/git-workflow/evals.json` (`eval-apply-groups`, `eval-apply-groups-ten`, `eval-apply-groups-resume`, `eval-apply-groups-switch`, `eval-store-apply-groups`, `eval-store-group-code-half`, `eval-store-group-store-half`, `eval-store-group-noop`), their fixture builders, and their `grade.py` checks. Keep `eval-apply-three-tasks` unchanged as the task-mode case, with the new no-trailer check. Verify `python evals/run.py --changed main` passes and flip the 5.1 rows green.
- [ ] 5.3 Run the eval cases of 5.2 with skill-creator (with-skill runs) and grade them with `python evals/git-workflow/grade.py <iteration-dir>`; every assertion passes, `eval-apply-groups` showing exactly two task-work commits with trailers for all five tasks. Record the iteration directory and pass counts in the commit body.

## 6. Release

- [ ] 6.1 Run `release.sh bump --to 0.10.0` and rewrite the summary of the proposal's `## Release Notes` section to describe the whole release. Verify `release.sh check` and `release.sh notes --proposal openspec/changes/commit-per-task-group/proposal.md` both exit 0, and `python evals/run.py --changed main` passes.
