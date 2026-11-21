# Tasks: fix-sw-port-gaps

## Test map

One row per delta-spec scenario. A blank Requirement or Test file cell repeats the row above. A blank Test name is the name derived from the scenario: in a `.py` file `test_` plus the scenario in lower snake case (punctuation dropped), in a `.dart` file the scenario text with a lower-case first letter. `red`: new or changed behaviour, written failing first. `green`: unchanged behaviour with a passing test, re-run by a task.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| A CRLF message file commits on every backend | GitButler commit with a CRLF message file | `evals/vcs/test_gitbutler_commit.py` |  | red |
|  | jj commit with a CRLF message file | `evals/vcs/test_commit.py` |  | red |
|  | Git commit with a CRLF message file under default cleanup | `evals/vcs/test_git_backend.py` |  | red |
|  | A message that still differs is a mismatch | `cli/test/vcs/gitbutler_backend_test.dart` | read-back with a differing body is commit_mismatch | red |
| GitButler reads the message file where sw runs | A relative message file named from outside the repo | `evals/vcs/test_gitbutler_commit.py` |  | red |
|  | The file exists only in the repo |  |  | red |
|  | A commit whose real command line just exceeds the limit | `cli/test/vcs/gitbutler_backend_test.dart` | windows: but.exe line over the limit is too_many_paths, no start | red |
|  | A batch-file `but` whose line is over the batch limit |  | windows: but.exe then but.cmd over the batch cap is too_many_paths | red |
| A committed GitButler undo refuses paths its commit would rename | A bracket in a committed undo's path | `evals/vcs/test_gitbutler_undo.py` |  | red |
|  | The same path in an uncommitted undo |  |  | green |
| A GitButler-selected undo reports a failed target read | A failed target read during a GitButler undo | `evals/vcs/test_gitbutler_undo.py` |  | red |
|  | An unset target during a GitButler undo |  |  | green |
| Fixed commit defects are exceptions to the backends' unchanged outputs | A CRLF commit that stopped before | `cli/test/vcs/gitbutler_backend_test.dart` | read-back folds a CRLF file to the stored body | red |
|  | A message file with an interior carriage return |  | read-back folds an interior lone CR | red |
|  | jj stores LF for a CRLF message | `cli/test/vcs/jj_backend_test.dart` | commit normalises CRLF; merge message keeps its bytes | red |
|  | A commit the old size check refused | `cli/test/vcs/gitbutler_backend_test.dart` | paths over the old 32,000-byte estimate commit | red |
|  | A Git commit line at the Windows boundary | `cli/test/vcs/git_backend_test.dart` | windows: git commit line of 32,767 units is not_utf8 | red |
|  | A non-commit VCS command at the Windows boundary |  | windows: merge line of 32,767 units is not_utf8 | red |
|  | A fenced network call at the Windows boundary |  | windows: fetch-main line of 32,767 units is git_network_error | red |
|  | A GitButler message path a batch shim cannot carry | `cli/test/vcs/gitbutler_backend_test.dart` | windows: but.cmd with % in the resolved message path | red |
|  | A Git commit through a batch shim over the limit | `cli/test/vcs/git_backend_test.dart` | windows: git.exe then git.cmd raw line over the limit | red |
|  | Any other commit | `evals/vcs/test_git_backend.py` | test_commit_outputs_unchanged | red |
| finish.sh finds the project from --code, then --dir | Store-backed plan finds the code checkout's sw | `evals/finish/test_finish_shim.py` | test_code_picks_the_project | green |
|  | Store-backed call without --code |  | test_store_without_code_is_sw_mismatch | green |
|  | Relative --code is read from the planning repo |  | test_relative_code_from_planning_repo | red |
|  | A missing code directory in a checkout of another version |  | test_missing_code_in_other_version_is_not_repository | red |
| A deferred archive's undo is planned by a script that runs nothing | Deferred archive found | `evals/finish/test_undo_jj.py` | test_jj_plan_changes_no_file | green |
|  | Plan run on a dirty unrelated path in a resume on main | `evals/finish/test_undo_plan.py` | test_resume_on_dirty_main_refused | red |
|  | No archive of the change |  | TestUndoPlan.test_no_archive_refused | green |
|  | Branch moved after the plan |  | TestUndoPlan.test_guard_fails_after_branch_moved | green |
|  | A jj plan with an unsnapshotted edit | `evals/finish/test_undo_jj.py` |  | green |
|  | A jj plan with a pending Git ref import |  |  | green |
| The undo planner reports paths whole | The first dirty path keeps its first character | `evals/finish/test_undo_plan.py` |  | red |
|  | A name that porcelain quotes |  |  | red |
|  | A staged rename on resume |  |  | red |
|  | The planner leaves the index alone |  | test_planner_leaves_a_stale_index_alone | red |
|  | A name with a backslash |  |  | red |
|  | A non-UTF-8 name in an unrelated archive |  |  | red |
|  | An unreadable directory in an unrelated archive |  |  | red |
|  | A dirty path that is not UTF-8 on resume |  |  | green |
| The undo planner's status reads list every untracked file | Untracked files hidden by configuration | `evals/finish/test_undo_plan.py` |  | red |
| A failed status read stops the undo plan | The resume status read fails | `cli/test/finish/undo_plan_test.dart` | a failed resume status read is vcs_error | red |
|  | The carried-edits status read fails |  | a failed carried-edits read is vcs_error | red |
|  | A carried-edits read fails on GitButler | `evals/vcs/test_gitbutler_undo.py` |  | green |
|  | A staged change on the change branch | `evals/finish/test_undo_plan.py` | TestUndoPlan.test_staged_changes_refused | green |
| A failed staged-index read stops the undo plan | The staged-index read fails | `cli/test/finish/undo_plan_test.dart` | a failed staged-index read is vcs_error | red |
|  | The staged-index read fails for an uncommitted archive |  | a failed staged-index read on an uncommitted archive | red |
| The staged-index checks see every staged path | A staged gitlink hidden by configuration before planning | `evals/finish/test_undo_plan.py` |  | green |
|  | A staged path that a diff helper would hide | `evals/finish/test_undo_steps.py` |  | red |
|  | The plan warns about the index | `cli/test/finish/undo_plan_test.dart` | a Git plan warns that the index must not change | red |
|  | A gitlink staged after planning | `evals/finish/test_undo_steps.py` |  | red |
| The resume cleanliness checks see submodule changes | A submodule dirty at planning | `evals/finish/test_undo_plan.py` |  | red |
|  | A submodule made dirty before the steps run | `evals/finish/test_undo_steps.py` |  | red |
|  | A dirty submodule under a GitButler undo | `evals/vcs/test_gitbutler_undo.py` |  | green |
| The resume checkout never overwrites an ignored file | An ignored local file the branch tracks | `evals/finish/test_undo_steps.py` |  | red |
| The GitButler undo guard compares trees itself | Another applied branch's edit with a diff helper that exits 0 | `evals/vcs/test_gitbutler_undo.py` |  | green |
|  | Another applied branch edits only a sibling path |  |  | green |
| The Git undo treats each path literally and reads one object view | A Git undo leaves a pattern-matching sibling alone | `evals/finish/test_undo_steps.py` |  | red |
|  | A replaced archive parent |  |  | red |
| The Git undo refuses a Git environment that changes what it reads or writes | An inherited attribute source | `evals/finish/test_undo_steps.py` |  | red |
|  | Inherited pathspec settings |  |  | red |
|  | An index override present from planning | `evals/finish/test_undo_plan.py` |  | red |
|  | Another checkout named by the environment |  |  | red |
|  | A work tree rerouted by configuration | `evals/finish/test_undo_steps.py` |  | red |
|  | An index routed elsewhere |  |  | red |
| The Git undo refuses while a Git operation is in progress | A Git operation in progress | `evals/finish/test_undo_steps.py` |  | red |
| The undo plan stops when a read it relies on fails | A planner read fails | `evals/finish/test_undo_plan.py` |  | red |
|  | A member replaced by a file |  |  | red |
|  | An unlistable delta directory |  |  | red |
|  | A GitButler target that cannot be read |  |  | red |
|  | A failed target read with GitButler selected | `evals/vcs/test_gitbutler_undo.py` |  | red |
|  | A partial clone | `evals/finish/test_undo_plan.py` |  | red |
|  | Configuration that reroutes Git only on the archive branch | `evals/finish/test_undo_steps.py` |  | red |
|  | A resume from main passes both branch guards |  |  | red |
|  | A code directory reached through a symlink and `..` | `evals/finish/test_finish_shim.py` |  | green |
|  | A relative code directory resolved from the store |  |  | red |
|  | Options are validated before the version check |  |  | red |
|  | A code directory that does not exist |  |  | red |
|  | A missing planning directory |  | test_missing_dir_is_not_a_repo_before_any_version_check | red |
|  | The emitted steps check the version the planner checked |  |  | red |
|  | The archive branch carries another committed version | `evals/finish/test_undo_plan.py` |  | red |
|  | A version stamp the checkout changes | `evals/finish/test_undo_steps.py` |  | red |
|  | A decision file that is not a regular file on the current branch | `evals/finish/test_undo_plan.py` |  | red |
|  | An explicit filter unset |  |  | red |
|  | Two members whose names differ only by case |  |  | red |
|  | A filter whose name is unspecified |  |  | red |
|  | A change marker that is not a regular file | `evals/finish/test_undo_steps.py` |  | red |
|  | A settings file that is not a regular file |  |  | red |
|  | A detached HEAD moved after planning |  |  | red |
|  | A version stamp that is not a regular file |  |  | red |
|  | A jj store resume whose backend changed after planning | `evals/finish/test_undo_jj.py` |  | red |
|  | A sparse checkout on resume | `evals/finish/test_undo_plan.py` |  | red |
|  | The version check names the same checkout | `evals/finish/test_finish_shim.py` |  | red |
|  | A backend selection changed before the resume checkout | `evals/finish/test_undo_steps.py` |  | red |
|  | A resumed branch that selects another backend |  |  | red |
|  | GitButler set up after planning |  |  | red |
|  | Settings that cannot be read | `evals/finish/test_undo_plan.py` |  | red |
|  | An unreadable work-tree tasks file |  |  | red |
|  | A tag named like the archive branch | `evals/finish/test_undo_steps.py` |  | red |
|  | A tag that spells the full branch ref | `evals/finish/test_undo_plan.py` |  | red |
|  | The archive branch deleted after planning | `evals/finish/test_undo_steps.py` |  | red |
|  | A branch name that is not UTF-8 at the guard |  |  | red |
|  | A task file hidden by an index flag | `evals/finish/test_undo_plan.py` | test_a_task_file_hidden_by_an_index_flag_is_git_env | green |
|  | A main spec with a hidden local edit |  |  | red |
|  | An unrelated file with a hidden edit on resume |  |  | red |
|  | Ignored content under the archive root |  |  | red |
|  | An edit a filesystem monitor missed on resume | `evals/finish/test_undo_steps.py` |  | red |
|  | A GitButler undo over a hidden edit | `evals/vcs/test_gitbutler_undo.py` |  | green |
|  | An archive sibling Git cannot list | `evals/finish/test_undo_plan.py` |  | red |
|  | A status read that warns and exits 0 | `evals/finish/test_undo_steps.py` |  | red |
|  | A main spec whose type the archive changed | `evals/finish/test_undo_plan.py` |  | red |
|  | An empty code directory | `evals/finish/test_finish_shim.py` |  | red |
|  | A clean resume reads an empty status | `evals/finish/test_undo_plan.py` | TestUndoPlan.test_resume_on_main_checks_out_branch | green |
|  | A rerun under a nested planning root | `evals/finish/test_undo_steps.py` | `TestNestedPlanningRoot.test_a_rerun_under_a_nested_planning_root` | red |
|  | A new spec that is a case alias of a tracked one | `evals/finish/test_undo_plan.py` |  | red |
|  | An untracked case alias owned by another GitButler branch | `evals/vcs/test_gitbutler_undo.py` |  | red |
|  | The archive branch lookup fails | `evals/finish/test_undo_plan.py` |  | red |
|  | The state read's branch lookup fails | `cli/test/finish/undo_plan_test.dart` | a failed branch lookup in the state read is git_error | red |
|  | The state read's status fails |  | a failed status in the state read is git_error | red |
| Rerun eligibility is read from the copy the undo restores | A checkout filter on a rerun input | `evals/finish/test_undo_plan.py` |  | red |
|  | An untracked attributes file in the work tree |  |  | red |
|  | A checkout filter configured only when the steps run | `evals/finish/test_undo_steps.py` |  | red |
|  | A current-branch filter on an unchanged decision file | `evals/finish/test_undo_plan.py` |  | red |
|  | Restored decision bytes differ from the tip | `evals/finish/test_undo_steps.py` | test_restored_decision_bytes_that_differ_from_the_tip_stop_the_steps_after_the_checkout | red |
|  | A submodule inside an archived member | `evals/finish/test_undo_plan.py` |  | red |
|  | A committed symlink as a decision file |  |  | red |
|  | A Git too old to read the tip's attributes |  |  | red |
|  | A tasks file deleted from the work tree |  |  | red |
|  | A member deferred after its archive commit |  |  | red |
| A Git undo that fails between index steps names what to clean up | A Git undo that fails between index steps | `evals/finish/test_undo_steps.py` |  | red |
| The Git undo checks each restore destination after the checkout | An ignored directory at a restore destination | `evals/finish/test_undo_steps.py` |  | red |
|  | An untracked file in a resumed archive |  |  | red |
| A committed GitButler undo stops on a path it cannot commit as named | A GitButler undo of a path with glob characters | `evals/vcs/test_gitbutler_undo.py` |  | red |
| The undo keeps a copy of every change marker it removes | An edited change marker in the archive | `evals/finish/test_undo_steps.py` |  | red |
|  | A guard refuses before the backup |  |  | green |
|  | A resumed undo's marker |  |  | red |
|  | A marker deleted after planning |  |  | green |
|  | A marker copy that fails | `cli/test/finish/undo_step_test.dart` | a failed marker copy stops before any index change | red |
| The dirty_tree message names each record plainly | Other dirty stops keep their messages | `evals/finish/test_undo_plan.py` | TestUndoPlan.test_dirty_stops_keep_their_messages | green |
|  | Ordinary names read as before |  |  | red |
|  | A rename and a name with a tab |  |  | red |
|  | A carriage return and a trailing space in a name |  |  | red |
| A usage error from the planner's state read exits 2 | State read refuses its arguments | `cli/test/finish/undo_plan_test.dart` | a usage stop from the state read exits 2 | red |
|  | State read fails for another reason | `evals/finish/test_undo_plan.py` | test_malformed_settings_state_read_exits_1 | green |
| Fixed undo-plan defects are exceptions to the script's refusals | A usage error from the state read | `cli/test/finish/undo_plan_test.dart` | an injected usage VcsStop is one usage document, exit 2 | red |
|  | A guard that now refuses | `evals/finish/test_undo_plan.py` | test_a_staged_gitlink_hidden_by_configuration_is_staged_changes | green |
|  | A plan carries the new index warning | `cli/test/finish/undo_plan_test.dart` | a clean-index Git plan carries the index warning | red |
|  | Any other refusal | `evals/finish/test_parity.py` | TestPlanGit.test_refusal_dirty_tree | green |
| An undo destination is absent only by evidence | The first undo in a fresh checkout | `evals/finish/test_undo_steps.py` | `test_the_first_undo_in_a_fresh_checkout_proves_its_backup_absent` | green |
|  | An ancestor that cannot be listed | `cli/test/finish/undo_step_test.dart` | check absent with an unlistable ancestor refuses | red |
| A rerun plan warns that it writes specs in place | A bulk undo that reruns the archive | `cli/test/finish/undo_plan_test.dart` | a rerun plan warns that it writes specs in place | red |
| Every printed undo step fits the command line | A POSIX commit sized in bytes | `cli/test/finish/undo_plan_test.dart` | posix: a jj fileset over 32,766 UTF-8 bytes is plan_too_large | red |
|  | A jj bulk undo whose commit fileset is too long | `evals/finish/test_undo_jj.py` |  | red |
|  | A GitButler bulk undo whose commit runs through `but.cmd` | `cli/test/finish/undo_plan_test.dart` | windows: but.cmd payload over 8,191 is plan_too_large | red |
|  | A Git bulk undo whose synced spec paths force batching | `evals/finish/test_undo_steps.py` |  | red |
|  | A bulk undo with a very long member list | `cli/test/finish/undo_plan_test.dart` | a long member list keeps every line within the limit | red |
| An undo never writes inside a nested repository | A rerun spec inside a submodule | `evals/finish/test_undo_plan.py` | `test_a_rerun_spec_inside_a_submodule_is_unsupported_entry` | red |
|  | A linked worktree inside an archived member |  | `test_a_linked_worktree_inside_an_archived_member_is_unsupported_entry` | red |
|  | A linked `.git` marker inside an archived member |  | `test_a_linked_git_marker_inside_an_archived_member_is_unsupported_entry` | red |
|  | A worktree marker spelled in another case |  | `test_a_worktree_marker_spelled_in_another_case_is_unsupported_entry` | red |
|  | A gitlink only on the archive branch |  | `test_a_gitlink_only_on_the_archive_branch_is_unsupported_entry` | red |
| An undo writes only the paths it names | A restore destination that is a link | `evals/vcs/test_gitbutler_undo.py` |  | red |
|  | A removed spec under a linked directory | `evals/finish/test_undo_steps.py` |  | red |
|  | A hard-linked restore destination | `evals/vcs/test_gitbutler_undo.py` | `test_a_hard_linked_restore_destination` | green |
|  | A rerun spec under a linked directory |  |  | red |
|  | A rerun destination linked after the undo | `evals/finish/test_undo_steps.py` |  | red |
|  | A plain-Git removal under a linked directory |  | `test_a_plain_git_removal_under_a_linked_directory` | red |
|  | Two absent rerun specs that differ only by case | `evals/finish/test_undo_plan.py` | `test_two_absent_rerun_specs_that_differ_only_by_case_are_unsupported_entry` | red |
|  | Two absent rerun specs where one lies under the other |  |  | red |
|  | A rerun spec blocked by an existing directory |  |  | red |
|  | A linked archive directory | `evals/finish/test_undo_steps.py` |  | red |
|  | Another GitButler branch's edit at a rerun-only spec | `evals/vcs/test_gitbutler_undo.py` | `test_another_gitbutler_branchs_edit_at_a_rerun_only_spec` | red |
|  | Another GitButler branch's assigned edit on an uncommitted undo |  |  | red |
|  | Another GitButler branch's assigned edit at a backslash path |  |  | red |
|  | An archived member edited after a GitButler plan |  |  | green |
|  | A foreign assignment made after a GitButler plan |  |  | red |
|  | An unassigned member edit on a GitButler undo |  |  | green |
| Windows record replacement retries a transient refusal | A refusal that clears within the retry window | `cli/test/pr/feedback_record_test.dart` | a refused replace that clears writes the record | red |
|  | A refusal that persists |  | a persistent replace failure rethrows the first error after 6 attempts | red |
|  | The temporary source disappears during a pause |  | a source removed during a pause ends the retries | red |
|  | A refusal that persists |  | a failed temp cleanup keeps the first error | red |
|  | The temporary source is gone after the first attempt |  | a replace whose source is gone is not retried | green |
|  | Other platforms |  | off Windows a failed replace is not retried | green |
|  | The lock create and publication are not retried |  | the lock create and publication make one attempt | green |
|  | A refusal that clears within the retry window | `cli/test/pr/feedback_pass_test.dart` | adopt holds the lock through a retry pause, and cleans up before the release | red |
|  | Concurrent adoption on Windows | `evals/pr-pair/test_workflow_records.py` | test_concurrent_mutations_acquire_one_lock | red |
| A PR call's new helper refusal keeps its exit with a fixed diagnostic | A reaction whose gh line fits only without the helper | `cli/test/pr/reply_test.dart` | windows: react line over the limit only behind the helper exits 127 | red |
|  | A snapshot query that fits only without the helper | `cli/test/pr/snapshot_test.dart` | windows: GraphQL line over the limit only behind the helper | red |
|  | A PR call refused by an older check | `cli/test/pr/reply_test.dart` | windows: line over the limit as given is unrepresentable | red |
|  | A PR call whose batch payload is too long |  | windows: gh.cmd payload over 8,191 is unsafe batch argument | red |
| Fixed snapshot defects are exceptions to the scripts' contract | A fixed case differs from its record | `evals/pr-pair/test_parity.py` | SnapshotParity.test_fixed_cases_are_listed_differences | red |
|  | An unaffected case still matches its record |  | SnapshotParity.test_snapshot_of_an_empty_pr | green |
| sw pr snapshot reads --timeout as decimal seconds | A leading zero | `cli/test/pr/snapshot_test.dart` | --timeout 08 wakes at 8 seconds | red |
|  | A value that is not a number |  | a non-decimal --timeout is a usage error | red |
|  | A value out of range |  | an out-of-range --timeout is a usage error | red |
|  | Large values stay accepted |  | 2147483648 and 2^63-1 run the first poll | red |
| sw pr snapshot names a material file it cannot write | The material file cannot be written | `cli/test/pr/snapshot_test.dart` | an unwritable material file is named on stderr | red |
|  | Material file written |  | a written material file prints nothing | red |
| Snapshot logs keep the order their output arrived in | stderr that arrives partway through the log | `cli/test/process/bounded_run_merged_test.dart` | merged mode keeps arrival order | red |
|  | A line split across chunks |  | a stderr chunk inside a stdout line is kept | red |
|  | The snapshot keeps the merged order | `cli/test/pr/snapshot_test.dart` | the log tail keeps a stderr line in the middle | red |
|  | A long log through the helper | `evals/pr-pair/test_pr_snapshot.py` | test_logs_tail_of_101_lines_through_the_helper | red |
|  | Helper protocol bytes never reach the log |  | test_logs_hold_no_frame_bytes | red |
|  | The log call fails to start |  | test_logs_show_the_start_failure_text | red |
|  | Two streams that fit alone but not together | `cli/test/process/bounded_run_merged_test.dart` | two streams over maxBytes together are response_too_large | red |
|  | The log call passes a bound | `evals/pr-pair/test_pr_snapshot.py` | test_logs_over_a_lowered_cap_show_the_limit_line | red |
| Long Windows arguments reach native tools whole | A 20,000-character argument on Windows | `evals/pr-pair/test_as_shim.py` | test_long_argument_reaches_fenced_tool_on_windows | green |
|  | Over the Windows command-line limit | `cli/test/resolved_line_test.dart` | a started line over 32,766 units is refused | red |
|  | The last accepted and first refused lengths |  | 32,766 units start, 32,767 are refused | red |
|  | Under the limit alone, over it behind the helper | `cli/test/bounded_run_test.dart` | windows: helper line over the limit is a failed helper start | red |
|  | A batch launch behind the helper | `cli/test/launch_test.dart` | windows: raw cmd.exe line fits, helper line does not | red |
|  | An inherited batch launch through the identity fence | `evals/pr-pair/test_as_shim.py` | test_inherited_batch_line_over_the_limit_exits_2 | red |
|  | A reviewer run behind the helper | `evals/review-routes/test_review_run.py` | test_reviewer_line_over_the_limit_behind_the_helper | red |
|  | A reviewer line of exactly 32,767 units |  | test_reviewer_line_of_32767_units | red |
|  | A base-branch read behind the helper |  | test_remote_base_probe_behind_the_helper_is_no_base | red |
|  | A reviewer argument that cannot be represented |  | test_nul_in_reviewer_argument_is_not_utf8 | red |
|  | An explicit omp run whose version probe is over the limit | `cli/test/review/routes_test.dart` | test_omp_version_probe_over_the_limit_is_not_utf8 | red |
|  | An explicit omp run whose resolved version probe is exactly at the limit |  | test_omp_version_probe_of_32767_units_is_omp_too_old | red |
|  | An explicit omp run whose batch version probe is over the limit |  | test_omp_cmd_version_probe_raw_line_is_omp_too_old | red |
|  | A line of exactly 32,767 units before lookup | `cli/test/launch_test.dart` | windows: 32,767 units to a .cmd over the batch cap is UnsafeBatchArgument | red |
|  | A line of exactly 32,767 units that resolves shorter |  | windows: 32,767 units resolving shorter starts | red |
|  | A review's Git read over the limit | `evals/review-routes/test_review_run.py` | test_git_read_over_the_limit_is_not_utf8 | red |
|  | A review's Git read the old checks admitted |  | test_git_read_of_32767_units_is_a_failed_start | red |
|  | A review's Git read through a batch shim over the limit |  | test_git_cmd_raw_line_over_the_limit_is_not_a_repo | red |
|  | A route probe through a batch shim over its limit | `cli/test/review/routes_test.dart` | windows: omp.cmd probe over the batch cap skips the route | red |
|  | A route probe behind the helper |  | windows: models find over the limit falls through | red |
| Arguments reach native executables unchanged | A long argument to a native executable | `evals/cli/test_sw_args.py` | test_long_argument_to_native_exe_is_unchanged | green |
|  | Arguments that fit only once they move to stdin | `cli/test/resolved_line_test.dart` | bash -c arguments fit once moved to stdin | red |
|  | A long argument through bash -c on Windows | `evals/cli/test_sw_args.py` | test_long_argument_through_bash_c_transport | green |
|  | A missing transport end marker |  | test_missing_transport_marker_exits_126 | green |
|  | An argument the launcher cannot represent | `cli/test/run_command_test.dart` | a NUL argument is unrepresentable and nothing starts | green |
| sw reports its version and interface version | Version report of a CI build | `evals/cli/test_sw_version.py` | test_version_json_reports_version_and_interface | red |
|  | Unknown command or flag |  | test_unknown_command_or_flag_prints_usage_and_exits_2 | green |
| Skills check the project version before running sw | VERSION is not a version | `evals/git-workflow/test_skill_sw_calls.py` | test_skills_validate_version_before_building_path | green |
|  | The version probe hangs or floods |  | test_probe_has_10_second_timeout_and_one_object | green |
|  | An older project with newer skills | `evals/cli/test_skill_probe.py` | test_older_project_with_newer_skills_stops | red |
| Project commands check the project's version | Matching version | `evals/cli/test_sw_project_version.py` | test_matching_version_runs | green |
|  | Another version |  | test_another_version_is_sw_mismatch | green |
|  | No VERSION |  | test_no_version_is_sw_mismatch | green |
|  | A fenced call with another version |  | test_fenced_call_with_another_version_starts_nothing | green |
|  | The undo planner validates options first | `evals/finish/test_finish_shim.py` | test_missing_change_is_usage_in_another_version | red |
| The project is chosen by --project, then the command's own argument | A store-started call | `evals/cli/test_sw_project_version.py` | test_store_started_call_with_project | green |
|  | Store-started call without --project |  | test_store_started_call_without_project_is_sw_mismatch | green |
|  | Two leading --project options |  | test_two_leading_project_options_is_usage | green |
|  | A relative --code in the undo planner | `evals/finish/test_finish_shim.py` | test_relative_code_is_anchored_at_the_planning_root | red |
| A bounded launch checks the helper's own command line | A line that fits only without the helper | `cli/test/bounded_run_test.dart` | windows: planBoundedLaunch refuses the serialized helper argv | red |
| A caller's check of the command as given keeps its limit | A command exactly at the caller's limit | `cli/test/launch_test.dart` | windows: as-given precheck admits 32,767 units | red |
| The failed-job log call caps its two streams together | Two streams under their old separate caps | `evals/pr-pair/test_pr_snapshot.py` | test_logs_over_the_shared_cap_are_response_too_large | red |
| Command lookup takes only files the user can execute | A file only another user can run comes first | `evals/cli/test_sw_run.py` | test_lookup_skips_a_file_the_user_cannot_execute | red |
|  | No file the user can execute | `cli/test/resolve_test.dart` | no executable candidate is command not found | red |
|  | An explicit path the user cannot execute | `evals/cli/test_sw_run.py` | test_explicit_path_without_execute_keeps_the_start_failure | red |
| The undo plan's Git steps carry their safety options | An undo plan's Git step | `cli/test/finish/undo_plan_test.dart` | every Git step carries --literal-pathspecs and --no-replace-objects | red |
|  | A resume with submodule recursion enabled | `evals/finish/test_undo_steps.py` | test_resume_with_submodule_recurse_leaves_submodule | red |
|  | Another printed command | `evals/pr-pair/test_workflow_transport.py` | WorkflowTransport.test_cleanup_plan_names_running_sw | green |
| The project root is found from the physical path | A project path through a link and `..` | `evals/cli/test_sw_project_version.py` | test_project_through_link_and_dotdot_is_physical | red |
| The sw download is bounded | Download completes in time | `evals/update/test_sw_install.py` | test_download_over_http_completes | green |
|  | A partial file that is slow to open | `cli/test/update/download_test.dart` | the deadline clock starts after the part is open | red |
|  | A partial file that cannot be created |  | an open failure is download_failed with no request | red |
|  | Server stalls | `evals/update/test_sw_install.py` | test_stalled_download_hits_deadline | green |
|  | A file mirror that finishes after the deadline | `cli/test/update/download_test.dart` | a late file:// copy is deadline_exceeded | red |
|  | A file mirror |  | a file:// copy over 64 MiB is response_too_large | red |
|  | Oversized answer | `evals/update/test_sw_install.py` | test_oversized_download_is_refused | green |
|  | An oversized error or redirect body | `cli/test/update/download_test.dart` | a 404 or redirect body over the budget is response_too_large | red |
|  | Bodies that fit alone but not together |  | a 40 MiB redirect body and a 40 MiB asset share one budget | red |
|  | The partial file cannot be closed after an oversized answer |  | a failing or held close keeps response_too_large | red |
|  | The deadline passes before an oversized chunk is read |  | an oversized chunk after the deadline is deadline_exceeded | red |
|  | An oversized length with a stalled body |  | an oversized Content-Length ends at once | red |
|  | A write failure while the body stalls |  | a write failure during a stall is download_failed | red |
|  | A connection failure after the deadline |  | a getUrl or write failure after the deadline is deadline_exceeded | red |
|  | A compressed answer |  | a gzip 200 is download_failed naming the encoding | red |
|  | A partial answer |  | an identity 206 is download_failed | red |
|  | A compressed 404 |  | a small gzip 404 is the missing asset | red |
|  | A compressed answer handled after the deadline |  | gzip headers handled after the deadline are deadline_exceeded | red |
|  | An answer of exactly 64 MiB |  | a body of exactly maxBytes succeeds | red |
|  | A body that ends in time with a close that settles late |  | a close settling after the deadline is deadline_exceeded | red |
|  | The partial file is held | `cli/test/update/sw_install_test.dart` | deadline_exceeded survives a failed part delete | red |
| The macOS install clears quarantine only on the file it checked | Quarantined download on macOS arm64 | `evals/update/test_sw_install.py` | test_quarantine_cleared_after_checksum | green |
|  | Mismatched file is left quarantined | `cli/test/update/sw_install_test.dart` | checksum mismatch survives a failed part delete | red |
| Placing sw is atomic and keeps other versions | Rerun with the binary already placed | `evals/update/test_sw_install.py` | test_rerun_keeps_matching_binary | green |
|  | Interrupted before the rename |  | test_interrupt_before_rename_leaves_no_final_file | green |
|  | A stale file at the final path |  | test_stale_final_file_is_replaced | green |
|  | Matching hash but not runnable |  | test_unrunnable_matching_file_is_replaced | green |
|  | Two installs of one version at once |  | test_concurrent_installs_both_succeed | green |
|  | Rename blocked by a running binary | `cli/test/update/place_test.dart` | a blocked rename leaves the part for the caller | red |
|  | The final file cannot be read after a blocked rename | `cli/test/update/sw_install_test.dart` | an unreadable final file on recovery is sw_in_use | red |
|  | A temporary file left by a killed run | `evals/update/test_sw_install.py` | test_only_old_part_files_are_cleaned | green |
| A missing or incompatible sw stops a tagged install before any change | Release assets not uploaded yet | `evals/update/test_sw_install.py` | test_unsealed_release_stops_assets_not_uploaded | green |
|  | Checksum mismatch |  | test_checksum_mismatch_stops_before_stage | green |
|  | Wrong interface |  | test_wrong_interface_stops_before_stage | green |
|  | Unattached assets and an unwritable version directory | `cli/test/update/sw_install_test.dart` | an uncreatable part is download_failed before any request | red |
| Part-file cleanup never replaces the install's result | A locked binary part after a notice write failure | `cli/test/update/sw_install_test.dart` | notice_write_failed survives a failed part delete | red |
|  | A locked part after a rename lost to a concurrent install |  | race hook: kept, part left | red |
|  | A locked part after a rename that fails otherwise |  | fail hook: sw_in_use, part left | red |
|  | A part left when the release has no SHA256SUMS | `evals/update/test_sw_install.py` | test_missing_sums_keeps_undeletable_part | red |
|  | A version directory that cannot be listed | `cli/test/update/sw_install_test.dart` | an unlistable version directory skips the sweep | red |
|  | A source build whose stage cannot be deleted |  | a failed .stage delete keeps the build result | red |
|  | Cleanup succeeds |  | success removes only this run's parts | red |
|  | A later run meets the leftover | `evals/update/test_sw_install.py` | test_only_old_part_files_are_cleaned_after_a_held_part | green |

Verification: never run an eval suite locally. Locally run only the module being written, red then green: `python -m unittest evals/<suite>/test_<x>.py`, or from `cli/` `mise exec -- dart test <file>`; modules that spawn process trees run only in PR CI (`evals.yml`, `cli.yml`, three OSes), and OS-only cases pass on their own CI job. After adding a tracked file, add its rule to `evals/suites.json` and run `python -m unittest evals/runner/test_suite_map.py`. A `Cn:` task writes that carried constraint's fact, as design `## Carried constraints` states it, at the named destination; it is verified by reading the destination and, for Dart, `mise exec -- dart analyze` from `cli/`. Open a draft PR at the first CI-verified task.

## 1. ADRs and the facts kept by decision

- [x] 1.1 Write `docs/adr/0041-a-bounded-launch-reports-a-newly-refused-line-as-a-failed-helper-start.md` as design `## ADRs` and D5 state it: it amends ADR 0034's Refusals clause for bounded launches only. No carried constraint has this ADR as its destination (the related code-side fact is C13). Mark ADR 0034 amended and index 0041 in `openspec/architecture.md`. Verify: the file exists and the index links it.
- [x] 1.2 Write `docs/adr/0042-skills-and-sw-move-to-interface-3.md` as design `## ADRs` and D10 state it: it supersedes only ADR 0040's interface-2 pin. No carried constraint has this ADR as its destination (the related code-side fact is C35). Mark ADR 0040, and in `openspec/architecture.md` change "version and interface 2" to 3 and index 0042. Verify: the index links 0042 and no line of `openspec/architecture.md` still says the skills require interface 2.
- [x] 1.3 Write `docs/adr/0043-the-undo-planner-checks-the-version-of-the-checkout-it-uses.md` as design `## ADRs` and D2 state it: it amends ADR 0040's entry check for `sw finish undo-archive-plan` only. No carried constraint has this ADR as its destination (the related code-side facts are C36 and C47). Index it in `openspec/architecture.md`. Verify: the file exists and the index links it.
- [x] 1.4 C4: doc comment of `gateUnlock` in `cli/lib/src/gate/lock.dart`.
- [x] 1.5 C4c: doc comment of `gateLock` in `cli/lib/src/gate/lock.dart`.
- [x] 1.6 C4b: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 1.7 C24: module docstring of `evals/pr-pair/oracle/check_records.py`. Verify: `python -m unittest evals/pr-pair/test_oracle_records.py` passes.

## 2. Windows line check and the bounded launch (D5)

- [x] 2.1 Write failing tests for the red rows mapped to `cli/test/resolved_line_test.dart`, `cli/test/launch_test.dart`, `cli/test/bounded_run_test.dart`, `cli/test/pr/reply_test.dart`, `cli/test/vcs/git_backend_test.dart` (Windows boundary rows) and `evals/pr-pair/test_as_shim.py`: native-cli "Long Windows arguments reach native tools whole", "A bounded launch checks the helper's own command line", "A caller's check of the command as given keeps its limit", "Arguments that fit only once they move to stdin", and pr-script-runtime "A PR call's new helper refusal keeps its exit with a fixed diagnostic". Expectations are computed independently (hand-built ASCII lines, the helper path's known length). Move `resolved_line_test.dart:29-52` to 32,766 passing and 32,767 refused; keep `launch_test.dart:500-504` admitting 32,767. Verify each fails for the missing check (boundary cases locally, Windows rows in PR CI).
- [x] 2.2 Implement `checkCommandLine(countNul:)`, the NUL-counted started-line checks in `planLaunch`, `helperArguments` and `planBoundedLaunch` in `cli/lib/src/process/command_line.dart`; `BoundedRun` starts the argv it was given and returns a new refusal as `BoundedResult(startError: 'cannot start the helper: its command line is too long')` with a structured `lineTooLong` cause, copied by `_batch` into `LaunchResult.startFailed`; switch every `BoundedRun` construction site (`pr/gh.dart`, `launch.dart` `_batch`, `commands/run.dart`, `review/run.dart`) and update `cli/test/launch_sites_test.dart`. Verify: the 2.1 tests pass (Dart locally, evals and Windows Dart in PR CI) and their rows turn green.
- [x] 2.3 Write failing tests for the reviewer rows of "Long Windows arguments reach native tools whole" (`evals/review-routes/test_review_run.py` and `cli/test/review/routes_test.dart`), plus a failing `models find` with stderr that keeps reporting only the exit status, and the `provider/a%b` unsafe-character case that stays `internal_error`. Verify they fail in PR CI for the right reason.
- [x] 2.4 Make route-selection probes catch only an old-check length refusal (`Unrepresentable` `command line`, or `UnsafeBatchArgument` `line too long`) and skip the route with `unrepresentable command line: <resolved path>`, carried in `_Probe` as a structured field; explicit `--route omp` keeps today's mapping. Verify: the 2.3 tests pass in PR CI and their rows turn green.
- [x] 2.5 Record stream errors (C49 behaviour): the native and bounded launchers set `streamError` instead of reading a pipe error as end of stream, and any stream error or helper exit before the go byte is a failed start with no go byte. Unit tests in `cli/test/launch_test.dart` and `cli/test/bounded_run_test.dart` deliver a complete reply, then a pipe error, with exit 0 (result keeps exit 0, bytes and `streamError`; `sw run --bounded` and `runGh` keep their mapping), and the Windows pre-hello and pre-ready cases. Verify: the tests fail first, then pass (Dart locally, Windows cases in PR CI).
- [x] 2.6 Re-run the green rows "A 20,000-character argument on Windows", "A long argument to a native executable", "A long argument through bash -c on Windows", "A missing transport end marker" and "An argument the launcher cannot represent". Verify: `evals/pr-pair/test_as_shim.py`, `evals/cli/test_sw_args.py` and `cli/test/run_command_test.dart` pass in PR CI on three OSes.
- [x] 2.7 C1: doc comment of `planBoundedLaunch` in `cli/lib/src/process/command_line.dart`.
- [x] 2.8 C13: doc comment of `BoundedRun` in `cli/lib/src/process/bounded_run.dart`.
- [x] 2.9 C23: doc comment of `runExecHelper` in `cli/lib/src/process/exec_helper.dart`.
- [x] 2.10 C25: doc comment of `checkLaunchInput` in `cli/lib/src/process/launch.dart`.
- [x] 2.11 C29: doc comment of `commit` in `cli/lib/src/vcs/git_backend.dart`.
- [x] 2.12 C49: doc comment of `launch` in `cli/lib/src/process/launch.dart`, with a pointer from `BoundedRun`'s comment.

## 3. POSIX command lookup (D6)

- [x] 3.1 Write failing tests: `evals/cli/test_sw_run.py` rows of native-cli "Command lookup takes only files the user can execute" (non-root; skipped as root) and the Linux `setpriv` real/effective-ID case; `cli/test/resolve_test.dart` with injected `isFile` and access checks; `cli/test/native/libc_test.dart` pinning `AT_FDCWD` and `AT_EACCESS` per OS. Verify they fail for the missing check.
- [x] 3.2 Bind `faccessat` in `cli/lib/src/native/libc.dart` and accept a `PATH` candidate only when `faccessat(AT_FDCWD, path, X_OK, AT_EACCESS) == 0`; a name with a separator keeps the execute-bit filter. Add rules for the new test files to `evals/suites.json`. Verify: the 3.1 tests pass (Dart locally, evals in PR CI on Linux and macOS), `python -m unittest evals/runner/test_suite_map.py` passes, and the rows turn green.
- [x] 3.3 C22: doc comment of `_isFile` in `cli/lib/src/process/resolve.dart`.
- [x] 3.4 C26: doc comment of `resolveCommand` in `cli/lib/src/process/resolve.dart`.

## 4. CRLF message files and the GitButler size guard (D1)

- [x] 4.1 Write failing tests for the rows of vcs-backends "A CRLF message file commits on every backend", "GitButler reads the message file where sw runs" and the GitButler and jj rows of "Fixed commit defects are exceptions to the backends' unchanged outputs": Dart in `cli/test/vcs/gitbutler_backend_test.dart` and `cli/test/vcs/jj_backend_test.dart`; real tools in `evals/vcs/test_gitbutler_commit.py` (Linux, run from outside the repo), `evals/vcs/test_commit.py` and `evals/vcs/test_git_backend.py`, reading stored messages as raw bytes. Verify they fail for the right reason.
- [x] 4.2 Implement: jj folds CRLF to LF on the commit path only; GitButler resolves the message path once against `sw`'s directory and passes it to `but commit -F`, folds the file text before `_rstripNl`, removes `_argvCheck` and its estimator tests and `argMax` seam, and maps only length refusals to `too_many_paths` around the real launch (`lengthRefusals: true`; on POSIX `LaunchResult` keeps the OS error and `runToolCapped` takes the `tooLong` stop for `E2BIG`). Verify: the 4.1 tests pass (Dart locally, evals in PR CI; GitButler fixtures on Linux) and their rows turn green, the "Any other commit" row included.
- [x] 4.3 Add the D1 rules to `evals/suites.json`: `cli/lib/src/vcs/**` and `cli/test/vcs/**` to `vcs`; `process/launch.dart`, `command_line.dart`, `resolve.dart` and `bounded_run.dart` to `vcs`; `vcs/git_backend.dart` to `finish` too; `commands/vcs.dart`, `pr/settings_commands.dart` and `evals/finish/fixtures.py` to `vcs` and `finish`. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.
- [x] 4.4 C8: doc comment of `_readMessage` in `cli/lib/src/vcs/jj_backend.dart`.
- [x] 4.5 C11: doc comment of `commit` in `cli/lib/src/vcs/gitbutler_backend.dart`.
- [x] 4.6 C12: doc comment of `commit` in `cli/lib/src/vcs/gitbutler_backend.dart`.
- [x] 4.7 C16: doc comment of `commit` in `cli/lib/src/vcs/gitbutler_backend.dart`.
- [x] 4.8 C18: doc comment of `butRun` in `cli/lib/src/vcs/gitbutler_backend.dart`.

## 5. `sw pr snapshot`: `--timeout`, the material file and merged logs (D7, D9, D4)

- [x] 5.1 Write failing tests in `cli/test/pr/snapshot_test.dart` for the rows of "sw pr snapshot reads --timeout as decimal seconds" and "sw pr snapshot names a material file it cannot write" (injected clock and sleep; the 1, LF, 2 one-line diagnostic; the one-day sleep cap; the `fixedTemp` seam), replacing the tests at `:652-660` and `:155-175`. Verify they fail for the right reason.
- [x] 5.2 Check `--timeout` against `^[0-9]+$` with a signed 64-bit range when options are read, exit 2 with the one-line diagnostic and no `gh` call, cap each sleep at one day, and name the material file and OS reason on stderr. Verify: the 5.1 tests pass locally and their rows turn green.
- [x] 5.3 Write failing tests for the rows of "Snapshot logs keep the order their output arrived in" and native-cli "The failed-job log call caps its two streams together": `cli/test/process/bounded_run_merged_test.dart` (chunk order, split line, one budget at, under and over `maxBytes`, `ArgumentError` without finite bounds), `cli/test/pr/snapshot_test.dart` (fixtures at `:1010-1035` and `pr_support.dart:10-21` move to merged bytes) and `evals/pr-pair/test_pr_snapshot.py` (real helper, lowered `SPECWRIGHT_NET_MAX_BYTES`, two 20 MiB streams). Verify they fail for the right reason.
- [x] 5.4 Add `BoundedRun`'s opt-in merged mode and pass it from `runGh` for `--log-failed` only; the snapshot tails the combined bytes. Add the D4 rules to `evals/suites.json` (`process/exec_helper.dart`, `frame.dart`, `bounded_run.dart`, `command_line.dart`, `limits.dart`, `resolve.dart`, `platform_tree.dart`, `windows_tree.dart`, `posix_tree.dart`, `native/kernel32.dart`, `native/libc.dart` to the suite holding the `--logs` outcome tests) and a rule for the new test file. Verify: the 5.3 tests pass (Dart locally, evals in PR CI on three OSes), `python -m unittest evals/runner/test_suite_map.py` passes, and the rows turn green.
- [x] 5.5 Write `SnapshotParity.test_fixed_cases_are_listed_differences` in `evals/pr-pair/test_parity.py`, listing each case whose frozen record a fix changes, with the new outcome asserted by its own test (D9), no record edited. Verify: it passes in PR CI, the green row "An unaffected case still matches its record" stays green, and `git diff --stat main -- evals/pr-pair/oracle/records` is empty.
- [x] 5.6 C3: doc comment of `BoundedRun` in `cli/lib/src/process/bounded_run.dart`.
- [x] 5.7 C3b: doc comment of `BoundedRun` in `cli/lib/src/process/bounded_run.dart`.

## 6. Windows record replace retry and the `pr-pair` eval flakes (D3, #227, #231)

- [x] 6.1 Write failing tests in `cli/test/pr/feedback_record_test.dart` for the red rows of "Windows record replacement retries a transient refusal", through a `FeedbackRecordStore` with a fake `RecordFiles`, an injected pause and a Windows switch, asserting the attempt count, each requested pause duration (20 ms), that the rethrown error is the first replacement error and not a later one (each attempt fails with a distinct error), and the record's bytes; the source-removed case removes it from inside the injected pause; the cleanup case runs the exhausted retry path and asserts the temp delete was attempted after the last attempt. In `cli/test/pr/feedback_pass_test.dart`, drive a refused replace through `FeedbackPass.adopt` with the injected pause, and assert that a competing lock acquisition during the pause gets `record_busy` and that the temp cleanup comes before the lock release attempt. Verify they fail because nothing retries.
- [x] 6.2 Write the green rows of that requirement (a source gone after the first failed attempt, other platforms, the lock create and publication making one attempt) in the same file. Verify they pass before the fix.
- [x] 6.3 Retry in `FeedbackRecordStore.replaceRecord` only: on Windows, at most 6 attempts, each retry after a requested 20 ms pause and one source check; a missing source or a failed check stops without another replace; rethrow the first error; remove the temporary file on a best-effort basis that never replaces it. The pause is synchronous and `replaceRecord` stays synchronous, so `adopt` holds its lock through every attempt and the cleanup. Verify: the 6.1 and 6.2 tests pass locally and their rows turn green.
- [x] 6.4 In `evals/pr-pair/test_workflow_records.py`, keep every check of the concurrent-adoption test and each worker's distinct new owner, capture each worker's raw result (exit status, stdout and stderr, or the exception) before decoding, add that all six workers report a result, that the winner exits 0 and each loser exits 1, and that the stored record equals the pre-race record except for the owner, which is the winner's, and print every raw result when an assertion or a JSON decode fails; in `evals/pr-pair/test_parity.py`, name subtest folders `w-<ordinal>`. Verify: both modules pass in PR CI on three OSes, and the concurrent-adoption test repeated 300 times on `windows-latest` from a throwaway branch fails none (A1). Its red evidence is the baseline repeat (evals run 44837787942: 15 failures in 300), not a deterministic pre-fix assertion.
- [x] 6.5 C2: doc comment of `replaceRecord` in `cli/lib/src/pr/feedback_record.dart`.
- [x] 6.6 C6: doc comment of `acquireLock` in `cli/lib/src/pr/feedback_record_files.dart`.
- [x] 6.7 C6b: doc comment of `publish` in `cli/lib/src/pr/feedback_record.dart`.

## 7. Bounded download and best-effort install cleanup (D8)

- [x] 7.1 Write failing tests in `cli/test/update/download_test.dart` for the new rows of install-update "The sw download is bounded" (injected clock, timer factory and `PartWriter`; one stop slot, settle function, wire-byte budget, encoding check, bounded shutdown), and move `:112-126`, `:144-163` and `:231-284` to "no response byte written" instead of deletion. Verify they fail for the right reason.
- [x] 7.2 Redesign the download's stop as D8 states: open the part synchronously before the deadline starts, one stop slot, monotonic deadline at admission and settle, counted drain of redirect and error bodies, `Accept-Encoding: identity` with `autoUncompress = false`, the 200 encoding check, one memoized close with a 10-second grace. Verify: the 7.1 tests pass locally and their rows turn green.
- [x] 7.3 Write failing tests for the rows of "Part-file cleanup never replaces the install's result" and the changed rows of the macOS quarantine, placing and stop requirements: `cli/test/update/sw_install_test.dart` (a `fileOps` whose `remove` throws for one path; rename hooks; recovery-path hash; listing denied), `cli/test/update/place_test.dart` (`:262-270` now keeps the part), and `evals/update/test_sw_install.py` (missing-`SHA256SUMS` leftover; the concurrent cases at `:331-343` and `:659-672` assert the exact listing on POSIX only). Verify they fail for the right reason.
- [x] 7.4 Implement one owner per part (`swInstall`'s `finally` and the build's `.stage` `finally`, through `removeQuietly`), forward the command's `fileOps`, move the sweep's listing inside its catch, and treat a hash failure as unconfirmed on the failed-rename recovery only (`placeChecked` takes a destination-hash parameter). Verify: the 7.3 tests pass (Dart locally, evals in PR CI on three OSes) and their rows turn green.
- [x] 7.5 Re-run the green rows of `evals/update/test_sw_install.py` ("Download completes in time", "Quarantined download on macOS arm64", "Rerun with the binary already placed", "Interrupted before the rename", "A stale file at the final path", "Matching hash but not runnable", "Release assets not uploaded yet", "Checksum mismatch", "Wrong interface"). Verify: they pass in PR CI on three OSes.
- [x] 7.6 C9: doc comment of `_cleanStale` in `cli/lib/src/update/sw_install.dart`.
- [x] 7.7 C14: doc comment of `placeChecked` in `cli/lib/src/update/place.dart`.
- [x] 7.8 C15: doc comment of `swInstall` in `cli/lib/src/update/sw_install.dart`.
- [x] 7.9 C17: doc comment of `discard` in `cli/tool/build.dart`.
- [x] 7.10 C20: doc comment of `_copyFile` in `cli/lib/src/update/download.dart`.
- [x] 7.11 C21: doc comment of `downloadReleaseFile` in `cli/lib/src/update/download.dart`.
- [x] 7.12 C27: doc comment of `downloadReleaseFile` in `cli/lib/src/update/download.dart`.

## 8. Undo planner: whole records, complete reads and exit codes (D2)

- [x] 8.1 Write failing tests for the red rows of change-finish "The undo planner reports paths whole" through "A usage error from the planner's state read exits 2" in the test map, the usage row of "Fixed undo-plan defects are exceptions to the script's refusals", and the state-read rows of "The undo plan stops when a read it relies on fails": real Git in `evals/finish/test_undo_plan.py` (strengthen `test_resume_on_dirty_main_refused` and the `evals/finish/test_parity.py` dirty-tree cases to assert `files` and the message, D9), injected reads in `cli/test/finish/undo_plan_test.dart`, framing tests of the shared reader in `cli/test/vcs/git_backend_test.dart`. Give every Git-backed planner test a committed matching `VERSION`. Verify they fail for the right reason.
- [x] 8.2 Split `parseZRecords` out of `parsePorcelain`; add the shared inventory reader (whole logical records, stderr fails the read, stream errors fail it); read both planner status reads with `--no-optional-locks status --porcelain=v1 -z --untracked-files=all`, `GIT_OPTIONAL_LOCKS=0` and `-c core.fsmonitor=false` through the planner-only option, check every exit status, decode strictly, sort `carried_edits` in UTF-8 byte order, render the dirty message, and keep the stop code of a `usage` stop. Verify: the 8.1 tests pass (Dart locally, evals in PR CI on three OSes) and their rows turn green.
- [x] 8.3 Add the D2 rules to `evals/suites.json`: map to `finish` every file in D2's mapping list (the VCS layer, settings and options, process and native files, `fs/walk.dart`, `entry/project_version.dart`, `cli.dart`, `commands/finish.dart`, and the `evals/vcs` helpers), and `native/libc.dart` to `vcs` and `pr-pair` too. Verify: `python -m unittest evals/runner/test_suite_map.py` passes.
- [x] 8.4 C5: confirm the fact is in `specs/change-finish/spec.md` under "The undo planner reports paths whole". Verify: `openspec validate fix-sw-port-gaps --strict` passes and the requirement holds the text.
- [x] 8.5 C10: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 8.6 C50: doc comment of `parseZRecords` in `cli/lib/src/vcs/git_backend.dart`.

## 9. Undo planner: the version check, the project root and regular-file reads (ADR 0043)

- [x] 9.1 Write failing tests: `evals/finish/test_finish_shim.py` for the new rows of change-finish "finish.sh finds the project from --code, then --dir" and the option, code-directory, version and settings rows of "The undo plan stops when a read it relies on fails" mapped there; `evals/cli/test_sw_project_version.py` for native-cli "The project root is found from the physical path"; the `VERSION`, settings and decision-file FIFO rows in `evals/finish/test_undo_plan.py` and `evals/finish/test_undo_steps.py` (POSIX, 60-second bound); `cli/test/entry/regular_file_test.dart` for `readRegularFile` and the source test that no other file-opening API appears in `cli/lib/src/finish/` or `entry/project_version.dart`; a `projectRoot` unit test in `cli/test/entry/project_version_test.dart`. Verify they fail for the right reason.
- [x] 9.2 Implement ADR 0043: `projectRoot` resolves an existing start physically; the CLI skips its entry check only for `undo-archive-plan`; the planner validates options, anchors a relative `--code` at `projectRoot(--dir)`, refuses an empty or missing `--code` with `not_repository`, runs `versionMismatch` once and passes that root as every emitted step's `--project`; add `cli/lib/src/entry/regular_file.dart` and route every work-tree open of the finish code through it. Add rules for the new files (`finish` and `vcs`). Verify: the 9.1 tests pass (Dart locally, evals in PR CI), `python -m unittest evals/runner/test_suite_map.py` passes, and the rows turn green.
- [x] 9.3 Re-run the green rows "Store-backed plan finds the code checkout's sw", "Store-backed call without --code" and the native-cli rows of "Project commands check the project's version" and "The project is chosen by --project, then the command's own argument". Verify: `evals/finish/test_finish_shim.py` and `evals/cli/test_sw_project_version.py` pass in PR CI.
- [x] 9.4 C36: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 9.5 C38: doc comment of `readRegularFile` in `cli/lib/src/entry/regular_file.dart`.
- [x] 9.6 C47: doc comment of `projectRoot` in `cli/lib/src/entry/project_version.dart`.

## 10. Undo planner: Git environment, index and guards (D2)

- [x] 10.1 Write failing tests for the red rows of the change-finish index, submodule, ignored-file, literal-path, Git-environment, operation-in-progress and failed-index-step requirements, the guard and warning rows of "Fixed undo-plan defects are exceptions to the script's refusals", the Git rows of "The undo plan stops when a read it relies on fails" not taken by groups 8, 9 and 11, and native-cli "The undo plan's Git steps carry their safety options", in `evals/finish/test_undo_plan.py`, `evals/finish/test_undo_steps.py` and `cli/test/finish/undo_plan_test.dart`. Move the argv-pinning tests (`evals/finish/test_undo_steps.py:236`, `:256`, the `evals/finish/test_undo_jj.py` step-program checks, the `undo_plan_test.dart` lines C19 lists) to the new argv. Verify they fail for the right reason.
- [x] 10.2 Implement D2's Git-side guards: `diff-index --cached --ignore-submodules=none` for both index checks and `--ignore-submodules=none` on cleanliness checks; checkout `-q --no-overwrite-ignore --no-recurse-submodules`; `--literal-pathspecs` and `--no-replace-objects` on every planner and emitted Git command; the `git_env`, partial-clone, sparse, grafts and GitButler-metadata refusals in the planner and `check preflight`; the operation-in-progress check; the exact `for-each-ref` tip lookup; the role-aware `check branch --backend`; the index-flag scan; the recovery warning. Verify: the 10.1 tests pass (Dart locally, evals in PR CI on three OSes) and their rows turn green.
- [x] 10.3 Re-run the green rows "No archive of the change", "Branch moved after the plan", "A staged change on the change branch" and "Any other refusal". Verify: `evals/finish/test_undo_plan.py` and `evals/finish/test_parity.py` pass in PR CI.
- [x] 10.4 C19: doc comment of `checkIndex` in `cli/lib/src/finish/undo_step.dart`.
- [x] 10.5 C28: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 10.6 C31: doc comment at the index check in `cli/lib/src/finish/undo_step.dart`.
- [x] 10.7 C34: doc comment of `_Planner` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 10.8 C43: doc comment of `_detectMain` in `cli/lib/src/pr/settings_commands.dart`.
- [x] 10.9 C44: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 10.10 C45: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.

## 11. Undo planner: rerun eligibility from the restored copy (D2)

- [x] 11.1 Write failing tests for the rows of change-finish "Rerun eligibility is read from the copy the undo restores" (except "Restored decision bytes differ from the tip", which needs the post-checkout `check inputs` of 12.2) and the decision-file rows of "The undo plan stops when a read it relies on fails" ("An explicit filter unset", "A filter whose name is unspecified", "Two members whose names differ only by case", "An unreadable work-tree tasks file", "A task file hidden by an index flag"), including the case-insensitive `σ`/`ς` fixture (skipped where the volume is case-sensitive) and the 2.39 `git` for `tool_too_old`: `evals/finish/test_undo_plan.py` and `evals/finish/test_undo_steps.py`. Verify they fail for the right reason.
- [x] 11.2 Implement: work-tree decision files on the current branch with `lstat`-only absence; on resume, raw blobs with `check-attr -z --all` at `--source=<tip>` and `--source=HEAD` before classifying any member, the untracked `.gitattributes` refusal, `GIT_ATTR_SOURCE`/`attr.tree` in `git_env`, the re-check before the checkout, `unsupported_filter` for a filter, encoding or symlink, `tool_too_old` below Git 2.40; the rerun delta from the same copy; `uniqueMembers` by upper and lower case; the warning "after this plan is printed". Add the README Step 1 line: a Git undo that resumes the archive branch needs Git 2.40 or later. Verify: the 11.1 tests pass in PR CI and their rows turn green, and `README.md` holds the line.
- [x] 11.3 C33: doc comment of `rerun` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 11.4 C39: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 11.5 C40: doc comment of `uniqueMembers` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 11.6 C41: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.

## 12. Undo planner: destinations, nested repositories, markers and line sizing (D2)

- [x] 12.1 Write failing tests for the Git rows of the change-finish destination, marker, absence, in-place-warning, line-sizing, nested-repository and named-paths requirements, and the destination and change-marker FIFO rows of "The undo plan stops when a read it relies on fails", and the "Restored decision bytes differ from the tip" row of "Rerun eligibility is read from the copy the undo restores", in `evals/finish/test_undo_plan.py`, `evals/finish/test_undo_steps.py`, `cli/test/finish/undo_plan_test.dart` and `cli/test/finish/undo_step_test.dart`. Migrate every whole-argv-list comparison in `cli/test/finish/` and `evals/finish/` to order and content assertions (C46). Verify they fail for the right reason.
- [x] 12.2 Implement D2's destination rules: one destination list and walk (`check destinations`, `check absent` from positive listing evidence), case-fold and prefix collisions, gitlink and `.git`-marker refusals, restore through a sibling temporary file, the marker copy before the first index change, the post-checkout `check inputs`, batching under the launcher's own sizing, `plan_too_large`, and the in-place rerun warning. Verify: the 12.1 tests pass (Dart locally, evals in PR CI on three OSes) and their rows turn green.
- [x] 12.3 C32: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 12.4 C37: confirm the fact is in `specs/change-finish/spec.md` under "An undo destination is absent only by evidence". Verify: `openspec validate fix-sw-port-gaps --strict` passes and the requirement holds the text.
- [x] 12.5 C46: doc comment of `runUndoStep` in `cli/lib/src/finish/undo_step.dart`.
- [x] 12.6 C48: confirm the gap is in `specs/change-finish/spec.md` under "A rerun plan warns that it writes specs in place". Verify: `openspec validate fix-sw-port-gaps --strict` passes and the requirement holds the text.
- [x] 12.7 C51: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 12.8 C52: confirm the gap is in `specs/change-finish/spec.md` under "Every printed undo step fits the command line". Verify: `openspec validate fix-sw-port-gaps --strict` passes and the requirement holds the text.

## 13. Undo planner on jj and GitButler (D2)

- [x] 13.1 Write failing tests for the jj rows (`evals/finish/test_undo_jj.py`: unsnapshotted edit, pending Git ref import, conflicted resume bookmark, unbookmarked child, store backend changed after planning with zero `jj` invocations, over-long fileset; the jj half of "Deferred archive found") and the GitButler rows (`evals/vcs/test_gitbutler_undo.py`, real `but`, Linux: vcs-backends "A committed GitButler undo refuses paths its commit would rename" and "A GitButler-selected undo reports a failed target read", and every change-finish row mapped there). Verify they fail for the right reason in PR CI.
- [x] 13.2 Implement: the jj planner reads the requested bookmark by exact name and stops with `ambiguous_branch` when it is conflicted; the jj resume's first `check branch --backend jj` before `check clean --jj` and `jj new`; on GitButler the failed carried-edits read stops, `bad_path` for a path the GitButler check would refuse or rewrite on a committed undo, `vcs_error`/`not_managed` for the strict target read, the lossless foreign-assignment check at planning and in `check destinations`. Update `skills/specwright-finish/SKILL.md` ("It only reads the repo" → the plan changes no file; on jj it may record jj's own snapshot and Git import) and the doc comment at `undo_plan.dart:74`. Verify: the 13.1 tests pass in PR CI and their rows turn green.
- [x] 13.3 C30: doc comment of `undoArchivePlan` in `cli/lib/src/finish/undo_plan.dart`.
- [x] 13.4 C42: confirm the gap is in `specs/change-finish/spec.md` under "A deferred archive's undo is planned by a script that runs nothing". Verify: `openspec validate fix-sw-port-gaps --strict` passes and the requirement holds the text.

## 14. Interface 3 (D10)

- [x] 14.1 Write failing tests: `evals/cli/test_sw_version.py` expecting interface 3, `evals/cli/test_sw_interface_pin.py` with `INTERFACE = ["3"]`, `evals/cli/test_skill_probe.py` with a 0.38.x binary reporting interface 2 and only `version --json` reaching it, the skill-text and install checks in `evals/git-workflow/` and `evals/cli/test_install_sw.py`; move the Dart tests D10 lists (`version_test.dart`, `update/fake_sw.dart`, `update/place_test.dart`, `commit/commit_command_test.dart`, `finish/finish_command_test.dart`) to 3 where they mean the current interface. Verify they fail because `sw` reports 2.
- [x] 14.2 Set `interfaceVersion` to 3 in `cli/lib/src/commands/version.dart`; make the `interface` line of `skills/specwright-pr/SKILL.md` read 3 and the `<sw>` paragraph of `specwright-branch`, `-commit`, `-debug`, `-finish`, `-pr`, `-release`, `-review` and `-roadmap` require interface 3 and tell the user to update a project whose binary reports 2 or 1; map `skills/specwright-pr/SKILL.md` to `cli/test_sw_interface_pin.py` in `evals/suites.json`. Verify: the 14.1 tests pass (Dart locally, evals in PR CI), `python -m unittest evals/runner/test_suite_map.py` passes, and the rows turn green.
- [x] 14.3 Re-run the green rows "Unknown command or flag", "VERSION is not a version" and "The version probe hangs or floods". Verify: `evals/cli/test_sw_version.py` and `evals/git-workflow/test_skill_sw_calls.py` pass in PR CI.
- [x] 14.4 C35: doc comment of `interfaceVersion` in `cli/lib/src/commands/version.dart`.

## 15. Integration and release

- [ ] 15.1 Every row of the test map is green: `evals.yml`, `cli.yml` and `sw-build.yml` pass on the PR head on Linux, Windows and macOS, and `openspec validate fix-sw-port-gaps --strict` passes.
- [ ] 15.2 Bump the release: `<sw> release bump --to 0.39.0` (the `release.sh bump --to 0.39.0` step, run with the tree-built `sw` from `mise run install-sw`). Rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify: `<sw> release check` and `<sw> release notes --proposal openspec/changes/fix-sw-port-gaps/proposal.md` pass.

## Workflow follow-up

- Close #232 with the S1 reason, and #214 item 4 as moot, when the PR merges.
- After merge, publish v0.39.0 with `specwright-release`.
- No `[user]` task: the proposal's M9 exit criterion is agent-verified.
