# Spec Delta

## MODIFIED Requirements

### Requirement: Design review verdict values are checked
A design review's `VERDICT:` value SHALL be `APPROVE`, `APPROVE_WITH_CHANGES` or `REVISE`, and its `CHANGES_APPLIED:` value SHALL be `no` or `yes` after `APPROVE_WITH_CHANGES` and `n/a` after any other verdict. Any other value SHALL fail validation, naming the value. The verdicts the author or the user records (`USER_OVERRIDE`, `SKIPPED_LIGHT`, `DEFERRED`, `WAIVED`) are among the refused values.

#### Scenario: Design review that could not review
- **WHEN** a codex design review prints `VERDICT: BLOCKED` and `CHANGES_APPLIED: n/a`, and the change's `review.md` holds an earlier valid review
- **THEN** the run exits 3 with `status: invalid` and an error naming `BLOCKED`, `review.md` is byte-identical to before, and no other route runs

#### Scenario: Verdict a reviewer may not set
- **WHEN** a reviewer CLI or the subagent returns `VERDICT: USER_OVERRIDE`, `VERDICT: SKIPPED_LIGHT`, `VERDICT: DEFERRED` or `VERDICT: WAIVED`
- **THEN** validation exits non-zero with `status: invalid` naming the value, and no review file is written by the run

#### Scenario: CHANGES_APPLIED does not match the verdict
- **WHEN** a design review returns `VERDICT: APPROVE` with `CHANGES_APPLIED: yes`, or `VERDICT: REVISE` with `CHANGES_APPLIED: none`
- **THEN** validation exits non-zero with `status: invalid` naming the value

#### Scenario: Valid re-check
- **WHEN** a reviewer's re-check run returns `VERDICT: APPROVE_WITH_CHANGES` with `CHANGES_APPLIED: yes`
- **THEN** the run exits 0 and writes `review.md`
