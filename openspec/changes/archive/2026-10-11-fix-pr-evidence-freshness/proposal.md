# Proposal

## Why

Milestone **M1 - Hardening**, change 3 of 3 (release 0.1.11). `specwright-pr` can act on evidence that no longer describes the PR it is acting on:

- pair readiness can pass on a snapshot of another PR or of an old head;
- when GitHub's push activity is missing, a reviewer's report on the previous head counts as a report on the current one;
- a reply written for a finding's old text can hide the reviewer's edit of it;
- the store's git reads run with the code account's credentials, so a private store fails its push check;
- a watcher's cleanup can delete a newer watcher's ownership token, and then nobody watches the PR;
- a long review clipped in the snapshot can be judged, or dropped, on its preview alone.

Each one makes watch report ready too early, hides feedback, or silently stops monitoring. Each leads to a manual rescue, which the milestone outcome rules out: a change runs from branch to merged PR without manual git or PR rescue. This change advances the exit criteria "every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/pr-pair` or `evals/git-workflow`", "`evals/pr-pair` passes", and "each change ships as its own release" (0.1.11). It is the last planned change of M1.

## What Changes

- **#31** `pr-pair.sh pair-state` treats a snapshot as evidence only for the PR and head that discovery reports now. A snapshot whose repository, PR number or `head_oid` differs blocks readiness with a `refresh` blocker naming the mismatch, and never counts as passing. Watch takes a fresh snapshot of that PR and asks again.
- **#31 (reviewer cutoff)** When the push time of the head is missing from the repository activity log, `pr-snapshot.sh` no longer counts reports from the head's commit date on. A timestamp-based reviewer (Mira and any reviewer without a commit-precise signal) counts as reported only for output at or after the earliest moment a Specwright watcher saw the head. That moment is kept on disk per repository, PR and head, so a later process does not move it forward. Codex (reviewed-commit SHA) and Kody (check run on the commit) keep their exact signals. The snapshot says when the cutoff is a first-seen time rather than a push time.
- **#33** Replies are bound to the revision they answer. `pr-reply.sh` takes the item's `rev` from the snapshot, reads the item again before it posts or resolves, and refuses with a distinct exit status when the revision has changed. The handled marker carries that revision, and the snapshot counts an item as handled only while its current revision matches the marker. Markers from earlier versions keep the time-based rule.
- **#35** Git transport on the store (`ls-remote` and `fetch` in `pr-pair.sh`, including the push checks of `rounds` and `pass plan`) runs under the store's login, pinned the way `as.sh` pins pushes. The code repo's transport keeps the code login.
- **#39** Watch ownership is atomic. A watcher removes its token only if the token is still its own, in a step that another watcher's takeover cannot interleave with. The watch key keeps the repository owner, the repository name and the PR number apart, so `acme-tools/widget#5` and `acme/tools-widget#5` no longer share a token file.
- **#47** The snapshot marks every clipped body (`clipped: true`). A new `pr-snapshot.sh --full <item id>` call prints the full body of one item. Feedback reads the full body of a clipped item before judging or dropping it, and hands over to the user when the full body cannot be read.
- `specwright-pr` SKILL.md: watch refreshes a snapshot on a `refresh` blocker, and on a replaced PR (`refresh:pr`) moves its wait to the PR that `pair-state` names; feedback passes each item's `rev` to `pr-reply.sh`, takes a fresh snapshot and judges the item again on a revision refusal, and reads full bodies of clipped items.
- Everything moves to 0.1.11.

## Capabilities

### New Capabilities
- `pr-evidence`: what `specwright-pr` may treat as evidence about a PR: reviewer reports bound to the current head, replies bound to the item revision they answer, and clipped bodies read in full before they are judged.
- `pr-watch`: background watch ownership: one owner per PR, atomic handover and cleanup, collision-free keys.

### Modified Capabilities
- `planning-stores`: **Watch covers the expected PR set** (a snapshot counts only for the PR and head discovery reports); **Commands run where they resolve correctly** (store git transport authenticates as the store login).

## Impact

- Scripts in `skills/specwright-pr/scripts/`:
  - `pr-snapshot.sh`: reviewer cutoff, revision-bound markers, `clipped`, `--full`, watch ownership and keys.
  - `pr-reply.sh`: `--rev` and the re-read before posting or resolving.
  - `pr-pair.sh`: `pair-state` binding, store git transport under the store login.
- Skill: `specwright-pr` SKILL.md (feedback steps 1, 4 and 8, watch steps 1-3). `metadata.version` moves to 0.1.11 in all six skills.
- Docs: README badge, `VERSION`, and `openspec/architecture.md`: the state, boundary and resource rows that describe these gaps (reply markers, watch ownership, the new first-seen record, store git transport, snapshot bodies, reviewer cutoff, watch polling). The Known gaps table is frozen at the baseline and is not edited; the issues close when their fixes merge. Accepted ADRs are not edited.
- Version: 0.1.11, approved by the user on 2026-10-10. The reply marker gains a revision suffix. ADR 0003 calls a marker change a workflow change (minor version), but this one is additive and readable both ways, so no change in flight needs a migration (design D3).
- Tests: `evals/pr-pair` gets cases for each issue. The fake `gh` gains the snapshot query, the reply re-read, node lookups for `--full`, and git transport that checks credentials. The snapshot and reply scripts have had no harness tests before this change.
- Compatibility: the new `--rev` is required by feedback but optional in the script; without it `pr-reply.sh` behaves as before, so a reply from an older session still works. Markers from 0.1.10 and earlier stay valid under the time rule. Watch token files under the old key are not migrated. A watcher started by 0.1.10 still writes and reads the old key, so it does not see a 0.1.11 watcher's token. It ends at its own timeout (30 minutes at most), or earlier when the session stops it by task id, as watch step 1 already does.
- Out of scope: snapshot pagination beyond 100 items (#9, parked), bounds and deadlines in the PR scripts (#40, M4), identity fencing as a default (#38, M2).
