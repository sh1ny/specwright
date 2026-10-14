# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| github-identity → The trailing-dot host is github.com | Token in a trailing-dot URL | evals/pr-pair/test_as_sh.py | test_trailing_dot_token_in_fetch_url_refused | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot URL argument or rewrite | evals/pr-pair/test_as_sh.py | test_trailing_dot_argument_and_rewrite_refused | green |
| github-identity → The trailing-dot host is github.com | Credential-free trailing-dot URL | evals/pr-pair/test_as_sh.py | test_credential_fill_trailing_dot_returns_verified_token | green |
| github-identity → The trailing-dot host is github.com | Look-alike host | evals/pr-pair/test_as_sh.py | test_lookalike_host_not_github | green |
| github-identity → The trailing-dot host is github.com | Trailing-dot store remote | evals/pr-pair/test_pr_pair.py | test_trailing_dot_store_remote_is_fenced | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Enterprise store read by rounds | evals/pr-pair/test_pr_pair.py | test_rounds_non_github_store_gets_enterprise_vars | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Variables were unset | evals/pr-pair/test_pr_pair.py | test_rounds_non_github_store_without_enterprise_vars | green |
| github-identity → Unfenced git keeps the caller's enterprise host settings | Fenced calls stay on github.com | evals/pr-pair/test_as_sh.py | test_enterprise_vars_saved_but_not_in_fence | green |
| preship-review → A review after the archive commit reads the archived artifacts | Recovery review after archive | evals/review-routes/test_review_run.py | test_prompt_names_archived_artifacts_after_archive_commit | green |
| preship-review → A review after the archive commit reads the archived artifacts | Subagent route after archive | evals/review-routes/test_review_run.py, evals/review-routes/test_skill_text.py | test_preflight_lists_archived_artifacts, test_subagent_dispatch_passes_preflight_artifacts | green |
| preship-review → A review after the archive commit reads the archived artifacts | Active change | evals/review-routes/test_review_run.py | test_preflight_lists_active_artifacts | green |
| preship-review → A review after the archive commit reads the archived artifacts | Several archives of the same name | evals/review-routes/test_review_run.py | test_archived_artifacts_from_the_reviewed_range_only | green |
| preship-review → A review after the archive commit reads the archived artifacts | No artifacts anywhere | evals/review-routes/test_review_run.py | test_no_artifacts_falls_back_to_active_paths | green |
| change-finish → A merged PR whose branch is gone is done after the backstop | Cleanup already ran | evals/git-workflow (graded) | eval-finish-resume-merged-branch-gone (also eval-finish-resume-squash-merged) | red |
| change-finish → A merged PR whose branch is gone is done after the backstop | Stale main holds an older change's archive | evals/git-workflow (graded); evals/git-workflow/test_instructions.py | eval-finish-resume-stale-main; test_finish_resume_merged_pr_without_branch_refreshes_main | red |
| change-finish → A merged PR whose branch is gone is done after the backstop | Refreshed main has no archive | evals/git-workflow/test_instructions.py | test_finish_resume_merged_pr_without_archive_after_refresh_not_done | green |
| change-finish → A merged PR whose branch is gone is done after the backstop | Store-backed code repo after merge | evals/git-workflow/test_instructions.py | test_finish_resume_store_code_repo_needs_no_archive | green |
| change-finish → A merged PR whose branch is gone is done after the backstop | Dirty tree before the refresh | evals/git-workflow/test_instructions.py | test_finish_resume_merged_row_checks_dirty_tree_before_refresh | green |
| change-finish → A merged PR whose branch is gone is done after the backstop | Branch still present | evals/git-workflow/test_instructions.py | test_finish_resume_merged_pr_with_branch_runs_cleanup | green |
| change-finish → A merged PR whose branch is gone is done after the backstop | Backstop cannot read GitHub | evals/git-workflow/test_instructions.py | test_finish_resume_backstop_exit_3_is_not_done | green |
| change-finish → A reused branch name stops finish before any report | Newest PR closed unmerged, older PR merged, nothing local | evals/git-workflow/test_instructions.py | test_finish_resume_reused_check_precedes_no_archive_report | green |
| change-finish → A reused branch name stops finish before any report | Closed-PR row with an older merged PR | evals/git-workflow/test_instructions.py | test_finish_resume_closed_pr_row_defers_to_reused_rule | green |
| change-finish → A reused branch name stops finish before any report | Only a closed PR | evals/git-workflow/test_instructions.py | test_finish_resume_closed_pr_row_reports_closed_pr | green |

## 1. Trailing-dot host (#83)

- [x] 1.1 Write the failing `as.sh` tests from the test map (trailing-dot fetch URL, argument and `insteadOf` rule refused with mixed case `GitHub.COM.`; credential fill for host `github.com.` returns the verified token; look-alike `github.com.example.org` gets no credential and is not refused) in `evals/pr-pair/test_as_sh.py`; run `python -m pytest evals/pr-pair/test_as_sh.py -k "trailing_dot or lookalike"` and confirm each fails on the missing match, not on setup.
- [x] 1.2 In `skills/specwright-pr/scripts/as.sh`, make `gh_url` and `gh_userinfo` match `github\.com\.?([:/]|$)`, and make the credential helper lower-case the host and strip one terminal dot before comparing it with `github.com` (review S1). Update the header comment. Verify that 1.1's tests pass and all of `evals/pr-pair/test_as_sh.py` stays green, then flip those rows green.
- [x] 1.3 Write the failing `test_trailing_dot_store_remote_is_fenced` in `evals/pr-pair/test_pr_pair.py` (store origin `https://github.com./o/s.git` is read through `as.sh`, never with `unfenced_env`), then make `GH_URL` in `skills/specwright-pr/scripts/pr-pair.sh` accept `github\.com\.?` in its URL and scp forms. Verify that the test passes with `python -m pytest evals/pr-pair/test_pr_pair.py`, and flip the row green.
- [ ] 1.4 Where the skill texts decide "fetch URL on github.com" (`specwright-finish`, `specwright-pr`, `specwright-branch`, `specwright-roadmap`), say that `github.com.` counts as github.com (review S3), and add a skill-text assertion for it in `evals/git-workflow/test_instructions.py`. Verify with `python -m pytest evals/git-workflow/test_instructions.py`.

## 2. Enterprise variables for unfenced store reads (#84)

- [x] 2.1 Write the failing tests: `test_enterprise_vars_saved_but_not_in_fence` in `evals/pr-pair/test_as_sh.py` (with `GH_HOST`/`GH_ENTERPRISE_TOKEN`/`GITHUB_ENTERPRISE_TOKEN` set, a fenced `gh` shim and a fenced git credential call see none of them, while `AS_SH_ORIG_SET` lists them). In `evals/pr-pair/test_pr_pair.py`, write `test_rounds_non_github_store_gets_enterprise_vars`: a store origin on `https://ghe.example/o/s.git` with credential helper `!gh auth git-credential`, where a fake `gh` records `GH_HOST` and `GH_ENTERPRISE_TOKEN` and answers, and `rounds` runs under `as.sh`. Also write `test_rounds_non_github_store_without_enterprise_vars` (unset stays unset, never empty). Confirm that they fail for the right reason.
- [x] 2.2 In `skills/specwright-pr/scripts/as.sh`, save `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` into `AS_SH_ORIG_*`/`AS_SH_ORIG_SET` before the unset on line 44. Use one "once" guard for all saved variables, so the git-variable save still runs (review S2); `GH_TOKEN` and `GITHUB_TOKEN` are never saved. Update the header comment. Verify that 2.1's tests pass, that `test_rounds_under_as_sh_reads_non_github_store_with_user_git` and `test_gh_host_and_enterprise_tokens_unset` stay green, then flip the rows green.

## 3. Archived artifacts for a pre-ship review after archive (#81)

- [x] 3.1 Write the failing tests in `evals/review-routes/test_review_run.py` from the test map. They cover the prompt naming the archived paths after an archive commit on the branch; `preflight` printing `artifacts` for active and archived changes; only the archive directory added in `<base>...HEAD` counting when an older `2026-09-01-<change>` also exists; and the active paths named when no artifacts exist. Store-backed coverage: an archive in the store's range. Confirm that they fail for the right reason.
- [x] 3.2 In `skills/specwright-review/scripts/review-run.sh`, have `artifact_paths` take the planning repo directory and its base ref and choose the paths per design D3, using the `archive_only` name pattern. Use it in `build_prompt`, and add `artifacts` to `cmd_preflight` output. Verify that 3.1's tests pass, that `python -m pytest evals/review-routes` is green (including `test_prefix_builds_artifact_paths`), then flip the rows green.
- [x] 3.3 In `skills/specwright-review/SKILL.md`, Pre-ship review step 1 `subagent`: pass the preflight `artifacts` to `specwright-reviewer`. In `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md` pre-ship mode, read the artifact paths the request names. Add `test_subagent_dispatch_passes_preflight_artifacts` to `evals/review-routes/test_skill_text.py`, and verify with `python -m pytest evals/review-routes/test_skill_text.py`.

## 4. Finish resume: refresh before a merged-PR row, reused-name precedence (#75, #77)

- [x] 4.1 Write the failing skill-text tests in `evals/git-workflow/test_instructions.py` from the test map: the merged-PR, branch-gone row refreshes `main` behind the dirty-tree guard and re-reads A in the planning repo only; no archive after the refresh means not done; the store-backed code repo needs no archive; the reused-name check reads the no-archive rule's `discover` and comes before the no-archive report; the closed-PR row defers to it, and with only a closed PR reports that PR. Confirm that each fails on the current text.
- [x] 4.2 Edit `skills/specwright-finish/SKILL.md` Resume per design D1 and D2. Move the reused-name rule ahead of the "None of A, M, B" paragraph, tie it to the same `discover` result, extend the "`pr`, the branch's PR merged, not B" row with the guarded refresh and the planning-repo A re-read, and align the closed-PR row. Verify that 4.1's tests pass, that `test_finish_resume_merged_pr_with_branch_runs_cleanup`, `test_finish_resume_backstop_exit_3_is_not_done` and `test_finish_resume_reused_branch_rule_takes_precedence` stay green (update the last only where its text moved), then flip the rows green.
- [ ] 4.3 Give the shared fixture `build_finish_resume_merged` (`evals/git-workflow/fixtures.py`) a local bare origin holding `main`, reached through the watch-merge `bin/git` shim (a command-scoped `-c url.<bare>.insteadOf=https://github.com/<slug>.git` on `pull`/`fetch` only). Update `check_finish_resume_merged` in `evals/git-workflow/grade.py` to allow exactly `checkout main` and `pull --ff-only`, still forbidding commit, merge, push and branch deletion, and update both evals' text in `evals/git-workflow/evals.json`. Verify with `python -m pytest evals/git-workflow/test_grade.py evals/git-workflow/test_fixtures_shim.py`.
- [ ] 4.4 Add the graded eval `eval-finish-resume-stale-main`. Local `main` holds `2026-09-01-add-greeting` from an older change; origin `main` additionally holds the merge of PR #7 with `2026-10-14-add-greeting`; PR #7 is merged and the branch is gone. Expected: a fenced pull before A is read, one `closed-check` of #7, no branch deletion, and `Nothing to finish - archive is on main`. Add its fixture and grader with grader unit tests in `evals/git-workflow/test_grade.py`, and verify with `python -m pytest evals/git-workflow`.

## 5. Release 0.4.1 and integration

- [ ] 5.1 Bump to 0.4.1: `VERSION`, the README badge, and `metadata.version` in every `skills/*/SKILL.md`. Verify with `grep -rn '0\.4\.0' VERSION README.md skills/*/SKILL.md` (no hits) and `openspec schema validate specwright`.
- [ ] 5.2 Run `python -m pytest evals/pr-pair evals/git-workflow evals/review-routes`; all green.
- [ ] 5.3 Re-run the graded evals after the last `specwright-finish` edit (M2 lesson): `eval-finish-resume-merged-branch-gone`, `eval-finish-resume-squash-merged` and `eval-finish-resume-stale-main`, each graded with `evals/git-workflow/grade.py`; record pass/fail per assertion in the PR description.

## Workflow follow-up

- Pre-ship review, then ship PR with closing lines for #75, #77, #81, #83 and #84.
- Archive after merge-ready; release 0.4.1 is cut manually (the release workflow arrives in `add-release-workflow`, which backfills the 0.4.1 tag and notes).
