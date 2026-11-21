# Review

## Metadata

- **Round:** 146
- **Prior round:** Round 145 returned APPROVE_WITH_CHANGES. This revision scopes the failed-replace guarantee, clarifies the pause and lock-release paths, and strengthens the retry and adoption test plans. The owner’s acceptance of #239 stands.
- **Reviewer:** cross-model CLI (omp)
- **Reviewed:** #227 amendment (FULL), PR runtime delta, group 6 and its test map, proposal and release notes, and the Dart and Python call sites. Static review only; the Windows baseline is as reported in the design.

## Findings

### Critical (blocking)

None. D3 and Flow & State Gaps accurately disclose #239: `publish` can roll back a readable record without the mutation lock, and `MoveFileExW` replaces by path. The retry repeats an operation already exposed to that interleaving; the rejected byte check would not make the replace conditional. No fix to #239 is required here.

### Moderate

1. **The concurrent-adoption scenario promises more than the existing adopter preserves.** The delta spec (lines 30–32) promises equality except for `owner` for any record with a valid current owner. `FeedbackPass.adopt` always sets `version: 2` and backfills a missing `written_at` from `owner.at` (`feedback_pass.dart:1316–1326`). A record like the one in `feedback_pass_test.dart:172–175` gains a field even with no concurrent publication. The stress fixture is narrower: `write_record` dispatches native `pass write`, which already sets both fields (`feedback_pass.dart:425–434`). Task 6.4’s equality check is correct for that fixture, not for the scenario as written.
2. **Resource Bounds still reads as a timeout.** The spec, decision table, Risks / Trade-offs and proposal S4 say *requested* pauses. Resource Bounds instead puts “100 ms of pauses at most” in the Timeout column, and A1 still says “20 ms apart” (`design.md:238,366`). The design limits attempts and requested delay, not elapsed time. T3 correctly checks the source after the pause, but the retry limit should count that check even when it prevents the next replace.
3. **Group 6 does not prove the production lock survives the pause.** Task 6.1 drives the store directly; 6.4 relies on real contention. Neither deterministically catches a caller that starts an asynchronous retry and returns without awaiting it. `adopt` currently calls a `void` `replaceRecord`, and `withLock` releases in `finally` when its body settles (`feedback_pass.dart:1327–1334`, `feedback_record.dart:85–93`). The `UnexpectedReplacement` test throws synchronously, so it does not cover that failure mode. If the pause yields, the caller must await replacement and cleanup inside `withLock`; the current Impact list and task 6.3 do not name that dependency.

### Suggestions

- The red/green split is sound: immediate source loss, off-Windows behavior and the single-attempt lock/publication boundaries are baseline-green; clearing a refusal, exhaustion, source loss during a pause and cleanup after exhaustion exercise new behavior. The reported 15 failures in 300 runs are valid baseline evidence for the stress row, not a deterministic red. In 6.4, use the captured exit statuses to check that the winner exits 0 and each loser exits 1.
- The ordinal folder name removes the collision without changing iteration order or frozen-oracle lookup (`test_parity.py:470–480`, `oracle_capture.py:181–192`). C6/C6b, proposal Impact and Release Notes keep the retry scoped to record replacement, not lock creation or publication.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Scope the concurrent-adoption scenario to the race the eval sets up: adopters of a freshly written native record, with no competing publication or deletion. Keep the full-record comparison in 6.4 and leave existing adoption normalization unchanged.
2. Align D3, A1 and Resource Bounds: at most six replace attempts, five requested 20 ms pauses and one source check after each pause. No wall-clock timeout. A missing source or failed check stops the loop without another replace and preserves the first replacement error.
3. Specify in 6.3 that `adopt` holds its lock through all attempts and temp cleanup. If replacement becomes asynchronous, update the caller and Impact list. Drive a refusal through `FeedbackPass.adopt` with the injected pause and verify a competing acquisition gets `record_busy` during that pause and that cleanup precedes the release attempt.

CHANGES_APPLIED: yes

## Rebuttals

Round 142’s four Moderate findings stay closed in the design. C10/D2 retain planner-only status stdout drain/discard and strict resume decoding; the finish delta retains the out-of-checkout GitButler probe and cleanup; C27 retains the ten-redirect limit and the planned no-twelfth-request assertion; D2 retains `text_result.dart` in the planned `finish` mapping. None is reopened.