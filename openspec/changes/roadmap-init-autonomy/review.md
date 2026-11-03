# Review

## Metadata

- **Round:** 2, re-check
- **Prior round:** Round 2 APPROVE_WITH_CHANGES; two Required Changes outstanding.
- **Reviewer:** Codex, read-only re-check.
- **Reviewed:** Commit `0b60e86`; current change’s `specs/project-planning/spec.md` owner-gate requirement and scenarios; `design.md` D5, summary row and Failure & Visibility table; `tasks.md` rows 20 and 38 and tasks 4.1–4.2. Context: roadmap skill close steps 2–4.
- **Scope:** Only round 2’s two Required Changes. Planning artifacts assessed; task group 4 implementation remains future work. No files edited.

## Findings

### Critical (blocking)

None.

### Moderate

Retained as the record of round 2:

1. **The owner-gate requirement prohibits actions even after owner approval.**  
   The requirement unconditionally prohibited writing a `Split agreed` line, applying an agreed-split amendment and enabling a pack, conflicting with owner-approved interactive actions.

2. **An autonomous close that stops before promotion has no defined path to persist its required pending row.**  
   D5 and the scenario required a pending row before the close branch existed, conflicting with the prohibition on writing before branch creation.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. Qualify the split-line, split-amendment and pack-enablement prohibitions as actions forbidden **without explicit owner agreement**. Preserve the prohibition on the agent supplying that agreement itself. Add an interactive approval scenario and map its verification to an implementation task.

2. Define the persistence procedure for a close that must record summary rows and then stop before promotion: create/check the appropriate docs branch before writing, preserve Now unchanged, and specify how the summary-only result is committed or resumed. Add a failure scenario asserting the pending row survives, main stays clean, and the milestone is not moved; map it to an implementation task.

CHANGES_APPLIED: yes

## Rebuttals

1. **Fixed — accepted by reviewer.** The requirement now prohibits the agent from supplying owner agreement and qualifies the actions with “Without the owner's explicit agreement.” D5 explicitly permits owner-approved interactive actions. “Owner agrees in an interactive run” verifies pack enablement after approval; test-map row 38 and tasks 4.1–4.2 cover verification and implementation.

2. **Alternative resolution — accepted by reviewer.** The owner chose report-only handling instead of a persisted pending row. The requirement explicitly exempts stops before branch creation from writing. The revised unverified-criterion scenario asserts no branch, no file writes, clean main, Now unchanged, reporting the criterion and rediscovery on the next close. D5, its summary row and the Failure & Visibility table agree. Row 20 and tasks 4.1–4.2 map the behavior to verification and implementation. This removes the contradictory persistence obligation and resolves the finding.