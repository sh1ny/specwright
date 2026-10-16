# Review

## Metadata

- **Round:** 6
- **Prior round:** 5. APPROVE: publish stops on a push URL to another repository. Its Suggestion S1 was applied and re-checked: publish also stops when an insteadOf rewrite turns the configured github.com repository into another one, and the check runs first, before any network read. The verdict stood (`CHANGES_APPLIED: n/a`). This round reviews the uncommitted amendments since commit 90faf3b. They answer a Codex P2 on PR #92 (thread PRRT_kwDOS22yKc6tR3sc): a non-GitHub shorthand origin that insteadOf expands to github.com got `not_github`, so the GitHub release was silently skipped.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (S1-S2):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. I read the specwright-release SKILL.md Run login paragraph (:34) and `code_slug` in release.sh, and ran `-k shorthand -k store -k not_github`: 3 passed.
  - **S1 is applied.** "Origin on github.com" now means the fetch URL from `git remote get-url origin` (after `insteadOf`, `github.com.` included), never the raw `remote.origin.url`. That matches specwright-finish, specwright-pr and `release_slug`, so a shorthand origin is fenced (ADR 0008).
  - **S2 is applied.** `code_slug` returns `release_slug(st)` and still raises `no_github_origin` when that is None, so store-backed pr-mode notes and the release name the same repository.
  - These edits apply this round's Suggestions and change no reviewed decision, so the APPROVE verdict stands.
- **Reviewed:**
  - The amendment diff (`git diff -- openspec skills evals`):
    - design.md D6 step 1
    - specs/releases/spec.md: "The tag is pushed where it was checked", and the new scenario "Shorthand rewritten to GitHub"
    - release.sh: `release_slug` and `release_state`
    - evals/release/test_release.py: `test_shorthand_rewritten_to_github_creates_release`
  - Also read in release.sh: `check_push_destination`, `origin_url`, `code_slug`/`merged_pulls`, `GH_URL`.
  - Also read: skills/specwright-release/SKILL.md (Run login, publish steps 1-3); the fence rule in skills/specwright-finish/SKILL.md:16 and skills/specwright-pr/SKILL.md:51; ADRs 0008 and 0010.
  - Ran `-k shorthand -k not_github -k rewrite_to_another`: 3 passed, on git 2.55.0.windows.4.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

What holds:
- **`release_slug` order.** It prefers the configured `remote.origin.url` when that is a github.com URL. Otherwise it uses `git remote get-url origin`, the URL after insteadOf, and returns None only when neither is on github.com.
- **Agreement with the push check.** `check_push_destination` runs first in `cmd_publish` and has already stopped when both URLs are on github.com but name different repositories. The push URLs must name the fetch URL's repository. So for the shorthand case, the release repository, the tag checks and the push all name the same repository.
- **Mirror rewrite.** Publish still releases on the configured repository when insteadOf points it at a mirror that is not on github.com. That is unchanged and is what the spec states.
- **The eval.** It drives real git over a fake ssh to the bare repository. It asserts that `--repo` is the slug and that the tag reached the bare repository.
- **Old configurations.** The `not_github` eval still passes, so a genuinely non-GitHub origin is still skipped.
- **ADR 0010.** It is unaffected: no tag is moved or deleted.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

- **S1. specwright-release SKILL.md should say which URL "origin on github.com" means.**
  - **The gap.** The skill fences each step (fetch, `untagged`, `publish`) only "with origin on github.com" (SKILL.md:34-38) and never says which URL to test. specwright-finish (:16) and specwright-pr (:51) both define it as the fetch URL from `git remote get-url <remote>`. `release_slug` now uses that rewritten URL too.
  - **The risk.** An agent that tests the raw `remote.origin.url` sees `corp:acme/app`, judges it not on github.com, and runs `bash scripts/release.sh publish` without `as.sh`. Publish then reaches GitHub with `git ls-remote`, `git push` and, new this round, `gh release create`, under whatever account is active. ADR 0008 forbids exactly that.
  - **Why not blocking.** The unfenced git calls were already possible before this round. The change adds the `gh` call.
  - **The fix.** One sentence in the Run login paragraph, matching finish and pr: on github.com means "`git remote get-url origin` is on github.com (`github.com.` included), whatever `remote.origin.url` says". This is recommended before merge.
- **S2. `code_slug` still reads the raw `remote.origin.url`.** It serves `merged_pulls`, which finds the merged code PRs for store-backed notes in pr mode. With a shorthand origin, a store-backed project now gets its GitHub release, but `status` and `publish` stop earlier with `no_github_origin` ("need origin to be a github.com repository"). Have `code_slug` use `release_slug`, or say in D5/D6 that store-backed pr-mode notes need a github.com `remote.origin.url`.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: n/a

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->
