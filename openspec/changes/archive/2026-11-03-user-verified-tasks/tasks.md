# Tasks

## Test map

`task-cover.sh` behaviour is tested against real fixture repositories in `evals/git-workflow/test_task_cover.py`. Every other rule is a wording check in the new `evals/git-workflow/test_user_tasks.py`, in the style of `evals/git-workflow/test_instructions.py`: it asserts where each rule sits and its key terms in the delivered schema, templates, skills and agent definitions. A wording check shows the rule is in the instructions, not that a live agent follows it.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| user-tasks → A task can be marked as the user's | Kinds are reported | evals/git-workflow/test_task_cover.py | test_task_kinds_reported | green |
| user-tasks → A task can be marked as the user's | Marker not at the start of the text | evals/git-workflow/test_task_cover.py | test_marker_elsewhere_or_other_case_is_agent | green |
| user-tasks → A task can be marked as the user's | Ticked user task | evals/git-workflow/test_task_cover.py | test_ticked_user_task_not_waiting | green |
| user-tasks → An agent never ticks or delegates a user task | Apply skips a user task | evals/git-workflow/test_user_tasks.py | test_apply_skips_and_never_dispatches_user_tasks | green |
| user-tasks → An agent never ticks or delegates a user task | Packet with a user task | evals/git-workflow/test_user_tasks.py | test_implementers_refuse_user_tasks | green |
| user-tasks → An agent never ticks or delegates a user task | User says it passed in chat | evals/git-workflow/test_user_tasks.py | test_chat_report_asks_user_to_tick | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence present | evals/git-workflow/test_task_cover.py | test_evidence_present_not_missing | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence file missing | evals/git-workflow/test_task_cover.py, evals/git-workflow/test_user_tasks.py | test_evidence_file_missing_reported, test_commit_stops_on_evidence_missing | green |
| user-tasks → An evidence task is ticked only with its evidence | Evidence only in the working tree | evals/git-workflow/test_task_cover.py | test_evidence_untracked_is_missing | green |
| user-tasks → An evidence task is ticked only with its evidence | Store-backed evidence | evals/git-workflow/test_task_cover.py | test_store_backed_evidence_read_from_tasks_repo | green |
| user-tasks → An evidence task is ticked only with its evidence | No evidence path named | evals/git-workflow/test_task_cover.py | test_evidence_without_path_reported | green |
| user-tasks → The test map can point a scenario at a user task | Person-judged scenario | evals/git-workflow/test_user_tasks.py | test_test_map_user_state | green |
| user-tasks → The test map can point a scenario at a user task | Testable scenario mapped to a user task | evals/git-workflow/test_user_tasks.py | test_review_flags_testable_scenario_on_user_task | green |
| user-tasks → A user-verified exit criterion reaches the tasks | Criterion carried to a task | evals/git-workflow/test_user_tasks.py | test_user_criterion_becomes_user_task | green |
| user-tasks → A user-verified exit criterion reaches the tasks | Criterion judged only at close | evals/git-workflow/test_user_tasks.py | test_criterion_at_close_explained_in_proposal | green |
| user-tasks → Archive and verify wait for the user | Archive with a user task open | evals/git-workflow/test_user_tasks.py | test_archive_context_line_stops_on_user_task | green |
| user-tasks → Archive and verify wait for the user | User ticks, then archive | evals/git-workflow/test_user_tasks.py | test_archive_gate_only_on_unticked | green |
| user-tasks → Archive and verify wait for the user | Archived with a user task open | evals/git-workflow/test_user_tasks.py | test_finish_checks_archived_user_tasks | green |
| user-tasks → The agent merge waits for the user | Agent merge waits | evals/git-workflow/test_user_tasks.py | test_watch_waits_on_user_before_archive_and_merge | green |
| user-tasks → The agent merge waits for the user | Tick arrives while waiting | evals/git-workflow/test_user_tasks.py | test_watch_rejudges_after_tick | green |
| user-tasks → The agent merge waits for the user | Archived task unticked by a later commit | evals/git-workflow/test_task_cover.py | test_rev_reads_archived_tasks_at_commit | green |
| user-tasks → The agent merge waits for the user | Local copy differs from the ready head | evals/git-workflow/test_task_cover.py | test_rev_ignores_working_tree | green |
| user-tasks → The agent merge waits for the user | tasks.md unreadable at the ready head | evals/git-workflow/test_task_cover.py, evals/git-workflow/test_user_tasks.py | test_rev_missing_file_exits_2, test_watch_unknown_user_check_blocks_merge | green |
| task-commits → A group is committed once at its boundary | Two groups | evals/git-workflow/test_grade.py | test_group_apply_two_commits_pass | green |
| task-commits → A group is committed once at its boundary | Shared file within a group | evals/git-workflow/test_grade.py | test_group_apply_split_group_fails | green |
| task-commits → A group is committed once at its boundary | Unowned edits present | evals/git-workflow/test_grade.py | test_group_apply_swept_scratch_fails | green |
| task-commits → A group is committed once at its boundary | Interrupted before the group is complete | evals/git-workflow/test_instructions.py | test_commit_group_waits_for_every_task | green |
| task-commits → A group is committed once at its boundary | Group with a user task | evals/git-workflow/test_user_tasks.py | test_group_commit_skips_user_tasks | green |
| task-commits → End-of-apply check uses task evidence | Group mode complete | evals/git-workflow/test_grade.py | test_completion_accepts_task_work_wording | green |
| task-commits → End-of-apply check uses task evidence | Lost coverage | evals/git-workflow/test_task_cover.py | test_uncovered_ticked_task_reported | green |
| task-commits → End-of-apply check uses task evidence | User task still open | evals/git-workflow/test_user_tasks.py | test_completion_reports_waiting_on_user | green |
| task-commits → An interrupted group resumes without loss | Resume in a fresh session | evals/git-workflow/test_grade.py | test_group_resume_one_commit_pass | green |
| task-commits → An interrupted group resumes without loss | Group already partly committed | evals/git-workflow/test_task_cover.py | test_pending_excludes_covered_tasks | green |
| task-commits → An interrupted group resumes without loss | Two groups pending | evals/git-workflow/test_task_cover.py | test_two_pending_groups_reported | green |
| task-commits → An interrupted group resumes without loss | Interrupted group plus a user tick | evals/git-workflow/test_task_cover.py | test_user_tick_never_makes_group_pending | green |
| task-commits → An interrupted group resumes without loss | All-user group | evals/git-workflow/test_task_cover.py | test_all_user_group_never_pending | green |
| task-commits → User ticks ride the next tasks.md commit | User tick with nothing pending | evals/git-workflow/test_task_cover.py, evals/git-workflow/test_user_tasks.py | test_user_task_trailer_covers, test_record_user_checks_commit | green |
| task-commits → User ticks ride the next tasks.md commit | Two user ticks at once | evals/git-workflow/test_task_cover.py | test_two_user_trailers_cover_both | green |
| task-commits → User ticks ride the next tasks.md commit | User tick while a group is pending | evals/git-workflow/test_task_cover.py | test_user_trailer_on_group_commit_not_cross_group | green |
| task-commits → User ticks ride the next tasks.md commit | Trailer for an agent task | evals/git-workflow/test_task_cover.py | test_user_trailer_does_not_cover_agent_task | green |

## 1. The contract

- [x] 1.1 Write `docs/adr/0024-tasks-the-user-checks-are-marked-and-only-the-user-ticks-them.md` (MADR-short, `Status: accepted`, today's date) from design D1, D2, D3 and D6, and add its row to the in-force ADR index in `openspec/architecture.md`, plus a Contracts bullet for the `[user]`/`[evidence]` markers and the `Specwright-User-Task` trailer. Verify that the ADR file exists, the index row and bullet are present, and `python -m unittest evals/runner/test_suite_map.py` passes.

## 2. task-cover.sh reads kinds, user ticks, evidence and a revision

- [x] 2.1 Add the red tests to `evals/git-workflow/test_task_cover.py` for every `test_task_cover.py` row marked red in the test map (kinds, marker position and case, ticked user task, evidence present/missing/no path, `Specwright-User-Task` coverage and its rules, user ticks never pending, `--rev` reading the active or archived `tasks.md` at a commit and ignoring the working tree, a missing file at the revision exiting 2). Run `python -m unittest evals/git-workflow/test_task_cover.py` and confirm each new test fails because the field or option is missing, not because of a fixture error.
- [x] 2.2 Implement in `skills/specwright-commit/scripts/task-cover.sh` (design D3, D4): `kind` per task from an exact lowercase `[user]` or `[evidence]` first token after the id; `waiting_on_user`; `user_uncommitted`; `evidence_missing` (a ticked evidence task whose text names no `evidence/` path, or whose file under the change folder is missing or empty); `Specwright-User-Task` trailers count as coverage for user tasks only and never as cross-group; `uncovered` and `pending_groups` count agent and evidence tasks only; `--rev <sha>` reads `--tasks` with `git show <sha>:<path>` from `--repo` and checks evidence at that revision, exiting 2 when the file is absent there. Update the script's header comment. Verify `python -m unittest evals/git-workflow/test_task_cover.py` passes (old and new tests) and flip the rows green.

## 3. Planning and apply rules

- [x] 3.1 Create `evals/git-workflow/test_user_tasks.py` with the red tests for the rows of the "never ticks or delegates", "test map", "exit criterion" requirements (rows for apply, implementers, chat report, test map state, review finding, criterion carry-through and close). Run `python -m unittest evals/git-workflow/test_user_tasks.py` and confirm each fails because the rule is missing.
- [x] 3.2 In `schemas/specwright/schema.yaml`: the tasks instruction gains the `[user]` and `[evidence]` markers with one example each, the test map state `user` for a scenario only a person can judge (turning `green` when its user task is ticked), the evidence rule (one `evidence/` path under the change, ticked only when present, non-empty and committed), and the exit-criterion carry-through (a `[user]` task per user-verified criterion the proposal names, or the proposal says it is judged at close and why); the proposal instruction asks the proposal to say so; the review instruction lists a testable scenario mapped to a user task as a finding; the apply instruction never ticks, implements or dispatches a `[user]` task to any implementer or worker, skips it, lists it as waiting on the user, and asks the user to tick it in `tasks.md` when they report a result in chat. Add the marker examples to `schemas/specwright/templates/tasks.md`. In all four implementer definitions under `agents/claude/` and `agents/omp/`, a `[user]` task in a packet is refused as BLOCKED. Verify the rows pass, `openspec schema validate specwright` passes, and flip them green.

## 4. Commit rules

- [x] 4.1 Add the red tests for `test_group_commit_skips_user_tasks`, `test_completion_reports_waiting_on_user`, `test_commit_stops_on_evidence_missing` and `test_record_user_checks_commit` to `evals/git-workflow/test_user_tasks.py` and confirm they fail for the right reason.
- [x] 4.2 In `skills/specwright-commit/SKILL.md`: group completeness counts agent and evidence tasks only and never ticks a user task; every commit that stages `tasks.md` carries a `Specwright-User-Task: X.Y` trailer for each tick in `user_uncommitted`; with no agent work pending, `tasks.md` alone is committed as `<type>(<change-name>): record user checks <ids>`; Reconcile lists `user_uncommitted` apart from pending groups; the end-of-apply check stops on `evidence_missing`, reports `waiting on the user: <ids>` and hands off with user tasks open. Verify the four rows pass and flip them green.

## 5. Archive, verify and merge gates

- [x] 5.1 Add the red tests for the "Archive and verify wait for the user" and "The agent merge waits for the user" wording rows to `evals/git-workflow/test_user_tasks.py` and confirm they fail for the right reason.
- [x] 5.2 Add the context lines to `templates/openspec/config.yaml`: before archiving, an unticked `[user]` task in the change's `tasks.md` stops the archive (move nothing, sync no spec, name the tasks; in a bulk archive skip that change); verify reports unticked `[user]` tasks as waiting on the user and never reports the change verified. In `skills/specwright-finish/SKILL.md` step 0, run `task-cover.sh` on the archived `tasks.md` and stop on `waiting_on_user` with the same undo plan as DEFERRED. In `skills/specwright-pr/SKILL.md` watch, before archive and before every merge request, run `task-cover.sh --rev <ready head>` on the planning repo's active, else archived, `tasks.md`: `waiting_on_user` → report `ready, waiting on the user: <ids>`, no archive, no merge; exit 2 or 3 → report the user-task check as unknown and send no merge request; a new head after the tick is judged as usual. Verify the rows pass and flip them green.

## 6. Docs and coverage

- [x] 6.1 Add a short "Tasks only you can tick" paragraph to `README.md` (markers, what apply, archive and the agent merge do, how to tick), and run `python -m unittest evals/runner/test_suite_map.py`; add a rule to `evals/suites.json` for `evals/git-workflow/test_user_tasks.py` if it is reported uncovered. Verify the map test passes.

## 7. Release

- [x] 7.1 Run `release.sh bump --to 0.18.0`, rewrite the summary of the proposal's `## Release Notes` to describe the whole release, and verify with `release.sh check` and `release.sh notes --proposal openspec/changes/user-verified-tasks/proposal.md`.

## Workflow follow-up

- Pre-ship review, PR, watch, archive and the v0.18.0 release follow the usual `finish: pr` flow.
