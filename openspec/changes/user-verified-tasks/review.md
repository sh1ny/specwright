# Review

## Metadata

- **Round:** 2
- **Prior round:** 1 — APPROVE_WITH_CHANGES; three Required Changes outstanding.
- **Reviewer:** Codex, read-only review.
- **Reviewed:** `user-verified-tasks` proposal, design, both delta specs, prior review; `skills/specwright-commit/SKILL.md`, `scripts/task-cover.sh`; `skills/specwright-pr/SKILL.md`, `scripts/vcs.sh`; ADR 0020; `openspec/specs/task-commits/spec.md`.
- **Scope:** Re-check of round-1 Required Changes and concrete defects introduced by their fixes.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

None.

## Verdict

All three Required Changes are met at the design level. The revised rules define commit ordering compatible with whole-file commits, separate user ticks from agent recovery, and bind merge checks to the ready planning revision. No new blocking defect was identified within this review’s scope.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **Applied — user-tick commit ordering and isolation.** D3 and “User ticks ride the next tasks.md commit” explicitly defer user ticks while agent work is pending. Scenarios assert the actual `tasks.md` diff for a standalone tick, multiple simultaneous ticks, and a pending group with a user tick. Separate trailer kinds preserve agent-group coverage without requiring partial staging from `vcs.sh`.

2. **Applied — merge checks at the exact planning revision.** D4 introduces `--rev`; D6 and “The agent merge waits for the user” require active-or-archived task reads at the ready planning head before archive and every merge request. Unreadable state blocks merging. Scenarios cover a later archived-task untick, differing local and remote states, and missing task files. This addresses the checkout/head distinction documented in ADR 0020.

3. **Applied — recovery distinguishes user ticks.** D4 excludes user tasks from `pending_groups` and `uncovered`, listing them separately in `user_uncommitted`. The modified recovery requirement resumes pending agent/evidence work before recording deferred user ticks in that commit. Scenarios cover an interrupted agent group plus a user tick in another group, and an all-user group requiring only a user-check commit.

CHANGES_APPLIED: yes

## Rebuttals

None.