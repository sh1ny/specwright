# Review

## Metadata

- **Round:** 2 (re-check of round 1's required changes)
- **Prior round:** Round 1: APPROVE_WITH_CHANGES. RC1: a cut-off tag push read-back must keep the tag_conflict and tag_mismatch guards. RC2: the #114 scenarios must fail on today's code and pass reliably on Windows. Suggestions S1-S5.
- **Reviewer:** fresh-context subagent (Claude Code)
- **Reviewed:** 2026-10-26. openspec/changes/fix-m4-gaps/review.md (round 1), proposal.md, design.md (D1, D2, D3, D5, D8, D9, Failure & Visibility), specs/{change-finish,install-update,pr-descriptions,pr-script-runtime,releases,review-routes}/spec.md; source skills/specwright-pr/scripts/bounded.py (resolve, _spawn, _piped loop), skills/specwright-review/scripts/review-run.sh (capture loop and copy readers, make_receipt, fail), skills/specwright-release/scripts/release.sh (cmd_publish tag guards ~1385-1440, tag_push_failed), scripts/update.sh (highest_tag, its call site), evals/update/fixtures.py (make_mini_download), evals/fakes/reviewcli.py (the LINGER child). Scope: round 1's Required Changes, plus whether the S1-S5 edits introduce a defect.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

None.

**RC1: applied.** The releases requirement "A cut-off tag push or release creation is decided by a read-back" now says that a pushed tag counts as done only when origin's tag is the local tag object at the release commit, "else the tag conflict or mismatch stop applies". The requirement has the two scenarios the author named. "Push cut off while another clone's tag won" expects `tag_mismatch` naming both tag objects, with no GitHub release. "Push cut off with origin's tag on another commit" expects `tag_conflict` naming both commits, with no GitHub release. The existing stops already name both values (release.sh:1394 `tag_commit`/`release_commit`, 1404 `local_object`/`remote_object`) and exit 1 by default, so both THENs can be asserted. D5 matches: "The push counts as done only when origin's tag is the local tag object at the release commit", with the same two stops and no GitHub release. The release body is therefore origin's tag again, as the header of release.sh promises.

**RC2: applied.**
- `bounded.py` (pr-script-runtime "Exit just before the deadline with a held pipe"): the eval uses a 3 s deadline, `SPECWRIGHT_TEST_POLL` set to 5 s, and an exit at the test's start + 2 s. In today's `_piped` the readers set `over` only on a bound (bounded.py:146-148), so EOF never wakes the loop. With the interval raised, `over.wait(min(POLL, left))` sleeps until the deadline. It then first sees the exit at or after `end` and reports `deadline_exceeded`, so the eval is red once only the hook is in place. With the watcher, the exit is recorded at about start + 2 s, which is before `end`, so the run keeps status 0. The author's note is right that the red step needs the hook first. That is the option round 1 offered, so it is accepted.
- `capture` (review-routes "Exit in the last poll interval with a held pipe"): the eval uses a 5 s timeout, a 10 s interval and an exit at the test's start + 4 s. In today's code the copy readers set `wake` only on a bound or on EOF (review-run.sh:376, 383). The existing LINGER child is a plain `Popen` that inherits both stdout and stderr (reviewcli.py:110), so neither stream reaches EOF. The old loop then sleeps until the deadline and reports `timeout`, so the eval is red. With the watcher it reports `held`, which is `status: failed`.
- The timing is now robust on Windows. The exit time is absolute and taken before the run starts, and both runners set their deadline after spawn, so the real deadline is at least the test's start plus the timeout. Even if start-up is slow and the fake exits as soon as it starts, its exit still falls before that deadline. Both WHENs state the timing. The recorded-exit-before-deadline check is assertable against the test's start plus the timeout, which is a lower bound on the deadline. In pr-script-runtime the check is in the THEN; in review-routes it is a condition in the WHEN. Both forms can be asserted.

### Suggestions

**S1-S5 edits: addressed, with no new defect found.**
- **S1:** D3 gives `_piped` its own `wake` event, and `over` keeps meaning only "a stream passed its bound".
- **S2:** D5 loads `bounded.py` lazily in `highest_tag`, which runs only at the `store_version` refusal (update.sh:1708), with a deadline of `min(60, resolve()'s deadline)`. A missing file becomes that refusal's reason. The failure table has a row for this case. `make_mini_download` (fixtures.py:134-142) is unaffected.
- **S3:** The releases MODIFIED requirement and D9 state the rule for an unreadable judged-against version: greater than each version it matched, and a parent with no semver counts every matched version as greater.
- **S4:** Both "stopped on every platform" requirements now name the reporting of the fallback (a stderr line; `process_group: none` in the receipt), and each has a `SPECWRIGHT_TEST_NO_JOB` scenario. The receipt is already extended with optional keys (`windows_sandbox`, review-run.sh:1003-1004), and failing runs carry a receipt (`fail`, 1008-1009), so the timeout scenario can be asserted.
- **S5:** The change-finish requirement and D8 check `test ! -e <spec>` before any `openspec archive`, with the scenario "Spec recreated before the after-rerun script".

**R2-S1. A sentence in D1 is left over from before the S2 edit.** D1 still says "`update.sh` loads `<download>/skills/specwright-pr/scripts/bounded.py` ... and a missing file is a refusal before any write". Read alone, this suggests a plan-wide check, which would refuse every mini-download eval. D5 and the failure table now say the opposite: the module is loaded lazily, and a missing file is only the reason inside the `store_version` refusal. Change D1 to point to D5, for example: "loads it lazily for the tag lookup only (D5)". This is not blocking, because D5 is specific and the update evals would catch a plan-wide check.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (Round 1, RC1) Read-back after a cut-off tag push keeps the tag_conflict and tag_mismatch stops: applied in the releases spec (requirement text and two new scenarios) and in D5.
2. (Round 1, RC2) The #114 scenarios fail on today's code once the test hook exists, and pass reliably on Windows: applied in pr-script-runtime and review-routes (the `SPECWRIGHT_TEST_POLL` hook, an absolute exit time 1 s before a deadline measured from before the run starts, and an assertion that the exit came first) and in D3.

CHANGES_APPLIED: yes

## Rebuttals
