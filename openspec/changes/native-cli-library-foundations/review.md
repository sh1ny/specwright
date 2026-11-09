# Review

## Metadata

- **Round:** 2
- **Prior round:** REVISE — file-input bound, BigInt producers, and carried path constraints.
- **Reviewer:** Codex
- **Reviewed:** Proposal, design, five delta specs, proposed ADR 0033, architecture, ADRs 0014/0027–0030, M8 roadmap, and cited tracked source ranges. No files modified.

## Findings

### Critical (blocking)

None.

### Moderate

**1. D8 still omits numbered headings as an integer producer.**

D8 specifies oversized task IDs, commit subjects and trailers, but not headings. [`parseTasks`](cli/lib/src/commit/task_cover.dart:627) independently inserts heading numbers as `BigInt` keys. [`groupIds`](cli/lib/src/commit/task_cover.dart:308) includes those keys even without matching tasks, and the output emits them as numeric `groups[].group` values.

Consequently, a file containing `## 99999999999999999999. Heading` can still reach the replacement encoder with an unsupported integer and return `internal_error`, losing the entire coverage report. Filtering oversized task lines does not prevent this.

The round-1 BigInt finding is therefore only partially resolved. The file-size bound and C8/C9 address the other two round-1 findings.

### Suggestions

None.

## Verdict

Approve with the exact changes below.

## Required Changes

1. Extend D8 and its producer table to cover numbered headings explicitly: ignore headings whose group number exceeds signed 64-bit range before inserting them into `ParsedTasks.headings`. Include this rule in C11’s destination requirement and the task-commits contract’s exceptions.
2. Add a task-commits scenario containing an oversized heading alongside an ordinary task. Assert that the oversized group is absent, the ordinary task retains its coverage result, and the command emits its normal report rather than `internal_error`.

## Rebuttals

None.

VERDICT: APPROVE_WITH_CHANGES
CHANGES_APPLIED: yes