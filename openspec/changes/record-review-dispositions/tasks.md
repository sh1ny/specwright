# Tasks

## Test map

Every new test below lives in `evals/git-workflow/test_instructions.py`, in a new class `DesignReviewDispositions` (DRD below), unless the row names another file. These are instruction-text checks, as the module docstring describes: they prove the rule is in the delivered text.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| design-review-gate → The tasks precheck accepts only recorded passing dispositions | Deferred parking change writes tasks | evals/git-workflow/test_instructions.py | DRD.test_tasks_precheck_accepts_deferred_with_target | green |
| design-review-gate → The tasks precheck accepts only recorded passing dispositions | Waived change writes tasks | evals/git-workflow/test_instructions.py | DRD.test_tasks_precheck_accepts_waived_with_user_words | green |
| design-review-gate → The tasks precheck accepts only recorded passing dispositions | Verdict that only starts with a passing value | evals/git-workflow/test_instructions.py | DRD.test_tasks_precheck_matches_whole_lines_for_new_verdicts | green |
| design-review-gate → A deferred review never ships code | Apply on a deferred change | evals/git-workflow/test_instructions.py | DRD.test_apply_gate_refuses_deferred_and_says_review_needed | green |
| design-review-gate → A deferred review never ships code | Archive on a deferred change | evals/git-workflow/test_instructions.py | DRD.test_config_context_refuses_archive_of_deferred | green |
| design-review-gate → A deferred review never ships code | Archive ran anyway | evals/git-workflow/test_instructions.py | DRD.test_finish_step0_stops_on_deferred_and_lists_restore_groups | green |
| design-review-gate → A deferred review never ships code | Deferral with no target | evals/git-workflow/test_instructions.py | DRD.test_tasks_precheck_stops_on_deferred_without_target | green |
| design-review-gate → A parking change lands without archive | Watch on a parking change's PR | evals/git-workflow/test_instructions.py | DRD.test_watch_skips_archive_for_deferred_and_reports_parked | green |
| design-review-gate → A parking change lands without archive | Watch on an ordinary change | evals/git-workflow/test_instructions.py | DRD.test_watch_archive_before_merge_kept_for_other_verdicts | green |
| design-review-gate → A waiver records the user's decision | User waives the design review | evals/git-workflow/test_instructions.py | DRD.test_waiver_records_user_words_and_no_review_ran | green |
| design-review-gate → A waiver records the user's decision | Waiver without the user's words | evals/git-workflow/test_instructions.py | DRD.test_waiver_without_user_words_refused_at_tasks_and_apply | green |
| design-review-gate → A waiver records the user's decision | Review route unavailable | evals/git-workflow/test_instructions.py | DRD.test_agent_never_offers_waiver_or_deferral | green |
| design-review-gate → A waiver records the user's decision | Waived change ships | evals/git-workflow/test_instructions.py | DRD.test_waiver_does_not_waive_preship | green |
| design-review-gate → USER_OVERRIDE follows only an escalation | Parking change with no review rounds | evals/git-workflow/test_instructions.py | DRD.test_user_override_only_after_escalation | green |
| design-review-gate → USER_OVERRIDE follows only an escalation | Escalation after two REVISE rounds | evals/git-workflow/test_instructions.py | DRD.test_user_override_only_after_escalation (escalation half) | green |
| review-routes → Design review verdict values are checked | Design review that could not review | evals/review-routes/test_review_run.py | test_design_blocked_verdict_invalid_keeps_review | green |
| review-routes → Design review verdict values are checked | Verdict a reviewer may not set | evals/review-routes/test_review_run.py | test_design_override_and_skipped_verdicts_invalid (extended to DEFERRED, WAIVED) | green |
| review-routes → Design review verdict values are checked | CHANGES_APPLIED does not match the verdict | evals/review-routes/test_review_run.py | test_design_changes_applied_must_match_verdict | green |
| review-routes → Design review verdict values are checked | Valid re-check | evals/review-routes/test_review_run.py | test_design_recheck_with_changes_applied_yes_valid | green |
| project-planning → A parked change is never resumed | Only a parking change is active | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_next_skips_parked_change | green |
| project-planning → A parked change is never resumed | Status shows the parked change | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_status_lists_parked_with_targets | green |
| project-planning → A parked change is never resumed | Parking change and a change in progress | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_next_resumes_non_parked_change | green |
| project-planning → A parked change is never resumed | Next run on the parking change's branch | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_next_and_status_on_parking_branch | green |
| project-planning → A parked change is never resumed | Active change with no review yet | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_next_resumes_non_parked_change (no-review half) | green |
| project-planning → The baseline gate passes only a review or an escalation | Baseline passes review | evals/git-workflow/test_instructions.py | ProjectPlanning.test_roadmap_accepts_adrs_only_after_gate | green |
| project-planning → The baseline gate passes only a review or an escalation | Baseline recorded as waived or deferred | evals/git-workflow/test_instructions.py | ProjectPlanning.test_baseline_gate_lists_own_verdicts_without_deferred_or_waived | green |

Extra tests, with no scenario row: `DRD.test_template_context_lines_use_managed_prefixes` (review S4/M1: every `context:` line in `templates/openspec/config.yaml` starts with a prefix README install Step 5 names) and `DRD.test_review_template_and_readme_list_new_verdicts`.

## 1. Gate verdicts in the schema and review template

- [x] 1.1 Add the DRD class with the failing tests for the tasks precheck, the apply gate, the waiver and USER_OVERRIDE rows (test map rows 1-4, 7, 10-15) and `test_review_template_and_readme_list_new_verdicts`. Confirm with `python -m unittest evals.git-workflow.test_instructions -k DesignReviewDispositions` (or `discover` with `-p test_instructions.py`) that each fails because the schema or template lacks the rule, not because of an error.
- [x] 1.2 Schema gates: `schemas/specwright/schema.yaml`: in the review instruction, define `DEFERRED` (user-declared parking change, `- **Deferred to:**` line, `CHANGES_APPLIED: n/a`) and `WAIVED` (explicit user decision, `- **User decision:** "<words>"`, `No design review ran.`, `CHANGES_APPLIED: n/a`, pre-ship review not waived). Narrow USER_OVERRIDE to escalation only, and state that the agent never offers either new verdict, including when no route works. Extend the tasks PRECHECK with both whole-line values and their required records. Replace the apply `GATE` line with the tasks precheck plus a `DEFERRED` stop that names the targets and says a design review is needed first. Verify the rows from 1.1 pass and `cd F:/Dev/specwright && openspec schema validate specwright` passes, then flip the rows green.
- [x] 1.3 Review template and README: `schemas/specwright/templates/review.md`: add `DEFERRED | WAIVED` to the verdict comment with their rules, the Reviewer values `none (DEFERRED by the user)` and `none (WAIVED by the user)`, and the Metadata lines `Deferred to:` and `User decision:`. README "Review verdicts" table: two rows and the note that a project which recorded a deferral as USER_OVERRIDE may rewrite it as DEFERRED. Verify `test_review_template_and_readme_list_new_verdicts` passes.
- [x] 1.4 Reviewer refusal: `skills/specwright-review/SKILL.md` (Design reviews): list `DEFERRED` and `WAIVED` among the invalid reviewer values. In `evals/review-routes/test_review_run.py`, extend `test_design_override_and_skipped_verdicts_invalid` to DEFERRED and WAIVED. It passes with no script change (`review-run.sh` VERDICTS is unchanged). Run `python -m unittest discover evals/review-routes` and flip its row green.

## 2. Archive refusal

- [x] 2.1 Write the failing DRD tests for test map rows 5-6 and `test_template_context_lines_use_managed_prefixes`. Confirm that they fail because the context line, the README prefix and finish step 0 are missing.
- [x] 2.2 Archive context line: `templates/openspec/config.yaml`: add the context line starting `MANDATORY: Before archiving a change (/opsx:archive, /opsx:bulk-archive, openspec-archive-change, 'openspec archive'), read its review.md`. A `VERDICT: DEFERRED` line means no move, no spec sync, the targets are named, and a bulk archive skips the change. README install Step 5: add `MANDATORY: Before archiving a change` to the managed-line prefixes. Also add the line to this repo's own `openspec/config.yaml` `context:`. Verify rows 5 and the prefix test pass, then flip green.
- [x] 2.3 Finish backstop: `skills/specwright-finish/SKILL.md`: add step 0 before step 1 (also reached from the Resume table's first row, steps 1-3). For each archived change whose archived `review.md` holds `VERDICT: DEFERRED`, stop before any commit, merge or push, run no restore, and list the three restore groups: modified main specs (`git restore -- <file>`, with the uncommitted-edits warning), created main specs (delete), and the change directory (`git restore` when committed, else move it back). Verify row 6 passes, flip green, and run the full `python -m unittest discover evals/git-workflow -p "test_instructions.py"` to confirm the finish Resume tests still pass.

## 3. Parking changes in watch and the roadmap

- [x] 3.1 Write the failing tests for test map rows 8-9 (DRD), the five project-planning `red` rows in `ProjectPlanning`, and `test_baseline_gate_lists_own_verdicts_without_deferred_or_waived`. Confirm that they fail for the missing text.
- [x] 3.2 Watch skips parked changes: `skills/specwright-pr/SKILL.md` watch **Archive before merge**: when the change's `review.md` holds `VERDICT: DEFERRED`, archive nothing, report the PR ready as a parked change for the user to merge, and send no merge request. Ordinary changes are unchanged. Verify rows 8-9 pass, flip green, and run `python -m unittest discover evals/pr-pair` to confirm nothing regressed.
- [x] 3.3 Roadmap parking changes: `skills/specwright-roadmap/SKILL.md`:
  - init step 5: replace "the same precheck as tasks" with its own list, and state that DEFERRED, WAIVED and SKIPPED_LIGHT never pass the baseline.
  - next step 2: a change whose `review.md` holds `VERDICT: DEFERRED` is parked, never offered for resume, and next continues as if it were not active. On the parking branch, next says it starts from main once the parking change has merged, and starts nothing.
  - status: lists parked changes with their `Deferred to:` targets, and says the same on the parking branch (review S5).
  - A short parking-change note: when the pattern fits, DEFERRED only by the user's decision, the user merges the parking branch, next moves a milestone's part into its own reviewed change, and removing an emptied parking change is the user's edit.

  Verify the project-planning rows and the baseline test pass, flip them green, and confirm `test_roadmap_accepts_adrs_only_after_gate` is still green.
- [x] 3.4 `openspec/architecture.md`: the `review.md` State ownership row gains the orchestrator writing DEFERRED and WAIVED on the user's decision, and the baseline row says neither verdict is written there. Verify by `git diff openspec/architecture.md` showing only those two rows changed.

## 4. Integration and release

- [ ] 4.1 Run every suite the M4 exit criteria name: `python -m unittest discover evals/git-workflow`, `evals/review-routes`, `evals/pr-pair`, `evals/update`, `evals/release` (each with its usual `-p` pattern). All pass, and every test map row is green.
- [ ] 4.2 `openspec validate record-review-dispositions --strict` and `cd F:/Dev/specwright && openspec schema validate specwright` both pass.
- [ ] 4.3 `bash skills/specwright-release/scripts/release.sh bump --to 0.7.0` (`VERSION`, the README badge, every `skills/*/SKILL.md` `metadata.version`), verified by `bash skills/specwright-release/scripts/release.sh check` reporting 0.7.0, and by `release.sh check --main origin/main` passing after a fenced fetch.

## Workflow follow-up

- Pre-ship review, ship (PR closes #100), watch, archive, merge; then publish v0.7.0.
- After release, the yagura `platform-backlog` review can be rewritten from USER_OVERRIDE to DEFERRED (user's call, in that project).
