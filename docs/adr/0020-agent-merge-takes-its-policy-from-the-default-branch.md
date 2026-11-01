# 0020. Agent merge takes its policy from the default branch

- Status: accepted
- Date: 2026-11-01
- Adds to: 0009 (does not supersede it)

## Context

ADR 0009 lets watch merge a ready PR with `pr.merge: agent`. Watch read that setting, the merge method, remote branch deletion and the required reviewers from `openspec/specwright.yaml` in the local checkout of the PR branch. Anyone who can push to the branch can edit that file. They can turn on agent merge and name an account they control as the only required reviewer. One review from that account then makes the PR ready, and watch merges it with the maintainer's credentials (#141). The local checkout is not even the copy that gets merged: a push to the remote branch changes the merged head and leaves the checkout as it was. The `main_branch` setting sits in the same file, so the branch could also point "main" at a branch it controls.

## Decision

- **The policy keys:** `pr.merge`, `pr.merge_method`, `pr.delete_branch`, `pr.reviewers` and `planning_store.reviewers`. They decide whether, how and after whose review the agent merges.
- **Read from GitHub, twice, at the right moments:** `pr-pair.sh policy` reads `default_branch` from `repos/<o>/<n>`, then `openspec/specwright.yaml` through the contents API at that branch and at the ready head that would be merged, fenced as the repository's run login and bounded (ADR 0008, 0014). `main_branch` from settings is not used for this read. Watch runs it before the archive decision and again right before each merge request, after the Version check. The work tree's copy only starts the wait and gives early `bad_setting` and notes.
- **Main decides:** watch merges on its own only when main's `pr.merge` is `agent`, main's required reviewers reported on the head and the head's policy does not differ from main's. Watch archives a ready change without asking only on the same conditions; otherwise it asks, as in user mode.
- **Normalized comparison:** each key is compared after the same parsing and normalization that `context` uses (an unrecognised `merge` is `user`, method and deletion with their defaults, reviewers by login without `[bot]`, role, timeout in seconds and request text). Comments, key order and quoting never count as a difference.
- **A difference needs the user, for one head:** watch lists every difference (key, main's value, the head's value). It asks only when the head's `pr.merge` is `agent` and the head's required reviewers reported on it; a yes merges at that head with the head's method, a no reports ready. With a head that is not `agent`, watch reports ready and asks nothing. A yes covers that head only; a new head is read and asked again.
- **Reviewer reports are checked against the authorizing set, per repository, in the script:** `policy` takes the latest snapshot of each expected PR and reports, for main's set and for the head's, whether every `required` reviewer of that set reported on that repository's reviewed head (`--reviewed-head <repo>=<sha>` for the store PR and for the archive-only carry-over). When the set watch relies on is short, watch merges nothing and restarts that PR's wait with that set's reviewers; it never posts the head's request text before a yes.
- **Unknown merges nothing:** a failed, cut-off, non-file or unparseable read, and a missing file at the head, are exit 3 `merge policy unknown`; watch reports ready and tries again the next time it reaches the merge step. Only a missing file on main reads as an empty file, which means user mode. There is no fallback to the work tree.

**Rejected: read main from a local `origin/<main>` after a fetch, inside `context`.** The ready head is a remote commit the checkout may not have, and `context` also serves ship, finish and cleanup, which do not merge.

**Rejected: check that the work-tree file equals main's.** A push after the check still changes the merged head; the decision must bind to the merged commit.

**Rejected: merge with main's policy and ignore the head's.** A PR that legitimately changes the method or the reviewers would merge under rules it is replacing, without anyone seeing it.

**Rejected: a three-way comparison against the merge base.** It adds a read for a case that only costs one question; a false positive asks, a false negative merges.

**Reversal cost: low.** One subcommand behind a JSON contract and the watch text. Relaxing any of these guards needs a superseding ADR, as for 0009.

## Consequences

- A PR that leaves the merge policy alone merges exactly as before.
- A PR that changes the merge policy, including one that turns on agent merge for itself, always needs the user's yes for its ready head.
- Watch makes three small GitHub reads per ready head, in user mode too.
- Residual risk: a maintainer merge to main in the moment between the read and the merge request is not seen. Only someone who can already merge to main can cause it.
