# Review

## Metadata

- **Round:** 6 (re-check)
- **Prior round:** Round 6 ended APPROVE_WITH_CHANGES with three Required Changes.
- **Reviewer:** cross-model CLI (codex)
- **Reviewed:** Only the three Required Changes against the current uncommitted planning artifacts: design.md D5/C6, pr-merge and pr-script-runtime delta specs, and tasks.md’s test map and task 3.3. Checked the change-directory diff and cited review/release coercions. No files written.

## Findings

### Critical (blocking)

None.

### Moderate

1. **Resolved — D5 incorrectly assumes review and release already reject malformed sections.**

   D5 now explicitly identifies the existing coercions and requires review and release consumers to reject present, non-null, non-mapping sections with `bad_settings`, exit 1, naming the key. It covers `review`, `release` and release’s `pr`, preserves absent/null defaults, and requires refusal before reviewer probing, git calls or release writes. C6 includes review and release.

   Task 3.3 explicitly replaces both coercions. The delta spec and test map cover block lists, flow lists, scalars and empty strings for these sections.

### Suggestions

1. **Resolved — Repair three requirement-to-scenario mappings.**

   “A duplicate key in a reviewer,” “An alias” and “A block sequence” are under “Settings constructs a settings file never needs are refused,” matching their test-map rows. “A flow list in a message” is under the shape requirement, also matching its row.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

All three Required Changes are applied to the planning artifacts. This re-check confirms the planning amendments; implementation and test execution remain pending.

## Required Changes

1. **Applied.** D5 and C6 cover review/release shape validation, correct the existing-check claim, and preserve absent/null defaults with the required error and exit status.
2. **Applied.** Task 3.3 replaces `_reviewSection` and release `_section`; mapped scenarios cover all requested malformed forms for `review`, `release` and release’s `pr`, with refusal before probes or git calls.
3. **Applied.** All three misplaced scenarios now sit beneath the constructs requirement and match their existing test-map rows.

CHANGES_APPLIED: yes

## Rebuttals

- Required Change 1: fixed. D5 now covers `review`, `release` and `pr` as release reads them, and cites the coercions at `cli/lib/src/review/settings.dart:55-59` and `cli/lib/src/release/settings.dart:159-160`. The claim that they already stop is gone. Review and release stop with `bad_settings`, exit 1, naming the key, and absent or null keeps its default. C6 names review and release. **Accepted by reviewer.**
- Required Change 2: fixed. Task 3.3 replaces `_reviewSection` and release `_section`. Two new scenarios, "A review section that is not a mapping" and "A release or pr section that is not a mapping", cover block and flow lists, scalars and `''`, and assert the stop before any probe or git call. Both have mapped tests. **Accepted by reviewer.**
- Required Change 3: fixed. "A duplicate key in a reviewer", "An alias" and "A block sequence" are back under the constructs requirement. "A flow list in a message" now sits under the shape requirement, and its test-map row names that requirement. **Accepted by reviewer.**