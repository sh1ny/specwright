# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (Required Changes 1-4 only):** fresh-context subagent (specwright-reviewer, Claude Code harness), a separate run from round 1. Read review.md, design.md and the four delta specs, plus skills/specwright-finish/SKILL.md:72 (local merge uses `git merge --no-ff`, so a local `merge: <change>` release commit has two parents and passes the RC1 check). All four items are applied:
  - RC1 (option b): D3 drops rebase from the "works for" claim and adds "Rebase merges are refused" (settings refusal, plus the single-parent, no `(#<n>)` stop naming the commit); releases spec adds "Rebase-merged releases are refused" with two scenarios; Failure table row "Release commit check" and Flow & State Gaps "Rebase merge" added. The backfill commits pass the check (9b33ec5 is a merge commit, 4f9b823's subject ends in `(#90)`).
  - RC2 (first option): change-finish and pr-merge read `release.sh untagged`, offer or auto-publish oldest first and stop at the first failure, each with an "An earlier version was left untagged" scenario (0.5.0 then 0.5.1). D8 matches, and the new releases requirement "Older untagged versions are published first" makes publish refuse a newer version while a lower one on the list is untagged, so the skip in M1 can no longer happen through the scripts.
  - RC3: the releases requirement "Version files agree before any write" and D7 state that bump and check read the working tree, while status and publish read V's release commit (`git ls-tree -r --name-only <c>`, `git show <c>:<path>`, current `version_files`) and stop unless the shared version there is V; scenario "Backfill checks the release commit" (0.4.1 from a 0.5.0 checkout, read at 9b33ec5) added.
  - RC4: D6 step 2 fetches an origin-only tag through `as.sh` and never creates a second tag object; D6 step 4 and the requirement "The GitHub release is optional and created once" use the tag's message as the body, never re-derived notes, which matches the State table Notes row; scenario "Tag only on origin" added. Residual note, not blocking: in the Failure table's two-sessions race the losing session still holds its own local tag object (same commit; `%(contents)` is the same because notes come from the same commit range), so only the tag object id differs from origin's.
  - Edits outside RC1-4 (S1, S3, S4, S5) apply round-1 Suggestions and do not change the reviewed decisions; they do not void the verdict.
- **Reviewed:** proposal.md; design.md; specs/releases/spec.md, specs/change-finish/spec.md, specs/pr-merge/spec.md, specs/project-planning/spec.md; openspec/architecture.md (in-force ADR index); openspec/roadmap.md (M3); CONTRIBUTING.md (Releases); README.md (badge, install Step 4); skills/specwright-finish/SKILL.md (local, pr, roadmap offer); skills/specwright-pr/SKILL.md (watch merge, Cleanup after merge, Next step); skills/specwright-roadmap/SKILL.md (close); skills/specwright-review/SKILL.md (Gate) and scripts/review-run.sh (`archive_only`); skills/specwright-pr/scripts/pr-pair.sh (YAML reader, `merge_method`, `merge`, `norm_pr`/`discover`) and as.sh (header); evals/review-routes/test_skill_text.py; GitHub issue #28. Read-only git checks on main: first-parent history of `VERSION`, archive directory sets at 65fbb41, f4f3f28, 9b33ec5 and 4f9b823, and the version lines of every version file at 9b33ec5 and 4f9b823.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

Verified against the code: the design's citations hold (finish :72-73, :83, :85; pr :159; roadmap close :67-81; review gate :71-72; `archive_only` at review-run.sh:1156; `merge_commit_sha` at pr-pair.sh:2101-2102 and its absence from `norm_pr`; CONTRIBUTING.md:49; README install Step 4; test_skill_text.py:48-51). `git log --first-parent main -- VERSION` gives 4f9b823 (0.4.2), 9b33ec5 (0.4.1), 65fbb41 (0.4.0), as D3 states. The archive set differences match the notes scenarios exactly: (65fbb41, 9b33ec5] adds only `2026-10-15-fix-m2-gaps` (f4f3f28 `docs/close-m2` adds none), and (9b33ec5, 4f9b823] adds only `2026-10-15-pin-openspec-version`. At both backfill commits all nine version files agree (0.4.1 and 0.4.2), and each `skills/*/SKILL.md` has exactly one `^  version:` line, so the planned regexes will match once.

## Findings

### Critical (blocking)

**C1. Rebase merges put the tag on the wrong commit and drop the release's own change from its notes.** `pr.merge_method: rebase` is a supported setting (pr-pair.sh:570-573, :2080), and a user merging on GitHub can pick it whatever the setting says. D3 claims its rule "works for squash merges, merge commits, user merges and backfill alike", but rebase merges are not covered. A rebase merge replays the branch's commits onto main's first-parent line one by one. The first first-parent commit that reads V is then the replayed bump task commit (`<type>(<change>): task X.Y bump to V`). Commits after it in the same change are not in the tag: later commits of the last task group, fix rounds after the pre-ship review, and the archive commit. Consequences:
- The tag names a tree that lacks part of the reviewed change. Under D6's never-move rule that is permanent, and #36 will install from it.
- D4's range `(prev, release]` ends before the archive commit, so V's notes leave out the change that cut V. That change shows up in V+1's notes instead.
- The release commit's subject carries no `(#n)`, so no PR number is shown.

The Failure table, Flow & State Gaps and the specs have no scenario for this case. See Required Change 1.

### Moderate

**M1. An older untagged version disappears from every later offer once a newer one is published.** The finish and watch specs check only "main's version" (change-finish, "Finish offers a release..."; pr-merge, "Watch offers a release..."). D8 likewise says "If the current version has no tag". But `untagged` and close list only versions "since the latest tag" (D9; project-planning, "Close offers untagged releases"). Example: 0.5.0 is merged and its offer declined, or its auto publish fails at the push and nobody re-runs it. 0.5.1 then merges, and finish or watch offers 0.5.1 only (or auto-publishes it). Once `v0.5.1` exists it is the latest tag, so `untagged` and close never list 0.5.0 again. 0.5.1's notes absorbed 0.5.0's changes, and notes are never rebuilt (State table). The design's own rule, "the skill publishes oldest first when several are untagged" (Flow & State Gaps), is not in any spec, and the callers named by the specs would break it. The result is a silent gap in the tag series that only someone running `publish --version 0.5.0` by hand would close. That conflicts with the M3 criterion that every release has a tag and notes. See Required Change 2.

**M2. Nothing says which tree publish reads for the agreement check, and the backfill depends on it.** The releases requirement "Version files agree before any write" applies "before bump or publish uses a version", but neither it nor D7 or D9 says which tree publish checks. The cases that need an answer:
- For `publish --version 0.4.1` run from a 0.5.0 checkout, the working tree agrees on 0.5.0, which is not V. A literal reading stops, or leaves the outcome to the implementer.
- `release.version_files` does not exist at 9b33ec5 or 4f9b823.
- The glob `skills/*/SKILL.md` matches eight files at HEAD but seven at those commits.
- Publish also runs from finish or watch right after cleanup. If the working tree is the release commit's tree only by coincidence, a dirty or moved checkout gives a wrong stop or a wrong pass.

The backfill of 0.4.1 and 0.4.2 is an M3 exit criterion, so this has to be pinned. Both commits pass when the check runs at the release commit (verified above). See Required Change 3.

**M3. A tag that is on origin but not local gets a second, different tag object, and the source of the release notes is contradictory.** D6 step 2 creates `git tag -a <tag> -F <notes>` whenever the local tag is absent, even when step 1 found the tag on origin at the right commit. That happens on a fresh clone, on another machine, and for the losing session in the Failure table's "Two sessions publish V at once" row. The local annotated tag then has a different object id from origin's: a different tagger date, and possibly different notes if the archive moved. Origin's tag is never replaced, so the local clone disagrees with origin for that name (the two `ls-remote` and `rev-parse <tag>` values differ). The GitHub release text is also contradictory:
- D6 step 4 creates the release with `--notes-file <notes>`, freshly derived.
- The State table says "a re-run reuses the existing tag's message for the release".
- The releases spec says the release has "the same notes" as the tag, and the scenario "Re-run after an interrupted publish" relies on that.

With a fresh derivation, a re-run on another machine can publish a release body that differs from the tag annotation. See Required Change 4.

### Suggestions

- S1. releases spec, "Remote tags unreadable": the WHEN says "the fetch of origin's tags fails", but D6 step 1 uses `git ls-remote`. Name the call the design makes so the eval asserts the right failure.
- S2. Add a scenario for the schema side of D2: with `release.enabled` true, the tasks instruction puts a `release.sh bump --to <version>` task in the last group, and with it false the instruction has no bump task. Right now only the proposal's Impact covers it, and an eval in `evals/git-workflow` can pin it.
- S3. The Mechanism Ledger says "only one of nine files is checked". After this change there are eight `skills/*/SKILL.md` files, so ten version files. Update the count, and include `skills/specwright-release/SKILL.md` in the repo's own agreement test.
- S4. Have tasks.md fix the order for this repo's releases: backfill 0.4.1, then 0.4.2, then 0.5.0, or 0.5.0 first. All of these give per-version notes. Publishing 0.4.1, then 0.5.0, then 0.4.2 folds `pin-openspec-version` into 0.5.0's notes permanently.
- S5. Two changes in flight that both target the same next version (both bump 0.4.2 to 0.5.0 on their branches) are not covered. The second merge either conflicts in every version file or lands with no bump, and re-bumping after the pre-ship review voids its pass (D2). One Flow & State Gaps line on the expected handling would help, for example: rebase the branch, re-run bump, and accept the new pre-ship review.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **Rebase merges (C1).** In design.md D3 and in specs/releases/spec.md "The release commit is found on main", define the release commit for a rebase-merged PR and add a scenario for it. Pick one of these options:
   - (a) Resolve the first V commit to its PR with `[as] gh api repos/<o>/<r>/commits/<sha>/pulls`. If that PR was rebase-merged, take its `merge_commit_sha` (for a rebase merge, the last replayed commit), check that it is on first-parent main and still reads V, and use it as the release commit.
   - (b) Refuse. `release.enabled: true` with `pr.merge_method: rebase` is a bad setting. Publish also stops before any write, naming the commit, when the first V commit is a non-merge commit whose subject is a Specwright task subject rather than a squash `(#n)` or `merge: <change>` subject.

   Either way, add the matching rows to the Failure table and Flow & State Gaps, and correct D3's "works for ... alike" claim.
2. **Older untagged versions (M1).** In specs/change-finish/spec.md and specs/pr-merge/spec.md, have finish and watch use `release.sh untagged`, not only main's current version. They offer every untagged version oldest first, and with `release.auto` they publish oldest first, stopping at the first failure. Add a scenario: 0.5.0 untagged and 0.5.1 merged leads to an offer of 0.5.0 then 0.5.1. Alternatively, define `untagged` and close in D9 and specs/project-planning/spec.md as listing every version in the primary file's first-parent history that has no tag, not only those after the latest tag, and say how the backfill-only history before the first tag is excluded. Update D8 to match.
3. **Agreement check tree (M2).** In design.md D7/D9 and the releases requirement "Version files agree before any write", state that bump and `check` read the working tree, and that publish and status read V's release commit: globs via `git ls-tree -r --name-only <c>`, contents via `git show <c>:<path>`, using the current `release.version_files`. Publish stops when the shared version there is not V. Add a scenario: backfill of 0.4.1 from a checkout at 0.5.0 passes the check at 9b33ec5.
4. **Remote-only tag and notes source (M3).** In design.md D6 step 2, when the tag is on origin at the release commit but absent locally, fetch it (`git fetch origin refs/tags/<tag>:refs/tags/<tag>`, through `as.sh`) instead of creating a new tag object. In D6 step 4 and the releases requirement "The GitHub release is optional and created once", state that the GitHub release body is the existing tag's message (origin's when present), never a fresh derivation, so it matches the State table. Add a scenario: the tag is on origin, there is no local tag and no release, and publish fetches the tag, creates no tag object, and creates the release with origin's tag message.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

- **C1 / RC1 (rebase merges):** fixed, option (b). New releases requirement "Rebase-merged releases are refused" (two scenarios); design D3 "Rebase merges are refused" with the rejected PR lookup, the "works for ... alike" claim corrected, plus a Failure-table row and a Flow & State Gaps entry.
- **M1 / RC2 (older untagged versions):** fixed, first option. change-finish and pr-merge read `release.sh untagged`, offer or auto-publish oldest first and stop at the first failure (new scenarios "An earlier version was left untagged"). New releases requirement "Older untagged versions are published first": publish refuses while a lower version after the latest tag is untagged, and backfill below the latest tag is not blocked. D8 and D9 (`untagged`, and the history before the first tag offered only on request) updated, plus a Failure-table row.
- **M2 / RC3 (agreement check tree):** fixed. The releases requirement "Version files agree before any write" says bump and check read the working tree, while status and publish read V's release commit; new scenario "Backfill checks the release commit". D7 names the `ls-tree` and `show` reads.
- **M3 / RC4 (remote-only tag, notes source):** fixed. D6 step 2 fetches an origin-only tag, and step 4 always uses the tag's message as the body. The releases requirements "Re-runs never move a published tag" (new scenario "Tag only on origin") and "The GitHub release is optional and created once" are updated, as is the Notes row in the State table.
- **S1:** fixed (the scenario says `ls-remote`). **S3:** fixed (ten files, Context). **S4:** addressed in Flow & State Gaps ("Backfill order"); tasks run backfill oldest first. **S5:** addressed in Flow & State Gaps (two changes bumping to the same version). **S2:** taken into tasks (the schema text test for the bump task).
