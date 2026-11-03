# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** cross-model CLI (Codex)
- **Reviewed:** `openspec/changes/roadmap-init-autonomy/proposal.md`, `design.md`, `specs/project-planning/spec.md`; supporting sources: `openspec/specs/project-planning/spec.md`, `skills/specwright-pr/SKILL.md`, `openspec/architecture.md`, `skills/specwright-review/scripts/review-run.sh`, and `schemas/specwright/templates/review.md`. Fresh re-check limited to round 1’s four Required Changes; no new full review.

## Findings

### Critical (blocking)

None.

### Moderate

1. The delta left “Close keeps an agreed Next split” unmodified although autonomous close promotes an unagreed listing without asking.
2. Question caps could not fit all answers on tools with a 3-question limit (init two rounds, pack one round).
3. Escalation recovery relied on `architecture-review.md` keeping both rounds, but `review-run.sh` replaces the file each round.
4. The summary’s gate exemption was missing from `skills/specwright-pr/SKILL.md` feedback step 7 and the architecture’s design-review rule.

### Suggestions

None.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

All four required changes are now applied to the planning artifacts. The original findings above are retained as the record of round 1.

## Required Changes

1. Modify “Close keeps an agreed Next split” in the delta to reconcile interactive and autonomous promotion, retaining the existing requirement’s full scenario coverage.
2. Resolve interview-round versus tool-call limits for init and pack; add capacity-overflow scenarios.
3. Define how both baseline review reports survive escalation, and align proposal, design and verification with the actual storage mechanism.
4. Include the PR feedback baseline-review caller and architecture review rule in the gate-exemption updates and checks.

CHANGES_APPLIED: yes

## Rebuttals

1. **Fixed — accepted by reviewer.** The delta now modifies “Close keeps an agreed Next split” and retains coverage for agreed promotion, amendments, an unsplit Next, and an unagreed listing. The amendment scenario now explicitly applies to `important` or `all`; a separate autonomous scenario keeps the agreed changes and records the proposed amendment as pending. Autonomous promotion of an unagreed listing is also explicitly covered.

2. **Fixed — accepted by reviewer.** Design D6 and the added “A question round may span several ask-tool calls” requirement distinguish interview rounds from tool calls without dropping questions. Overflow scenarios cover ten init questions with a three-question tool limit and four pack questions across two calls, preserving init’s two-round and pack’s one-round caps.

3. **Fixed — accepted by reviewer.** The proposal now states that `architecture-review.md` retains round 2 and the pending summary row carries round 1’s findings. Design D5 specifies copying each earlier finding, with severity and a one-line summary, before the next round replaces the review file; its recovery description uses those two locations. The delta’s preservation and escalation scenarios verify that mechanism. This matches the script’s replacement behavior without requiring script changes or claiming that both complete reports remain in the review file.

4. **Fixed — accepted by reviewer.** The proposal’s Impact section explicitly includes PR feedback step 7 and the architecture’s design-review rule. Design D3 applies the exemption to those callers as well as init and close. The delta covers a summary-only PR feedback fix that leaves the review file unchanged, alongside an outside-section edit that requires another baseline round. These are planned implementation updates; their absence from the current source files does not leave this design-review correction outstanding.