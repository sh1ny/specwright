# Review

## Metadata

- **Round:** 7
- **Prior round:** 6. APPROVE: a shorthand origin that insteadOf expands to github.com gets its GitHub release (`release_slug`). Its two Suggestions were applied and re-checked: S1, "origin on github.com" means the rewritten fetch URL in specwright-release SKILL.md; S2, `code_slug` uses `release_slug`. The verdict stood (`CHANGES_APPLIED: n/a`). This round reviews the uncommitted amendments since commit 362de6e. They answer Codex P2 PRRT_kwDOS22yKc6tSfCJ: a `release.tag` without `{version}` maps every version to one tag. The coordinator also asked whether declining Kody's PRRT_kwDOS22yKc6tSovm was right.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (S1):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. I read skills/specwright-release/SKILL.md publish step 1 (:36) and evals/release/test_skill_text.py:67, and ran `evals.release.test_skill_text`: 16 passed.
  - **S1 is applied.** The fenced and plain forms are both `git fetch --no-tags origin <main>`. The step says to keep `--no-tags` because of `remote.origin.tagOpt=--tags`, and no tag-fetching form is left in the skill. The text test pins the line.
  - This edit applies this round's Suggestion and changes no reviewed decision, so the APPROVE verdict stands.
- **Reviewed:**
  - The amendment diff (`git diff -- openspec skills evals`):
    - release.sh `Settings.gate`
    - specs/releases/spec.md: "Publish creates and pushes an annotated tag", and the new scenario "Tag template without the version"
    - evals/release/test_release.py: `test_tag_template_without_version_refused`
  - Also read in release.sh: `Settings.__init__` (the `release.tag` default), `tag_for`, every `gate` call site (`main` at :1358, and `cmd_bump`/`cmd_publish` with `rebase=True`); skills/specwright-release/SKILL.md publish step 1; ADRs 0008 and 0010.
  - Runs:
    - `-k tag_template`: 1 passed, on git 2.55.0.windows.4.
    - For the Kody thread, a scratch reproduction outside the repo, described under S1.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

What holds:
- **Every subcommand stops.** `main` calls `st.gate()` before dispatching any command, so check, bump, status, untagged and publish all stop with `bad_tag_template`. Settings parsing, which only reads `openspec/specwright.yaml`, is the only thing that runs first, so the stop comes before any version-file read, git read or write. The eval asserts this with a snapshot and an empty tag list.
- **The check is sufficient.** `tag_for` is `st.tag.replace("{version}", version)`. Any template that contains `{version}` therefore maps distinct versions to distinct tags, so it is the only property needed. Other braces are left alone (no `.format`), so a template like `{name}-{version}` cannot raise.
- **No other requirement contradicts the stop.** The default `v{version}` is unaffected, and ADRs 0008 and 0010 are untouched.
- **Kody PRRT_kwDOS22yKc6tSovm: the decline is right for default configuration.** I reproduced it in a scratch directory: origin has annotated `v1` at C, the clone has a different annotated `v1` at C, and origin's main has moved ahead. Plain `git fetch origin main` exits 0. Auto-follow fetches only tags missing locally, so nothing is clobbered. See S1 for the one configuration where this does not hold.

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

- **S1. Publish step 1 could use `--no-tags` to cover `remote.origin.tagOpt=--tags`.**
  - **The edge case.** The decline holds by default, but a clone with `remote.origin.tagOpt=--tags` breaks it. In the same reproduction, setting that and running `git fetch origin main` fetched every tag and exited 1 with `! [rejected] v1 -> v1 (would clobber existing tag)`. Publish would then stop at step 1, before `release.sh` could report `tag_mismatch`. `git fetch --no-tags origin main` exited 0.
  - **Why it is safe to add.** `release.sh` reads origin's tags itself (`ls-remote`) and fetches only the tag it publishes, so `--no-tags` in SKILL.md publish step 1 loses nothing. It would also make step 1's "never `--tags`" claim hold whatever the clone's config.
  - **Why it is optional.** It is a rare setting. In the reply declining Kody's thread, you could mention it as the one case where the reported failure is real.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: n/a

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->
