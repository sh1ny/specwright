# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| install-update → Install checks the OpenSpec version against the pin | Pinned version installed | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_step3_compares_with_downloaded_pin_before_step4 | green |
| install-update → Install checks the OpenSpec version against the pin | Newer patch release installed | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_mismatch_stops_before_any_write | green |
| install-update → Install checks the OpenSpec version against the pin | Pre-release of the pinned version installed | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_exact_match_counts_prerelease_as_mismatch | green |
| install-update → Install checks the OpenSpec version against the pin | Build of the pinned version installed | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_exact_match_counts_build_metadata_as_mismatch | green |
| install-update → Install checks the OpenSpec version against the pin | Version output has no version number | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_unreadable_version_stops | green |
| install-update → Install checks the OpenSpec version against the pin | Version token runs into other version characters | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_step3_run_on_token_is_unreadable, TestOpenSpecPin.test_readme_token_rule_on_sample_outputs | green |
| install-update → Install checks the OpenSpec version against the pin | Root check reads a run-on version token | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_step1_run_on_token_is_unreadable | green |
| install-update → Install checks the OpenSpec version against the pin | Downloaded copy has no pin file | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_missing_pin_file_stops | green |
| install-update → Install checks the OpenSpec version against the pin | Root check fails on an unpinned OpenSpec | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_step1_root_failure_on_unpinned_cli_names_pin_not_init | green |
| install-update → Install checks the OpenSpec version against the pin | OpenSpec missing | evals/git-workflow/test_instructions.py | TestOpenSpecPin.test_step1_missing_openspec_names_pinned_install | green |
| install-update → Workflow update validates changes in flight | Changes in flight still validate | evals/update/test_inflight.py | test_valid_change_allows_workflow_update | green |
| install-update → Workflow update validates changes in flight | A change in flight fails | evals/update/test_inflight.py | test_failing_change_refuses_workflow_update | green |
| install-update → Workflow update validates changes in flight | Change started after planning | evals/update/test_inflight.py | test_change_started_after_plan_stops_swap | green |
| install-update → Workflow update validates changes in flight | Patch update with a change in flight | evals/update/test_inflight.py | test_patch_update_skips_validation | green |
| install-update → A refused change is also checked against the installed schema | Change already incomplete on the installed version | evals/update/test_inflight.py | test_refusal_names_installed_version_when_change_already_fails (plan and swap-check) | red |
| install-update → A refused change is also checked against the installed schema | Change fails only on the target | evals/update/test_inflight.py | test_refusal_blames_target_when_installed_passes | red |
| install-update → A refused change is also checked against the installed schema | Installed schema fails under the current OpenSpec | evals/update/test_inflight.py | test_no_installed_claim_when_installed_schema_invalid | red |
| install-update → A refused change is also checked against the installed schema | No installed schema to compare with | evals/update/test_inflight.py | test_no_installed_claim_without_installed_version | red |
| releases → Older untagged versions are published first | Older version untagged | evals/release/test_release.py | TestUntagged.test_older_blocks_newer | green |
| releases → Older untagged versions are published first | Tag push failed earlier | evals/release/test_release.py | TestUntagged.test_local_only_tag_is_not_published | green |
| releases → Older untagged versions are published first | First release's tag push failed | evals/release/test_release.py | TestUntagged.test_first_release_push_failed | green |
| releases → Older untagged versions are published first | Backfill below the latest tag | evals/release/test_release.py | TestUntagged.test_backfill_below_latest | green |
| releases → Older untagged versions are published first | Local tags only | evals/release/test_release.py | TestUntagged.test_local_flag_reads_no_remote | green |
| releases → Older untagged versions are published first | Local read with a local-only tag | evals/release/test_release.py | TestUntagged.test_local_flag_counts_local_tag_and_says_so (also test_without_origin_reports_local_tags) | green |
| releases → A bumped version is greater than main's before it merges | Two changes bump to the same version | evals/release/test_release.py | TestCheckMain.test_duplicate_bump_refused | green |
| releases → A bumped version is greater than main's before it merges | Main moved past the bump | evals/release/test_release.py | TestCheckMain.test_main_ahead_refused | green |
| releases → A bumped version is greater than main's before it merges | Bump still ahead | evals/release/test_release.py | TestCheckMain.test_bump_ahead_passes | green |
| releases → A bumped version is greater than main's before it merges | Branch did not bump | evals/release/test_release.py | TestCheckMain.test_no_bump_passes | green |
| releases → A bumped version is greater than main's before it merges | Main was merged into the branch after the duplicate landed | evals/release/test_release.py | TestCheckMain.test_duplicate_after_main_merged_in_refused | green |
| releases → A bumped version is greater than main's before it merges | Main has no version yet | evals/release/test_release.py | TestCheckMain.test_main_without_version_passes | green |
| releases → Ship, local merge and watch check the version against main | Ship of a duplicate version | evals/release/test_skill_text.py | TestShipText.test_ship_checks_version_against_fetched_main_before_push | green |
| releases → Ship, local merge and watch check the version against main | Main merged a duplicate while the PR waited | evals/release/test_skill_text.py | TestWatchText.test_watch_checks_version_before_ready_and_merge | green |
| releases → Ship, local merge and watch check the version against main | Local merge of a duplicate version | evals/release/test_skill_text.py | TestFinishText.test_local_merge_checks_version_before_merge | green |
| releases → Ship, local merge and watch check the version against main | Releases disabled | evals/release/test_skill_text.py | test_version_check_only_with_release_enabled | green |
| change-finish → Finish offers a release once the change is on main | Untagged version after a PR merge | evals/release/test_skill_text.py | TestFinishText.test_release_step_before_roadmap_offer | green |
| change-finish → Finish offers a release once the change is on main | Auto release | evals/release/test_skill_text.py | TestFinishText.test_offers_untagged_oldest_first | green |
| change-finish → Finish offers a release once the change is on main | An earlier version was left untagged | evals/release/test_skill_text.py | TestFinishText.test_offers_untagged_oldest_first | green |
| change-finish → Finish offers a release once the change is on main | Version already tagged | evals/release/test_skill_text.py | TestFinishText.test_no_offer_when_untagged_empty | green |
| change-finish → Finish offers a release once the change is on main | Releases disabled | evals/release/test_skill_text.py | TestFinishText.test_release_step_before_roadmap_offer | green |
| change-finish → Finish offers a release once the change is on main | Auto publish fails | evals/release/test_skill_text.py | TestFinishText.test_publish_failure_keeps_roadmap_offer | green |
| change-finish → Finish offers a release once the change is on main | Local finish with a github.com origin and no login | evals/release/test_skill_text.py | TestFinishText.test_local_mode_reads_local_tags_unfenced | green |
| review-routes → Reviewers run isolated and read-only | OMP review starts a fresh session | evals/review-routes/test_review_run.py | test_omp_fresh_session_dir_per_run | green |
| review-routes → Reviewers run isolated and read-only | Reviewer tries to write | evals/review-routes/trial.md | recorded trial (`git status --porcelain` after the write request); re-run for codex on Windows in 3.5 | n/a (recorded trial: needs real reviewer CLIs; 3.5 run recorded, porcelain unchanged) |
| review-routes → Reviewers run isolated and read-only | Codex on Windows with a sandbox setting | evals/review-routes/test_review_run.py | test_codex_windows_forwards_sandbox_only | green |
| review-routes → Reviewers run isolated and read-only | Codex on Windows without a usable setting | evals/review-routes/test_review_run.py | test_codex_windows_no_usable_sandbox_adds_nothing | green |
| review-routes → Reviewers run isolated and read-only | Codex off Windows | evals/review-routes/test_review_run.py | test_codex_off_windows_adds_no_sandbox | green |
| review-routes → Review output is validated and fails closed | Valid findings | evals/review-routes/test_review_run.py | test_valid_findings_recorded | green |
| review-routes → Review output is validated and fails closed | Output that is not JSON | evals/review-routes/test_review_run.py | test_prose_output_invalid_no_fallthrough | green |
| review-routes → Review output is validated and fails closed | Subagent design review without a verdict | evals/review-routes/test_review_run.py | test_record_design_without_verdict_invalid | green |
| review-routes → Review output is validated and fails closed | Design review with two verdicts | evals/review-routes/test_review_run.py | test_design_two_verdicts_invalid_no_file | green |
| review-routes → Review output is validated and fails closed | Reviewer exceeds the deadline | evals/review-routes/test_review_run.py | test_timeout_kills_reviewer_exit_3 | green |
| review-routes → Review output is validated and fails closed | Design review that could not review | evals/review-routes/test_review_run.py | test_design_blocked_verdict_invalid_keeps_review | green |
| review-routes → Review output is validated and fails closed | Subagent design review that could not review | evals/review-routes/test_review_run.py | test_record_out_refused_keeps_review_and_scratch | green |
| review-routes → Review output is validated and fails closed | Valid subagent design review | evals/review-routes/test_review_run.py | test_record_out_valid_writes_review_removes_scratch | green |
| review-routes → Review output is validated and fails closed | Verdict a reviewer may not set | evals/review-routes/test_review_run.py | test_design_override_and_skipped_verdicts_invalid | green |
| review-routes → Review output is validated and fails closed | CHANGES_APPLIED does not match the verdict | evals/review-routes/test_review_run.py | test_design_changes_applied_must_match_verdict | green |
| review-routes → Review output is validated and fails closed | Valid re-check | evals/review-routes/test_review_run.py | test_design_recheck_with_changes_applied_yes_valid | green |
| review-routes → Review output is validated and fails closed | Large OMP event stream with a small answer | evals/review-routes/test_review_run.py | test_omp_large_stream_small_answer_valid | green |
| review-routes → Review output is validated and fails closed | OMP answer over the bound | evals/review-routes/test_review_run.py | test_omp_answer_over_bound_invalid | green |
| review-routes → Review output is validated and fails closed | OMP stream without a final message | evals/review-routes/test_review_run.py | test_omp_stream_without_agent_end_invalid | green |
| planning-stores → Store staging belongs to one checkout | Two checkouts stage against one store | evals/update/test_store.py | TestStagingPerCheckout.test_two_checkouts_stage_separately | red |
| planning-stores → Store staging belongs to one checkout | Discard after a refused swap keeps the other checkout's rollback copy | evals/update/test_store.py | TestStagingPerCheckout.test_refused_swap_recover_keeps_other_rollback_copy | red |
| planning-stores → Store staging belongs to one checkout | Another checkout's staging makes the store busy | evals/update/test_store.py | TestStagingPerCheckout.test_other_checkout_staging_makes_store_busy | red |
| planning-stores → Store staging belongs to one checkout | Both checkouts staged before either swapped | evals/update/test_store.py | TestStagingPerCheckout.test_both_staged_first_refused_swap_discards_and_other_swaps | red |
| planning-stores → Store staging belongs to one checkout | Interrupted update from an earlier version | evals/update/test_store.py | TestStagingPerCheckout.test_recover_uses_legacy_shared_staging_from_journal | red |
| debugging → A debug stash is named and reported | Dirty tree is tested | evals/git-workflow/test_instructions.py | DebugStash.test_stash_is_named_and_ref_reported | green |
| debugging → A debug stash is named and reported | Restore conflicts | evals/git-workflow/test_instructions.py | DebugStash.test_conflicting_restore_keeps_stash_and_stops | green |
| debugging → An interrupted debug stash is found on the next run | Earlier run was interrupted | evals/git-workflow/test_instructions.py | DebugStash.test_start_of_run_lists_leftover_stash_and_offers_restore | green |
| debugging → An interrupted debug stash is found on the next run | Stash ref moved since it was reported | evals/git-workflow/test_instructions.py | DebugStash.test_ref_resolved_by_message_before_apply_and_drop | green |
| debugging → An interrupted debug stash is found on the next run | No leftover stash | evals/git-workflow/test_instructions.py | DebugStash.test_no_leftover_reported_and_continues | green |
| debugging → An interrupted debug stash is found on the next run | Other stashes are left alone | evals/git-workflow/test_instructions.py | DebugStash.test_only_specwright_debug_stashes_are_offered | green |

## 1. Install version token boundary (#91)

- [x] 1.1 Write the failing tests in `evals/git-workflow/test_instructions.py` `TestOpenSpecPin`:
  - `test_step3_run_on_token_is_unreadable`: the Step 3 bullet says a token directly followed by a digit, letter, `.`, `+` or `-` is unreadable output, with `1.14.1.0` and `1.14.1vendor` as examples.
  - `test_step1_run_on_token_is_unreadable`: Step 1 applies the same rule "as Step 3 takes it".
  - `test_readme_token_rule_on_sample_outputs`: takes the token pattern from the README text and applies the stated rule (first match, then the boundary character) to `1.14.1`, `openspec 1.14.1\n`, `1.14.1+vendor.1`, `1.14.1.0` and `1.14.1vendor`. Expect `1.14.1`, `1.14.1`, `1.14.1+vendor.1`, unreadable and unreadable.

  Run `python -m pytest evals/git-workflow/test_instructions.py -k OpenSpecPin` and confirm that the new tests fail on the missing rule.
- [x] 1.2 Edit `README.md` Step 3 (around line 134) and Step 1 (around line 78) per design D1. State the boundary rule once, in Step 3; Step 1 refers to it. Verify that 1.1's tests pass and that all of `TestOpenSpecPin` stays green (update `test_exact_match_counts_build_metadata_as_mismatch` only where the token's surrounding text moved, and keep the `pin_drift` prose check passing). Then flip those rows green.

## 2. Releases: local tag read and version-ahead check (#93, #94)

- [x] 2.1 Write the failing `release.sh` tests in `evals/release/test_release.py`:
  - `TestUntagged.test_local_flag_reads_no_remote`: origin points at an unreachable URL, and a `git` shim on PATH records any `ls-remote`.
  - `TestUntagged.test_local_flag_counts_local_tag_and_says_so`
  - `TestUntagged.test_without_origin_reports_local_tags`: `"tags": "local"`.
  - The new class `TestCheckMain`, built from the `make_repo`, `merge_commit` and `push` fixtures, for the six check scenarios. These include `feat/b` with `origin/main` merged in, and `origin/main` without a `VERSION` file.

  Confirm that each fails for the right reason (unknown option, or no refusal).
- [x] 2.2 In `skills/specwright-release/scripts/release.sh`:
  - add `untagged --local` and the `tags` field per design D2;
  - add `check --main <ref>` per design D3: the merge-base version, the `--no-merges <ref>..HEAD` primary-file log, refusal `version_not_ahead_of_main`, and no readable version at `<ref>` passing;
  - update the `COMMANDS` table and the stale header comment ("no local tag", line 33).

  Verify that 2.1's tests pass and that `python -m pytest evals/release` is green, then flip the rows green.
- [x] 2.3 Write the failing skill-text tests in `evals/release/test_skill_text.py`:
  - `TestFinishText.test_local_mode_reads_local_tags_unfenced`: `untagged --local`, no login, no `as.sh` on the local path, and the "from local tags" wording.
  - `TestFinishText.test_local_merge_checks_version_before_merge`
  - `TestShipText.test_ship_checks_version_against_fetched_main_before_push`: a fenced fetch of main, then `check --main origin/<main>` next to `pr.validate`, before any push.
  - `TestWatchText.test_watch_checks_version_before_ready_and_merge`
  - `test_version_check_only_with_release_enabled`

  Confirm that they fail on the current text.
- [x] 2.4 Edit the skill texts:
  - `skills/specwright-finish/SKILL.md`: the Release step uses `--local` in `finish: local`, and the `## local` merge step runs `check --main <main>` before `git merge`.
  - `skills/specwright-pr/SKILL.md`: ship runs `check --main origin/<main>` after the fenced fetch, before the push; watch step 3 runs it before ready and before the merge, against a refreshed `origin/<main>`. A refusal stops with the message to bump again.
  - `skills/specwright-release/SKILL.md`: the `bump` and `publish` sections describe `check --main` and `untagged --local`, plus the error-table row.

  Verify that 2.3's tests pass and that `python -m pytest evals/release evals/git-workflow/test_instructions.py` is green, then flip the rows green.

## 3. Review routes: verdict values, subagent scratch, codex sandbox, OMP answer (#95)

- [x] 3.1 Move the review-routes fixtures to valid values: `VERDICT_OK` becomes `VERDICT: APPROVE` with `CHANGES_APPLIED: n/a`, and the two-verdict fixtures use valid values. Then write the failing validation tests in `evals/review-routes/test_review_run.py`:
  - `test_design_blocked_verdict_invalid_keeps_review`: an earlier `review.md` stays byte-identical.
  - `test_design_override_and_skipped_verdicts_invalid`, for `run` and `record`.
  - `test_design_changes_applied_must_match_verdict`
  - `test_design_recheck_with_changes_applied_yes_valid`
  - `test_record_out_refused_keeps_review_and_scratch`
  - `test_record_out_valid_writes_review_removes_scratch`, plus `record --kind design --scratch` printing a fresh path under the state dir.

  Confirm that they fail for the right reason, and that the existing design tests are still green with the new fixtures.
- [x] 3.2 In `skills/specwright-review/scripts/review-run.sh`, implement `validate_design` per design D5 (whole lines, the value sets, the pairing, the value named in the error), and `record --kind design --scratch` and `--out` (atomic write on success, scratch removed; on exit 3, `--out` untouched and scratch kept and reported). Verify that 3.1's tests pass and that `python -m pytest evals/review-routes` is green, then flip the rows green.
- [x] 3.3 Write the failing tests, then implement:
  - **Codex sandbox (D4).** `test_codex_windows_forwards_sandbox_only`, `test_codex_windows_no_usable_sandbox_adds_nothing` (missing file, a TOML error, no key, a non-name value) and `test_codex_off_windows_adds_no_sandbox`, with `os.name` and `CODEX_HOME` controlled through test hooks. Update `test_command_lines_read_only_allowlists` and `test_model_and_thinking_flags` for the possible extra `-c` (look up `model_reasoning_effort` by value, not by the first `-c`). Implement the `windows.sandbox` read with `tomllib`, appended as `-c windows.sandbox="<value>"`, and record the forwarded value in the receipt.
  - **OMP answer (D6).** `test_omp_large_stream_small_answer_valid` (a 3 MiB recorded stream from the `reviewcli.py` fake with a 19 KB final answer), `test_omp_answer_over_bound_invalid` and `test_omp_stream_without_agent_end_invalid`. Implement the line-scanning OMP reader with `readline(MAX_EVENT_LINE + 1)`, drop the raw stdout size check for `omp`, and bound the answer with `MAX_OUTPUT`.

  Verify with `python -m pytest evals/review-routes` and flip the rows green.
- [x] 3.4 Switch the subagent design-review dispatch to the scratch file and `record --out`:
  - `schemas/specwright/schema.yaml` (review instruction, subagent route; instruction text only);
  - `skills/specwright-review/SKILL.md` (Design reviews `subagent`, and the CLI-route sentence naming the value check);
  - `skills/specwright-roadmap/SKILL.md` (init step 5);
  - `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md` (write the single output file the request names).

  Add `test_subagent_design_dispatch_uses_scratch_and_record_out` to `evals/review-routes/test_skill_text.py`. Verify with `python -m pytest evals/review-routes` and `openspec schema validate specwright` (from `schemas/`, and from the repo root for the installed copy).
- [x] 3.5 Recorded trial on this Windows machine: run a real design review with `review-run.sh run --kind design --route codex` against this change, with the user's `windows.sandbox` forwarded. Confirm that codex reads the checkout (a valid verdict, and no `BLOCKED`) and that `git status --porcelain` is unchanged after a write request. Append the run (CLI version, argv, exit, verdict, porcelain) to `evals/review-routes/trial.md`. If codex is not installed or has no `windows.sandbox` setting here, record that and report it for the user to run.

## 4. Store staging per checkout (#97)

- [ ] 4.1 Write the failing tests in `evals/update/test_store.py`, new class `TestStagingPerCheckout`, using `make_store_pair`. Cover all five scenarios from the test map:
  - both A and B stage, giving two directories, each named in its own journal;
  - A swaps, B stages and its swap is refused: B's refused swap removes only B's staging and journal, A's `<idA>/old` survives and A's `recover --rollback` restores the old schema;
  - B's busy message names A's staging directory and says to rerun the update in that checkout, and B's staging and journal are gone;
  - both staged: A's swap is refused and removes A's staging and journal, B's swap runs, and A's rerun after B finished is not refused for staging;
  - `test_second_claimer_names_owner` without moving B's staging aside (B stages after A finished);
  - a hand-written `format: 1` journal naming the legacy shared path is recovered with that path.

  Confirm that they fail for the right reason.
- [ ] 4.2 In `scripts/update.sh`:
  - key the store schema group's staging path in `mk_group` by the first 12 hex digits of SHA-256 of the normalised `code` path (design D7);
  - make `store_busy_reason` report `another checkout's update is staged in the store: <path>; finish or recover it by rerunning the update in that checkout` for an untracked `openspec/.specwright-update-schemas*` that is not this journal's;
  - make a swap refused before its first rename remove its own staging directories and journal, as `recover` does for a swap that never started (design D7, review round 2 M1);
  - leave every other user reading the journal's path.

  Verify that 4.1's tests pass, that `evals/update/test_update.py` (the code-side staging names at lines 175-177), `test_store.py` and `test_interrupt.py` stay green, and flip the rows green.

## 5. Update refusal names the installed version (#99)

- [ ] 5.1 Write the failing tests in `evals/update/test_inflight.py`:
  - `test_refusal_names_installed_version_when_change_already_fails`: a change with `tasks.md` and no `review.md`, at the plan and at swap-check;
  - `test_refusal_blames_target_when_installed_passes`, using `Base.download(failing=True)`;
  - `test_no_installed_claim_when_installed_schema_invalid`: the installed schema corrupted so that `openspec schema validate` fails;
  - `test_no_installed_claim_without_installed_version`

  Confirm that they fail for the right reason.
- [ ] 5.2 In `scripts/update.sh`:
  - have `check_change` return the failing step with its error;
  - add the installed-schema recheck for invalid entries in `make_plan` and `cmd_swap_check` per design D8, in its own scratch directory, labelled by `VERSION` or by the store's `STORE` version;
  - append the note only when the installed schema validates.

  Verify that 5.1's tests pass and that `python -m pytest evals/update/test_inflight.py` is green, then flip the rows green.

## 6. Debug stash recovery (#53)

- [x] 6.1 Write the failing skill-text tests in `evals/git-workflow/test_instructions.py`, new class `DebugStash` (constant `DEBUG = ROOT / "skills" / "specwright-debug" / "SKILL.md"`), one per test-map row. They cover:
  - the named stash `git stash push -u -m "specwright-debug: <topic>"` with the ref reported;
  - the start-of-run `git stash list` scan for `specwright-debug: ` with a restore offer and no new stash until the user decides;
  - restore with `apply`, then `drop` only after the files are verified, each with the ref looked up again by its message;
  - a conflict keeping the stash and stopping;
  - no leftover reported;
  - other stashes left alone.

  Confirm that they fail on the current text.
- [x] 6.2 Edit `skills/specwright-debug/SKILL.md` per design D9. Verify that 6.1's tests pass with `python -m pytest evals/git-workflow/test_instructions.py -k DebugStash`, then flip the rows green.

## 7. Architecture, release 0.6.1 and integration

- [ ] 7.1 Update `openspec/architecture.md`:
  - the `specwright-debug` row: it owns the named stash until it is restored;
  - the update journal and staging row: the store staging is keyed by checkout;
  - the Reviewer routes contract sentence: the verdict and `CHANGES_APPLIED` values, the subagent's scratch file with `record --out`, the OMP answer bound, and that this tightens ADR 0007's validation.

  Verify with `grep -n "specwright-debug: \|schemas-<id>\|record --out" openspec/architecture.md`.
- [ ] 7.2 `bash skills/specwright-release/scripts/release.sh bump --to 0.6.1` (`VERSION`, the README badge, every `skills/*/SKILL.md` `metadata.version`), verified by `bash skills/specwright-release/scripts/release.sh check` reporting 0.6.1, and by `release.sh check --main origin/main` passing after a fenced fetch.
- [ ] 7.3 Run `python -m pytest evals/pr-pair evals/git-workflow evals/review-routes evals/update evals/release`. Everything must pass; the update suite takes about half an hour on Windows, so run it in the background. Then run `openspec validate fix-m3-gaps --strict` and `openspec schema validate specwright`.

## Workflow follow-up

- Pre-ship review, then ship the PR with closing lines for #91, #93, #94, #95, #97, #99 and #53.
- After merge-ready: archive, then publish release 0.6.1 through `specwright-release` (the release workflow is enabled).
