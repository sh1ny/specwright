# 0043. The undo planner checks the version of the checkout it uses

- Status: accepted
- Date: 2026-11-20
- Supersedes: —
- Amends: 0040 (its entry check, for `sw finish undo-archive-plan` only)

## Context

ADR 0040 has every project command check `openspec/.specwright/VERSION` once, in the CLI's entry check before dispatch. `sw finish undo-archive-plan` takes `--code` and `--dir`, so the checkout it plans against can differ from the one the entry check read, and either checkout could veto the call.

## Decision

- `sw finish undo-archive-plan` skips the CLI's entry check, so the check still runs once. The planner runs it, after option validation and before any Git, on the anchored, existing code checkout it uses.
- The result is the same as for any other project command: a mismatch stops with `sw_mismatch` naming the expected binary path.
- Every other `finish` form, including a malformed leading part, and every other project command keep ADR 0040's entry check unchanged. Each `undo-step` the plan emits keeps the normal entry check, against the same project root the planner checked.

## Consequences

- The version checked is the version of the checkout whose files the plan reads and the steps write.
- Reversal cost: low. The check moves back to the entry.
