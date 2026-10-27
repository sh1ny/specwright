# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| eval-grading → Git writes are everything off a read-only allowlist | Plumbing and dash targets are writes | evals/git-workflow/test_grade.py | GitAllowlist.test_plumbing_and_dash_targets_are_writes | green |
| eval-grading → Git writes are everything off a read-only allowlist | Unknown subcommand is a write | evals/git-workflow/test_grade.py | GitAllowlist.test_unknown_subcommand_is_a_write | green |
| eval-grading → Git writes are everything off a read-only allowlist | Fetch into a local branch is a write | evals/git-workflow/test_grade.py | GitAllowlist.test_fetch_into_local_branch_is_a_write | green |
| eval-grading → Git writes are everything off a read-only allowlist | Reads stay reads | evals/git-workflow/test_grade.py | GitAllowlist.test_reads_stay_reads (default-refspec fetches move out of its list) || green |
| eval-grading → Git writes are everything off a read-only allowlist | Quiet branch listing is a read | evals/git-workflow/test_grade.py | GitAllowlist.test_quiet_branch_listing_is_a_read || green |
| eval-grading → Git writes are everything off a read-only allowlist | Tag verification is a read | evals/git-workflow/test_grade.py | GitAllowlist.test_tag_verification_is_a_read || green |
| eval-grading → Git writes are everything off a read-only allowlist | Quiet flag does not hide a branch write | evals/git-workflow/test_grade.py | GitAllowlist.test_quiet_flag_does_not_hide_a_branch_write (guard: holds before and after) | green |
| eval-grading → Git writes are everything off a read-only allowlist | Verify flag does not hide a tag write | evals/git-workflow/test_grade.py | GitAllowlist.test_verify_flag_does_not_hide_a_tag_write (guard: holds before and after) | green |
| eval-grading → A fetch that stores refs is a write | Default refspec follows tags | evals/git-workflow/test_grade.py | GitAllowlist.test_fetch_that_stores_refs_is_a_write || green |
| eval-grading → A fetch that stores refs is a write | No tags does not excuse a branch or tag write | evals/git-workflow/test_grade.py | GitAllowlist.test_no_tags_does_not_excuse_a_branch_or_tag_write (guard) | green |
| eval-grading → A fetch that stores refs is a write | No tags or no destination stays a read | evals/git-workflow/test_grade.py | GitAllowlist.test_fetch_with_no_tags_or_no_destination_is_a_read (guard) | green |
| eval-grading → A fetch that stores refs is a write | Pull's own child fetch | evals/git-workflow/test_grade.py | GitAllowlist.test_pull_child_fetch_is_judged_with_the_pull (green now; would turn red under the new fetch rule without the child rule) | green |
| eval-grading → A fetch that stores refs is a write | Update-head-ok without a pull | evals/git-workflow/test_grade.py | GitAllowlist.test_update_head_ok_without_a_pull_is_a_write || green |
| eval-grading → GraphQL calls are found by their endpoint | Mutation sent as GET | evals/git-workflow/test_grade.py, evals/pr-pair/test_fake_gh.py | GhAllowlist.test_graphql_mutation_sent_as_get_is_a_write; GraphqlWriteDispatch.test_mutation_sent_as_get_applies | green |
| eval-grading → GraphQL calls are found by their endpoint | Query with options before the endpoint | evals/git-workflow/test_grade.py | GhAllowlist.test_graphql_read_with_options_before_the_endpoint | green |
| eval-grading → GraphQL calls are found by their endpoint | Unreadable document after an option | evals/git-workflow/test_grade.py | GhAllowlist.test_graphql_input_after_get_is_a_write | green |
| eval-grading → Only the executed GraphQL operation is classified | Named query beside a mutation | evals/git-workflow/test_grade.py, evals/pr-pair/test_fake_gh.py | GraphqlOperations.test_operation_name_selects_a_query; GraphqlWriteDispatch.test_named_query_beside_a_mutation_changes_nothing | green |
| eval-grading → Only the executed GraphQL operation is classified | Named mutation | evals/git-workflow/test_grade.py | GraphqlOperations.test_operation_name_selects_a_mutation (guard) | green |
| eval-grading → Only the executed GraphQL operation is classified | Unknown operation name | evals/git-workflow/test_grade.py, evals/pr-pair/test_fake_gh.py | GraphqlOperations.test_unknown_operation_name_is_a_write; GraphqlWriteDispatch.test_several_operations_need_a_known_name (guard) | green |
| eval-grading → The fake gh rejects duplicate operation names | Two mutations with the same name | evals/pr-pair/test_fake_gh.py | GraphqlWriteDispatch.test_duplicate_operation_names_fail_unchanged | green |
| eval-grading → The fake gh rejects duplicate operation names | One operation with the name | evals/pr-pair/test_fake_gh.py | GraphqlWriteDispatch.test_operation_name_selects_the_operation | green |
| eval-runner → The runner runs each test file as its own process | All files pass | evals/runner/test_run.py | RunnerTests.test_all_files_pass | green |
| eval-runner → The runner runs each test file as its own process | A file fails | evals/runner/test_run.py | RunnerTests.test_a_failing_file_is_reported_and_kept | green |
| eval-runner → The runner runs each test file as its own process | Unknown suite | evals/runner/test_run.py | RunnerTests.test_unknown_suite_exits_2 | green |
| eval-runner → The runner runs each test file as its own process | A file's process crashes | evals/runner/test_run.py | RunnerTests.test_a_crashing_file_is_reported | green |
| eval-runner → The runner runs each test file as its own process | A file times out | evals/runner/test_run.py | RunnerTests.test_a_timed_out_file_tree_is_stopped | green |
| eval-runner → Faster suites keep every test | Counts after the change | n/a | Mechanical check (task 7.2): `python evals/run.py --ids` against `test-ids-base.txt`; a one-time comparison at ship time, since the base list exists only for this change | n/a |
| eval-runner → Faster suites keep every test | A shared fixture is not shared state | evals/runner/test_fixturecache.py | FixtureCacheTests.test_copies_are_independent | green |
| eval-runner → Suite wall times are recorded | Before and after recorded | evals/runner/test_timings.py | TimingsRecord.test_every_suite_has_before_and_after_and_the_total_is_lower | red |
| eval-runner → Suite wall times are recorded | A suite that did not get faster | evals/runner/test_timings.py | TimingsRecord.test_a_suite_not_faster_is_named_in_a_note | red |
| eval-runner → Suite wall times are recorded | A test ID went missing | evals/runner/test_timings.py | TimingsRecord.test_record_states_every_base_id_is_present (with the 7.2 comparison) | red |

## 1. Baseline test IDs

- [x] 1.1 At the base commit (no `evals/` edit yet), list every suite's test IDs (pr-pair, update, review-routes, git-workflow, release, finish) with the `unittest` loader only, no test runs (`discover -s evals/<suite> -t evals/<suite>`, flattened, one id per line, prefixed by the suite), into `openspec/changes/fix-eval-gaps/test-ids-base.txt`. The before timing column is the #127 figures (design D8); no before run is made. Verify: the file has one block per suite, and each suite's count is at least its #127 count (pr-pair 559, update 95, review-routes 157, git-workflow 323, release 118, finish 41).

## 2. Git grader rules (#121, #122, #123)

- [x] 2.1 Write the failing tests in `GitAllowlist`: `test_fetch_that_stores_refs_is_a_write`, `test_update_head_ok_without_a_pull_is_a_write`, `test_quiet_branch_listing_is_a_read` and `test_tag_verification_is_a_read`. Move the default-refspec fetches out of `test_reads_stay_reads` (`fetch origin`, `fetch --prune origin`, `fetch --update-head-ok`, `fetch -q origin`, `fetch --all --prune`, `fetch -j 4 --all`, `fetch --jobs=4 --all`, `fetch origin refs/heads/x:refs/remotes/origin/x`) into the write test, and add `fetch origin main` and `fetch --no-tags origin` to the read list. Add the guard tests (`test_quiet_flag_does_not_hide_a_branch_write`, `test_verify_flag_does_not_hide_a_tag_write`, `test_no_tags_does_not_excuse_a_branch_or_tag_write`, `test_fetch_with_no_tags_or_no_destination_is_a_read`, `test_pull_child_fetch_is_judged_with_the_pull`). Verify: the red rows fail for the stated reason and the guard rows pass.
- [x] 2.2 Implement D2 in `git_read_only` (preconditions, then the no-tags-stored clause) and the pull-child rule in `changing_git`. Update the line-319 assertion (`changing_git([["fetch", "origin"]])`) and `test_real_traces_of_reads_are_reads` (a real `pull` trace keeps its child fetch out of the changes; a plain `fetch origin` trace is now a write). Verify: `python -m unittest discover evals/git-workflow` passes, including `FinishResumeMerged` (the guarded refresh still passes) and the release evals' `fetch -q --no-tags origin main`. Flip the #121 rows green.
- [x] 2.3 Add `-q`/`--quiet` to `BRANCH_FLAGS` and `-v`/`--verify` to `TAG_READ` (D4). Verify: the #122/#123 rows and their guards pass, and `ReleaseHelpers.test_tag_writes_only_flags_what_changes_tags` still passes. Flip them green.

## 3. GraphQL classification and the fake (#119, #124, #125)

- [x] 3.1 Write the failing tests: `GhAllowlist.test_graphql_mutation_sent_as_get_is_a_write`, `test_graphql_read_with_options_before_the_endpoint` and `test_graphql_input_after_get_is_a_write`; `GraphqlOperations.test_operation_name_selects_a_query` (with the guards `test_operation_name_selects_a_mutation` and `test_unknown_operation_name_is_a_write`); in `test_fake_gh.py`, `GraphqlWriteDispatch.test_mutation_sent_as_get_applies`, `test_named_query_beside_a_mutation_changes_nothing` and `test_duplicate_operation_names_fail_unchanged`. Verify: each red row fails for the stated reason.
- [x] 3.2 Route `gh api` calls by `api_endpoint(a).lstrip("/") == "graphql"` in `gh_read_only` (D1). Verify: the #119 rows pass and `GhAllowlist`/`ChangingCommands` stay green. Flip them green.
- [x] 3.3 Read `operationName` in `graphql_read_only` and filter with `gqlops.named_operations` (D3). Verify: the #124 rows pass. Flip them green.
- [x] 3.4 Make the fake fail with `GraphQL: There are multiple operations named '<name>'.` when more than one operation matches, before any dispatch. Verify: `test_duplicate_operation_names_fail_unchanged` passes (state file unchanged) and `python -m unittest discover evals/pr-pair` passes. Flip it green.

## 4. Fixture cache (#127)

- [x] 4.1 Write `evals/runner/test_fixturecache.py`: `FixtureCacheTests.test_copies_are_independent` (two copies of one key, one commits, tags and deletes a branch; the other copy and the cached original are unchanged), a failing-build test (the key stays missing and the next call rebuilds), and an equivalence test (one shape built directly and through the cache gives the same `git log --format=%H %T`, file tree and clean `git status`). Verify: they fail because `evals/fixturecache.py` does not exist.
- [x] 4.2 Implement `evals/fixturecache.py` (D5: per-process root, `atexit` cleanup with a read-only-safe rmtree, key = builder name plus shape arguments, never the destination). Verify: the 4.1 tests pass. Flip the row green.
- [x] 4.3 Before adopting the cache, find where each suite's time goes with `python -m unittest discover evals/<suite> --durations 20` (Python 3.12+), and record the slowest tests and their builders in the 4.3 commit message. Verify: the commit message lists them per suite.
- [x] 4.4 Use the cache in the builders the profile names, caching only path-independent stages (D5): git-workflow `base`/`project`, finish `make_repo`, release `make_repo` (remote added after the copy), update `init_repo` plus first commit, and the pr-pair repo setup in `test_as_sh.py`/`test_pr_pair.py`. Verify: each touched suite passes; `python evals/git-workflow/fixtures.py <name> <dest>` gives the same tree as before for two fixtures (compared by `git log --format=%T` and file list); the test IDs of each touched suite are unchanged against `test-ids-base.txt`.

## 5. In-process fake gh (#127)

- [x] 5.1 Write tests in `test_fake_gh.py` for `run()`: it returns the same `(code, stdout, stderr)` as the process for a read, a write and a `Fail`; the logged `cwd` is the given `cwd`; `os.environ`, the cwd and `sys.std*` are restored after a normal return, a `Fail`, a `SystemExit` (`flood`) and an unexpected exception. Verify: they fail because `run` does not exist.
- [x] 5.2 Implement `run(argv, env, stdin="", cwd=None)` in `evals/fakes/gh.py` (D6) and switch `FakeGhCase.gh()` to it, with `process=True` for the `hang`, PID-file, signal and pipe-stdin tests and a few kept process-level tests (exit codes, UTF-8 stdout). Verify: `python -m unittest discover evals/pr-pair` passes, and the pr-pair test IDs are unchanged against `test-ids-base.txt`.

## 6. Parallel runner (#127)

- [x] 6.1 Write `evals/runner/test_run.py` against throwaway suites built in a temp dir (the runner takes a `--root` for the suites' parent): `test_all_files_pass`, `test_a_failing_file_is_reported_and_kept`, `test_unknown_suite_exits_2`, `test_a_crashing_file_is_reported` and `test_a_timed_out_file_tree_is_stopped` (a file that starts a child sleeper; after the timeout, neither process is alive, checked by PID). Verify: they fail because `evals/run.py` does not exist.
- [x] 6.2 Implement `evals/run.py` (D7: `bounded.spawn`, `bounded.kill(p)` on a timeout, `close_job(p)` after each file, logs on disk, failed logs kept and their paths printed, `SERIAL` run after the parallel batch, `--jobs`, `--timeout`, `--ids` to print test IDs, exit 0/1/2). Verify: the 6.1 tests pass. Flip the rows green.
- [ ] 6.3 Run every suite through `python evals/run.py` twice. Any file that fails only in parallel moves to `SERIAL` (or is fixed when the cause is a shared path), with the reason in a comment next to `SERIAL`. Verify: two consecutive full runs exit 0.
- [x] 6.4 Document the runner: `README.md` (the test commands paragraph) and `CONTRIBUTING.md` (testing list) name `python evals/run.py [suite ...]` next to the per-suite `unittest discover` commands, which still work. The `openspec/architecture.md` Evals row names `evals/run.py`, `evals/fixturecache.py` and `evals/timings.md`. Verify: `python -m unittest discover evals/git-workflow -p test_instructions.py` and `-p test_specs_strict.py` pass, and `openspec schema validate specwright` passes.

## 7. After measurement, record and release

- [x] 7.1 Write `evals/runner/test_timings.py` (`TimingsRecord`: six suites, each with a before and an after time and both test counts; the after total lower than the before total; every suite whose after time is not lower named in a note; the record states that every base test ID is present). Verify: it fails because `evals/timings.md` does not exist.
- [ ] 7.2 With no other load from this work on the machine, run each suite on its own with `python evals/run.py <suite>`. Compare `python evals/run.py --ids` with `test-ids-base.txt`: every base ID must be present (any missing ID blocks the change). Write `evals/timings.md` (D8): the before column is the #127 figures (cite the issue and 2026-10-26, with its test counts), the after column is these results with their test counts and the machine, OS, git and Python versions, plus the ID comparison. The `runner` suite (new in this change) has no before figure; a note says it is excluded from both totals. Verify: `TimingsRecord` passes. Flip the eval-runner timing rows green and mark the "Counts after the change" check done.
- [ ] 7.3 Run all six suites plus `runner` (`python evals/run.py pr-pair update review-routes git-workflow release finish runner`) and `openspec validate fix-eval-gaps --strict`. Verify: exit 0 for both.
- [ ] 7.4 `release.sh bump --to 0.9.1`, and rewrite the summary in the proposal's `## Release Notes` so it describes the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/fix-eval-gaps/proposal.md` pass.

## Workflow follow-up

- The PR body closes #119, #121, #122, #123, #124, #125 and #127.
