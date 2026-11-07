# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 2 requested fail-closed Windows path conversion, grounding the usage-consumer claim, and correcting the process-cost baseline; all three fixes are present.
- **Reviewer:** OpenAI Codex / GPT-6.1, fresh review context
- **Reviewed:** Proposal, task-commits delta, design and every cited range; installed review instruction/template; architecture index; ADRs 0014, 0016, 0024, 0027 and 0028; main task-commits, user-tasks and native-cli specs; both commit scripts; VCS shim/resolver; CLI dispatcher, VCS command, args, codec, document and transport; commit/finish/PR callers; named evals, cited instruction/error assertions and eval workflow.
- **Verification limits:** Static inspection only. Runtime execution and Git tracking/symlink verification were unavailable.

## Findings

### Critical (blocking)

None.

### Moderate

**M3 — D9 rejects valid UNC conversion results.**

Location: `openspec/changes/native-cli-commit/design.md:99`, assumption A2 at line 125.

D9 treats output “that is not a drive-form path” as conversion failure. A valid absolute Windows path need not have a drive letter: UNC paths such as `//server/share/m.txt` are another absolute form.

[INFERENCE] A successful `cygpath -m` conversion returning that UNC form would therefore stop fitting or coverage with exit 2. This introduces a path restriction absent from the existing file checks (`fit-subject.sh:19-22`, `task-cover.sh:136-142`) and conflicts with the promised parity.

Accept validated absolute native paths, including UNC forms, while retaining the fail-closed behavior for genuinely failed conversions. Do not restore the unconverted-path fallback.

**Re-check: M3 fixed.** D9 accepts absolute drive and UNC results while rejecting non-zero, empty or non-absolute conversion output before file access or Git calls. A2 explicitly includes UNC form, and C7 retains the no-fallback invariant. The “UNC path on Windows” scenario requires successful fitting; “Path conversion fails on Windows” retains the failure and unchanged-file requirements.

D9 now includes explicit verification: conversion unit tests cover accepted UNC output alongside drive-form output and rejected non-zero, empty and relative output. A planned Windows-only test in `evals/git-workflow/test_fit_subject.py` exercises fitting through a UNC path, skipping when the administrative share is unreachable; a separate stub-induced conversion-failure test checks that neither file changes. This satisfies the requested design amendment; these tests were not executed for this re-check.

### Suggestions

None.

### Round-2 re-check

- **C1 fixed:** D9, C7 and the new failure scenario consistently require stopping before target-file access or Git calls when conversion fails.
- **M1 fixed:** A1 was removed; Context now cites the usage definition and consumer assertions. Those ranges support the claim.
- **M2 fixed:** The cost note now identifies direct Python-to-Git execution as the baseline and explicitly leaves the added transport cost unmeasured.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Amend D9 and A2 to distinguish valid absolute UNC output from malformed conversion output. Keep C7’s no-fallback invariant. Add a Windows UNC-path scenario and verification covering successful UNC conversion, alongside the existing conversion-failure scenario.

CHANGES_APPLIED: yes

## Rebuttals