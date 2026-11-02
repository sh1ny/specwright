# Review

## Metadata

- **Round:** 4
- **Prior round:** Round 3 was APPROVE_WITH_CHANGES with 0 Critical, 3 Moderate (M1: the archive wait's "rest of `pr.settle`" timeout fell outside "Watch waits for attention"; M2: a bad `pr.settle` and `too_many_reviewers` still made `context` exit 2 and blocked ship, finish and cleanup; M3: "Looser rules at the archive decision" contradicted the main pr-merge requirement "Agent mode archives before merging without asking") and 1 Suggestion. It set three Required Changes. The author's Rebuttals list all three as applied with no rebuttal.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Agent SDK harness)
- **Scope:** Required Changes re-check only. Each of the three round-3 Required Changes was checked against proposal.md, design.md and specs/{pr-evidence,pr-watch,pr-merge,change-finish}/spec.md. The review also checked whether the edits created contradictions between those artifacts or with the main specs openspec/specs/{pr-evidence,pr-watch,pr-merge,change-finish}/spec.md. The rest of the design was not reviewed again.
- **Reviewed:** openspec/changes/generic-reviewer-detection/{review.md (round 3), proposal.md, design.md, specs/pr-evidence/spec.md, specs/pr-watch/spec.md, specs/pr-merge/spec.md, specs/change-finish/spec.md}; main specs openspec/specs/{pr-merge, pr-watch, pr-evidence, change-finish}/spec.md. Installed project skills: none named.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

Round-3 Required Changes:
- **RC1 (M1): applied.** pr-watch MODIFIED "Watch waits for attention" now says: "An archive head under 'An archive-only head needs no further quiet window' SHALL first wait for the rest of `pr.settle` since its push." The scenario "Watch's wait command" names `--timeout 1800`, `--timeout <pr.settle in seconds>` and the archive head's `--timeout <rest of pr.settle since the push>`, "with the condition for each", and the skill-text test fails if any is missing. This agrees with the archive requirement ("timeout: the rest of `pr.settle`, then 1800"), D7 and the archive sequence diagram. The rule that any `timeout` wake counts as the quiet window does not conflict with the archive rule, which needs no further quiet window.
- **RC2 (M2): applied.** D5 says a bad `pr.settle` and `too_many_reviewers` are reported as `settings_problem` naming the key, and `policy` keeps exiting 2. D6 says a bad value is a `settings_problem` in `context` (watch starts no wait) and exit 2 `bad_setting` in `policy`. The Resource Bounds row "Reviewers per set" gives `context` printing `settings_problem` and `policy` exiting 2 `too_many_reviewers`. The scenario "Bad settle value" now reads "`pr-pair.sh context` prints `settings_problem` naming `pr.settle`, and watch starts no wait". This agrees with pr-evidence "Reviewer settings are read strictly everywhere", where ship, finish and cleanup ignore `settings_problem`. No remaining artifact has `context` exit 2 on settings.
- **RC3 (M3): applied.** The pr-merge delta adds MODIFIED "Agent mode archives before merging without asking". It keeps the main requirement text and adds: "When `policy` reports `rules_mismatch` for main's set at that decision, watch SHALL archive nothing, ask nothing, and wait on the ready head with main's reviewer config." Its three main-spec scenarios ("Ready change, not archived", "Archive fails", "Branch-only agent mode asks first") are carried over unchanged. "Looser rules at the archive decision" now sits under this requirement. The "Otherwise ... keep asking" clause lists only `user`, a differing policy or an unknown policy, so it no longer covers the mismatch case. "Required reviewers are those of the authorizing set" still carries all four of its main-spec scenarios. The design's Failure table row "Archive rules mismatch" matches.

The edits create no new contradiction between the change's artifacts or with the main specs they touch.

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

All three round-3 Required Changes are applied correctly and completely, and no new contradiction was found.

VERDICT: APPROVE

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

