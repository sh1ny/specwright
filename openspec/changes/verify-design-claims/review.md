# Review

## Metadata

- **Round:** 1 (second re-check run)
- **Prior round:** Round 1 returned APPROVE_WITH_CHANGES. The first re-check found M2 fixed and M1 open only for an explicit wording-test commitment.
- **Reviewer:** fresh-context Codex reviewer
- **Reviewed:** Round 1 review; `verify-design-claims` design.md, proposal.md and specs/design-grounding/spec.md; schemas/specwright/schema.yaml:285,394–398,585–586; schemas/specwright/templates/design.md:42; openspec/architecture.md ADR index.
- **Scope:** Re-check of the two Required Changes only.
- **Installed project skills:** none.

## Findings

### Critical (blocking)

None introduced by the required fixes.

### Moderate

**M1 — Conflicting LIGHT instructions: fixed.**

D1 explicitly places `## Assumptions` after the Decision summary and above the template’s LIGHT deletion boundary, and changes the schema’s LIGHT section list to include Assumptions (`design.md:30`).

The new **Tested by** entry (`design.md:31`) explicitly commits to wording tests in `evals/git-workflow/test_design_grounding.py` covering both conditions: section placement above the deletion boundary and inclusion of Assumptions in the schema’s LIGHT section list. This satisfies the remaining requirement. Test implementation belongs to apply; it is not required at this design-review gate.

**M2 — Missing ADR commitment for the binding artifact contract: fixed.**

D1 commits to ADR 0025 in the first task group, with its architecture-index row (`design.md:32`). The ADR section lists it under **To record during apply**, covering the Assumptions format, identifiers, FULL-review and LIGHT-re-check consumers, and verify-first tasks (`design.md:163`). This satisfies the ADR recording and ordering requirements in `schema.yaml:394–398,585–586`.

### Suggestions

- **S1 — Historical ADR attribution: fixed in the prior revision; carried forward.** The design identifies 0005 as superseded and names 0007 as the in-force constraint.
- **S2 — Overstated recovery guarantee: fixed in the prior revision; carried forward.** The design describes skipped citation checking as residual risk with no assured recovery.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

Both Required Changes are applied at the design level. No required item remains open.

## Required Changes

1. **Applied:** Specify LIGHT-safe Assumptions placement, update the LIGHT section list, and explicitly commit to wording tests covering both.
2. **Applied:** Commit to an ADR for the Assumptions contract and its consumers, written in the first task group with the architecture-index update.

CHANGES_APPLIED: yes

## Rebuttals

- **M1:** Author’s fix accepted by reviewer; D1 now includes the previously missing explicit wording-test commitment.
- **M2:** Author’s fix accepted by reviewer; the ADR scope, first-task-group placement and architecture-index update remain explicit.
- No outstanding rebuttals.