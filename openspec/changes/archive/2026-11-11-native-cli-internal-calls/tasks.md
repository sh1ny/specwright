# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| vcs-backends → sw vcs reads settings and fences identity in process | Settings read through pr-pair.sh | evals/vcs/test_sw_scripts.py | test_settings_read_through_pr_pair | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unknown backend in the settings | evals/vcs/test_sw_scripts.py | test_unknown_backend_stops_as_before | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Scripts installed under a non-UTF-8 directory | evals/vcs/test_sw_scripts.py | test_scripts_under_non_utf8_directory | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Unpinned settings stop a GitButler push | evals/vcs/test_gitbutler_push.py | test_unassigned_settings_edit_stops_push | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced push | evals/vcs/test_sw_fence.py | test_fenced_push_runs_in_process (replaces test_sw_scripts.py test_fenced_push_runs_through_as_sh) | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Refused fence | evals/vcs/test_sw_fence.py | test_refused_fence_maps_to_fence_failed (Git, jj, GitButler) | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Login resolved in process | evals/vcs/test_sw_fence.py | test_login_resolved_in_process | green |
| vcs-backends → sw vcs reads settings and fences identity in process | No gh account to resolve | evals/vcs/test_sw_fence.py | test_no_gh_account_is_fence_failed | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Store without a Specwright version | evals/vcs/test_sw_fence.py | test_store_without_version_pulls | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Fenced commands stay unbounded | evals/vcs/test_sw_fence.py | test_fenced_command_has_no_deadline | green |
| vcs-backends → sw vcs reads settings and fences identity in process | Non-GitHub remote runs unfenced | evals/vcs/test_sw_fence.py | test_non_github_remote_runs_unfenced | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Snapshot with a matching sw | evals/pr-pair/test_pr_shims.py | test_snapshot_runs_sw | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Reply with a matching sw | evals/pr-pair/test_pr_shims.py | test_reply_runs_sw | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | A refusal keeps its exit status | evals/pr-pair/test_pr_shims.py | test_reply_refusal_keeps_its_exit_status | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Store-started snapshot selects the code project | evals/pr-pair/test_snapshot_native.py | test_store_snapshot_selects_code_project | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Store-started reply selects the code project | evals/pr-pair/test_snapshot_native.py | test_store_reply_selects_code_project | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Missing selected binary refuses without fallback | evals/pr-pair/test_snapshot_native.py | test_missing_selected_binary_has_no_fallback | green |
| pr-script-runtime → PR snapshots and replies run in the project's sw | Malformed project prefix | evals/pr-pair/test_snapshot_native.py | test_malformed_project_prefix_is_usage | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Reviewer states decided in sw | evals/pr-pair/test_pr_shims.py | test_snapshot_evaluates_reviewers_in_sw | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | A pattern that backtracks past the deadline | evals/pr-pair/test_pr_shims.py | test_backtracking_pattern_stops_at_the_deadline (limit line asserted exactly) | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Bad reviewer config | evals/pr-pair/test_snapshot_native.py | test_bad_config_checked_without_child | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | No Python on PATH | evals/pr-pair/test_snapshot_native.py | test_snapshot_without_python | green |
| pr-script-runtime → Snapshots evaluate reviewers through sw | Evaluator output that is not a document | cli/test/pr/snapshot_test.dart | evaluator output that is not a document fails the poll | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Internal scripts are not launched | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_internal_scripts_are_not_launched | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Nested VCS fetch runs the fence in process | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_nested_vcs_fetch_runs_the_fence_in_process | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Fenced read uses one deadline | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_fenced_read_uses_one_deadline | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Rounds reports an outer read deadline as unreadable | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_rounds_reports_an_outer_read_deadline_as_unreadable | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Nested fence lookup limit retains refusal mapping | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_nested_fence_lookup_limit_retains_refusal_mapping | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Direct VCS failures retain wrapper mapping | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_direct_vcs_failures_retain_wrapper_mapping | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Another repository is checked under its own identity | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_another_repository_is_checked_under_its_own_identity | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Non-GitHub transport restores the original environment | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_non_github_transport_restores_the_original_environment | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Command arguments remain exact | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_command_arguments_remain_exact | green |
| pr-script-runtime → Native workflow integration calls every ported operation in process | Unbounded VCS calls remain unbounded | evals/pr-pair/test_workflow_transport.py | WorkflowTransport.test_unbounded_vcs_calls_remain_unbounded | green |
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
| native-cli → JSON input that is not plain JSON is refused | An oversized feedback record stays unreadable | cli/test/pr/feedback_record_test.dart | an oversized record blocks replacement | green |
| native-cli → JSON input that is not plain JSON is refused | Oversized workflow and intent files | cli/test/pr/workflow_transport_test.dart | oversized workflow JSON retains its stop and raw path | green |
| native-cli → JSON input that is not plain JSON is refused | Feedback integers are exact | cli/test/pr/feedback_pass_test.dart | oversized intent round is invalid_intent | green |
| native-cli → JSON input that is not plain JSON is refused | rounds with max_fix_rounds beyond 64 bits stops with bad_setting | evals/pr-pair/test_workflow_parity.py | test_rounds_without_feedback_trailers | green |
| native-cli → JSON input that is not plain JSON is refused | policy lists an oversized head integer in invalid and exits 0 | cli/test/pr/policy_test.dart | oversized head timeout is invalid with default values | green |
| native-cli → JSON input that is not plain JSON is refused | Lone surrogate keeps its pre-change digest | cli/test/settings/reviewer_config_test.dart | a lone surrogate in a report string keeps its pre-change digest (pin existing surrogate behavior) | green |
| native-cli → JSON input that is not plain JSON is refused | Printed undo guard reads the compact branch | evals/finish/test_undo_jj.py | test_undo_plan_jj_commands_and_result | green |
| native-cli → JSON input that is not plain JSON is refused | Watcher compact keys remain readable | cli/test/pr/snapshot_test.dart | spaced snapshot and evaluator documents read the same as compact ones | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Retrofitted paths with sentinels and no Python | evals/vcs/test_sw_fence.py, evals/pr-pair/test_snapshot_native.py, evals/pr-pair/test_workflow_transport.py | test_retrofitted_vcs_paths_run_no_script_or_python; test_retrofitted_snapshot_runs_no_script_or_python; WorkflowTransport.test_internal_scripts_are_not_launched (sentinels + failing python) | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Reviewer evaluator stays a separate process | evals/pr-pair/test_pr_shims.py | test_backtracking_pattern_stops_at_the_deadline | green |
| native-cli → sw starts itself only for its helper and the reviewer evaluator | Printed commands are not launches | evals/vcs/test_sw_fence.py | test_printed_plan_commands_are_not_launched | green |
| native-cli → A launch-site allowlist guards process starts | Current tree passes | cli/test/launch_sites_test.dart | the tree matches the allowlist | green |
| native-cli → A launch-site allowlist guards process starts | A new unlisted launch fails | cli/test/launch_sites_test.dart | an unlisted runner call fails naming the file | green |
| native-cli → A launch-site allowlist guards process starts | A script in launch arguments fails | cli/test/launch_sites_test.dart | a script name in launch arguments fails | green |
| native-cli → A launch-site allowlist guards process starts | A self-launch outside the allowed two fails | cli/test/launch_sites_test.dart | a changed, non-literal or unbounded self-launch fails | green |
| native-cli → A launch-site allowlist guards process starts | A script name built away from the launch fails | cli/test/launch_sites_test.dart | a script name built away from the launch fails | green |

## 1. In-process fence for `sw vcs`

- [x] 1.1 Add the shared eval helper in `evals/vcs/` (reused by `evals/pr-pair/`) that writes recording `as.sh`, `vcs.sh`, `pr-pair.sh` and `sw-path.sh` sentinels into the handoff scripts directory and failing recording `python`/`python3` (exit 97) first on `PATH`, building on `evals/pr-pair/test_workflow_transport.py:24-45` (D8). Verify: a probe test in the new module shows each sentinel records when run directly.
- [x] 1.2 Write `evals/vcs/test_sw_fence.py` with the vcs-backends rows marked red above, plus `test_retrofitted_vcs_paths_run_no_script_or_python` (fetch, pull, push on Git, jj and GitButler, with and without `--login`; argument bytes, per-call token scope, target repo) and `test_printed_plan_commands_are_not_launched`. Run `python -m unittest evals/vcs/test_sw_fence.py` on the current code and confirm each red test fails because a sentinel recorded a run or the store pull is `sw_missing`, not for a harness error. Move `test_fenced_push_runs_through_as_sh` out of `evals/vcs/test_sw_scripts.py` (replaced by `test_fenced_push_runs_in_process`).
- [x] 1.3 Add `fencedText` in `cli/lib/src/fence/` per D1: `runFence` with bounded `runGh`, unbounded `runTool` git checks and a capturing `runTool` launch in the repo, returning `TextResult`; a refusal is exit 3 with the `as.sh:` message on stderr. Add Dart unit tests in `cli/test/fence/` for refusal text, `--resolve` output and the unbounded launch. Write C3 as the `fencedText` doc comment. Verify: `mise exec -- dart test test/fence/<new file>` from `cli/` passes.
- [x] 1.4 Switch `fenceLogin` and `runAs` callers (`networkGit`, `networkJj`, `fencedButPull`) to `fencedText`; remove `VcsScripts.run`, the shim path in `runAs`, `fenceProject` and `VcsContext.branchFetchProject` (`cli/lib/src/vcs/scripts.dart`, `cli/lib/src/commands/vcs.dart`). Keep Git's `not_fast_forward` check first and the exit-3 mapping (D2). Write C4 as the `networkGit` doc comment. Verify: `python -m unittest evals/vcs/test_sw_fence.py` passes; flip the vcs-backends red rows and the Printed-commands row green.

## 2. Snapshot: in-process config check, no probe, parsed documents

- [x] 2.1 Verify A1: run a fenced `sw pr snapshot` on a closed PR of this repository (`bash skills/specwright-pr/scripts/as.sh KintsugiBot bash skills/specwright-pr/scripts/pr-snapshot.sh 219 --repo sh1ny/specwright`) and confirm the printed line `jsonDecode`s to one object (a one-line Dart or Python `json.loads` check). A failure is design drift for D4: stop and amend.
- [x] 2.2 Write `evals/pr-pair/test_snapshot_native.py` red tests: `test_bad_config_checked_without_child`, `test_snapshot_without_python`, `test_retrofitted_snapshot_runs_no_script_or_python`, and `--full` with compact and spaced `not_found` documents (exit 1 both). Tighten `test_backtracking_pattern_stops_at_the_deadline` in `evals/pr-pair/test_pr_shims.py` to assert the exact line `bounded: deadline_exceeded: reviewers.py python3`. Confirm each fails for the stated reason on the current code.
- [x] 2.3 Write Dart red tests in `cli/test/pr/snapshot_test.dart`: evaluator output that is not a document fails the poll with exit 1; spaced snapshot and evaluator documents read the same as compact ones. Update `cli/test/pr/text_test.dart` for the helpers that remain. Confirm red with `mise exec -- dart test test/pr/snapshot_test.dart`.
- [x] 2.4 Implement D3 and D5: expose the reviewer config load from `cli/lib/src/pr/reviewers.dart` and call it in `snapshot.dart` before any gh call (exit 2, `reviewers.py:` line); remove the `--check-config` child, the Python probe and `PrContext.python`; make the limit label the constant `reviewers.py python3`. Write C6 as the `evaluate` doc comment. Verify: `test_bad_config_checked_without_child`, `test_snapshot_without_python` and the backtracking test pass; flip their rows green.
- [x] 2.5 Implement D4 (C12): decode the snapshot line once per poll and the evaluator stdout, `readFull` included (error member `not_found` → exit 1, output unchanged); drop the JSON regex readers from `cli/lib/src/pr/text.dart`. Verify: `mise exec -- dart test test/pr/snapshot_test.dart test/pr/text_test.dart` and `python -m unittest evals/pr-pair/test_snapshot_native.py` pass; flip the Evaluator-output and Watcher rows green.

## 3. `--project` on the snapshot and reply shims

- [x] 3.1 Add red tests to `evals/pr-pair/test_snapshot_native.py`: store-started snapshot and reply select the code project, missing selected binary refuses without fallback, malformed prefix is a usage error (2 for snapshot, 4 for reply) after the Python check. Confirm red, and re-run `test_reply_refusal_keeps_its_exit_status` green (its row rides along unchanged).
- [x] 3.2 Implement D6 in `skills/specwright-pr/scripts/pr-snapshot.sh` and `pr-reply.sh`: one optional leading `--project <dir>`, read after the Python check, replacing the discovery start, never forwarded to `sw`. Verify: the 3.1 tests and `python -m unittest evals/pr-pair/test_pr_shims.py` pass; flip the rows green.
- [x] 3.3 Update `skills/specwright-pr/SKILL.md` to pass `--project <code toplevel>` on store-started snapshot, `--full` and reply calls, and remove the S-1 and C11 notes there and in `skills/specwright-finish/SKILL.md`. Update `openspec/architecture.md`: C9, C11 and S-1 closed, C13 owned by `native-cli-retire-scripts` (D9). Verify: `grep -n "S-1\|C11" skills/specwright-pr/SKILL.md skills/specwright-finish/SKILL.md` finds nothing, and the release suite's SKILL.md checks pass in CI.

## 4. Workflow nested fetch

- [x] 4.1 Add red `WorkflowTransport.test_nested_vcs_fetch_runs_the_fence_in_process` to `evals/pr-pair/test_workflow_transport.py` (store without `VERSION`, recording `as.sh` sentinel, no `--login`). Confirm it fails because the sentinel recorded a run.
- [x] 4.2 Remove the `branchFetchProject` flag from `cli/lib/src/pr/workflow.dart`; the non-Git branch-check fetch-main calls the in-process VCS fetch. Verify: `python -m unittest evals/pr-pair/test_workflow_transport.py` passes; flip the Nested VCS fetch and Retrofitted-paths rows green.

## 5. Launch-site allowlist

- [x] 5.1 Write `cli/test/launch_sites_test.dart` per D7 with its negative in-memory fixtures first (unlisted runner call, script in launch arguments, changed evaluator head with equal counts, evaluator on `PrContext.tool`, non-literal self-launch list, `as.sh` built in a variable and passed to `runTool`), and confirm each fixture fails for its reason.
- [x] 5.2 Fill the allowlist for the tree: every runner call with its kind, the self-launch heads (`__exec`; `pr reviewers` under `PrContext.bounded`), and the listed non-launch script-name sites, the `exec_inherit.dart` `$0` label included. Verify: `mise exec -- dart test test/launch_sites_test.dart` from `cli/` passes; flip the five allowlist rows green.
- [x] 5.3 Carried constraints: confirm C1, C2 and C5 read as written in `specs/native-cli/spec.md` (their spec destinations); write C7 as the `runFramed` doc comment in `cli/lib/src/vcs/tool_runner.dart`. Verify: `grep -n "native-cli-launcher" cli/lib/src/vcs/tool_runner.dart` finds the comment.

## 6. Coverage map, release and integration

- [x] 6.1 Add `evals/suites.json` rules for the new files (`cli/test/launch_sites_test.dart`, the shared sentinel helper, `evals/vcs/test_sw_fence.py`, `evals/pr-pair/test_snapshot_native.py`) unless an existing glob already covers them. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.
- [x] 6.2 `bash .claude/skills/specwright-release/scripts/release.sh bump --to 0.32.0`, and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `release.sh check` and `release.sh notes --proposal openspec/changes/native-cli-internal-calls/proposal.md` pass.
- [x] 6.3 Integration: open a draft PR and confirm `.github/workflows/evals.yml` and `.github/workflows/cli.yml` are green on Linux, Windows and macOS (the "Direct fence evals pass on the three CI platforms" exit criterion). Verify: both workflow runs green on the PR head.

## Workflow follow-up

- Pre-ship review, ship, archive and finish per specwright-commit, specwright-pr and specwright-finish.
- Show the Decision summary table from design.md before apply (done at the end of planning).
