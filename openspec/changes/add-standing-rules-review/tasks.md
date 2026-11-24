# Tasks

## Test map

| Requirement | Scenario | Test file (under `evals/`) | Test name | State |
|---|---|---|---|---|
| Legacy override | Parking change with no review rounds | `git-workflow/test_instructions.py` | `test_tasks_precheck_accepts_deferred_with_target` | green (existing) |
| Legacy override | Escalation after two REVISE rounds | `git-workflow/test_instructions.py` | `test_change_checkpoint_does_not_issue_override` (tasks lists stored override); `test_apply_gate_refuses_deferred_and_says_review_needed` (apply reuses tasks precheck) | Instruction checks only; end-to-end apply with a stored override is unverified |
| Owner checkpoint | Unresolved third round | `review-routes/test_design_review.py` | `test_default_checkpoint_keeps_revise` | green |
| Owner checkpoint | Configured round and conditional approval | `review-routes/test_design_review.py` | `test_scope_change_records_reason_and_restarts_round_budget` | green |
| Owner choice | One scoped pass stays unresolved | `review-routes/test_design_review.py` | `test_scoped_pass_survives_replacement_and_hands_back` | green |
| Owner choice | Scope change with reason | `review-routes/test_design_review.py` | `test_scope_change_records_reason_and_restarts_round_budget` | green |
| Owner choice | Stop or no choice | `review-routes/test_design_review.py` | `test_stop_keeps_checkpoint_unresolved`, `test_default_checkpoint_keeps_revise` | green |
| Standing requirements | Versioned rules reach either design review route | `review-routes/test_design_review.py` | `test_full_rules_use_branch_blobs_on_both_routes` | green |
| Standing requirements | No rules declared | `review-routes/test_design_review.py` | `test_no_rules_leaves_both_briefs_unchanged` | green |
| Standing requirements | A declared rule is unavailable | `review-routes/test_design_review.py` | `test_bad_rule_fails_before_reviewer` | green |

## 1. Standing rules and owner checkpoint

- [x] 1.1 Record ADR 0044 and its architecture index entry; keep the policy specific to FULL change-design reviews.
- [x] 1.2 Read declared versioned rules in both routes and verify present, absent and unavailable rules.
- [x] 1.3 Record the configured owner checkpoint and its three decisions without deciding readiness; verify the cap and durable choices.
- [x] 1.4 Wire the review schema and skill, document project settings and the eight-repository migration.
- [x] 1.5 Record the owner's second scope cut, remove non-core mechanisms and restore main's surrounding behavior.

## 2. Version and release notes

- [x] 2.1 `<sw> release bump --to 0.40.0`; verify with `<sw> release check` and `<sw> release notes --proposal openspec/changes/add-standing-rules-review/proposal.md`.
