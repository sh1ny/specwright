# Proposal

## Why

Seven known gaps in ship, feedback and finish can fail a change in a way the user has to repair by hand. Some leave a PR open after a failed push, some post a reply with no body, some delete commits main does not have, and some loop or stop during resume. All were filed against the PR flow during M1. This change serves **M2 - Ship flow** (change 2, release 0.1.13). It advances two exit criteria: *every issue is closed by a merged PR with a regression test in `evals/pr-pair` or `evals/git-workflow`*, and *both eval suites pass*. The pre-ship review and agent merge planned later in M2 build on a ship and cleanup flow that does not lose work.

## What Changes

- **#58 Store PR after the code push.** In a store-backed change, ship pushes every repo of the expected set (store, then code) before it finds or opens any PR. A failed push leaves no PR opened or updated in either repo, so the existing failure rule now holds as written.
- **#57 Re-request once when the push time is missing.** When the repository activity has no entry for the pushed head, `pass plan` falls back to the earliest time a snapshot on this machine saw the head, the GitHub time pr-evidence already uses, and then to the time the pass record was written. A matching request comment posted after that time counts as done, so a resumed pass requests review once per head instead of on every plan.
- **#56 No reply without a body.** `pr-reply.sh` refuses a body file that is missing, unreadable or empty. It exits non-zero before any GitHub call, so no marker-only reply can hide a finding.
- **#54 Temp files removed on every exit.** `pr-reply.sh` removes its temp file on success and on failure. Skill flows that tell the agent to write a body or message file also tell it to remove that file afterwards.
- **#55 Cleanup keeps commits main lacks.** Cleanup after merge deletes a change branch only when its tip is on main, or when the tip equals the merged PR's head (squash or rebase). Otherwise it keeps the branch and reports the commits main lacks. This applies to `cleanup-plan` for store-backed changes and to repo-local cleanup in `specwright-pr` and `specwright-finish`. Plain `git branch -d` is no longer trusted: it checks the upstream, not main.
- **#63 Resume finds a squashed or bulk archive.** `specwright-finish` **Resume** also counts the archive as found (fact A on main) when main holds the change's archive directory. A squash merge or a bulk archive commit that does not carry the `archive change` subject is then still found.
- **#65 Resume after a merged PR whose branch is gone.** In `pr` mode, a repo whose PR merged and whose change branch no longer exists is done once the issues-left-open backstop has run. Finish skips the branch cleanup and reaches `Nothing to finish` instead of failing on `git branch -d`.
- Release 0.1.13: `VERSION`, the README badge and every skill's `metadata.version`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `change-finish`: Resume reads the archive from main's archive directory as well as from the archive commit's subject (#63). It treats a merged PR with no branch left as done after the backstop (#65). Branch deletion after a merge keeps a branch whose tip main lacks (#55, repo-local and store-backed).
- `planning-stores`: ship pushes every repo of the expected set before it opens or updates any PR (#58).
- `feedback-passes`: the re-request step counts a request as done for a head whose push time GitHub does not report (#57).
- `pr-evidence`: a reply is never posted without its body (#56).
- `pr-script-runtime`: scripts remove their temp files on every exit, failure included (#54).

## Impact

- `skills/specwright-pr/scripts/pr-reply.sh`: body check and an `EXIT` trap.
- `skills/specwright-pr/scripts/pr-pair.sh`: the `request_state` fallback and a `written_at` field in new pass records; the `cleanup-plan` tip rule.
- `skills/specwright-pr/SKILL.md`: the order of ship step 4, temp-file cleanup in ship, feedback and after-the-limit, and the repo-local cleanup rule.
- `skills/specwright-finish/SKILL.md`: Resume fact A, the merged-PR-without-branch row, and the guarded branch deletion after a PR merges.
- `evals/pr-pair` (`test_pr_reply.py`, `test_pr_pair.py`, `test_skill_text.py`) and `evals/git-workflow` (agent evals for ship order and finish resume): one regression test per issue.
- Release files for 0.1.13. No new dependency. Pass records stay version 2: a record without `written_at` falls back to its owner's `at`.
