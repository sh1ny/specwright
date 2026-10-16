# Review

## Metadata

- **Round:** 3
- **Prior round:** 2. APPROVE_WITH_CHANGES with RC1-RC2: roadmap close runs the new `untagged` fenced and uses the published definition, and a local-only tag is always listed. Both were applied and re-checked (`CHANGES_APPLIED: yes`). This round reviews the PR #92 feedback amendments made after that verdict, all uncommitted: the git < 2.31 history pass (Kody), the lost push race (Codex P1) and the in-repo symlinked version file (Codex P2).
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness)
- **Re-check run (Required Change 1, S1-S2):** fresh-context subagent (specwright-reviewer, Claude Code harness), after the author's edits. I read the Rebuttals and `git diff -- openspec skills evals`: `WorkTree.files`, `CommitTree.names`/`files`, the `cmd_bump` revert, the `tag_push_failed` message, the new requirement "Version files are not symlinks", the "Push refused by the fence" scenario, D7, the state diagram, the Failure table and the SKILL.md Stops table. I ran `-k symlink -k outside -k lost_push_race -k glob_primary`: 7 passed. RC1 is applied with option (b):
  - **RC1.** `WorkTree.files` refuses a match whose realpath differs from its own path under the resolved root, which covers a file link and a linked directory, before any read or write. `CommitTree` reads `ls-tree` modes and refuses a mode-120000 match at the commit. `cmd_bump` writes `os.path.join(root, f)` again. The spec, D7 and the Stops table all state the refusal, so `check`/`bump` and `status`/`publish` now agree that a symlinked entry is invalid.
  - **S1** is fixed: the push-failure scenario, the message, the state diagram, the push row, the race row and the new "`publish` tag objects" row all name `tag_mismatch`. The author's reason for not adding the optional pointer from the tag requirement (the 500-character limit) is accepted. **S2** is moot.
  - **Residual note, not blocking.** When the primary entry itself is a link at a commit, `primary_history` reads it through `cat_batch`, not `CommitTree.files`. `status` then stops with `no_release_commit`, which does not name the link. It still stops, and `check`/`bump` refuse the link before such a bump commit can exist, so the gap is only in the message.
  - The edits outside RC1 apply this round's Suggestions and do not change the reviewed decisions, so they do not void the verdict.
- **Reviewed:** review.md (round 2); the amendment diff (`git diff -- openspec skills evals`), covering design.md D6 step 1 and D7, specs/releases/spec.md ("Version file paths stay inside the repository", the new "A release uses the tag on origin"), skills/specwright-release/SKILL.md Stops, release.sh and evals/release/test_release.py. In release.sh I read `inside`, `WorkTree.files`/`read_all`, `CommitTree.files`/`read_all`, `cat_batch`, `cmd_bump`, `primary_history`, `remote_tag`, `status_doc` and `cmd_publish`. I also read specs/releases/spec.md in full for contradictions (push-failure scenario :149-150, tag requirement :176), design.md (state diagram :143, Failure table :182), and docs/adr/0010 (D6 summary); ADR 0008 is unchanged by this diff, which adds no network call. Runs: `-k glob_primary_merge_diffs -k symlinked_version_file -k lost_push_race -k conflicting_tag -k lightweight` passed 5 of 5 on git 2.55.0.windows.4, symlinks enabled, so the symlink test was not skipped. I also ran a scratch probe outside the repo: commit an in-repo symlink `pkg/VERSION -> ../VERSION`, bump, commit, then `status` (result under M1).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

What holds:
- **Item 1 (history pass).** `git -c log.diffMerges=first-parent log -m --first-parent --name-status` is right on both sides of 2.31. On older git, `-m --first-parent` diffs merges against the first parent only, and git ignores the unknown key. On 2.31+, `-m` takes `log.diffMerges`, and the `-c` overrides a user's `combined`. The eval sets `combined` and passes. D7 states it accurately.
- **Item 2 (lost push race).** `remote_tag` returns the ls-remote ref object, which is the tag object for an annotated tag. `status_doc` adds `tag_object.local` from `rev-parse refs/tags/<tag>`. `cmd_publish` checks for a mismatch after `tag_conflict` and `lightweight_tag`, so both sides are known to be annotated at the release commit, and it stops before the fetch, tag, push or `gh` write. With no origin, `no_origin` stops earlier. This is consistent with ADR 0010: the user deletes the tag by hand, and Specwright never deletes one.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. A symlinked version file now gets bumped, but `status` and `publish` cannot read it at the release commit, so that version can never be published.**
- **What the amendment adds.** The new spec sentence and the scenario "Symlink inside the repository" make an in-repo symlink entry a supported setup. `cmd_bump` writes through `os.path.realpath`, and `check` and bump read the working tree, where the link is followed.
- **Why the release side fails.** `status` and `publish` read the release commit through `CommitTree` (release.sh:427-450). It uses `git ls-tree --name-only` and `cat-file --batch` on `<commit>:<path>`. For a link, git stores a mode-120000 blob whose content is the link text (`../VERSION`), not the target's content.
- **Probe result.** With `version_files` `{VERSION, pkg/VERSION}` and `pkg/VERSION -> ../VERSION` committed:
  - `check` passes and bump to 0.5.0 succeeds.
  - After the commit, `status --version 0.5.0` exits 1: `version_files_invalid: version files are not readable in commit ...: pkg/VERSION: pattern ... matches 0 times`.
- **Primary file.** The same applies through `primary_history` (literal and glob paths both use `cat_batch`). A symlinked primary file reads no version at any commit, so no release commit is ever found.
- **Effect.** The spec promises something only half the subcommands honour. A project using the setup Codex P2 described passes `check` on every change and then fails at publish, after merge, on the version already on main. `test_symlinked_version_file_written_through` checks only bump and check, so it does not catch this. See Required Change 1.

### Suggestions

- **S1. The push-failure text is wrong after a lost race.** The spec "Tag push failed" scenario (specs/releases/spec.md:149-150), the `tag_push_failed` message in `cmd_publish`, the design state diagram (`LocalTagged --> ... re-run resumes`, :143) and the Failure table row "`publish` push" (:182) all say "a re-run pushes it". When the push failed because another clone's tag reached origin first, the re-run stops with `tag_mismatch` instead. Add one Failure-table row for `tag_mismatch` (exit 1, before any write, the user deletes the local tag), and qualify "a re-run pushes it" with "unless origin now holds another tag object, in which case `tag_mismatch`". Also, the tag requirement at :176 still says "A tag that already exists on the release commit SHALL be kept and that step counted done". It would read cleaner with "(the same tag object on both sides; see 'A release uses the tag on origin')".
- **S2. Bump reports a symlink and its target as two changed files.** With both the link and its target listed, bump writes the same physical file twice and reports `changed: ["VERSION", "pkg/VERSION"]`. The bytes are identical, so the file is not harmed. If RC1 keeps the write-through, dedupe the plan by realpath, or say in D7 that `changed` lists entries, not distinct files.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **Make an in-repo symlinked version file consistent across all subcommands (M1).** Choose one:
   - **(a) Resolve links in `CommitTree`.** Read `ls-tree` modes. For a mode-120000 entry, resolve its link text against the link's directory. Refuse a result that leaves the repository or reaches a missing path, before any write, as the working tree does. Then read the target's blob, both in `read_all` and in `primary_history` (literal and glob). State this in D7 ("the commit tree follows an in-repo link the same way"). Extend the "Symlink inside the repository" scenario and its eval so that, after the bump is committed and merged, `status` and `publish` find 0.5.0 at that commit.
   - **(b) Refuse symlinked entries everywhere.** Have `WorkTree.files` stop on any matched path that is a symlink, naming it, before any write. Revert the `cmd_bump` realpath change, replace the spec sentence and scenario with that refusal, and adjust the eval.

   Either way, `check`/`bump` and `status`/`publish` must agree on whether a symlinked entry is valid.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1 / RC1 (symlinked version files):** fixed with option (b), refuse. `WorkTree.files` stops (`bad_version_files`) on a match whose realpath differs from its own path inside the repository, i.e. a file link or a linked directory; `CommitTree` reads `ls-tree -r -z` modes and stops on a mode-120000 match at the commit. The bump write-through (`os.path.realpath` in `cmd_bump`) is reverted. The spec sentence moved into a new requirement "Version files are not symlinks" whose scenario "Symlink inside the repository" now says check and bump stop and status of a commit holding the link stops; D7 states the refusal. Evals `test_symlinked_version_file_refused` (file link and directory link, check and bump, nothing changed) and `test_symlink_at_release_commit_refused` (mode 120000 committed via `update-index --cacheinfo`, status stops naming it).
- **S1:** fixed. The push-failure scenario, the `tag_push_failed` message and header comment, the state diagram and the Failure table "`publish` push" row now say a re-run pushes it or stops with `tag_mismatch` when another clone's tag reached origin first; a new Failure-table row "`publish` tag objects"; the "Two sessions publish V at once" row now describes the `tag_mismatch` path. The optional pointer from the tag requirement is not added: that requirement is already at openspec's 500-character limit, and "A release uses the tag on origin" states the rule on its own.
- **S2:** moot: symlinked entries are refused, so no file is written twice.
