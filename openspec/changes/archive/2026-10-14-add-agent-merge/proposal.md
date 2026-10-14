# Proposal

## Why

`specwright-pr` and `specwright-finish` never merge: the user merges on GitHub. In practice users tell the agent "merge, switch to main, pull and be ready for next", and the agent then pieces together the merge, branch deletion and main sync outside any skill, with no readiness check, no identity fence and none of the branch safety that cleanup already has (#15). Now that the pre-ship review gates every first PR (0.2.0) and identity fencing is on by default (0.3.0), an agent merge can rely on both.

This is M2 (Ship flow) change 5, released as 0.4.0, the last change of the milestone. It advances the exit criteria "An agent-merge eval merges a ready PR and runs cleanup when the project opts in, and never merges when it does not", "One change in a dogfood project goes from ship to merge through the pre-ship review and agent merge", "each code fix has a regression test in `evals/pr-pair` or `evals/git-workflow`" and "each change ships as its own release". It is constrained by ADR 0008 (fenced GitHub identity by default: the merge and every network call run through `as.sh`), ADR 0007 (the pre-ship gate a change passes before its first PR), ADR 0003 (git and GitHub as the state store: merge state is read from GitHub, never stored) and ADR 0002 (agent instructions with thin scripts).

## What Changes

- **New settings**, all with safe defaults, so an existing project keeps today's behaviour:
  - `pr.merge: user | agent` (default `user`: the agent never merges, as today);
  - `pr.merge_method: merge | squash | rebase` (default `merge`);
  - `pr.delete_branch: true | false` (default `true`; agent mode only): delete the remote branch once its PR merged.
- **Agent merge in watch.** With `pr.merge: agent` and `finish: pr`, once watch reports a PR ready:
  - On a change branch whose change is not archived yet, watch archives it without asking (the setting authorizes the whole path to merged), then watches the archive head until it is ready again. With `pr.merge: user` the archive question stays as it is.
  - An agent merge needs at least one `required` reviewer in `pr.reviewers` (store: `planning_store.reviewers`). Without one, watch reports ready and says so, and merges nothing. A head watched without reviewers after the archive is merged only if it is the archive head that `archive-only` judged.
  - On an archived change branch, or a roadmap branch (`docs/project-baseline`, `docs/close-<milestone>`), which has nothing to archive, watch merges the PR as the run login with the configured method. The merge is conditional on the head watch reported ready, so a push that lands in between fails the merge instead of merging unreviewed commits. Watch then confirms the PR is MERGED on GitHub and runs the existing **Cleanup after merge**: check out main, run the fenced `pull --ff-only`, delete the local branch only under the existing `branch-check` rule, and run the issues-left-open backstop. With `pr.delete_branch` set, cleanup in agent mode then deletes the remote branch (whoever merged, so a cleanup resumed after an interruption behaves the same), but only while that branch still points at the merged head and no open PR uses it as a base.
  - Store-backed: watch merges only when `pair-state` reports both PRs ready, the store PR first, then the code PR. A failed second merge stops and reports the split state (planning merged, code pending, which roadmap status already derives) and merges nothing else.
  - A merge that GitHub refuses (branch protection, a merge queue, a disallowed method, a moved head) stops with GitHub's message, and the PR stays open for the user. The agent never retries with another method, never uses admin rights, never enables auto-merge and never dismisses reviews.
  - After cleanup it offers `specwright-roadmap` **next** or **close**, as finish does today.
- **Finish in agent mode.** `specwright-finish`'s `pr` path starts **watch** instead of offering it and reporting "Ready to merge on GitHub", since the merge happens at watch's ready point. The `Never merge the PR` rule becomes conditional on `pr.merge: user`.
- **Thin scripts** (`pr-pair.sh`): `merge` merges one PR through GitHub's REST merge endpoint with the expected head SHA, then reads the PR back and prints whether it merged, one JSON document with the existing exit codes, where a refusal stops and a failed read means unknown. `delete-remote` deletes a remote branch only when it is still at the merged head and no open PR is based on it. Both run under `as.sh`.
- **Regression coverage:** `evals/pr-pair` unit tests for both subcommands against the fake `gh`, and `evals/git-workflow` cases in which an opted-in project merges a ready PR and cleans up, and a default project never merges.
- **Docs:** the settings template, the README and the architecture's component and state tables.
- Release 0.4.0.

Out of scope: merge queues and auto-merge, since the REST merge refuses on a queued branch and the user merges those; agent merge in `finish: local`, which already merges locally; deleting remote branches in `pr.merge: user` mode.

## Capabilities

### New Capabilities
- `pr-merge`: when Specwright merges a pull request itself (only with `pr.merge: agent` and a PR watch reported ready), how it merges (method, head guard, identity), how it verifies the merge and cleans up local and remote branches, and what it never does (retry with another method, use admin rights, enable auto-merge, merge without opting in).

### Modified Capabilities
<!-- None: watch readiness, cleanup safety and identity fencing keep their requirements; the new behaviour sits in pr-merge. -->

## Impact

- `skills/specwright-pr/SKILL.md` (settings block, watch step 3, Cleanup after merge, the Never list), `skills/specwright-pr/scripts/pr-pair.sh` (`merge`, `delete-remote`).
- `skills/specwright-finish/SKILL.md` (`pr` path in agent mode).
- `templates/openspec/specwright.yaml`, `README.md`, `VERSION`, every `skills/*/SKILL.md` `metadata.version`, `openspec/architecture.md` (component and state rows).
- Evals: `evals/fakes/gh.py` (the REST merge and ref endpoints), `evals/pr-pair/test_pr_pair.py`, `test_skill_text.py`; `evals/git-workflow/evals.json`, `test_instructions.py`.
- Users: none unless they set `pr.merge: agent`. With agent mode on, GitHub records the run login as the merger, and with `pr.delete_branch` on, remote branches disappear after the merge.
