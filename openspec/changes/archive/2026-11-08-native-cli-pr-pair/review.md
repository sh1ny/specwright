# Review

## Metadata

- **Round:** 5
- **Prior round:** Round 5 approved with changes; this re-check verifies only its two Required Changes.
- **Reviewer:** fresh-context reviewer (Codex harness)
- **Reviewed:** Tracked Round 5 review, proposal and runtime delta, compared with the main `pr-script-runtime` spec. No files modified.

This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal’s `## Release Notes` section) voids it.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The acceptance scenarios still forbid assertion changes that D11 explicitly permits.**

Proposal S3 and the runtime delta’s “Unchanged black-box evals pass on sw” and “Unchanged evaluator tests” scenarios allow assertion changes only for the format migration. Proposal What Changes additionally permits regex changes, but still omits message assertions.

D8 and D11 expressly require changing free-text assertions to compare prefixes. This matters for existing tests: `evals/pr-pair/test_pr_pair.py:440` compares the entire `message` value.

Following D11 can therefore violate the stated acceptance scenarios. Add the message-parity exception consistently without relaxing other fields.

**M2. The main snapshot contract still requires exact evaluator messages and output bytes.**

The main `pr-script-runtime` requirement “sw pr snapshot and sw pr reply keep the scripts’ contracts” requires identical stdout bytes and stderr messages, with unchanged assertions.

The new delta permits reworded `reviewers.py:` diagnostics, which snapshot passes through (`cli/lib/src/pr/snapshot.dart:185-196`, `433-466`). Format 2 also changes the snapshot’s `reviewer_config` digest. Neither exception is applied to that existing requirement.

Consequently, a snapshot following D10 and D11 violates an unchanged main-spec contract. The new evaluator requirements do not explicitly resolve that conflict.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Update proposal What Changes and S3, and both unchanged-eval scenarios in the runtime delta, to permit the D11 free-text assertion changes alongside the existing regex and format exceptions. Require exact comparison of all remaining fields, codes and statuses.
2. Add a modified delta for “sw pr snapshot and sw pr reply keep the scripts’ contracts,” including its unchanged-eval scenario. Explicitly permit format-derived reviewer-config digest differences and reworded evaluator diagnostics relayed by snapshot under D11. Preserve the existing contracts for unrelated snapshot output and reply behavior.

CHANGES_APPLIED: yes

## Rebuttals

1. **M1 — Fixed; accepted by reviewer.** [What Changes](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/proposal.md:18) and [S3](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/proposal.md:66) now permit prefix comparisons for message text alongside the regex and format exceptions. What Changes explicitly preserves exact comparison of every other field, code and status. Both runtime scenarios now state the same exceptions and exact-comparison rule: [subcommand evals](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/specs/pr-script-runtime/spec.md:44) and [evaluator tests](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/specs/pr-script-runtime/spec.md:70).

2. **M2 — Fixed; accepted by reviewer.** The [MODIFIED requirement](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/specs/pr-script-runtime/spec.md:93) retains the [main contract](F:/Dev/specwright/openspec/specs/pr-script-runtime/spec.md:169), adding only snapshot-specific exceptions for the format 2 `reviewer_config` digest and reworded relayed `reviewers.py:` lines with preserved prefixes. Its [unchanged-eval scenario](F:/Dev/specwright/openspec/changes/native-cli-pr-pair/specs/pr-script-runtime/spec.md:96) permits those exceptions while preserving every other stdout byte, stderr byte and exit status. The stale-revision and removed-flag scenarios remain intact, and reply behavior receives no exception.