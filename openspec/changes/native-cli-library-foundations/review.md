# Review

## Metadata

- **Round:** 4 — amendment recheck after apply drift; not a new full review.
- **Prior round:** Round 3 required-changes recheck accepted all ten changes, recording approval with changes applied. Those findings remain settled.
- **Reviewer:** Codex, fresh review context, read-only.
- **Reviewed:** Review instruction and template; amendment diff against `aed04d6`; relevant proposal, design, specs and tasks; `branchPattern` and its comment; mapped undo tests and finish/GitButler parity comparisons; ADRs 0027 and 0033.
- **Validation:** Source inspection only; no tests executed. Installed project skills: none.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The new scenario’s wrong-branch refusal is not covered by its test mapping or explicitly required by task 2.10.**

The scenario promises that the printed undo runs on the planned branch and refuses on another, for jj and GitButler.

The mapped Dart test, `the committed plan guards through vcs.sh and commits through it`, checks the GitButler script text (`cli/test/finish/undo_plan_test.dart:1299`). The mapped jj eval executes a successful undo (`evals/finish/test_undo_jj.py:106`). Neither executes the printed guard against a different branch.

The existing `test_undo_plan_jj_wrong_branch` checks planning-time refusal with a dirty working copy, rather than execution-time refusal of an already printed script. The parity comparisons normalize the guard text; they do not establish that refusal behavior.

Consequently, the mapped checks could pass without verifying the scenario’s negative outcome. Task 2.10 names the relevant test runs but does not require adding that assertion.

### Suggestions

None.

The remaining amendments are coherent:

- C2, D7, the approval note, proposal exception, native-cli exception and task 3.2 consistently recognize C12 and C13.
- C13 records the deliberate gap, reason, owner’s choice, retirement change and exactly one destination. The comment exists at `cli/lib/src/finish/undo_plan.dart:860`, immediately above `branchPattern`, and describes the implemented compact match.
- Task 2.10 carries the compact match, destination comment and narrowly documented parity difference.
- The new scenario has observable, assertable outcomes.
- The shortened pr-script-runtime requirement preserves argument compatibility, parsed output, exit status, settings behavior, reviewer-config guarantees, GitButler pinning and policy checks. Its reference to native-cli retains the exceptions previously enumerated; its scenarios lose no obligation.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Extend task 2.10 and the scenario’s test-map rows to require execution-time checks of the printed branch guard for both jj and GitButler. Exercise compact state documents naming the planned branch and a different branch; assert success for the former and nonzero refusal before undo mutations for the latter. These may use controlled state responses without requiring real backend installations. Name the added or extended cases in the map.

CHANGES_APPLIED: yes

Applied (author, 2026-11-10): task 2.10 now requires execution-time guard tests; `cli/test/finish/undo_plan_test.dart` adds "the printed guard runs on the planned branch and refuses another" (GitButler) and "the printed jj guard runs on the planned branch and refuses another" (jj), which run the printed `case` line against compact state documents for `feat/x` and `feat/y`; both are mapped in the test map. Both fail against the old spaced guard and pass against the compact one.

## Rebuttals

None.