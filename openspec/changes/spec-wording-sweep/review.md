# Review

## Metadata

- **Round:** 8 (FULL)
- **Prior round:** APPROVE_WITH_CHANGES (round 7); pre-ship amendments f242d3c, e8beb61
- **Reviewer:** OMP / openai-codex/gpt-6.2-sol
- **Reviewed:** Proposal, design, tasks and test map, affected deltas and matching main-spec requirements, finish and PR skills, README Steps 4 and 6–8, and relevant CLI and eval code. Confirmed all four commit IDs in the local reflog; `git show` was unavailable. Static review; no evals run. #243, #249, and waived README regex gaps excluded.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The archive-only fallback names the wrong exit code.** The “Check fails to run” scenario (`specs/change-finish/spec.md:85–87`) and ship instructions (`skills/specwright-pr/SKILL.md:102`) cite exit 3 for unreadable commits. The native command returns exit 1 with `git_error`; `evals/review-routes/test_review_run.py:1619–1626` expects exactly that when the commits cannot be read in the selected repo. An agent following the skill can treat exit 1 as a stop rather than report the error and run `pr.validate`. State that the check runs only with a handed-off planning ready head, and that every nonzero result, including exit 1, is reported and falls back to normal validation.
2. **The undo amendment conflates the planner’s JSON with what finish shows.** `specs/change-finish/spec.md:40` calls `after_rerun_steps` optional in the JSON, but the retained main requirement (`openspec/specs/change-finish/spec.md:394–395`) requires both arrays, and `cli/lib/src/finish/undo_plan.dart:2357–2359` always emits them. Only *display* is conditional: on exit 0, finish shows each step’s `cwd` and `argv`, the after-rerun list if nonempty, and every warning (`skills/specwright-finish/SKILL.md:74`). Treating the JSON key as optional permits a producer to omit it and break consumers that index it directly. Separate the two contracts and make the success scenario assert the amended display.
3. **Step 4 still defines `orphans` in a way that can bypass the restored consent prompt.** `README.md:343–345` defines the field as installed `specwright-*` names with no downloaded counterpart. Lines 367–369 then ask about other entries, including pack skills such as `web-ux`, which do not match that definition but can be returned by `plan` (`cli/lib/src/update/packs.dart:1073–1077`). An agent that filters the list using the earlier definition can leave a retired pack skill installed without ever asking; Step 7 does not check it. Describe the full list at first use and scope the every-path rule to the core-skill subset.
4. **The test map credits planner tests with covering agent behavior.** `tasks.md:16–26` marks both finish reporting and archive-only ship validation green under `evals/finish/` as unchanged wording. Those tests exercise the undo planner, not the deferred-check display or ship’s validation decision. The existing display check is `test_finish_step0_runs_undo_plan_and_runs_nothing` in `evals/git-workflow/test_instructions.py:2068`; the archive-only classifier tests are in `evals/review-routes/test_review_run.py`, and do not prove which validation ship runs. As written, green planner and classifier tests can be mistaken for evidence that ship handles a moved code head or a classifier error correctly. Map the existing checks to what they prove, identify how the ship outcomes are verified, and record the user-approved display amendment in the design and task map rather than labeling it wording-only.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

CHANGES_APPLIED: yes

Align the archive-only fallback, undo JSON and display contracts, README orphan classification, and test map as described above.

## Rebuttals

- Round 7’s Step 8 warning finding is addressed: the delta requires the full probe, and the map separates interface-source wording from the matching-binary outcome.
- Round 7’s milestone finding is addressed: the roadmap points to the inventory, the five exceptions have issue IDs, and D1 identifies the README CI evidence.
- The Step 6 decline fix matches the delta: no mapping is written, and Step 7 passes without it.