# Tasks

## Test map

Script tests live in `evals/release/test_release.py` (unittest; temporary git repos with a local bare `origin`, and the fake `gh` from `evals/fakes/gh.py` extended with `release view/create`, following the `evals/pr-pair` fixtures). Skill-text tests live in `evals/release/test_skill_text.py`. Graded agent evals go in `evals/git-workflow/evals.json` with their grader checks in `grade.py`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| releases → Releases are opt-in | Enabled project | evals/release/test_release.py | TestOptIn.test_enabled_runs | green |
| releases → Releases are opt-in | Missing release block | evals/release/test_release.py | TestOptIn.test_missing_block_refuses | green |
| releases → Version files agree before any write | All files agree | evals/release/test_release.py | TestCheck.test_all_agree | green |
| releases → Version files agree before any write | One file disagrees | evals/release/test_release.py | TestCheck.test_one_disagrees | green |
| releases → Version files agree before any write | A pattern matches nothing or twice | evals/release/test_release.py | TestCheck.test_zero_or_two_matches | green |
| releases → Version files agree before any write | Backfill checks the release commit | evals/release/test_release.py | TestCheck.test_status_reads_release_commit | green |
| releases → Version files agree before any write | A glob matches no file | evals/release/test_release.py | TestCheck.test_empty_glob | green |
| releases → Bump writes one commit across the version files | Minor bump | evals/release/test_release.py | TestBump.test_minor_bump_rewrites_only_versions | green |
| releases → Bump writes one commit across the version files | Target not greater | evals/release/test_release.py | TestBump.test_target_not_greater | green |
| releases → Bump writes one commit across the version files | Interrupted bump is completed | evals/release/test_release.py | TestBump.test_interrupted_bump_completes | green |
| releases → Bump writes one commit across the version files | Malformed target | evals/release/test_release.py | TestBump.test_malformed_target | green |
| releases → The release commit is found on main | Squash-merged change | evals/release/test_release.py | TestReleaseCommit.test_squash | green |
| releases → The release commit is found on main | Merge-commit change | evals/release/test_release.py | TestReleaseCommit.test_merge_commit | green |
| releases → The release commit is found on main | Version not on main | evals/release/test_release.py | TestReleaseCommit.test_not_on_main | green |
| releases → Rebase-merged releases are refused | Rebase-merged bump | evals/release/test_release.py | TestReleaseCommit.test_rebase_commit_refused | green |
| releases → Rebase-merged releases are refused | Rebase merge method configured | evals/release/test_release.py | TestOptIn.test_rebase_method_refused | green |
| releases → Notes list the changes merged since the previous release | One change in the range | evals/release/test_release.py | TestNotes.test_one_change | green |
| releases → Notes list the changes merged since the previous release | Several changes in the range | evals/release/test_release.py | TestNotes.test_several_changes_in_order | green |
| releases → Notes list the changes merged since the previous release | No change in the range | evals/release/test_release.py | TestNotes.test_empty_range | green |
| releases → Notes list the changes merged since the previous release | Backfill with no earlier tag | evals/release/test_release.py | TestNotes.test_backfill_no_tag; TestThisRepo.test_backfill_ranges | green |
| releases → Store-backed notes use the code-merge proof | Code PR merged in the range | evals/release/test_release.py | TestStoreNotes.test_merged_pr_in_range | green |
| releases → Store-backed notes use the code-merge proof | Code still pending | evals/release/test_release.py | TestStoreNotes.test_pending_left_out | green |
| releases → Store-backed notes use the code-merge proof | PR discovery fails | evals/release/test_release.py | TestStoreNotes.test_discovery_failure_stops | green |
| releases → Publish creates and pushes an annotated tag | New release | evals/release/test_release.py | TestPublish.test_new_release | green |
| releases → Publish creates and pushes an annotated tag | Push refused by the fence | evals/release/test_release.py | TestPublish.test_push_failure | green |
| releases → Publish creates and pushes an annotated tag | Store-backed project | evals/release/test_release.py | TestStoreNotes.test_store_not_tagged | green |
| releases → Older untagged versions are published first | Older version untagged | evals/release/test_release.py | TestUntagged.test_older_blocks_newer | green |
| releases → Older untagged versions are published first | Backfill below the latest tag | evals/release/test_release.py | TestUntagged.test_backfill_below_latest | green |
| releases → Re-runs never move a published tag | Re-run after an interrupted publish | evals/release/test_release.py | TestPublish.test_rerun_creates_only_release | green |
| releases → Re-runs never move a published tag | Tag only on origin | evals/release/test_release.py | TestPublish.test_origin_only_tag_fetched | green |
| releases → Re-runs never move a published tag | Tag on another commit | evals/release/test_release.py | TestPublish.test_conflicting_tag_stops | green |
| releases → Re-runs never move a published tag | Remote tags unreadable | evals/release/test_release.py | TestPublish.test_ls_remote_failure | green |
| releases → The GitHub release is optional and created once | Release created | evals/release/test_release.py | TestGithubRelease.test_created_with_tag_message | green |
| releases → The GitHub release is optional and created once | Release already exists | evals/release/test_release.py | TestGithubRelease.test_existing_left_alone | green |
| releases → The GitHub release is optional and created once | Release creation fails | evals/release/test_release.py | TestGithubRelease.test_create_failure_resumable | green |
| change-finish → Finish offers a release once the change is on main | Untagged version after a PR merge | evals/git-workflow/evals.json | eval-finish-release-offer | green |
| change-finish → Finish offers a release once the change is on main | Auto release | evals/git-workflow/evals.json | eval-finish-release-auto | green |
| change-finish → Finish offers a release once the change is on main | An earlier version was left untagged | evals/release/test_skill_text.py | TestFinishText.test_offers_untagged_oldest_first | green |
| change-finish → Finish offers a release once the change is on main | Version already tagged | evals/release/test_skill_text.py | TestFinishText.test_no_offer_when_untagged_empty | green |
| change-finish → Finish offers a release once the change is on main | Releases disabled | evals/git-workflow/evals.json | eval-finish-release-disabled | green |
| change-finish → Finish offers a release once the change is on main | Auto publish fails | evals/release/test_skill_text.py | TestFinishText.test_publish_failure_keeps_roadmap_offer | green |
| change-finish → Local finish publishes no tag without a push decision | Local merge with auto release | evals/git-workflow/evals.json | eval-finish-local-release-reported | green |
| change-finish → Local finish publishes no tag without a push decision | Local merge after main was pushed | evals/release/test_release.py | TestReleaseCommit.test_local_merge_commit_after_push | green |
| pr-merge → Watch offers a release after an agent merge | Unattended agent merge with auto release | evals/git-workflow/evals.json | eval-agent-merge-release-auto | green |
| pr-merge → Watch offers a release after an agent merge | Offer without auto | evals/release/test_skill_text.py | TestWatchText.test_offer_without_auto | green |
| pr-merge → Watch offers a release after an agent merge | An earlier version was left untagged | evals/release/test_skill_text.py | TestWatchText.test_untagged_oldest_first | green |
| pr-merge → Watch offers a release after an agent merge | Cleanup stopped | evals/release/test_skill_text.py | TestWatchText.test_release_only_after_cleanup | green |
| pr-merge → Watch offers a release after an agent merge | Publish fails after the merge | evals/release/test_skill_text.py | TestWatchText.test_publish_failure_reported | green |
| project-planning → Close offers untagged releases | Versions left untagged | evals/release/test_release.py | TestUntagged.test_lists_since_latest_tag | green |
| project-planning → Close offers untagged releases | Everything tagged | evals/release/test_release.py | TestUntagged.test_all_tagged_empty | green |
| project-planning → Close offers untagged releases | No tag yet | evals/release/test_release.py | TestUntagged.test_no_tag_current_only | green |
| project-planning → Close offers untagged releases | User declines | evals/release/test_skill_text.py | TestCloseText.test_offer_needs_yes_and_never_blocks | green |
| project-planning → Close offers untagged releases | Releases disabled | evals/release/test_skill_text.py | TestCloseText.test_disabled_no_offer | green |

## 1. ADR and architecture

- [x] 1.1 Write `docs/adr/0010-releases-are-annotated-tags-never-moved.md` (MADR-short, `Status: accepted`, today's date). It covers D2, D3, D5 and D6 from design.md: the bump is a reviewed task, the release commit is the first first-parent main commit reading V, rebase merges are refused, a tag is created once and never moved, deleted or force-pushed, and only the code repo is tagged. Each decision has its rejected alternative and reversal cost. Update `openspec/architecture.md`: add a component row and diagram node for `specwright-release`, state rows for tags and GitHub releases, a Boundaries line for `release:` settings and tag format, a resource-bounds row for publish, the T1 count, and the 0010 row in the in-force index. Verify that `grep -n "0010" openspec/architecture.md` shows the index row and that the ADR has a Status, Date, Context, Decision and Consequences.

## 2. release.sh: settings, check and bump

- [x] 2.1 Create `evals/release/` with a `fixtures.py` that builds a temp repo with version files, a local bare `origin` and helpers for squash, merge-commit and rebase-style histories. Write failing tests for `TestOptIn` (all three) and `TestCheck` (all five), and verify they fail because `skills/specwright-release/scripts/release.sh` does not exist.
- [x] 2.2 Implement `release.sh` (a bash entry with a Python standard-library body, like `pr-pair.sh`; copy the YAML subset reader from `pr-pair.sh:287-409`).
  - Settings: `release.enabled`, `version_files`, `tag`, `github_release`, `auto`, and the refusal of `pr.merge_method: rebase`.
  - JSON output and exit codes per design D9.
  - `check` reads the working tree. The release-commit reader uses `ls-tree` and `show`.

  Verify that `TestOptIn` and `TestCheck` pass and flip their rows green.
- [x] 2.3 Write failing `TestBump` tests (all four), then implement `bump --to` (semver compare, per-file temp and rename, completion of an interrupted bump per D7). Verify `python -m unittest evals.release.test_release -k TestBump` passes and flip the rows green.

## 3. release.sh: release commit, notes, untagged

- [x] 3.1 Write failing `TestReleaseCommit` tests (all five, including `test_local_merge_commit_after_push` and `test_rebase_commit_refused`), then implement `status --version --main`. The release commit is the first first-parent commit reading V; it must be a merge or `(#n)` commit; the agreement check runs at that commit. Verify the tests pass and flip the rows green.
- [x] 3.2 Write failing `TestNotes` tests (all four), then implement repo-local notes per D4: the archive set difference, the first sentence of Why clipped at 300 characters, the PR number from the subject, first-parent order, the previous release by the tagged lower version else the value before V, and the entry cap from the design's Resource Bounds. Verify the tests pass and flip the rows green.
- [x] 3.3 Write failing `TestUntagged` tests (all five), then implement `untagged` and publish's older-untagged refusal. Verify the tests pass and flip the rows green.
- [x] 3.4 Write failing `TestStoreNotes` tests (all four), with a store repo fixture and the fake `gh` `pulls` listing. Then implement store-backed notes per D5: candidates from the store's main archive excluding `code_changes: none`, proof by a `merge: <name>` subject or a merged PR's `merge_commit_sha` in range, a failed discovery as exit 3, and no store tag. Verify the tests pass and flip the rows green.

## 4. release.sh: publish

- [x] 4.1 Extend `evals/fakes/gh.py` with `release view <tag>` and `release create <tag> --verify-tag --title --notes-file`, with failure injection like its other commands. Add cases to `evals/pr-pair/test_fake_gh.py`. Verify `python -m unittest discover evals/pr-pair` passes.
- [x] 4.2 Write failing `TestPublish` (all five) and `TestGithubRelease` (all three) tests, then implement `publish` per D6: the `ls-remote` check, the conflict stop, fetching an origin-only tag, `tag -a` with the notes, a push of only `refs/tags/<tag>`, and `gh release create` with the tag's message. Every step is skipped when already done. Verify the tests pass and flip the rows green.
- [x] 4.3 Add `TestThisRepo.test_backfill_ranges`, which runs `status` on this repository for 0.4.1 and 0.4.2. It asserts release commits `9b33ec5` and `4f9b823`, notes `fix-m2-gaps` (#89) and `pin-openspec-version` (#90), and that the agreement check passes at both commits. The test skips when the history is shallow. Verify it passes.

## 5. specwright-release skill and callers

- [x] 5.1 Write failing tests in `evals/release/test_skill_text.py` for `TestFinishText`, `TestWatchText` and `TestCloseText` (all nine rows). They also check that the schema's tasks instruction requires the bump task when `release.enabled` is true (review S2). Verify they fail.
- [x] 5.2 Write `skills/specwright-release/SKILL.md` (`metadata.version` 0.5.0).
  - Triggers: release, tag, publish, backfill.
  - **bump**: run as a task.
  - **publish**: a fenced fetch of main, then `[as] bash scripts/release.sh publish`, oldest-first order, and commit-identity rules for the tagger.
  - Report lines.
  - Stop conditions for every exit 1 and exit 3.
- [x] 5.3 Edit `skills/specwright-finish/SKILL.md` (release offer before the roadmap offer, using `untagged`, auto oldest first; local mode reports and never publishes), `skills/specwright-pr/SKILL.md` (after agent-merge cleanup, before **Next step**) and `skills/specwright-roadmap/SKILL.md` (close lists `untagged` and offers each with a yes; never blocks close). Edit `schemas/specwright/schema.yaml`: the tasks instruction requires the bump task in the last group when `release.enabled` is true. Verify that `test_skill_text.py` passes, flip the rows green, and run `openspec schema validate specwright`.
- [x] 5.4 Add graded agent evals `eval-finish-release-offer`, `eval-finish-release-auto`, `eval-finish-release-disabled`, `eval-finish-local-release-reported` and `eval-agent-merge-release-auto` to `evals/git-workflow/evals.json`, with grader checks in `grade.py` and grader tests in `test_grade.py`. Run them against the installed skills (re-install first) and flip the rows green when they pass.

## 6. Settings and docs

- [x] 6.1 Add the `release:` block to `templates/openspec/specwright.yaml`, commented, with safe defaults (`enabled: false`, `auto: false`, `github_release: true`, `tag: "v{version}"`, a `version_files` example). Enable it in `openspec/specwright.yaml` with this repo's files: `VERSION: '^(\d+\.\d+\.\d+)$'`, the README badge, and `"skills/*/SKILL.md": '^  version: (\S+)$'`. Verify that `release.sh check` in this repo reports all ten files at the current version, and that the install-update template-key test still passes (`python -m unittest discover evals/git-workflow`).
- [x] 6.2 Add `TestVersionFiles.test_repo_version_files_agree` to `evals/release/test_release.py`. It runs `release.sh check` on this repo, so drift in any of the ten files fails the suite. Verify it passes.
- [x] 6.3 Update `README.md`: the skill tables gain a row for `specwright-release`, the Settings block gains `release:`, add a Releases note, and add `evals/release` to the Evals section. Update `CONTRIBUTING.md`: Releases replaces the manual three-file bump with `release.sh bump` and `publish`, and Testing names `python -m unittest discover evals/release`. Verify with `grep -n "specwright-release\|release:" README.md CONTRIBUTING.md`.

## 7. Release 0.5.0 bump and integration

- [x] 7.1 Bump to 0.5.0 with `bash skills/specwright-release/scripts/release.sh bump --to 0.5.0`. Verify that `release.sh check` reports 0.5.0 across all ten files and that `grep -rn '0\.4\.2' VERSION README.md skills/*/SKILL.md` has no version-file hits. Update the hard-coded `0.4.2` fixture in `evals/git-workflow/test_grade.py:363-364` only if it reads `VERSION`.
- [ ] 7.2 Run the full suites: `python -m unittest discover evals/release`, `python -m unittest discover evals/pr-pair`, `python -m unittest discover evals/review-routes` and `python -m unittest discover evals/git-workflow`, plus `openspec schema validate specwright` and `openspec validate add-release-workflow --strict`. All must pass.

## Workflow follow-up

- After the PR merges, re-run the install prompt so the installed copies include `specwright-release`.
- Publish 0.5.0 (no tags exist, so `untagged` lists only 0.5.0). Then backfill oldest first: `publish --version 0.4.1`, then `publish --version 0.4.2`, each with a GitHub release.
- Check with `git ls-remote --tags origin` and `gh release list` that `v0.4.1`, `v0.4.2` and `v0.5.0` exist at `9b33ec5`, `4f9b823` and the 0.5.0 merge commit.
