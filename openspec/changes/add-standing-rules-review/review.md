# Review

## Metadata

- **Round:** 9
- **Prior round:** Round 8 confirmed two amendments to the earlier design. The owner then reopened review for scope cut 2.
- **Reviewer:** Codex, independent read-only reviewer
- **Reviewed:** The live proposal, design, review, tasks, both spec deltas, ADR 0044, the schema checklist and review template, and the requested diffs against `1154e6f2` and `main`. No installed project skills were declared. Verification was by source inspection.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The review template still gives the old change-design override instruction.** The schema, spec delta, and README make existing change-design overrides historical and reserve the two-`REVISE` escalation for roadmap baseline review. The template still presents that escalation as the unqualified condition for writing `USER_OVERRIDE`. An author following the shared template can record a new override that the unchanged tasks precheck will accept. [Review template](schemas/specwright/templates/review.md#L25) · [Checkpoint instructions](schemas/specwright/schema.yaml#L562) · [Tasks precheck](schemas/specwright/schema.yaml#L615)
2. **The legacy-override scenario is marked green without checking the behavior it specifies.** The mapped eval checks that the schema forbids checkpoint-created overrides and that the tasks precheck mentions the verdict. It does not check that apply still recognizes a stored legacy override. The green row therefore overstates coverage of the compatibility path the cut restores. [Test map](openspec/changes/add-standing-rules-review/tasks.md#L7) · [Mapped eval](evals/git-workflow/test_instructions.py#L1990)

### Suggestions

None. The requested diffs show the removal of locks, snapshots, fingerprints, freshness checks, extra views, and the new tasks/apply guards. The remaining runtime changes deliver committed standing rules and checkpoint progress for FULL change design, with the existing conditional confirmation and Release Notes exemption in place.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In the review template’s verdict comment, replace the unqualified two-`REVISE` override instruction with wording that preserves existing change-design overrides and limits new overrides under that escalation rule to roadmap baseline review. Keep the allowed verdict values and line grammar.
2. Update the legacy-override test-map row to cite evidence for both tasks and apply recognition of a stored override. If existing evals cover only the instruction text, label that evidence as such and leave the uncovered behavior unverified.

CHANGES_APPLIED: no

## Rebuttals

None.

## Owner checkpoints

- **Round 3:** `scoped-pass` — “one more scoped design pass on the six open findings, with no change in product scope.”
- **Round 4:** `scoped-pass` — “one more scoped pass on the three open findings, with no change in product scope.”
- **Rounds 5–6:** The reviewer issued `APPROVE_WITH_CHANGES` in round 5, and the independent round-6 recheck confirmed the amendments to the refusal and diagnostic contract under the previous design.
- **After round 6:** `scope-change` (owner; superseded the earlier approval for the revised design) — “Pre-ship kept finding holes in the review-capture tracking; incremental rechecks were never part of the brief (delta-only rounds were rejected by the experiment). Design review keeps today's behaviour: every round is a full review, and any later edit voids a pass.” Round 7 reviewed the removal and resulting text.
- **After round 8:** `scope-change` (owner; suspends round 8's disposition for the revised design) — “fix rounds were creating new bugs in gating that the brief never asked for”. Scope: standing rules and the owner checkpoint only; review the removal and resulting contract once.