# Review

## Metadata

- **Round:** 142
- **Prior round:** round 141 REVISE (1 Critical, omp), after rounds 1-140 REVISE; the owner asked for fixes and further rounds until approval
- **Reviewer:** cross-model CLI (omp)
- **Reviewed:** Proposal, design, round-141 review, five delta specs and their main specs, `openspec/architecture.md`, ADRs 0018, 0025, 0027, 0034 and 0040; cited CLI implementation, tests and fixtures under `cli/` and `evals/`; `evals/suites.json`, CI workflows, README and skill text. Static review; no runtime checks.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The first Git state read still has an eager decoding path in D2.** Skipping `status.names()` removes the strict decode that caused round 141’s refusal. But D2 says the forwarded read still goes through `runText`, which captures all of stdout and eagerly builds replacement-decoded text (`cli/lib/src/vcs/scripts.dart:14-22`, `cli/lib/src/vcs/git_backend.dart:63-75`). The planner uses none of that stdout. A large unrelated work tree can therefore still make the exit-only read retain and decode a repository-wide status listing before the streamed member filter runs. D2 also still says the first read will reject the resume fixture’s invalid name, which is no longer true under C10.
2. **The planner’s no-write requirement omits the GitButler probe’s temporary directory.** The modified `change-finish` requirement allows writes only for jj synchronization. The retained GitButler probe creates `swb-probe-*` to run `but --version` outside the checkout and deletes it in `finally` (`cli/lib/src/vcs/probe.dart:147-154`). A missing or unwritable temp root can stop planning, and a killed planner can leave the directory behind, even though the checkout is unchanged.
3. **D8 does not carry forward the separate redirect-count bound.** The downloader follows at most ten redirects and then reports `download_failed` with `too many redirects` (`cli/lib/src/update/download.dart:14,95-112`). The rewritten loop describes byte and time budgets but omits the hop limit. Empty redirect responses consume no body budget, so dropping the counter would turn an immediate, named refusal into repeated requests until the deadline.
4. **The finish test map omits the strict name-result adapter.** D2 maps the runner and codec to `finish` but not `cli/lib/src/vcs/text_result.dart`. `gitRoot` and `gitCurrent` call `TextResult.names()` for the checkout and branch names (`cli/lib/src/vcs/probe.dart:55-63`, `cli/lib/src/vcs/git_backend.dart:51-61`). If that method regresses to returning replacement-decoded text, a change confined to this already-covered file will not select the finish outcome tests under `evals/run.py --changed` (`evals/run.py:385-410`).

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In D2 and C10, specify that the planner-only Git state status drains and discards stdout without buffering or decoding it, bypassing `runText` for that call. Preserve `git_error` on failed status and leave standalone `sw vcs state` unchanged. Replace D2’s obsolete resume-fixture rationale: the real CLI fixture now exercises strict decoding in the resume status read itself.
2. In the modified `change-finish` read-only requirement and its D2 documentation, state that planning does not write repository state except for jj’s existing snapshot and import. Explicitly retain the out-of-checkout GitButler probe directory and its existing cleanup.
3. In D8 and C27, retain the ten-redirect limit and its `download_failed` result. Keep the existing redirect-loop regression and make it assert that the eleventh redirect is refused without a twelfth request.
4. Add `cli/lib/src/vcs/text_result.dart` to D2’s planned `finish` mapping in `evals/suites.json`.

CHANGES_APPLIED: yes

## Rebuttals

Round 141’s blocking case is addressed in the design: C10 bypasses strict decoding in the first Git state read, and the revised Linux fixture places the invalid-byte filename beside a tracked file and verifies that Git actually reports the byte. Strict decoding remains required for resume reports and retained carried-edits records. Finding 1 concerns the remaining eager replacement decode and buffering, not the accepted raw-first filter.