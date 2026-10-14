# 0009. Opt-in agent merge at the ready head

- Status: accepted
- Date: 2026-10-13

## Context
Specwright never merged a pull request: watch reported a PR ready and the user merged it on GitHub. Users then asked the agent to "merge, switch to main, pull and be ready for next", and the agent pieced that together outside any skill, with no readiness check, no identity fence and none of cleanup's branch safety (#15). The strategy allows a merge on GitHub only under "a documented, opt-in setting". The pre-ship review now gates every first PR (ADR 0007) and every `gh` call runs fenced as the run login (ADR 0008), so an opt-in merge can rely on both. A merge to the default branch cannot be undone, and deleting a remote branch can lose commits nobody merged.

## Decision
Specwright merges a PR itself only inside the following contract.

- **Opt-in.** Only with `pr.merge: agent` and `finish: pr`. Absent, `user` or any other value means no skill or script merges; an unrecognised value is reported as treated like `user`.
- **From watch's ready state.** The merge is a branch of watch step 3, where readiness is already decided, not a separate mode with its own check. In agent mode watch archives a ready, unarchived change without asking and watches the archive head to ready first. Change branches and roadmap branches (`docs/project-baseline`, `docs/close-<milestone>`) merge; any other branch is reported ready and never merged.
- **Reviewed heads only.** The PR's repository's reviewer set (`pr.reviewers`; store: `planning_store.reviewers`) must have at least one `required` reviewer, else watch reports ready and merges nothing. A head watched without reviewers (the `archive-only` carry-over) is merged only when it is the archive head `archive-only` judged; any other head is judged again or watched with the reviewers.
- **At the ready head, read back.** `pr-pair.sh merge` sends GitHub's REST merge (`PUT pulls/N/merge`) with `pr.merge_method` and `sha=<ready head>`, fenced as the repository's run login, then reads the PR back. The read-back, not the PUT's status, decides: `merged`, `refused` (409 is `head_changed`) or unknown (exit 3). Cleanup runs only on `merged`; unknown deletes nothing.
- **Store first, then code.** A store-backed pair merges only when `pair-state` is `ready`, the store PR first. A code result other than `merged` after the store merged stops with `planning merged, code pending`, cleans up the store only, and the user merges the code PR.
- **A refusal stops.** No administrator rights, no auto-merge, no merge queue, no retry with another method and no review dismissal. The PR stays open with GitHub's message.
- **Remote deletion only at the merged head.** With `pr.merge: agent` and `pr.delete_branch` (default true), Cleanup after merge deletes the remote branch, whoever merged, only after the local cleanup succeeded, only while the ref is still at the merged head and no open PR uses it as a base. `pr.merge: user` never deletes remote branches.

**Rejected: `gh pr merge --match-head-commit`.** On a branch that requires a merge queue it queues the PR or enables auto-merge instead of merging, `--delete-branch` also deletes the local branch past `branch-check`, and its result is a text message, not structured state.

**Rejected: a separate merge mode that re-checks readiness.** Readiness (reviewers, cutoffs, stale verdicts, pair state) took several releases to get right; a second checker would drift from it.

**Rejected: `git push --force-with-lease=<b>:<sha> origin --delete <b>`.** It is atomic, but it pushes through the remote's push URLs and rewrite rules, which ADR 0008 spent a change fencing, and can target a remote that is not the PR's repository. The REST ref check, then delete, always names the PR's repository; its race window is milliseconds on a branch whose PR already merged.

**Reversal cost: low.** Two `pr-pair.sh` subcommands behind a JSON contract and text in watch and finish. A merge made under this contract cannot be undone, which is why relaxing a guard needs a superseding ADR.

## Consequences
- Default projects keep today's behaviour: no merge request is ever sent.
- With agent mode on, GitHub records the run login as the merger, and the archive runs without a question.
- With `pr.delete_branch` on, merged remote branches disappear; a branch pushed after the merge or used as a base is kept and reported.
- Merge-queue projects get a refusal and merge by hand; queue support would supersede this ADR.
