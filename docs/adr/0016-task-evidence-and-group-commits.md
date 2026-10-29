# 0016. Task evidence is an exact subject or trailer; groups commit at the boundary

- Status: accepted
- Date: 2026-10-28

## Context
`specwright-commit` makes one commit per numbered task, so a change with six task groups and twenty tasks fills its PR with twenty commits, though each group is the coherent unit of work (#20). Evidence that a task was committed is a subject substring, `task X.Y ` with a trailing space so 1.1 does not match 1.10, matched by the agent reading `git log --oneline`. ADR 0003 keeps that evidence in Git history with nothing cached, ADR 0006 pairs a code commit with a store commit, code first, and ADR 0002 puts deterministic matching in thin scripts. The jj and GitButler backends (#19) write ordinary Git commits and need an evidence format they can produce without rewriting history.

## Decision
- **Task evidence is a subject prefix or an exact trailer.** A task `X.Y` is covered by a commit on the change branch since main whose subject starts with `<type>(<change>): task X.Y ` (the per-task form `fit-subject.sh` already requires; `task 1.1 ` later in a subject is not evidence) or whose `Specwright-Task` trailer value is exactly `X.Y`, as Git's own trailer parser reads it. `task-cover.sh` does the matching, read-only, and reports duplicates and cross-group trailers; Reconcile and the end-of-apply check use it in both modes.
- **`commit_granularity: task | group`.** `task`, the default, keeps per-task commits and subjects byte for byte, with no trailers. `group` commits a task group once at its boundary, after every task of the group is ticked and verified, with the subject `<type>(<change>): group N <heading>` and one `Specwright-Task: X.Y` trailer per covered task in the final trailer block. Group N is every task whose ID has exactly N before the dot.
- **One group is pending at a time.** A complete group is committed, both halves when store-backed, before any task of another group is ticked, parallel dispatch included. On resume exactly one group with ticked, uncovered tasks is pending work to finish; more than one is put to the user.
- **Grouping never rewrites history.** No amend, squash, rebase or regroup of an existing commit, published or not. A group commit covers only its group's tasks that have no evidence yet, so earlier per-task commits stay.

**Rejected: per-task checkpoint commits squashed at the group boundary**, because the squash rewrites history on Git, needs a different procedure on jj and GitButler, and turns an interrupted squash into a recovery problem of its own. **Rejected: a task range in the subject (`group 1 (1.1-1.3)`)**, because a range cannot say which tasks are covered when an earlier task already has a commit, and range or substring matching is the 1.1/1.10 trap. **Rejected: trailers in task mode too**, because it changes per-task output, which must stay unchanged.

## Consequences
- A PR of a group-mode change has one task-work commit per group, and every task is still provable from Git history alone.
- `commit_granularity`, the `Specwright-Task:` trailer and the `group N` subject are formats later runs parse: changing them is a workflow change (minor version), and a later format must keep reading this one.
- A pending group's work sits uncommitted longer; resume re-verifies its ticked tasks, a ticked red step by running its named test.
- Reversal cost: high. Later runs, `task-cover.sh`, Reconcile, the end-of-apply check and #19's backends all read the format.
