# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 APPROVE_WITH_CHANGES; mode record moved to proposal.md and user choices protected in autonomous mode; both changes accepted.
- **Reviewer:** cross-model CLI (codex)
- **Reviewed:** openspec/changes/decision-making/proposal.md; openspec/changes/decision-making/specs/decision-making/spec.md; openspec/changes/decision-making/design.md; openspec/changes/decision-making/tasks.md; schemas/specwright/schema.yaml; schemas/specwright/templates/review.md; schemas/specwright/templates/design.md; templates/openspec/specwright.yaml; skills/specwright-commit/SKILL.md; openspec/architecture.md; docs/adr/0001-build-on-unmodified-openspec.md; docs/adr/0002-agent-instructions-with-thin-deterministic-scripts.md; README.md settings block.
- **Re-check:** Required Changes only, against the current proposal.md, specs/decision-making/spec.md, design.md and review.md in openspec/changes/decision-making/. Both changes are accepted within this scope. Task edits and test-map updates reported in the Rebuttals were not independently re-checked.

## Findings

### Critical (blocking)

None.

### Moderate

1. **The question flow does not accommodate smaller tool limits or tools unavailable in the current mode.** The spec’s “Harness with an ask tool” scenario requires six decisions to use batches of exactly 4 and 2. Codex’s `request_user_input` tool exposed in this session accepts at most three questions, with 2–3 options each, and is restricted to Plan mode. Design D5 and task 3.2 instead prescribe up to four substantive options plus discuss, and allow plain text only when the harness has no tool.

   Consequently, the specified four-question call cannot execute on this supported interface; some permitted option sets cannot fit either. Outside Plan mode, the harness possesses the tool but cannot use it, leaving the fallback condition unsatisfied. The instructions need to distinguish a usable tool from one merely present and adapt batches and options to its limits.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. In proposal What Changes, the spec requirement “Decisions go to the user per the mode,” design Context/D5/Resource Bounds, and task 3.2, specify that four is the maximum batch size, further reduced to the usable ask tool’s question limit. Fit options within its supported limit while retaining a recommendation and a discuss path. Permit plain text when no ask tool is usable in the current session or mode.
2. Replace the universal 4-and-2 scenario with a capacity-aware outcome. Add edge scenarios covering a three-question tool limit, a smaller option limit, and an ask tool unavailable in the current mode. Update tasks group 3’s test map and checks accordingly.

CHANGES_APPLIED: yes

## Rebuttals

1. Fixed. The batch is at most 4, or the usable ask tool's lower question limit. Options are cut to the tool's option limit, always keeping the recommended one and a way to discuss (the tool's free-text answer, else a discuss option). Plain text is the fallback when no ask tool is usable in the current session or mode. Changed in: proposal What Changes; the spec requirement "Decisions go to the user per the mode" (its description); design Context (Claude Code and Codex limits), D5 (choice and rejected) and Resource Bounds; task 3.2.

   **accepted by reviewer** — The proposal, spec requirement and design now cap batches at four or the usable tool’s lower question limit. They require options to fit the tool’s limit while preserving the recommendation and a discuss path. D5 explicitly permits discussion through free text or a dedicated option, and permits plain-text questions when no ask tool is usable in the current session or mode. Context records the differing harness limits, and Resource Bounds carries the adaptive bounds. Task 3.2 was outside this re-check’s specified file scope.

2. Fixed. The 4-and-2 scenario is replaced by "Ask tool that takes four questions" (batches of at most 4). New scenarios: "Ask tool that takes three questions", "Ask tool with a smaller option limit", "Ask tool not usable in the current mode", and "Harness without an ask tool". Test map rows 13-21 and the task 3.1/3.2 ranges are updated, and later groups are renumbered.

   **accepted by reviewer** — The spec replaces the fixed 4-and-2 outcome with batches bounded by tool capacity while requiring all six decisions to be asked. Separate scenarios cover a three-question limit, a three-option limit with the recommendation and discussion retained, an ask tool unavailable in the current mode, and no ask tool. Both plain-text fallback scenarios require waiting for the answer before writing decisions. Task-group test-map and check updates were outside this re-check’s specified file scope.