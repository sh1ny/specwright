# Review

## Metadata

- **Round:** 2
- **Prior round:** 1. APPROVE_WITH_CHANGES with RC1-RC4 (rebase merges, older untagged versions, the tree the agreement check reads, origin-only tags and the notes source), all applied and re-checked (`CHANGES_APPLIED: yes`). This round reviews the PR-feedback amendments to design.md and specs/releases/spec.md made after that verdict.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (Required Changes 1-2, S1-S3):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. Read the Rebuttals, `git diff -- openspec skills evals`, specs/project-planning/spec.md, specs/releases/spec.md, design.md (D7, D8, D9, Failure table, Resource Bounds, Flow & State Gaps), skills/specwright-roadmap/SKILL.md step 3b, skills/specwright-release/SKILL.md publish step 2, and release.sh (`untagged_since_latest`, `refuse_older_untagged`, `cmd_untagged`, `inside`, `WorkTree.files`). I ran the `untagged`, `first_release_push_failed`, `symlinked_directory_outside_refused` and `local_only` evals: 10 passed. Both items are applied:
  - RC1: "Close offers untagged releases" now lists what `release.sh untagged` lists, run fenced, with published meaning the tag is on origin (a local tag with no origin remote). Its three scenarios are reworded in terms of origin. D8 says all three callers run `untagged` fenced with the run login (ADR 0008). Roadmap close step 3b runs `[as] bash <specwright-release>/scripts/release.sh untagged --main <ref>`.
  - RC2: `untagged_since_latest` adds every version whose tag is local but not on origin to the list, whatever the anchor, also when nothing is published. `refuse_older_untagged` and `cmd_untagged` both pass `local_tags(st)`, so publish of a higher version stops naming it. The releases requirement and D9 state the rule. "Tag push failed earlier" now names `v0.4.2` on origin, and the new scenario "First release's tag push failed" (0.3.0 local-only, 0.3.1 merged; eval `test_first_release_push_failed`) pins the first-release case.
  - Suggestions: S1 is fixed. `WorkTree.files` refuses a match whose realpath is outside the repository, using `inside` with `commonpath` (another drive counts as outside). It has a scenario and the eval `test_symlinked_directory_outside_refused`, and D7 is updated. S2 is fixed: the Failure table, Resource Bounds and Flow & State Gaps now say "published", and the path requirement now says it stops the run before any write. S3 is fixed: a Flow & State Gaps entry "`finish: local` offline" was added.
  - Residual note, not blocking: by the RC2 rule, a backfill tag left local-only (say `v0.4.1` while `v0.5.0` is on origin) also blocks publish of any higher version until it is pushed. That is the intended "always listed" behaviour, and a re-run of publish for it pushes it.
  - The edits outside RC1-2 apply this round's Suggestions and do not change the reviewed decisions, so they do not void the verdict.
- **Reviewed:** proposal.md; design.md; review.md (round 1); specs/releases/spec.md, specs/change-finish/spec.md, specs/pr-merge/spec.md, specs/project-planning/spec.md; the amendment diff (`git diff -- openspec/`); openspec/architecture.md and the in-force ADRs it indexes (0008 and 0010 read in full); skills/specwright-release/scripts/release.sh (`Settings.entries`, `WorkTree`/`CommitTree.files`, `cmd_bump`, `primary_history`, `published_tags`, `previous_release`, `untagged_since_latest`, `branch_prefix`/`store_changes`, `remote_tag`, `status_doc`, `cmd_untagged`, `cmd_publish`); skills/specwright-release/SKILL.md; skills/specwright-finish/SKILL.md (Release); skills/specwright-pr/SKILL.md (Release step); skills/specwright-branch/SKILL.md step 6; skills/specwright-roadmap/SKILL.md (store-backed done rule at :26, close step 3b at :72); evals/release/test_release.py and its uncommitted diff (`git diff -- skills evals`). I ran the seven new tests (`-k "outside or glob_primary or local_only or without_origin or origin_unreadable or other_prefix or lightweight"`): 7 passed, 6 subtests passed.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

The amended decisions mostly hold against the code:
- `branch_prefix` (release.sh:279-288) copies `specwright-branch` step 6 word for word, and the roadmap's store-backed done rule (roadmap SKILL.md:26) applies the same exact-head-ref rule. Release notes and roadmap "done" therefore agree on what counts as proof.
- The lightweight-tag check (local `cat-file -t`, remote with no peeled `^{}` line) runs before any write and comes after the tag-conflict check.
- `published_tags` makes one `ls-remote --tags --refs origin` call.
- The glob history pass (`log -z --first-parent --diff-merges=first-parent --name-status`) tracks which files exist at each commit, and `test_glob_primary_reads_every_file_present` pins it.
- The relative-path refusal runs in `Settings.entries` before any read.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. Roadmap close was not updated for the new `untagged`. It now makes an unfenced network call, and its spec still uses the old definition.** Two problems:
- **The call is not fenced.** The amendment changes `untagged` from a local read to `git ls-remote --tags --refs origin` (release.sh:675-688). D9 now says "Run it as `[as] bash release.sh untagged ...`", and both finish and watch were edited to fence it with the run login. Close is the third caller D8 names, and it was not edited. `skills/specwright-roadmap/SKILL.md:72` still runs `` `specwright-release` `untagged --main <ref>` `` with no `[as]`. On a github.com origin that is a git network call outside `as.sh`. ADR 0008 forbids this ("Every `gh` call and every git network call to a github.com remote ... runs through `as.sh <run login>`"). It authenticates as whatever account or credential helper is active, so another agent's `gh auth switch` decides the identity. Against a private repo it can fail with exit 3, which skips the close offer.
- **The spec still uses the old definition.** specs/project-planning/spec.md, "Close offers untagged releases", still lists versions "since the latest tagged version, that has no tag (with no tag at all: ...)". Close's scenarios are also written in terms of tags ("`v0.5.0` is the latest tag", "Everything tagged", "No tag yet"). The releases spec now says a local tag whose push failed "SHALL NOT count as published". With `v0.5.1` only local, close's own requirement says 0.5.1 is tagged and must not be offered, but the script lists it. Once archived, the main specs would hold two conflicting definitions of the same list, and an eval written from the close spec would assert the wrong result.

See Required Change 1.

**M2. A first release whose tag push failed is never offered again once a newer version merges, and the scenario "Tag push failed earlier" leaves that case open.** The new rule anchors the list on "the latest published version (with none published: only the current version)" (`untagged_since_latest`, release.sh:706-712, with `published_tags`). Consider a project's first release:
1. Auto publish of 0.3.0 creates the local tag `v0.3.0`.
2. The push fails, for example because the fence refuses it.
3. The next change merges 0.3.1.

Then:
- Nothing is published, so `untagged` returns `[0.3.1]` only. 0.3.0 is not listed.
- `refuse_older_untagged` checks only that list, so publish of 0.3.1 is not blocked.
- `previous_release` uses local tags (status_doc, release.sh:1048), so 0.3.1's range starts at 0.3.0's release commit.
- After `v0.3.1` is pushed, 0.3.0 sits below the latest published version, so no later `untagged` or close lists it.

The result is that origin gets `v0.3.1`, and `v0.3.0` stays local-only forever. Its changes appear in no published notes, because 0.3.1's range excludes them. Round 1's M1 was this same silent gap in the tag series, and the amendment set out to close it ("a local tag left by a failed push is still offered and still blocks a newer version", D9). It is closed only when an earlier tag reached origin. The spec scenario "Tag push failed earlier" states no earlier published tag, so read literally it is the first-release case, and the requirement text then gives the opposite answer (only the current version). The eval (`test_local_only_tag_is_not_published`) publishes `v0.5.0` first, so it never exercises that case. See Required Change 2.

### Suggestions

- S1. The path refusal is lexical only, but D7 says "so bump never writes outside the repository". A committed symlinked directory that a `version_files` glob or literal path goes through still escapes:
  - `WorkTree.files` uses `glob.glob` and `os.path.isfile`, both of which follow symlinks (release.sh:375-380).
  - `cmd_bump` writes its temp file in `os.path.dirname(full)` and runs `os.replace` there (:568-575).

  For example, `pkg/*/VERSION` with `pkg/x -> ../../elsewhere` makes bump write a file outside the repository. Either add a check that `os.path.realpath` of each matched file lies under `realpath(root)`, or weaken D7's claim to "no absolute or `..` entry". Also add a test with a symlinked directory.
- S2. Stale wording left by the amendment in design.md:
  - The Failure table row "Publish with an older untagged version" says "A lower version after the latest tag has no tag".
  - The Resource Bounds row "`untagged` versions" says "Versions since the latest tag".
  - Flow & State Gaps "Two versions merged before either is published" says "until the older one is tagged".

  Change each to "published". In the releases spec, "Version file paths stay inside the repository" says every subcommand stops, but its scenario and the eval cover only check and bump. Add status or publish to the THEN, or narrow the requirement.
- S3. With the change to `untagged`, `finish: local` now needs origin reachable just to report "can be published after `main` is pushed". Offline, it skips the release report and shows an `ls-remote` error. That is consistent with the "`untagged` fails" row. Still, one Flow & State Gaps line saying it is expected would stop a reader from treating it as a regression.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **Close uses the new `untagged` (M1).** Make three edits:
   - In specs/project-planning/spec.md, "Close offers untagged releases", replace "since the latest tagged version, that has no tag (with no tag at all: only main's current version)" with the releases spec's definition: the versions `release.sh untagged` lists, published meaning the tag is on origin, or a local tag when there is no origin remote.
   - Reword the scenarios "Versions left untagged", "Everything tagged" and "No tag yet" in terms of published tags.
   - In design.md D8, state that close runs `untagged` fenced with the run login, as finish and watch do. The matching apply edit is `skills/specwright-roadmap/SKILL.md:72`: change it to `[as] bash <specwright-release>/scripts/release.sh untagged --main <ref>` (specwright-release **publish** step 2), with the same definition.
2. **A local-only tag is always listed (M2).** In specs/releases/spec.md, "Older untagged versions are published first", and in design.md D9 `untagged`, state that every version on main's first-parent history whose tag exists locally but not on origin is listed, whatever the published anchor, including when nothing is published. Publish of a higher version then stops naming it. Make "Tag push failed earlier" explicit, and add a scenario for this case: no tag on origin, `v0.3.0` only local (its push failed), 0.3.1 merged. `untagged` lists 0.3.0 then 0.3.1, and publish of 0.3.1 exits non-zero naming 0.3.0. An alternative that meets the same goal is to anchor on the latest version tagged locally or on origin rather than only published, but the rule must leave no local-only tag unlisted.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1 / RC1 (close and the new `untagged`):** fixed. specs/project-planning/spec.md "Close offers untagged releases" now lists what `release.sh untagged` lists, run fenced, with published meaning the tag is on origin (a local tag with no origin remote); the scenarios "Versions left untagged", "Everything tagged" and "No tag yet" are reworded in terms of origin. design.md D8 says all three callers run `untagged` fenced (ADR 0008). skills/specwright-roadmap/SKILL.md close step 3b runs `[as] bash <specwright-release>/scripts/release.sh untagged --main <ref>`.
- **M2 / RC2 (a local-only tag is always listed):** fixed. `untagged_since_latest` (release.sh) adds every version whose tag is local but not on origin, whatever the anchor, and `refuse_older_untagged` uses the same list, so publish of a higher version stops naming it. releases spec "Older untagged versions are published first" states it; "Tag push failed earlier" now has `v0.4.2` on origin, and the new scenario "First release's tag push failed" covers v0.3.0 local-only with 0.3.1 merged (eval `test_first_release_push_failed`). D9 updated.
- **S1:** fixed. `WorkTree.files` refuses a match whose realpath lies outside the repository; new scenario "Glob through a symlink outside the repository" and eval `test_symlinked_directory_outside_refused`; D7 updated.
- **S2:** fixed. The Failure table, Resource Bounds and Flow & State Gaps rows now say "published"; the path requirement now says it stops the run before any write (status and publish read commit trees, which cannot hold a path outside the repository).
- **S3:** fixed. Flow & State Gaps entry "`finish: local` offline".
