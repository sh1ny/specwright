# Review

## Metadata

- **Round:** 8
- **Prior round:** Round 7 required two scenario wording changes after the owner narrowed the scope.
- **Reviewer:** Codex, independent read-only confirmation (0.171.0, Windows job isolation)
- **Reviewed:** Round 7 Required Changes, both live spec deltas, and the relevant accepted text in `design.md`. Confirmation was limited to this change's prior-authoring workflow.

## Findings

### Critical (blocking)

None.

### Moderate

None outstanding.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Confirmed. “A reason alone does not restart the budget” refuses a review if the proposal, design and spec deltas are unchanged. It no longer exempts Release Notes, and the separate Release Notes scenario still requires a full review.
2. Confirmed. “A design input changes during an authorized pass” predicates refusal on different live planning digests at dispatch and publication; the previous report and scoped permission remain intact.

CHANGES_APPLIED: yes

## Rebuttals

None.

## Owner checkpoints

- **Round 3:** `scoped-pass` — “one more scoped design pass on the six open findings, with no change in product scope.”
- **Round 4:** `scoped-pass` — “one more scoped pass on the three open findings, with no change in product scope.”
- **Rounds 5–6:** The reviewer issued `APPROVE_WITH_CHANGES` in round 5, and the independent round-6 recheck confirmed the amendments to the refusal and diagnostic contract under the previous design.
- **After round 6:** `scope-change` (owner; superseded the earlier approval for the revised design) — “Pre-ship kept finding holes in the review-capture tracking; incremental rechecks were never part of the brief (delta-only rounds were rejected by the experiment). Design review keeps today's behaviour: every round is a full review, and any later edit voids a pass.” Round 7 reviewed the removal and resulting text.