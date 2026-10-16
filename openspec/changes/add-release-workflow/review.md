# Review

## Metadata

- **Round:** 5
- **Prior round:** 4. APPROVE, covering the notes boundary in a clone without tags and two entries capturing in one file. Its two Suggestions (the D4 wording, and the `status` header plus the design `status` line) were applied and re-checked, so the verdict stood (`CHANGES_APPLIED: n/a`). This round reviews the uncommitted amendments since commit b9237ba. They answer a Codex P1 on PR #92: with `remote.origin.pushurl` set to a fork, publish checked the tag on the fetch URL but pushed it to the push URL.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (S1):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. I read the Rebuttals, `check_push_destination` and `cmd_publish` in release.sh, and the requirement "The tag is pushed where it was checked" with its new scenario "Rewrite to another GitHub repository". I ran `-k push_url -k rewrite_to_another`: 2 passed. S1 is applied:
  - Publish now stops with `push_url_mismatch` when the configured `remote.origin.url` and the rewritten fetch URL are both github.com URLs naming different repositories.
  - The check now runs first in `cmd_publish`, before `load_main` and any `ls-remote`, using local reads only.
  - A rewrite to a mirror that is not on github.com still passes. The spec now says this plainly: the tag checks use the fetch URL and the release uses the configured one.
  - These edits apply this round's Suggestion and change no reviewed decision, so the APPROVE verdict stands.
- **Reviewed:**
  - The amendment diff (`git diff -- openspec skills evals`):
    - design.md D6 step 1
    - specs/releases/spec.md, the new requirement "The tag is pushed where it was checked"
    - skills/specwright-release/SKILL.md, the Stops row
    - release.sh: `same_remote`, `check_push_destination`, and the call in `cmd_publish`
    - evals/release/test_release.py, `test_push_url_elsewhere_stops`
  - Also read in release.sh: `GH_URL`, `origin_url`, `code_slug`, `release_state`/`github_release`, `remote_tag` and `published_tags`.
  - Also read: skills/specwright-pr/scripts/as.sh, the URL and userinfo checks over every remote's fetch and push URLs and the insteadOf/pushInsteadOf rules; ADRs 0008 and 0010.
  - Ran `-k TestPublish -k push_url`: 10 passed, on git 2.55.0.windows.4.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

What holds:
- **Placement.** `check_push_destination` runs after `no_origin` and before the tag checks and every write. Before it, only reads have happened (`status_doc`, including its `ls-remote` calls). So a mismatch leaves no tag, no push and no `gh` call, which the eval asserts against origin and the fork.
- **Rewrite rules.** `git remote get-url` and `get-url --push --all` return URLs after insteadOf and pushInsteadOf rewriting. The comparison is therefore between the URL `ls-remote` and `fetch` actually contact and the URL(s) `push` actually contacts.
  - The common `url."git@github.com:".pushInsteadOf "https://github.com/"` setup still passes, because `same_remote` matches the github.com owner/name in any form and case.
  - A pushInsteadOf that sends pushes to a fork is caught, as is an explicit `pushurl`.
  - Each of several push URLs is checked (`--all`).
- **Fails closed.** A non-GitHub pair that differs only in form (`ssh://host/x` against `host:x`) stops rather than passes.
- **Fence and ADRs.** as.sh already refuses a github.com push or fetch URL, or rewrite rule, that carries userinfo. The new reads are local `git remote` calls, outside ADR 0008's network rule. The stop writes nothing, which is consistent with ADR 0010.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

- **S1. The GitHub release repository still comes from the unrewritten URL.**
  - **The claim.** The new requirement says "the tag checks and the GitHub release use the fetch URL".
  - **The code.** `release_state` and `github_release` take the slug from `origin_url`, which is `git config --get remote.origin.url`: the raw value, before insteadOf. The tag checks and the push use the rewritten URL.
  - **Where they diverge.** They differ only under an insteadOf rule that changes the github.com owner or name. For example, `url."https://github.com/me/".insteadOf "https://github.com/upstream/"` with origin set to `https://github.com/upstream/x`. Fetch and push both go to `me/x`, so the new check passes, and the tag is checked and pushed there. `gh release create --repo upstream/x --verify-tag` then fails (exit 3, "a re-run resumes"), and every re-run fails the same way.
  - **Why it is not blocking.** That configuration is rare, and nothing is written to the wrong place: the release creation fails, it does not land elsewhere.
  - **The fix.** Either take the release slug from `git remote get-url origin`, or add the raw `remote.origin.url` to the `same_remote` comparison, so that all three destinations must agree. Alternatively, reword the requirement to name the raw URL for the release.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: n/a

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **S1:** applied. `check_push_destination` also stops (`push_url_mismatch`) when the configured `remote.origin.url` and the rewritten fetch URL are both github.com URLs naming different repositories; a rewrite to a non-GitHub mirror (the eval harness's own setup) still passes. The check now runs first in `cmd_publish`, before any network read. Requirement "The tag is pushed where it was checked" names it, with the new scenario "Rewrite to another GitHub repository"; D6 updated; eval `test_rewrite_to_another_github_repo_stops`.
