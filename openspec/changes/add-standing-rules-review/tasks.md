# Tasks

## Test map

| Requirement | Scenario | Test file (under `evals/`, except `cli/` tests) | Test name | State |
|---|---|---|---|---|
| Legacy override | Parking change with no review rounds | `git-workflow/test_instructions.py` | `test_tasks_precheck_accepts_deferred_with_target` | green (existing) |
| Legacy override | Escalation after two REVISE rounds | `review-routes/test_design_review.py` | `test_legacy_override_still_passes` | green |
| Owner checkpoint | Unresolved third round | `review-routes/test_design_review.py` | `test_default_checkpoint_keeps_revise` | green |
| Owner checkpoint | No count-based stop | `review-routes/test_design_review.py` | `test_default_checkpoint_keeps_revise` | green |
| Owner checkpoint | Configured round and conditional approval | `review-routes/test_design_review.py` | `test_custom_cap_blocks_conditional` | green |
| Owner checkpoint | Approval at the limit | `review-routes/test_design_review.py` | `test_approval_at_cap` | green |
| Owner choice | One scoped pass stays unresolved | `review-routes/test_design_review.py` | `test_scoped_pass_survives_replacement` | green |
| Owner choice | Scope change with reason | `review-routes/test_design_review.py` | `test_scope_change_requires_changed_artifacts` | green |
| Owner choice | A reason alone does not restart the budget | `review-routes/test_design_review.py` | `test_scope_change_requires_changed_artifacts` | green |
| Owner choice | Stop or no choice | `review-routes/test_design_review.py` | `test_stop_stays_stopped` | green |
| Owner choice | Failed or stale pass does not spend permission | `review-routes/test_design_review.py` | `test_subagent_capture_and_stale_publication` | green |
| Owner choice | Owner details cannot add a verdict | `review-routes/test_design_review.py` | `test_scoped_pass_survives_replacement` | green |
| Owner choice | A narrowed design cannot erase its unresolved FULL review | `review-routes/test_design_review.py` | `test_other_writers_cannot_erase_checkpoint` | green |
| Refusal durability | Subagent design review that could not review | `review-routes/test_review_run.py` | `test_record_out_refused_keeps_review_and_scratch` | green (existing) |
| Refusal durability | Valid subagent design review | `review-routes/test_review_run.py` | `test_record_out_valid_writes_review_removes_scratch` | green (existing) |
| Standing requirements | Versioned rules reach either design review route | `review-routes/test_design_review.py` | `test_full_rules_use_branch_blobs_on_both_routes` | green |
| Standing requirements | No rules declared | `review-routes/test_design_review.py` | `test_no_rules_does_not_add_section` | green |
| Standing requirements | A declared rule is unavailable | `review-routes/test_design_review.py` | `test_bad_rule_fails_before_reviewer` | green |
| Standing requirements | Standing rules do not reach pre-ship or baseline reviews | `review-routes/test_design_review.py` | `test_other_review_modes_do_not_resolve_rules` | green |
| Standing requirements | LIGHT still has no reviewer brief | `review-routes/test_design_review.py` | `test_other_review_modes_do_not_resolve_rules` | green |
| Rule identity | Rules added between conditional approval and its recheck | `review-routes/test_design_review.py` | `test_rules_change_requires_full_review` | green |
| Rule identity | Rule text changes after approval | `review-routes/test_design_review.py` | `test_rules_change_requires_full_review` | green |
| Rule identity | A sibling changes GitButler review settings | `review-routes/test_design_review.py` | `test_settings_pin_and_stale_selection` | green |
| Rule identity | Route selection used previous settings | `review-routes/test_design_review.py` | `test_settings_pin_and_stale_selection` | green |
| Captured input | Live artifacts change and change back during dispatch | `review-routes/test_design_review.py` | `test_subagent_capture_and_stale_publication` | green |
| Captured input | A capability directory in the spec tree is a link | `review-routes/test_design_review.py` | `test_linked_spec_tree_refuses_full_review` | green |
| Captured input | A proposal example contains a Release Notes heading | `review-routes/test_design_review.py` | `test_fenced_release_heading_does_not_hide_proposal_edits` | green |
| Captured input | A Setext heading follows Release Notes | `review-routes/test_design_review.py` | `test_setext_heading_after_release_notes_stays_reviewed` | green |
| Captured input | An earlier FULL approval lacks a capture fingerprint | `review-routes/test_design_review.py` | `test_legacy_unpinned_approval_requires_full_review` | green |
| Captured input | A conditional recheck receives unrelated changes | `review-routes/test_design_review.py` | `test_recheck_cannot_renew_baseline` | green |
| Captured input | A full pass cannot confirm a recheck | `review-routes/test_design_review.py` | `test_recheck_cannot_renew_baseline` | green |
| Captured input | A limited recheck cannot establish another baseline | `review-routes/test_design_review.py` | `test_recheck_cannot_renew_baseline` | green |
| Captured input | Publishing a new result fails after its conditional capture is staged | `cli/test/review/design_publication_test.dart` | `a failed report write leaves the original conditional baseline usable` | green (injected write failure) |
| Captured input | The ordinary writer targets an open checkpoint | `review-routes/test_design_review.py` | `test_other_writers_cannot_erase_checkpoint` | green |
| Captured input | Conflicting evidence cannot keep the publication lock | `cli/test/review/design_publication_test.dart` | `Git deadline during publication preserves the verdict and scoped pass` | green (manual deadline, real lock) |
| Captured input | Interrupted attempts reach the slot limit | `review-routes/test_design_review.py` | `test_interrupted_slots_and_bounded_failure` | green |
| Usable evidence and retention | A selected route cannot read the packet | `review-routes/test_design_review.py` | `test_unreadable_route_refuses_before_capture` | green |
| Usable evidence and retention | A bounded invalid FULL subagent reply | `review-routes/test_design_review.py` | `test_interrupted_slots_and_bounded_failure` | green |
| Usable evidence and retention | Repeated failures and oversized scratch output | `review-routes/test_design_review.py` | `test_interrupted_slots_and_bounded_failure` | green |

## 1. Design review inputs and checkpoint

- [x] 1.1 Record ADR 0044 (C3, C7) and update the architecture index; verify the pin, publication and owner boundaries against the design.
- [x] 1.2 Add red executable evals for the changed scenarios and the suite map entry; verify the new module fails on the old workflow.
- [x] 1.3 Implement shared native FULL packet capture, standing rules, pinned route selection, eligibility and bounded failure handling; verify against the mapped review-route tests and preserve C1, C4, C8–C13 in the delta.
- [x] 1.4 Implement durable round state, owner decisions, writer guards and existing verdict gates; verify the mapped checkpoint cases and carry C2, C5 and C6 in the delta.
- [x] 1.5 Wire the schema and review skill, document configuration and migration, and verify the installed schema, targeted eval module and suite map.
- [x] 1.6 Run a real Claude FULL packet read of a captured marker under the fixed route and record the observed result in the PR verification. Claude Code 2.1.331 returned the exact capture-only marker with `Read, Grep, Glob` and Windows `job` isolation.

## 2. Version and release notes

- [x] 2.1 `<sw> release bump --to 0.40.0`; verify with `<sw> release check` and `<sw> release notes --proposal openspec/changes/add-standing-rules-review/proposal.md`.
