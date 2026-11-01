# Proposal

## Why

With `pr.merge: agent`, watch merges a ready PR as the run login. It takes the merge policy (`pr.merge`, `pr.merge_method`, `pr.delete_branch` and `pr.reviewers` with their roles) from `openspec/specwright.yaml` in the local checkout of the PR branch. A collaborator who can push to the branch can edit that file. They can turn on `merge: agent` and name an account they control as the only `required` reviewer. One post from that account then makes the PR ready, and watch merges it with the maintainer's credentials (#141, found by Codex's security review on sh1ny/kehai#2). The local checkout is not even the copy that gets merged: a push to the remote branch changes the merged head and leaves the checkout as it was.

This is the third change of M6 - Packs. It lands before packs add more project-supplied content. It serves the exit criterion "with `pr.merge: agent`, a PR branch whose `pr.merge`, `merge_method`, `delete_branch` or `pr.reviewers` differ from main's is not merged by watch: it reports the difference and asks the user. With no difference, the agent merge is unchanged", and "every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/`". It ships as release 0.13.0.

## What Changes

- **Merge policy from main:** a new `pr-pair.sh policy` reads `openspec/specwright.yaml` from GitHub twice: on the repository's default branch and at the ready head that would be merged. Main's copy alone decides whether the agent may merge, with which method, and which reviewers are required, for the code PR and for the store PR (`planning_store.reviewers`).
- **Drift stops the agent merge:** when the head's `pr.merge`, `pr.merge_method`, `pr.delete_branch`, `pr.reviewers` or `planning_store.reviewers` differ from main's, watch merges nothing on its own. It lists each difference (key, main's value, the head's value). When the head itself has `pr.merge: agent` and its required reviewers reported, watch asks the user: on yes it merges at the ready head with the head's method, on no it reports ready and stops. Otherwise it reports ready and asks nothing. A PR that turns on agent merge for itself always needs this confirmation.
- **Reviewers are checked against main's set:** whatever reviewers the wait started with, a head is merged only when every required reviewer of main's set (or of the head's set, after a yes) reported on it. A wait started with another set is restarted with the right one.
- **Archive without asking needs main's consent:** watch archives a ready change without asking only when main's `pr.merge` is `agent` and nothing drifts. Otherwise it asks, as in user mode.
- **Fail closed:** when either copy cannot be read, the policy is unknown. Watch then merges nothing and says why. A settings file missing on main means user mode; one missing at the head counts as unknown.
- **No difference, no change:** a PR that leaves the merge policy alone merges exactly as today.
- **ADR 0020** records that merge authorization comes from the default branch, read at merge time. It adds to ADR 0009.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-merge`: the merge policy is read from main's settings at merge time, a difference at the ready head needs the user's yes, and the archive without asking needs main's agent mode.

## Impact

- **Script:** `skills/specwright-pr/scripts/pr-pair.sh` (new `policy` subcommand, its header, shared settings parsing with `context`).
- **Skill text:** `skills/specwright-pr/SKILL.md` (the merge settings, archive before merge and Merge in watch step 3).
- **Eval tooling:** `evals/fakes/gh.py` gains the `repos/<o>/<n>/contents/<path>?ref=<r>` endpoint.
- **Tests:** `evals/pr-pair/test_pr_pair.py` (policy, drift, unknown, missing file, store reviewers), `evals/pr-pair/test_skill_text.py` (watch reads the policy before archiving and before each merge request) and `evals/pr-pair/test_fake_gh.py` (the contents endpoint).
- **Docs:** `docs/adr/0020-...md`, the in-force index in `openspec/architecture.md`.
- **Unchanged:** `finish` still reads `merge` from `context` to decide whether to start watch, and cleanup still reads `delete_branch` from main after its pull, which is main's own copy by then. In user mode watch makes three extra GitHub reads per ready head and sends no merge request without the user's yes to a difference.
- **Version:** 0.13.0 (a workflow change).

## Release Notes

0.13.0 makes the agent merge take its policy from the default branch. A PR branch can no longer turn on agent merge, change the merge method or the remote branch deletion, or replace the required reviewers for itself: watch reads those settings from main and at the head it would merge. When the two differ, watch lists the differences and asks before merging.

### Changed
- With `pr.merge: agent`, watch reads `pr.merge`, `merge_method`, `delete_branch` and the reviewers from the default branch and at the ready head, and asks the user before merging a PR whose policy differs from main's (#141)
