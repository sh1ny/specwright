# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-script-runtime → A command that exits before its deadline keeps its result | Exit just before the deadline with a held pipe | evals/pr-pair/test_bounded.py | test_exit_before_deadline_with_held_pipe_keeps_result | green |
| pr-script-runtime → A command that exits before its deadline keeps its result | Exit after the deadline | evals/pr-pair/test_bounded.py | test_exit_after_deadline_is_deadline_exceeded | green (existing behaviour, pinned by a new test) |
| pr-script-runtime → A process a network command started is stopped on every platform | No job object on Windows | evals/pr-pair/test_bounded.py | test_no_job_object_falls_back_and_says_so | green |
| pr-script-runtime → A process a network command started is stopped on every platform | Orphan holding the pipe on Windows | evals/pr-pair/test_bounded.py | test_a_finished_command_with_a_child_holding_its_pipe_returns_its_status (Windows skip at :198 removed) | green |
| pr-script-runtime → A process a network command started is stopped on every platform | Hung command with a grandchild | evals/pr-pair/test_bounded.py | test_hung_command_grandchild_stopped | green (existing behaviour, pinned by a new test) |
| pr-script-runtime → The deadline override is read one way | Fractional override lowers the poll | evals/pr-pair/test_pr_snapshot.py | test_poll_fractional_net_deadline_lowers_poll | red |
| pr-script-runtime → The deadline override is read one way | Invalid override | evals/pr-pair/test_pr_snapshot.py | test_poll_invalid_net_deadline_keeps_120 | green (existing behaviour, pinned by a new test) |
| pr-script-runtime → The deadline override is read one way | Override above the default | evals/pr-pair/test_pr_snapshot.py | test_poll_net_deadline_above_120_capped | green (existing behaviour, pinned by a new test) |
| review-routes → The size bound applies to the answer | Large OMP event stream with a small answer | evals/review-routes/test_review_run.py | test_omp_large_stream_small_answer_valid | green |
| review-routes → The size bound applies to the answer | OMP answer over the bound | evals/review-routes/test_review_run.py | test_omp_answer_over_bound_invalid | green |
| review-routes → The size bound applies to the answer | OMP stream without a final message | evals/review-routes/test_review_run.py | test_omp_stream_without_agent_end_invalid | green |
| review-routes → The size bound applies to the answer | Codex answer taken from the event stream | evals/review-routes/test_review_run.py | test_codex_answer_from_last_agent_message | red |
| review-routes → The size bound applies to the answer | Codex answer over the bound | evals/review-routes/test_review_run.py | test_codex_agent_message_over_bound_invalid | red |
| review-routes → The size bound applies to the answer | Codex stream without an answer | evals/review-routes/test_review_run.py | test_codex_stream_without_agent_message_invalid | red |
| review-routes → Reviewer output is bounded while the CLI runs | Output within the bounds | evals/review-routes/test_review_run.py | test_omp_stream_within_bounds_passes | green |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stdout | evals/review-routes/test_review_run.py | test_claude_stdout_flood_stopped_nothing_written | green |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stderr | evals/review-routes/test_review_run.py | test_codex_stderr_flood_stopped_review_unchanged | green |
| review-routes → Reviewer output is bounded while the CLI runs | Codex event stream over the bound | evals/review-routes/test_review_run.py | test_codex_event_stream_flood_stopped (replaces test_codex_answer_file_flood_stopped) | red |
| review-routes → Reviewer output is bounded while the CLI runs | Codex answer file over the bound | evals/review-routes/test_review_run.py | test_codex_command_line_has_json_and_no_answer_file | red |
| review-routes → A reviewer that exits before the deadline is judged by its exit | Exit in the last poll interval with a held pipe | evals/review-routes/test_review_run.py | test_exit_in_last_poll_interval_with_held_pipe_is_not_timeout | red |
| review-routes → A reviewer that exits before the deadline is judged by its exit | Reviewer held past the deadline | evals/review-routes/test_review_run.py | test_an_exit_first_seen_after_the_deadline_is_a_timeout | green |
| review-routes → A process a reviewer started is stopped on every platform | No job object on Windows | evals/review-routes/test_review_run.py | test_no_job_object_receipt_names_it | red |
| review-routes → A process a reviewer started is stopped on every platform | Orphan holding the pipe on Windows | evals/review-routes/test_review_run.py | test_a_child_that_keeps_the_pipes_open_fails_the_run (Windows skip at :944 removed) | red |
| review-routes → A process a reviewer started is stopped on every platform | Reviewer stopped at the deadline with a grandchild | evals/review-routes/test_review_run.py | test_timeout_stops_grandchild | green (existing behaviour, pinned by a new test) |
| releases → An unreadable commit changes the version only when its parent is not among its versions | Bump reverted through an unreadable version | evals/release/test_release.py | test_bump_reverted_through_unreadable_passes | green |
| releases → An unreadable commit changes the version only when its parent is not among its versions | Bump reverted between two unreadable versions | evals/release/test_release.py | test_bump_reverted_between_two_unreadable_passes | green |
| releases → An unreadable commit changes the version only when its parent is not among its versions | Unreadable bump reverted by a readable commit | evals/release/test_release.py | test_unreadable_bump_reverted_by_readable_passes | green |
| releases → An unreadable commit changes the version only when its parent is not among its versions | Unreadable edit that keeps the matched versions | evals/release/test_release.py | test_unreadable_edit_keeping_versions_still_bumps | green (existing behaviour, pinned by a new test) |
| releases → Publish's network commands are bounded | Remote tags answer in time | evals/release/test_release.py | test_untagged_within_deadline_names_no_limit | green (existing behaviour, pinned by a new test) |
| releases → Publish's network commands are bounded | Hung tag lookup | evals/release/test_release.py | test_publish_hung_ls_remote_deadline_exceeded | red |
| releases → Publish's network commands are bounded | Oversized closed-PR read | evals/release/test_release.py | test_publish_oversized_pr_read_response_too_large | red |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off after it landed | evals/release/test_release.py | test_push_cut_off_after_landing_counts_done | red |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off while another clone's tag won | evals/release/test_release.py | test_push_cut_off_other_tag_object_is_tag_mismatch | red |
| releases → A cut-off tag push or release creation is decided by a read-back | Push cut off with origin's tag on another commit | evals/release/test_release.py | test_push_cut_off_other_commit_is_tag_conflict | red |
| releases → A cut-off tag push or release creation is decided by a read-back | Release creation cut off before it landed | evals/release/test_release.py | test_release_create_cut_off_not_found | red |
| releases → A cut-off tag push or release creation is decided by a read-back | Read-back fails too | evals/release/test_release.py | test_push_cut_off_read_back_fails_state_unknown | red |
| install-update → The release-tag lookup is bounded | Tags listed in time | evals/update/test_store.py | test_other_project_minor_refused_names_matching_tag | green |
| install-update → The release-tag lookup is bounded | Hung tag lookup | evals/update/test_store.py | test_hung_tag_lookup_names_deadline_exceeded | red |
| install-update → The release-tag lookup is bounded | Oversized tag list | evals/update/test_store.py | test_oversized_tag_list_names_response_too_large | red |
| change-finish → finish.sh runs no network command | Plan with an unreachable origin | evals/finish/test_undo_plan.py | test_plan_runs_no_network_command | green (existing behaviour, pinned by a new test) |
| change-finish → finish.sh runs no network command | A network command added to finish.sh | evals/finish/test_undo_plan.py | test_finish_sh_has_no_network_command | green (static scan; proven red by a temporary injected line) |
| change-finish → A spec deleted after a bulk archive stays deleted after the rerun | Spec synced by both members, deleted later | evals/finish/test_undo_plan.py | test_bulk_rerun_deletes_later_deleted_spec_again | green |
| change-finish → A spec deleted after a bulk archive stays deleted after the rerun | Spec recreated before the after-rerun script | evals/finish/test_undo_plan.py | test_after_rerun_stops_when_deleted_spec_recreated | green |
| change-finish → A spec deleted after a bulk archive stays deleted after the rerun | Spec synced only by the deferred member, deleted later | evals/finish/test_undo_plan.py | test_deleted_spec_only_in_deferred_member_left_deleted | green (existing behaviour, pinned by a new test) |
| pr-descriptions → A code span after a closing keyword ends the closing list | Code span between keyword and reference | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_code_span_after_keyword_ends_list | green |
| pr-descriptions → A code span after a closing keyword ends the closing list | Code span after a keyword in mid-line | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_code_span_after_midline_keyword_ends_list | green |
| pr-descriptions → A code span after a closing keyword ends the closing list | Code span after the list | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_code_span_after_list_ends_it | green |
| pr-descriptions → A code span after a closing keyword ends the closing list | Plain closing line | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_plain_closing_line | green (existing behaviour, pinned by a new test) |

Every test run below uses `python -m unittest` from the repo root: `discover evals/<suite>` for a whole suite, or `-k <name>` for one test.

## 1. ADR 0014 and the architecture file

- [x] 1.1 Write `docs/adr/0014-bounded-runs-share-one-process-module.md` (Status: accepted, today's date, Supersedes: 0012) with the decision listed under design.md "ADRs → To record during apply": 0012's bounds kept and its exceptions removed; `bounded.py` copied byte-identically per skill and loaded from the skill's own folder; `review-run.sh` takes spawn, kill and the exit watcher from its copy; Windows job objects, with the reported fallback; the exit watcher; codex's answer read from its event stream; `finish.sh` runs no network command. Leave `0012` unchanged. Verify: the file exists, and `git diff --stat docs/adr/0012-*` is empty.
- [x] 1.2 Update `openspec/architecture.md`: swap the ADR index row 0012 for 0014; in Resource bounds, drop "release.sh, finish.sh and update.sh stay unbounded (#111)" from the Network commands row and "an unbounded read (#111)" from the Release publish row, and in the Review run row replace "codex's answer file 2 MiB" with the event-stream answer; remove the #111 Known gaps row; add `bounded.py` copies to the components rows for `specwright-release` and `specwright-review`. Verify: `grep -n "#111\|answer file" openspec/architecture.md` prints nothing, and `grep -n "0014" openspec/architecture.md` shows the index row.

## 2. bounded.py: exit watcher, job objects, deadline helper, copies

- [x] 2.1 Add the test hooks `SPECWRIGHT_TEST_POLL` (the loop's wait interval) and `SPECWRIGHT_TEST_NO_JOB` to `skills/specwright-pr/scripts/bounded.py`, documented in its header beside the other test overrides, with no behaviour change. Verify: `discover evals/pr-pair -p test_bounded.py` still passes.
- [x] 2.2 Write the failing tests `test_exit_before_deadline_with_held_pipe_keeps_result` (3 s deadline, `SPECWRIGHT_TEST_POLL=5`, the fake exits at an absolute time 1 s before the deadline and records its exit time) and `test_no_job_object_falls_back_and_says_so` (Windows only); remove the Windows skip at `test_bounded.py:198`; add `test_exit_after_deadline_is_deadline_exceeded` and `test_hung_command_grandchild_stopped`. Verify: the first two fail for the expected reason (deadline_exceeded reported; no stderr line), and on Windows the un-skipped assert fails because the child survives.
- [x] 2.3 Implement in `bounded.py`: `spawn` (POSIX `start_new_session`; Windows `CREATE_SUSPENDED`, job object, `AssignProcessToJobObject`, `NtResumeProcess`, fallback with the `bounded: no job object: <reason>` stderr line), `kill` (`TerminateJobObject`, else `taskkill /T /F` / `killpg`), and the exit watcher thread with a caller-supplied wake event; `_piped` uses a separate `wake` event (design D3) and the watcher's exit time. Verify: the group 2 rows turn green, and `discover evals/pr-pair -p test_bounded.py` passes on Windows; flip those rows green.
- [x] 2.4 Add `bounded.py --deadline-at`, which prints `time.time()` plus `resolve()`'s deadline; add a unit test `test_deadline_at_honours_fractional_override`. Verify: that test passes.
- [x] 2.5 Copy `bounded.py` byte-identically to `skills/specwright-release/scripts/bounded.py` and `skills/specwright-review/scripts/bounded.py`; add `test_bounded_copies_identical` to `evals/pr-pair/test_bounded.py`, which compares all `skills/*/scripts/bounded.py` with the PR copy. Verify: it passes, and fails after a one-byte edit to a copy (then revert the edit).

## 3. pr-snapshot poll deadline (#117)

- [x] 3.1 Write `test_poll_fractional_net_deadline_lowers_poll`, `test_poll_invalid_net_deadline_keeps_120` and `test_poll_net_deadline_above_120_capped` in `evals/pr-pair/test_pr_snapshot.py`, reading `deadline_at` from the fake `gh` log. Verify: the fractional test fails (deadline_at is 120 s out), and the others pass.
- [ ] 3.2 Make `poll()` in `skills/specwright-pr/scripts/pr-snapshot.sh` export `SPECWRIGHT_NET_DEADLINE_AT` from `bounded.py --deadline-at`, falling back to `$(date +%s) + 120` when the helper prints nothing; update the header comment at line 28. Verify: all three tests pass and `discover evals/pr-pair` passes; flip the rows green.

## 4. review-run.sh: shared process module and codex event stream (#113, #114, #116)

- [ ] 4.1 Update `evals/fakes/reviewcli.py` so the codex fake prints `{"type":"item.completed","item":{"type":"agent_message","text":…}}` events on stdout (honouring the existing answer env vars), drops writing the `-o` file, and gets a stdout-flood mode and an absolute exit-time mode (`FAKE_U_EXIT_AT`, recording its exit time). Verify: `test_fake_flood_writes_past_size_and_stays_alive_until_killed` and the fake's own tests still pass.
- [ ] 4.2 Write the failing tests `test_codex_answer_from_last_agent_message`, `test_codex_agent_message_over_bound_invalid`, `test_codex_stream_without_agent_message_invalid`, `test_codex_event_stream_flood_stopped` (replacing `test_codex_answer_file_flood_stopped`), `test_codex_command_line_has_json_and_no_answer_file`, `test_exit_in_last_poll_interval_with_held_pipe_is_not_timeout` (5 s timeout, `SPECWRIGHT_TEST_POLL=10`), `test_no_job_object_receipt_names_it` and `test_timeout_stops_grandchild`; remove the Windows skip at `test_review_run.py:944`. Verify: each red test fails for the expected reason.
- [ ] 4.3 In `skills/specwright-review/scripts/review-run.sh`, load `bounded.py` from its own folder by path (as `pr-pair.sh:103-115` does), use its `spawn`, `kill` and exit watcher in `capture`, remove the local `kill_tree`, `watch` and `answer_over`, honour `SPECWRIGHT_TEST_POLL` for `POLL`, and write `process_group` in the receipt. Verify: the #114/#116 rows turn green; flip them.
- [ ] 4.4 Drop `-o` from the codex command line and add `codex_scan` (modelled on `omp_scan`, `review-run.sh:947-974`): the last `item.completed` event whose `item.type` is `agent_message`, under `MAX_EVENT_LINE` and the 2 MiB answer bound; no item gives `status: invalid` naming the missing answer. Verify: the #113 rows turn green, and `discover evals/review-routes` passes; flip them.
- [ ] 4.5 Update `skills/specwright-review/SKILL.md` and any reference to codex's answer file or `-o` under `skills/` and `docs/` (`grep -rn "last-message\|answer file\| -o " skills docs`). Verify: the grep prints no stale reference, and `evals/git-workflow` text tests pass.

## 5. release.sh bounded network commands and read-back (#111)

- [ ] 5.1 Write the failing tests `test_publish_hung_ls_remote_deadline_exceeded`, `test_publish_oversized_pr_read_response_too_large`, `test_push_cut_off_after_landing_counts_done`, `test_push_cut_off_other_tag_object_is_tag_mismatch`, `test_push_cut_off_other_commit_is_tag_conflict`, `test_release_create_cut_off_not_found` and `test_push_cut_off_read_back_fails_state_unknown`, plus `test_untagged_within_deadline_names_no_limit`, using the fake `gh`'s `hang`/`flood` keys, a hanging `pre-receive` hook or `git` shim for the push, and `SPECWRIGHT_NET_DEADLINE=1`. Verify: the red ones fail (they hang until the test's own timeout or report a generic failure).
- [ ] 5.2 Route `release.sh`'s network commands (`git ls-remote`, `fetch`, `push`, every `gh`) through its `bounded.py` copy, `paged` for the closed-PR read; raise `Stop(<limit>, …, code=3, call=…)` on a limit; after a cut-off push, read back with `remote_tag` and compare commit and tag object (`tag_conflict` / `tag_mismatch` as before the push); after a cut-off `gh release create`, read back with `release_state`; a failed read-back gives `state: unknown`. Update `skills/specwright-release/SKILL.md`'s error list. Verify: the group 5 rows turn green, and `discover evals/release` passes; flip them.

## 6. release.sh unreadable revert (#109)

- [x] 6.1 Write `test_bump_reverted_between_two_unreadable_passes`, `test_unreadable_bump_reverted_by_readable_passes` and `test_unreadable_edit_keeping_versions_still_bumps` in `evals/release/test_release.py` (`TestCheckMain`). Verify: the first two fail with `version_not_ahead_of_main`, and the third passes.
- [x] 6.2 Implement design D9 in `own_bump`: an immediate parent that is unreadable and on the branch makes any newly matched version a change, judged against `judged_parent` (with the unreadable-`judged_parent` rule); update the docstring and `release.sh`'s header comment (lines 13-16). Verify: the three tests and every existing `TestCheckMain` test pass; flip the rows green.

## 7. update.sh bounded tag lookup (#111)

- [ ] 7.1 Write `test_hung_tag_lookup_names_deadline_exceeded` (a `git` shim or `insteadOf` URL that hangs, `SPECWRIGHT_NET_DEADLINE=2`) and `test_oversized_tag_list_names_response_too_large` (`SPECWRIGHT_NET_MAX_BYTES` lowered) in `evals/update/test_store.py`. Verify: both fail as expected.
- [ ] 7.2 In `scripts/update.sh`'s `highest_tag`, load `<download>/skills/specwright-pr/scripts/bounded.py` lazily and run `ls-remote` with `run_bounded` at `min(60, resolve()'s deadline)`; a limit or a missing file becomes the reason in the `store_version` refusal. Verify: both tests and `discover evals/update` pass (mini-download evals included); flip the rows green.

## 8. finish.sh: no network command, deletion carried through the rerun (#111, #110)

- [x] 8.1 Add `test_plan_runs_no_network_command` (origin URL pointing nowhere, a hanging fake `gh` on `PATH` that logs calls) and `test_finish_sh_has_no_network_command` (a static scan of `finish.sh` for `fetch`/`pull`/`push`/`ls-remote`/`gh ` calls, naming the line) to `evals/finish/test_undo_plan.py`. Verify: both pass; inject a temporary `git fetch` line into a copy of the script, confirm the scan fails naming that line, then remove the line.
- [x] 8.2 Write `test_bulk_rerun_deletes_later_deleted_spec_again`, `test_after_rerun_stops_when_deleted_spec_recreated` and `test_deleted_spec_only_in_deferred_member_left_deleted`. Verify: the first two fail (the spec is recreated; no guard), and the third passes.
- [x] 8.3 Implement design D8 in `undo-archive-plan`: keep `gone`, add the `test ! -e` guards before the first `openspec archive` and the `rm -f --` lines after the archives and merges for specs in a rerun member's delta, and reword the warning. Verify: the three tests and `discover evals/finish` pass; flip the rows green.

## 9. pr-pair closing lists (#115)

- [x] 9.1 Write `test_code_span_after_keyword_ends_list`, `test_code_span_after_midline_keyword_ends_list`, `test_code_span_after_list_ends_it` and `test_plain_closing_line` in `ClosingRendered` (string-literal bodies), and record their GitHub renderings with `python evals/pr-pair/record_markdown.py` (fenced as `KintsugiBot` through `as.sh`). Verify: `ClosingRecordings.test_every_closing_body_has_a_recording` passes, and the three red tests fail (31, 33 and 35 are intended).
- [x] 9.2 Make `RenderedLines` (`pr-pair.sh:853-889`) emit U+FFFC for a code or `pre` span instead of a space, and update its docstring and `intended_issues()`'s. Verify: the four tests and all `ClosingCheck`, `ClosedCheck`, `ClosingRendered` and `ClosingRecordings` tests pass; flip the rows green.

## 10. Integration and release

- [ ] 10.1 Check the codex event shape: run the real codex once with `codex exec --json` and a one-line prompt where the codex route works on this machine, and confirm that the last `item.completed` / `agent_message` text matches what `codex_scan` reads. If codex cannot run here (#118), compare against codex's `exec/src/exec_events.rs` instead and say which check was done in the PR description.
- [ ] 10.2 Run every suite the M5 exit criterion names: `discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update`, `evals/release` and `evals/finish`. Verify: all pass on Windows, and the Test map has no `red` row left.
- [ ] 10.3 `release.sh bump --to 0.8.1`. Verify: `release.sh check` reports 0.8.1, with `VERSION`, the README badge and every `skills/*/SKILL.md` version agreeing.
- [ ] 10.4 `openspec validate fix-m4-gaps --strict` and `openspec schema validate specwright`. Verify: both pass.

## Workflow follow-up

- Pre-ship review, ship (PR closing #109, #110, #111, #113, #114, #115, #116, #117, one `Fixes` line per issue), watch, archive, finish; then publish 0.8.1.
