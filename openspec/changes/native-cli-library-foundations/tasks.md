# Tasks

## Test map
| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| native-cli → sw documents are compact JSON ending in one line feed | Document on Windows | evals/cli/test_documents.py | test_document_is_compact_with_one_lf | green |
| native-cli → sw documents are compact JSON ending in one line feed | Non-UTF-8 file name in a document | cli/test/vcs/document_test.dart | writes lone U+DC80..U+DCFF back as the original bytes | green |
| native-cli → sw documents are compact JSON ending in one line feed | A value a document cannot hold | cli/test/vcs/document_test.dart | a value JSON cannot hold is internal_error | green |
| native-cli → JSON input that is not plain JSON is refused | Well-formed input | evals/pr-pair/test_reviewers.py | GenericRules.test_review_on_head_reports_whatever_the_cutoff | green |
| native-cli → JSON input that is not plain JSON is refused | Non-finite number | cli/test/pr/reviewers_test.dart | NaN and Infinity in material stop naming the file | green |
| native-cli → JSON input that is not plain JSON is refused | Very deep nesting | cli/test/vcs/document_test.dart | 100,000 levels never crash | green |
| native-cli → JSON input that is not plain JSON is refused | An integer that cannot be held exactly | cli/test/pr/reviewers_test.dart | a timeout beyond 64 bits is a config error | green |
| native-cli → JSON input that is not plain JSON is refused | A JSON file over the size limit | cli/test/vcs/document_test.dart | a file over 32 MiB stops naming the file | green |
| native-cli → JSON input that is not plain JSON is refused | An integer setting beyond 64 bits | cli/test/settings/rules_test.dart | an integer setting beyond 64 bits is bad_setting | green |
| native-cli → JSON input that is not plain JSON is refused | Reviewer config for ordinary values | cli/test/settings/reviewer_config_test.dart | names the file by the SHA-256 of its bytes under <state>/reviewers | green |
| native-cli → sw options follow one parsing rule | Equals form | cli/test/options_test.dart | equals form matches the two-word form | green |
| native-cli → sw options follow one parsing rule | A value that looks like an option | cli/test/options_test.dart | the next word is the value | green |
| native-cli → sw options follow one parsing rule | A repeated option holding a comma | cli/test/options_test.dart | repeated values keep their commas | green |
| native-cli → sw options follow one parsing rule | Abbreviated option | cli/test/pr/reviewers_test.dart | an abbreviated option is a usage stop | green |
| native-cli → sw options follow one parsing rule | Missing value | cli/test/vcs/args_test.dart | a value-taking option at the end needs a value | green |
| native-cli → sw options follow one parsing rule | Words that are not paths | cli/test/vcs/args_test.dart | a word before -- is a usage stop | green |
| native-cli → sw options follow one parsing rule | Shipped callers use whole option names | evals/cli/test_option_callers.py | test_shipped_callers_use_whole_names | green |
| native-cli → The shipped dependencies stay hook-free and carry their notices | Current dependency set | cli/test/no_build_hooks_test.dart | the closure has no hooks and every package has a notice | red |
| native-cli → The shipped dependencies stay hook-free and carry their notices | A hook package enters the lock file | cli/test/no_build_hooks_test.dart | reports a package whose pubspec has a top-level hooks key | green |
| native-cli → The shipped dependencies stay hook-free and carry their notices | A dependency without a notice | cli/test/no_build_hooks_test.dart | a package with no notice is named | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | Several pages | cli/test/pr/workflow_transport_test.dart | slurped pages flatten in order | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | No items | cli/test/pr/workflow_transport_test.dart | an empty slurp is an empty list | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | A page that is not an array | cli/test/pr/workflow_transport_test.dart | a non-array page is an unknown read | red |
| pr-script-runtime → Paginated GitHub lists read every page or decide nothing | gh older than 2.48 | cli/test/pr/workflow_transport_test.dart | a slurp failure names gh 2.48 | red |
| pr-script-runtime → Prerequisites are stated and checked at install | All prerequisites present | evals/git-workflow/test_instructions.py | test_install_checks_core_and_pr_prerequisites (update floor to 2.48) | red |
| pr-script-runtime → Prerequisites are stated and checked at install | Python missing | evals/git-workflow/test_instructions.py | test_install_checks_core_and_pr_prerequisites | green |
| pr-script-runtime → Prerequisites are stated and checked at install | gh missing | evals/git-workflow/test_instructions.py | test_install_reports_pr_workflow_not_ready | red |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Policy's remote settings read is strict | evals/pr-pair/test_parity.py | test_policy_stops | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Git Bash path forms | evals/pr-pair/test_parity.py | test_git_bash_paths_read_the_same_repo | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Unchanged black-box evals pass on sw | .github/workflows/evals.yml | evals/pr-pair on three OSes | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Differential run against the frozen script | evals/pr-pair/test_parity.py | assertParity on parsed values | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | A malformed settings file names its line | evals/pr-pair/test_parity.py | test_context_tab_in_indentation_names_line_7 | green |
| pr-script-runtime → The ported pr-pair subcommands keep the script's contracts | Settings not pinned on GitButler | evals/pr-pair/test_parity.py | test_context_on_gitbutler_pins_the_settings | green |
| pr-script-runtime → sw pr reviewers keeps the evaluator's contract | Unchanged evaluator tests | .github/workflows/evals.yml | evaluator tests on three OSes | green |
| pr-script-runtime → sw pr reviewers keeps the evaluator's contract | Material that is not its head | evals/pr-pair/test_parity.py | ReviewersParity on parsed values | green |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unchanged black-box evals pass on sw | .github/workflows/evals.yml | evals/vcs on three OSes | green |
| vcs-backends → sw vcs keeps vcs.sh's output and exit-code contract | Unknown subcommand | cli/test/vcs/args_test.dart | an unknown subcommand is a usage document with exit 2 | green |
| vcs-backends → sw vcs documents keep their values and name bytes | Line separators parse back | cli/test/vcs/document_test.dart | U+2028 and U+2029 parse back | green |
| vcs-backends → sw vcs documents keep their values and name bytes | A non-UTF-8 name from a tool round-trips | evals/vcs/test_sw_bytes.py | test_non_utf8_name_round_trips | green |
| vcs-backends → sw vcs documents keep their values and name bytes | A valid U+FFFD in a name is just a character | evals/vcs/test_sw_bytes.py | test_valid_replacement_char_is_a_character | green |
| vcs-backends → sw vcs documents keep their values and name bytes | Tool input reaches the tool | evals/vcs/test_sw_bytes.py | test_check_ignore_receives_oversized_name | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Unchanged task-cover evals pass on sw | .github/workflows/evals.yml | task-cover tests on three OSes | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Usage error | cli/test/commit/task_cover_test.dart | usage error names --code | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | A group number beyond 64 bits is not a task | cli/test/commit/task_cover_test.dart | a group number beyond 64 bits is not a task | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | A numbered heading beyond 64 bits is ignored | cli/test/commit/task_cover_test.dart | an oversized heading leaves the report intact | green |
| task-commits → sw commit task-cover keeps task-cover.sh's contract | Task ids are ASCII digits | cli/test/commit/task_cover_test.dart | non-ASCII digit ids are not tasks | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Unchanged finish evals pass on sw | .github/workflows/evals.yml | evals/finish on three OSes | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Output bytes equal the old script's | evals/finish/test_parity.py | TestParityGit.test_committed_single_archive (compare parsed values) | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Printed scripts still call vcs.sh by path | evals/finish/test_parity.py | TestParityGit.test_committed_single_archive | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | Usage error | evals/finish/test_undo_plan.py | test_usage_errors_exit_2 | green |
| change-finish → sw finish undo-archive-plan keeps finish.sh's contract | User-task ids are ASCII digits | evals/finish/test_parity.py | user_task_ids_are_ascii_digits (add explicit case) | green |
| native-cli → JSON input that is not plain JSON is refused | An oversized feedback record stays unreadable | cli/test/pr/feedback_record_test.dart | an oversized record blocks replacement | green |
| native-cli → JSON input that is not plain JSON is refused | Oversized workflow and intent files | cli/test/pr/workflow_transport_test.dart | oversized workflow JSON retains its stop and raw path | green |
| native-cli → JSON input that is not plain JSON is refused | Feedback integers are exact | cli/test/pr/feedback_pass_test.dart | oversized intent round is invalid_intent | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Feedback round counters remain encodable | evals/pr-pair/test_workflow_parity.py | test_rounds_without_feedback_trailers; test_rounds_trailers_and_unreadable_remote | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Oversized feedback-round trailer is refused | evals/pr-pair/test_workflow_parity.py | test_rounds_preserves_arbitrary_precision_feedback_trailers (replace with explicit refusal difference) | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Every workflow command has differential coverage | evals/pr-pair/test_workflow_parity.py | test_every_workflow_command_has_differential_coverage | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Unknown read permits no follow-on mutation | evals/pr-pair/test_workflow_parity.py | test_unknown_read_permits_no_follow_on_mutation | red |
| pr-script-runtime → Native PR workflow commands preserve their effects | Merge is attempted once then read back | evals/pr-pair/test_workflow_parity.py | test_merge_is_attempted_once_then_read_back | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Moved remote branch is retained | evals/pr-pair/test_workflow_parity.py | test_moved_remote_branch_is_retained | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Rendered closing lines preserve code boundaries | evals/pr-pair/test_workflow_parity.py | test_rendered_closing_lines_preserve_code_boundaries | green |
| pr-script-runtime → Native PR workflow commands preserve their effects | Malformed table text follows HTML5 interpretation | cli/test/pr/closing_test.dart | raw table follows standard HTML5 interpretation | green |
| native-cli → JSON input that is not plain JSON is refused | rounds with max_fix_rounds beyond 64 bits stops with bad_setting | evals/pr-pair/test_workflow_parity.py | test_rounds_without_feedback_trailers (oversized setting becomes explicit refusal difference) | green |
| native-cli → JSON input that is not plain JSON is refused | policy lists an oversized head integer in invalid and exits 0 | cli/test/pr/policy_test.dart | oversized head timeout is invalid with default values | green |
| native-cli → JSON input that is not plain JSON is refused | Lone surrogate keeps its pre-change digest | cli/test/settings/reviewer_config_test.dart | a lone surrogate in a report string keeps its pre-change digest (pin existing surrogate behavior) | green |
| native-cli → JSON input that is not plain JSON is refused | Watcher compact keys remain readable | cli/test/pr/reviewers_test.dart | the reviewers document keeps the compact keys the watcher reads | green |
| native-cli → sw documents are compact JSON ending in one line feed | Printed undo guard reads the compact branch | cli/test/finish/undo_plan_test.dart | the printed guard runs on the planned branch and refuses another | green |
| native-cli → sw documents are compact JSON ending in one line feed | Printed undo guard reads the compact branch | cli/test/finish/undo_plan_test.dart | the printed jj guard runs on the planned branch and refuses another | green |
| native-cli → sw documents are compact JSON ending in one line feed | Printed undo guard reads the compact branch | evals/finish/test_undo_jj.py | test_undo_plan_jj_commands_and_result | green |
| vcs-backends → sw vcs documents keep their values and name bytes | Line separators stay escaped | cli/test/vcs/document_test.dart | U+2028 and U+2029 parse back (retained legacy scenario title) | green |

Refreshed against main `3fc5454` on 2026-11-10. Green rows name existing cases by inspection, not tests executed during planning; red rows name planned additions or assertions to revise. CI suite rows denote integration gates. No implementation task is ticked by this planning refresh.

## 1. Refresh and dependencies

- [x] 1.1 Confirm the 2026-11-10 refresh baseline `3fc5454` is still current before apply; A6 is verified at `workflow.dart:324-368`, VERSION is 0.30.0, and the notice already ships. Recheck changed citations/callers if main moved; preserve the merged MODIFIED requirements and exact test names. Verify with strict `openspec validate native-cli-library-foundations`.
- [x] 1.2 Verify A8 and add `crypto` and `path` to `cli/pubspec.yaml`: run `dart pub get`, then `mise exec -- dart test test/no_build_hooks_test.dart` from `cli/`, and confirm the test passes with the new lock file.
- [x] 1.3 Carry C6: confirm ADR 0033 states that focused packages need approval and no build hooks, and that a port preserves workflow guarantees and not Python bytes. Verify by reading the accepted ADR.

## 2. JSON wrapper, integers and crypto

- [x] 2.1 Verify A1, A2, A3 and A7: run the SDK on 100,000 nested levels, an integer beyond 64 bits and lone surrogate escapes, and compare `reviewerConfigBytes` with `JsonEncoder` output for values within 64 bits, including lone-surrogate strings and a fixed pre-change digest. Verify by recording the results in the group's test comments; if A3 or A7 fails, use the owner-approved D1 surrogate-string fallback and recheck the same invariants; other disproved assumptions stop this group under the drift rule.
- [x] 2.2 Write the failing tests for the red rows of "sw documents are compact JSON ending in one line feed", "JSON input that is not plain JSON is refused", "A group number beyond 64 bits is not a task", "A numbered heading beyond 64 bits is ignored" and "Line separators parse back". Verify each fails for the right reason.
- [x] 2.3 Reduce `documentText` and `documentBytes` in `cli/lib/src/vcs/document.dart` to `JsonEncoder` and `encodeEscaped` with the D1 string fallback if required by A3/A7, and add `decodeJson` and `readJsonFile` with the 32 MiB bound (D1, D2). Verify the document and deep-nesting rows turn green.
- [x] 2.4 Move every JSON read onto the wrapper including feedback record/pass and workflow file/tool-response reads listed in the design; extend the injected record-file seam for bounded reads, retain raw paths and existing error mappings, replace the obsolete uncapped-input comment, and delete `cli/lib/src/settings/pyjson.dart` and `cli/test/settings/pyjson_test.dart`. Verify with `grep` that no `pyjson` import remains and the non-finite, oversized-file and reviewer-timeout rows turn green.
- [x] 2.5 Implement D8 end to end: duration, max_fix_rounds and reviewersOf return no BigInt; oversized integer settings create a bad_setting problem plus defaults (timeout 1200, poll_interval 300, max_fix_rounds 2). Context stops with bad_setting/exit 2 before config writes. workflowContexts collects problems and rounds/pass stop with bad_setting/exit 2. Policy main uses bads; policy head lists invalid and uses defaults in values, drift, pr.reviewers and config. Render oversized raw merge_method/delete_branch as settingText. Keep int task groups and ignore oversized task/subject/trailer/heading groups. Convert in-range workflow rounds/max_trailer to int; refuse oversized trailers as unknown reads. Replace oversized max_fix_rounds and trailer oracle cases with explicit differences, and verify the red integer-setting, reviewer-timeout, feedback, policy-head and task-cover rows.
- [x] 2.6 Replace the hand-written SHA-256 in `cli/lib/src/settings/reviewer_config.dart` with `crypto`. Verify "Reviewer config for ordinary values" still passes with a fixed digest from before the change.
- [x] 2.7 Move stdout comparisons to parsed values in `evals/pr-pair/test_parity.py` (`assertParity`, `ReviewersParity.pair`), `evals/pr-pair/test_workflow_parity.py` (including normal round counters and explicit oversized refusals), `evals/finish`, `evals/vcs` and the `task-cover` tests in `evals/git-workflow`, listing the `NaN` and abbreviated-option differences. Remove the retired cases from `cli/test/vcs/document_test.dart`. Verify in the PR's CI on three OSes and flip the eval rows green.
- [x] 2.8 Carry C1, C3, C4, C10 and C12: write the doc comments on `reviewerConfigBytes`, `documentBytes`, `decodeJson`, `readJsonFile` and the snapshot regex gap in `cli/lib/src/pr/text.dart`. Verify by reading each at its destination.
- [x] 2.9 Carry C2 and C11: confirm the requirements "sw documents are compact JSON ending in one line feed" and "JSON input that is not plain JSON is refused" hold those facts after the refresh. Verify by reading the delta spec.
- [x] 2.10 Carry C13: make the jj and GitButler guards printed by `sw finish undo-archive-plan` match the compact `"branch":"<name>"`, comment `branchPattern`, add execution-time guard tests for jj and GitButler (a compact state document naming the planned branch passes; one naming another branch exits 1 with `wrong branch` before the next step), and list the guard text as the one `script` difference in `evals/finish/test_parity.py` and `evals/vcs/test_gitbutler_parity.py`. Verify with `mise exec -- dart test test/finish/undo_plan_test.dart` from `cli/` and the finish and vcs undo evals in CI.

## 3. Option parsing

- [x] 3.1 Verify A5: run `ArgParser` on a repeated single option, `--` as an option value and single-dash words. Verify by recording results in `cli/test/options_test.dart` comments; a disproved assumption stops this group under the drift rule.
- [x] 3.2 Write `evals/cli/test_option_callers.py`, which scans shipped skills, scripts and `sw`'s own launches for option words and for text matching on documents, including Dart consumers and only the documented C12 and C13 exceptions, and add it to `evals/suites.json`. Verify with `python -m unittest evals/cli/test_option_callers.py` and the map test.
- [x] 3.3 Write the failing tests for the red rows of "sw options follow one parsing rule". Verify each fails for the right reason.
- [x] 3.4 Add `cli/lib/src/options.dart` (D3) and replace `parsePairArgs`, `_parseArgs`, the loop in `parseVcsArguments`, `_parseOptions` and the `sw pr snapshot` and `sw pr reply` parsers. Verify the option rows turn green and usage tests in `cli/test/vcs/args_test.dart`, `cli/test/pr/*` and `cli/test/commit/task_cover_test.dart` assert the stop and exit status.
- [x] 3.5 Carry C7: write the doc comment on `parseVcsArguments`. Verify by reading it at its destination.

## 4. Paginated reads and the gh floor

- [ ] 4.1 Write the failing tests for "Paginated GitHub lists read every page or decide nothing", and make `evals/fakes/gh.py` emit one array of pages for `--slurp`, covered in `evals/pr-pair/test_fake_gh.py`. Update the failure injection at evals/pr-pair/test_workflow_parity.py:405 to `api --paginate (--slurp )?repos/o/n/pulls`, so both native and oracle fail the intended read. A6 was verified by the planning refresh. Verify each test fails for the right reason.
- [ ] 4.2 Replace the page scanner in `cli/lib/src/pr/workflow.dart` `list` with `gh api --paginate --slurp` through the wrapper (D4). Verify the four list rows turn green.
- [ ] 4.3 Raise the `gh` floor to 2.48 in `cli/lib/src/fence/fence.dart`, `README.md`, `CONTRIBUTING.md`, `skills/specwright-pr/SKILL.md`, the `pr-pair.sh` prerequisite comment and `evals/git-workflow/test_instructions.py` lines 614, 625, 628 and 640, plus current prerequisite statements in `openspec/strategy.md:13` and `openspec/architecture.md:150` (accepted ADRs stay unchanged). Verify the "All prerequisites present" row in CI.
- [ ] 4.4 Carry C5: confirm the requirement "Paginated GitHub lists read every page or decide nothing" holds the rule after the refresh. Verify by reading the delta spec.

## 5. Paths

- [x] 5.1 Verify A4: run `path` in `windows` style on mixed case, another drive and lone surrogates. Verify by recording results in `cli/test/vcs/raw_path_test.dart` comments; a disproved assumption stops this group under the drift rule.
- [x] 5.2 Replace `PyPath` in `cli/lib/src/commit/task_cover.dart` and the relpath helpers in `cli/lib/src/vcs/walk.dart` with `path.Context` (D5), keeping the raw-path symlink call and the cross-drive error, and narrow the `relpathText` group to the relative path produced for each OS style. Verify with `mise exec -- dart test test/vcs/raw_path_test.dart` from `cli/`, with a cross-drive case.
- [x] 5.3 Carry C8 and C9: write the doc comments on `realpath` and `relpathText`. Verify by reading each at its destination.

## 6. Notice, integration and release

- [ ] 6.1 Run the map test `python -m unittest evals/runner/test_suite_map.py` and add a rule to `evals/suites.json` for any new tracked file. Verify the test passes.
- [ ] 6.2 Add `crypto` and its closure to `cli/THIRD_PARTY_NOTICES.txt`, extending the existing shipped file (D6); retain the existing path notice without duplication, and check every package in the runtime closure (`dart pub deps --no-dev`) in `cli/test/no_build_hooks_test.dart`. Verify the "Current dependency set" and "A dependency without a notice" rows turn green; re-confirm A8.
- [ ] 6.3 Confirm the full suites are green in the PR's `evals.yml` and `cli.yml` runs on Linux, Windows and macOS. Verify by the PR's checks.
- [ ] 6.4 Run `release.sh bump --to 0.31.0` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-library-foundations/proposal.md`.
