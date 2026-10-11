# Tasks

## Test map

Text checks in `evals/git-workflow/test_instructions.py` prove that a rule is in the instructions, by position and key terms. Agent evals in `evals/git-workflow/evals.json` (fixtures in `fixtures.py`, graded by `grade.py <iteration-dir>`) prove that a live agent follows it on the paths that change branch state. Script behaviour runs through `bash` against real git repos and the fake `gh`, in `evals/pr-pair/test_pr_pair.py`.

The split-off `planning-stores` requirements (#66) state behaviour that already ships. Their new tests are expected to pass on the first run; a failure there is a defect to debug with `specwright-debug`, not a red step. Green rows are unchanged scenarios carried in a MODIFIED requirement; group 1 re-runs them.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| project-planning → A milestone end offers close, not a new change | All changes done, criteria not yet walked | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_roadmap_next_offers_close_at_milestone_end; eval-roadmap-next-milestone-end | green |
| project-planning → A milestone end offers close, not a new change | Next milestone already split | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_roadmap_next_starts_only_now_changes; eval-roadmap-next-milestone-end | green |
| project-planning → A milestone end offers close, not a new change | Status at a milestone end | evals/git-workflow/test_instructions.py | test_roadmap_status_names_milestone_end | green |
| project-planning → A milestone end offers close, not a new change | Last change archived but code pending | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_roadmap_milestone_end_needs_every_change_done; eval-store-roadmap-local | green |
| project-planning → Finish offers close after the milestone's last change | Last change of the milestone merged | evals/git-workflow/test_instructions.py | test_finish_offers_close_after_last_change | green |
| project-planning → Finish offers close after the milestone's last change | Changes left in the milestone | evals/git-workflow/test_instructions.py | test_finish_offers_close_after_last_change | green |
| project-planning → An agreed Next split is recorded | Author agrees a Next split at init | evals/git-workflow/test_instructions.py | test_roadmap_init_records_agreed_next_split | green |
| project-planning → An agreed Next split is recorded | Close records a split agreed for the new Next | evals/git-workflow/test_instructions.py | test_roadmap_close_records_agreed_split_for_new_next | green |
| project-planning → An agreed Next split is recorded | Init without an agreed Next split | evals/git-workflow/test_instructions.py | test_roadmap_init_records_agreed_next_split | green |
| project-planning → Close keeps an agreed Next split | Close promotes an agreed split | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_roadmap_close_keeps_agreed_split; eval-roadmap-close-agreed-split | green |
| project-planning → Close keeps an agreed Next split | Close finds a reason to amend the agreed split | evals/git-workflow/test_instructions.py | test_roadmap_close_proposes_split_amendments | green |
| project-planning → Close keeps an agreed Next split | Next without a split | evals/git-workflow/test_instructions.py | test_roadmap_close_keeps_agreed_split | green |
| project-planning → Close keeps an agreed Next split | Next lists changes without a recorded agreement | evals/git-workflow/test_instructions.py | test_roadmap_close_asks_about_unmarked_split | green |
| project-planning → Gap-closing roadmap edit is committed on the new change's branch | Criterion fails with no change left | evals/git-workflow/evals.json | eval-roadmap-next-gap (prompt now runs close) | green |
| project-planning → Gap-closing roadmap edit is committed on the new change's branch | Branch gate stops | evals/git-workflow/evals.json | eval-roadmap-next-gap-dirty-main (prompt now runs close) | green |
| project-planning → Gap-closing roadmap edit is committed on the new change's branch | No criterion shown failing | evals/git-workflow/test_instructions.py | test_roadmap_gap_change_needs_a_shown_failure | green |
| planning-stores → A failed store gate branch leaves no new branch | Store hook fails after the branch is created | evals/git-workflow/test_instructions.py | test_roadmap_store_branch_error_rolls_back_every_branched_repo | green |
| planning-stores → A failed store gate branch leaves no new branch | Store hook fails after the code branch exists | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_branch_store_error_rolls_back_every_branched_repo; eval-store-branch-hook-fail | green |
| planning-stores → A failed store gate branch leaves no new branch | Code hook fails after the store branch exists | evals/git-workflow/test_instructions.py; evals/git-workflow/evals.json | test_roadmap_store_branch_error_rolls_back_every_branched_repo; eval-store-roadmap-close-hook-fail | green |
| planning-stores → A failed store gate branch leaves no new branch | Branch creation refused outright | evals/git-workflow/test_instructions.py | test_roadmap_store_branch_error_rolls_back_every_branched_repo | green |
| planning-stores → A failed store gate branch leaves no new branch | One repo cannot switch back | evals/git-workflow/test_instructions.py | test_gate_rollback_judges_switch_by_current_branch | green |
| planning-stores → A failed store gate branch leaves no new branch | Gate passes without errors | evals/git-workflow/evals.json | eval-store-branch-clean | green |
| planning-stores → Git network reads authenticate as each repo's login | Store and code logins differ | evals/pr-pair/test_pr_pair.py | test_rounds_reads_each_remote_as_its_login | green |
| planning-stores → Git network reads authenticate as each repo's login | Code remote accepts only the code login | evals/pr-pair/test_pr_pair.py | test_code_remote_reads_keep_the_code_login | green |
| planning-stores → A snapshot counts only for the PR and head discovery reports | Snapshot matches discovery | evals/pr-pair/test_pr_pair.py | test_pair_state_ready_only_when_both_pass | green |
| planning-stores → A snapshot counts only for the PR and head discovery reports | Code snapshot of an old head | evals/pr-pair/test_pr_pair.py | test_pair_state_refreshes_an_old_head_code_snapshot | green |
| planning-stores → Fix rounds are counted across both branches | Round below the limit | evals/pr-pair/test_pr_pair.py | test_rounds_store_only_round_makes_the_next_pass_round_two | green |
| planning-stores → Fix rounds are counted across both branches | Trailer and legacy commits mixed | evals/pr-pair/test_pr_pair.py | test_rounds_ignores_code_subjects_when_store_has_a_trailer | green |
| planning-stores → A pass record is removed only when its pass is done | Every step done | evals/pr-pair/test_pr_pair.py | test_pass_done_removes_a_finished_record | green |
| planning-stores → A pass record is removed only when its pass is done | Reply posted, push missing | evals/pr-pair/test_pr_pair.py | test_pass_done_keeps_record_while_store_push_pending | green |
| planning-stores → Commands run where they resolve correctly | Store push with a repository-local auth header | evals/pr-pair/test_as_sh.py | test_scrubs_header_local_to_the_store | green |
| planning-stores → Commands run where they resolve correctly | Store login override | evals/pr-pair/test_pr_pair.py | test_context_login_per_repo | green |
| planning-stores → Commands run where they resolve correctly | Schema lookup with a root nested in the store repo | evals/git-workflow/evals.json | eval-install-nested-store | green |
| planning-stores → Commands run where they resolve correctly | Private store readable only by the store login | evals/pr-pair/test_pr_pair.py | test_rounds_and_pass_plan_read_a_private_store_remote_as_the_store_login | green |
| planning-stores → Commands run where they resolve correctly | Store login has no credential | evals/pr-pair/test_pr_pair.py | test_store_git_reads_stop_without_a_store_credential | green |
| planning-stores → Watch covers the expected PR set | Code PR green, store PR waiting | evals/pr-pair/test_pr_pair.py | test_pair_state_waits_for_both | green |
| planning-stores → Watch covers the expected PR set | Store PR alone is ready | evals/pr-pair/test_pr_pair.py | test_pair_state_single_store_pr_ready | green |
| planning-stores → Watch covers the expected PR set | One PR of the pair merged | evals/pr-pair/test_pr_pair.py | test_pair_state_split_hands_off | green |
| planning-stores → Watch covers the expected PR set | Archive before merge with no store PR | evals/git-workflow/evals.json | eval-store-archive-before-merge-local-store | green |
| planning-stores → Watch covers the expected PR set | Store snapshot of an old head | evals/pr-pair/test_pr_pair.py; evals/pr-pair/test_skill_text.py | test_pair_state_refreshes_an_old_head_snapshot; test_watch_refreshes_on_a_refresh_blocker | green |
| planning-stores → Watch covers the expected PR set | Snapshot of another PR | evals/pr-pair/test_pr_pair.py; evals/pr-pair/test_skill_text.py | test_pair_state_refreshes_a_snapshot_of_another_pr; test_watch_moves_its_wait_to_the_replaced_pr | green |
| planning-stores → Watch covers the expected PR set | Snapshot without a head | evals/pr-pair/test_pr_pair.py | test_pair_state_refreshes_a_snapshot_without_a_head | green |
| planning-stores → Feedback rounds span the PR pair | Spec fix requested on the code PR | evals/pr-pair/test_pr_pair.py | test_pass_plan_routes_spec_fix_to_store | green |
| planning-stores → Feedback rounds span the PR pair | Round limit across both repos | evals/pr-pair/test_pr_pair.py | test_rounds_highest_across_branches | green |
| planning-stores → Feedback rounds span the PR pair | Finishing an interrupted final pass | evals/pr-pair/test_pr_pair.py | test_pass_plan_final_pass_push_pending | green |
| planning-stores → Feedback rounds span the PR pair | Recovered partial fix | evals/pr-pair/test_pr_pair.py | test_rounds_ignores_subject_count_when_trailers_exist | green |
| planning-stores → Feedback rounds span the PR pair | Legacy branch without trailers | evals/pr-pair/test_pr_pair.py | test_rounds_legacy_subject_count_without_trailers | green |
| planning-stores → An interrupted feedback pass is completed first | Interrupted between the two fix commits | evals/pr-pair/test_pr_pair.py | test_pass_plan_missing_store_commit | green |
| planning-stores → An interrupted feedback pass is completed first | Interrupted after both pushes | evals/pr-pair/test_pr_pair.py | test_pass_plan_rerequest_and_replies_pending | green |
| planning-stores → An interrupted feedback pass is completed first | Commit made but not recorded | evals/pr-pair/test_pr_pair.py | test_pass_plan_commit_found_by_trailer | green |
| planning-stores → An interrupted feedback pass is completed first | Reply posted, then its resolution failed | evals/pr-pair/test_pr_pair.py | test_pass_plan_reply_done_resolution_pending | green |
| planning-stores → An interrupted feedback pass is completed first | Reviewer follow-up during the interruption | evals/pr-pair/test_pr_pair.py | test_pass_plan_stale_disposition_stops | green |
| planning-stores → An interrupted feedback pass is completed first | Interrupted halfway through a spec fix | evals/pr-pair/test_pr_pair.py | test_pass_plan_partial_edit_not_committable | green |
| planning-stores → An interrupted feedback pass is completed first | Review requests disabled | evals/pr-pair/test_pr_pair.py | test_pass_plan_rerequest_not_applicable | green |
| planning-stores → An interrupted feedback pass is completed first | Pass with an open question thread | evals/pr-pair/test_pr_pair.py | test_pass_plan_question_thread_done_when_replied | green |
| planning-stores → An interrupted feedback pass is completed first | Reply posted, reaction not sent | evals/pr-pair/test_pr_pair.py | test_pass_plan_reaction_todo_until_github_shows_it | green |
| planning-stores → An interrupted feedback pass is completed first | Reaction already present | evals/pr-pair/test_pr_pair.py | test_pass_plan_reaction_done_when_present | green |
| planning-stores → An interrupted feedback pass is completed first | Code PR adopted before the pair was linked | evals/pr-pair/test_pr_pair.py | test_pass_plan_adopted_code_pr_needs_the_link | green |

## 1. Planning-stores requirements pass strict validation (#66, D4, D5)

- [x] 1.1 Add `evals/git-workflow/test_specs_strict.py`. It copies `openspec/` to a temp directory, runs `openspec archive <name> --yes` there for every active change (`openspec list --json`), then `openspec validate --specs --strict`, and asserts exit 0 with the CLI output in the failure message. It skips, naming the missing CLI, when `openspec` is not on `PATH`. Its helper takes the list of changes to archive. Red evidence: call the helper with no changes and confirm it fails on `spec/planning-stores` with the four over-500-character warnings. Then confirm the test passes with this change active.
- [x] 1.2 Add the tests for the split-off requirements in `evals/pr-pair/test_pr_pair.py`, reusing the existing fixtures: `test_rounds_reads_each_remote_as_its_login`, `test_code_remote_reads_keep_the_code_login`, `test_pair_state_refreshes_an_old_head_code_snapshot`, `test_rounds_store_only_round_makes_the_next_pass_round_two`, `test_rounds_ignores_code_subjects_when_store_has_a_trailer`, `test_pass_done_removes_a_finished_record` and `test_pass_done_keeps_record_while_store_push_pending`. Verify that each passes. A failure is a defect: stop and debug it before going on. Flip those rows green.
- [x] 1.3 Re-run the green `planning-stores` rows: `python -m unittest discover evals/pr-pair`, which must pass. The `evals.json` green rows are not affected by a text split, so they need no re-run. Verify `openspec validate fix-roadmap-milestone-end --strict` passes.

## 2. Store gates roll back a failed `git checkout -b` (#60, D3)

- [x] 2.1 Write the failing text checks in `evals/git-workflow/test_instructions.py`:
  - Rewrite `test_roadmap_store_checks_code_repo_before_any_branch`'s step 3 assertions as `test_roadmap_store_branch_error_rolls_back_every_branched_repo`. After any `git checkout -b` error, each repo where the gate ran it and `<branch>` exists is switched to main and `<branch>` deleted with `git branch -d`, then the lock is released and the error shown. Its step 2 assertions stay in the original test.
  - `test_branch_store_error_rolls_back_every_branched_repo`, the same for `specwright-branch` Store-backed changes step 3, including the code-side error.
  - `test_gate_rollback_judges_switch_by_current_branch`: both skills check `git branch --show-current`, not the switch's exit status; a repo still on `<branch>` keeps it, the other repo is still rolled back, and the stop names that repo and both branches.

  Verify that they fail against the current text.
- [x] 2.2 Rewrite `skills/specwright-roadmap/SKILL.md` Committing project files step 3 and `skills/specwright-branch/SKILL.md` Store-backed changes step 3 as the single rule in D3. Keep the lock release in step 4 and every other stop unchanged. Verify that the 2.1 tests and the rest of `test_instructions.py` pass, and flip the rows green.
- [x] 2.3 Add the agent evals to `evals/git-workflow/evals.json`, `fixtures.py` and `grade.py`:
  - `eval-store-roadmap-close-hook-fail`: local mode, planning in a store, M1 done with a passing agent criterion, the roadmap in the code repo. The code repo's `.git/hooks/post-checkout` exits 1 and the store has no hook. Prompt: close M1.
  - `eval-store-branch-hook-fail`: a clean store pair. The store's `post-checkout` exits 1. Prompt: start change `add-csv-export`, scaffold only.

  Grade both: each repo on main, the new branch in neither, no gate lock, mains unchanged, no change directory, no amend, and the report quotes the hook failure. The fixture writes a POSIX `sh` hook, which Git for Windows runs through its bundled shell. Verify with one graded run of each (`python evals/git-workflow/grade.py <iteration-dir>`). Verify too that `eval-store-roadmap-close-locked` and `eval-store-branch-clean` still pass. Flip those rows green.
- [x] 2.4 Update `openspec/architecture.md`'s Resource bounds and failure visibility "Store gate" row: a `git checkout -b` that errors is rolled back in every repo the gate branched (#60). Do not edit the frozen Known gaps table or any accepted ADR. Verify by reading the row.

## 3. Milestone end, kept split and finish offer (#51, D1, D2)

- [x] 3.1 Write the failing text checks in `evals/git-workflow/test_instructions.py` for the project-planning rows:
  - `test_roadmap_next_offers_close_at_milestone_end`
  - `test_roadmap_next_starts_only_now_changes`
  - `test_roadmap_status_names_milestone_end`
  - `test_roadmap_milestone_end_needs_every_change_done`: a planning-merged/code-pending change is not done, so it does not count toward a milestone end.
  - `test_finish_offers_close_after_last_change`: the offer is close when every Now change is done, next otherwise, never both.
  - `test_roadmap_init_records_agreed_next_split`: init splits only Now unless the author agrees a Next split, recorded as a `Split agreed:` line; the roadmap template documents the line.
  - `test_roadmap_close_records_agreed_split_for_new_next`
  - `test_roadmap_close_keeps_agreed_split`: names and order kept, the line dropped on promotion, a Next without changes split as before.
  - `test_roadmap_close_proposes_split_amendments`
  - `test_roadmap_close_asks_about_unmarked_split`
  - `test_roadmap_gap_change_needs_a_shown_failure`: the gap path only for a criterion close found failing or the user reports failing.

  Verify that they fail against the current text.
- [x] 3.2 Edit `skills/specwright-roadmap/SKILL.md`:
  - **next** step 3: the milestone end comes first, then the existing planned-change and gap paths, the gap path now limited to a shown failure.
  - **close** step 5: keep a marked split, propose amendments, ask about an unmarked list, drop the line on promotion, and record a split agreed for the new Next.
  - **init** step 6 roadmap rules: the agreed Next split exception and its line.
  - **status**: `milestone end: run close`.
  - The front-matter description, if its wording of next or close changes.

  Edit `skills/specwright-roadmap/references/roadmap.md`: the Next section's comment and an example `**Split agreed:** <YYYY-MM-DD>` line with a Changes list. Verify that the 3.1 roadmap tests pass.
- [x] 3.3 Edit `skills/specwright-finish/SKILL.md`'s roadmap offer (the paragraph after "After the PR is merged") to the decisive form. Verify that `test_finish_offers_close_after_last_change` passes, and flip the 3.1 rows green.
- [x] 3.4 Agent evals in `evals/git-workflow/evals.json`, `fixtures.py` and `grade.py`:
  - `eval-roadmap-next-milestone-end`: repo-local, local mode. M1's only change is done; its exit criterion is user-verified with no recorded result. Next (M2) lists two changes with `**Split agreed:** 2026-10-01`. Prompt: run next. Grade: still on main, main unchanged, no new branch, no change directory, a clean tree, and the report offers close and names no M2 change to start.
  - `eval-roadmap-close-agreed-split`: the same roadmap, but the M1 criterion is agent-verified and passes. Prompt: close M1; the user agrees any question with the recommended default. Grade: main has `merge: docs/close-m1`. The roadmap's Now is M2 with the same two changes in the same order and no `Split agreed:` line. M1 is in Done with a date. No `docs/close-m1` branch is left.
  - Change the prompts of `eval-roadmap-next-gap` and `eval-roadmap-next-gap-dirty-main` from next to close. Close finds the criterion failing and proposes the gap change, which the user accepts as `add-farewell`. Their assertions stay unchanged.

  Verify with one graded run of each of the four cases, and that `eval-store-roadmap-local` still passes. Flip those rows green.
- [x] 3.5 Check the README against the behaviour (CONTRIBUTING "README follows behaviour"): the "whole project" line (next to start each change, close to finish a milestone) and the `specwright-roadmap` row of the skills table. Update them where the milestone end or the agreed split changes what they say. Verify by naming the sections checked in the commit body.

## 4. Release 0.1.12

- [x] 4.1 Bump to 0.1.12: `VERSION`, the README badge and `metadata.version` in all six `skills/*/SKILL.md`. Verify with `grep -rn "0\.1\.1[12]" VERSION README.md skills/*/SKILL.md`: only 0.1.12 appears where a version belongs.

## 5. Integration checks

- [x] 5.1 Run `python -m unittest discover evals/pr-pair` and `python -m unittest discover evals/git-workflow`. Both must pass. Every Test map row must be green.
- [x] 5.2 Run `openspec validate fix-roadmap-milestone-end --strict` and `openspec schema validate specwright` (from the repo root after re-installing the schema copy, if the schema changed; this change does not edit it). Both must pass.

## Workflow follow-up

- Re-install Specwright into this repo (README install prompt) after merge, so this session's installed `specwright-roadmap`, `specwright-branch` and `specwright-finish` copies follow 0.1.12.
- After archive on the branch, `openspec validate --specs --strict` on the branch must pass. `test_specs_strict.py` then runs against the main specs directly, with no active change.
- After merge, cleanup's issues-left-open backstop checks that #51, #60 and #66 closed. Then `/specwright-roadmap next` starts `fix-ship-flow-gaps`.
