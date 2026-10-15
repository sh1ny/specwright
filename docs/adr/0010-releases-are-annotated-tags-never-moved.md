# 0010. Releases are annotated tags on the merged main commit, never moved

- Status: accepted
- Date: 2026-10-16

## Context
Specwright had no release step: the version lives in `VERSION`, the README badge and the `metadata.version` of every skill, bumped by hand in a change's last task, and no tag or GitHub release records which main commit shipped it. Consumers will install from a tag (#36), so a tag is published history: one on the wrong commit, or moved after someone fetched it, silently changes what they install. Merge evidence is uneven. `pr-pair.sh merge` returns a merge commit SHA, but a user merge, a local `merge: <change>` and a backfill give the scripts none, while main's first-parent history always has the answer. The pre-ship review record is keyed by head (ADR 0007), so any commit after a pass voids it. A store-backed project has two repositories, and one store serves several projects (ADR 0006).

## Decision
Releases follow these rules.

- **The bump is a reviewed task on the change branch (D2).** With `release.enabled`, the schema's tasks instruction puts `release.sh bump --to <version>` in the change's last task group. `specwright-commit` commits it like any task, pre-ship reviews it and it merges with the PR. The proposal states the target version by the pre-1.0 rule and the design review checks it.
- **The release commit is found from main's history (D3).** The release commit of V is the first commit in main's first-parent history, oldest first, whose primary version file reads V. That covers squash merges, merge commits, local merges, user merges and backfill. Rebase merges are refused: `release.enabled` with `pr.merge_method: rebase` is refused, and publish stops, naming the commit, when the first V commit has one parent and its subject does not end in `(#<n>)`.
- **A tag is created once and never moved (D6).** Publish is a sequence of idempotent steps judged by observed state: `ls-remote` and local `rev-parse` first, a conflict stops with both commits named, a tag that exists only on origin is fetched (never a second tag object), `git tag -a` when absent, a push of `refs/tags/<tag>` only, then `gh release create` with the tag's own message. Specwright never uses `--force`, `--tags`, or a tag move or deletion, and keeps no state file. A wrong tag is fixed by the user by hand.
- **Only the code repo is tagged (D5).** A store-backed project's notes read the store's archive, but the store gets no tag.

**Rejected (D2): a separate release PR after merge.** It doubles the PRs per change, runs the review gates again for a three-line diff and leaves main, between merge and release, with a version naming the previous release. **Rejected: a bump commit after pre-ship**, because it voids the head-keyed pass.

**Rejected (D3): `merge_commit_sha` from `pr-pair.sh merge`**, because user merges and backfill have none. **Rejected: tagging `origin/<main>` at publish time**, because a later merge may already have landed and the tag would name the wrong commit.

**Rejected (D5): tagging the store as well**, because several projects share a store with independent versions, so one tag namespace would collide.

**Rejected (D6): a publish journal**, because the tag and the release are the evidence (ADR 0003) and a journal could disagree with them. **Rejected: moving a wrong tag with `--force`**, because consumers may already have installed it.

**Reversal cost.** D2: medium, the schema instruction and task convention change but no stored format. D3: low, `release.sh` logic only. D5: medium, store tags could be added later without changing code tags. D6: high for the never-move rule, which binds #36's install-from-tag and every tag already published; relaxing it needs a superseding ADR.

## Consequences
- Every release has one annotated tag on the commit where its version first reached main, found the same way for every merge method but rebase.
- A failed or interrupted publish is recovered by running it again; two sessions converge on the same tag and release.
- A tag at another commit, or a lower untagged version, stops publish and the user decides; Specwright never repairs a published tag.
- Rebase-merge projects cannot enable releases until they change the merge method or tag by hand.
- Store-backed projects get code-repo tags only; a store tag would supersede this ADR.
