# Review

## Metadata

- **Round:** 4
- **Prior round:** Round 3: APPROVE_WITH_CHANGES with no Critical, 4 Moderate findings (D14's HEAD-on-main exemption, the delete precondition reading `gitbutler.project.targetRef`, D4's call-site list missing ship step 1 and the roadmap rollback, the archive commit naming whole `<P>/changes/` and `<P>/specs/`) and 3 Suggestions. Its 8 Required Changes were re-checked and recorded as applied (CHANGES_APPLIED: yes). That pass was voided when the CI install of `but` changed from the official installer to a pinned, SHA-256-checked download, so this is a new full round.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:**
  - Change artifacts, all under `openspec/changes/add-gitbutler-backend/`: review.md (rounds 1-3), proposal.md, design.md, specs/vcs-backends/spec.md, specs/eval-runner/spec.md, specs/preship-review/spec.md and specs/github-identity/spec.md (headings), and tasks.md (checked against the design for consistency).
  - CI: `.github/workflows/evals.yml` (the whole file, including the pinned-jj step at lines 59-76), `evals/runner/test_ci_workflow.py`, `evals/suites.json`, `JJ_VERSION`.
  - Source, to check the design's citations:
    - `skills/specwright-pr/scripts/vcs.sh`: `get_settings` (132), `probe` (157-188), the Git `branch-create`, `commit` and `push` branches (407-464), `jj_fetch_main` (656-664) and `main()` (840-846).
    - `skills/specwright-pr/scripts/pr-pair.sh`: `norm_pr` and `discover` (687-708), `cmd_vcs` (755-773), `remote_contains` (1272-1276), `dirty_paths` (1635-1646), the `unrecorded_change` stop (1779-1783), `cleanup-plan` (2055-2088) and the agent-merge result (2105-2121).
    - `skills/specwright-review/scripts/review-run.sh`: `current_heads` (1244-1248), `parent_of` (1251), the after-archive lookup (1390-1398) and the `Preship-Round` count (1504-1506).
    - `skills/specwright-release/scripts/release.sh:753-759`, `skills/specwright-finish/scripts/finish.sh` (168-180, 191-199, 410-448), `skills/specwright-pr/scripts/as.sh:172-201`.
    - `skills/specwright-pr/SKILL.md:156-159` (cleanup, store-backed and repo-local, and remote branch deletion).
  - GitButler download listing: one read-only `curl -s https://app.gitbutler.com/api/downloads?channel=release` on 2026-10-30. The binary was not downloaded, and `but` was not run.
  - Project skills named in the request: none.

### Round 3 resolution check

All 8 of round 3's Required Changes are still in the artifacts as applied. The new CI text did not touch them:
- D14 and its spec requirement refuse whatever HEAD is.
- The proposal has no HEAD-on-main exemption.
- D8 reads the stored workspace base, never `gitbutler.project.targetRef`, and the matching Risk is present.
- The State row for "Local target / main" is present.
- The delete requirement and the "Pull skipped" scenario use workspace-base wording.
- D4 names the roadmap branches, ship step 1 and the branch rollback.
- The archive commit names finish's exact paths.

Round 3's Suggestions:
- S3 (the reviewer reads surrounding code with `git show <branch>:<path>`) is in task 8.2.
- S1 (the spec's narrower `clean` definition) and S2 (the scope of "never a SHA from the caller") were not applied. They remain optional and are not raised again here.

### The CI change, checked

- The listing returns the Linux x86_64 standalone `but` for 0.23.1-3317 at the URL the design gives. It returns no file checksum: each entry's `sha` field is a source commit (`d6feaf66…` for 0.23.1), not a hash of a file. Both claims hold.
- D10 mirrors the jj step's shape: `curl --fail` into `$RUNNER_TEMP`, `sha256sum --check` before use, a job-local bin directory on `GITHUB_PATH`, the `SPECWRIGHT_REQUIRE_*` flag and a `--version` check.
- `fail-fast: false` (`evals.yml:34`) keeps the other suites' jobs running when the `vcs` job's setup fails, so the spec's "Downloaded bytes differ" THEN holds.
- The existing test helper `install_run_block` finds a step by name and skips an `if:` line before `run:`, so the planned `test_workflow_checks_but_sha256_before_use` can reuse the jj test's fake-`curl` approach.

### Required Changes re-check

All 3 of round 4's Required Changes are applied as written:
- **RC1 (merge_commit_sha source).** D8 names GitHub's `merge_commit_sha`, says `norm_pr` (`pr-pair.sh:687-690`, which today lacks it) gains the field, and gives the repo-local cleanup's source and the null case. D13 step 3 adds the source and "omitted when null". Tasks 6.2 and 9.2 both carry `norm_pr`'s new field and the `--merged-commit` pass-through.
- **RC2 (download listing).** The Context "Downloads" bullet states the 10-release window, the 0.23.1-3317 to 0.20.4-3116 range and the unknown URL lifetime. The Risk "GitButler removes an old build" ends with the window and its horizon. The Open Question carries the no-evidence sentence.
- **RC3 (task 5.2).** Task 5.2 now normalizes paths with `bad_path`, stops with `nothing_to_commit`, passes paths with `--json` and never CLI IDs, and checks the parent, file set, message and other tips, matching D5 and the vcs-backends commit requirement.

The suggestion edits introduce no new inconsistency:
- S1: the Risk now says trust-on-first-use from one download, and the Context says Scoop hashes only the Windows installer.
- S2: D10 and task 2.2 set `SPECWRIGHT_REQUIRE_BUT=1` in every suite job, D10 has `test_butenv.py` clear it itself, and the eval-runner requirement says "suites with tests that need a real `but`" and "as every CI job sets". tasks.md's preamble (skip locally unless the flag is set) still holds.
- S3: D10 and task 2.2 derive the version check from `BUT_VERSION` in the step, and the Context names the `ubuntu-24.04` runner (`evals.yml:31`).
- S4: task 1.1 no longer cites "M7". Task 9.1 and the Test map share `test_feedback_pass_ignores_other_and_preexisting_paths`. D11 cites `finish.sh:433`, which is the `git cat-file --filters` line. The proposal's `delete-branch` bullet uses workspace-base wording.

Two cosmetic leftovers, not blocking and not Required Changes: in "Downloads", "For Linux x86_64 that includes the standalone CLI" now follows the "not known" sentence, so "that" has lost its antecedent (the listing). The Failure-modes row "CI `but` install" still says `but --version` "differs from `BUT_VERSION`" where D10 now says the version part of it.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. D8 and D13 depend on a squash-merge commit that no cleanup path has.**

D8 says: "for a squash merge, the `--merged-commit <sha>` is [its ancestor]. The caller already reads that commit in the merged-PR lookup." D13's GitButler plan emits `vcs.sh delete-branch --branch <b> --force --merged-commit <sha>`.

The merged-PR lookup is `pr-pair.sh discover --state merged`, which the repo-local cleanup reads at `skills/specwright-pr/SKILL.md:158`, and `cleanup-plan` uses the same PR data. Both build their PR objects with `norm_pr` (`pr-pair.sh:687-690`), which keeps only:
- `number`;
- `url`;
- `state`;
- `base`;
- `head_sha`;
- `merged_at`;
- `title`.

`merge_commit_sha` appears in exactly one place, the agent-merge result (`pr-pair.sh:2120-2121`). That result is only there when the agent merged the PR, never when the user did (`merge: user`). The repo-local cleanup's `[vcs] delete-branch --branch <branch> --force` (`SKILL.md:158`) passes no merge commit either.

Consequences:
- `cleanup-plan` cannot build D13's step 3 from the data it has.
- An implementer either adds an unreviewed field to `norm_pr`, whose output also feeds `expected` and `pair-state`, or drops `--merged-commit`.
- If the flag is dropped, a squash-merged branch that `but pull` did not remove as integrated fails the tip-ancestor test forever. Specwright then reports `left_applied`, saying the base lacks the merge when it does not.

*Fix:* name the source. The GitHub pulls payload that `norm_pr` already reads carries `merge_commit_sha`, so `norm_pr` adds it. `cleanup-plan` and the repo-local cleanup pass it as `--merged-commit` when it is not null. Required Change 1.

**M2. The design's claims about the download listing do not match the listing, and the pin's expected lifetime follows from the difference.**

The Context says: "every build stays downloadable at a versioned URL, listed by `https://app.gitbutler.com/api/downloads?channel=release` (builds back to 0.22.1-3215)". The Risk "GitButler removes an old build" ends: "Builds back to 0.22.1 are listed today."

The listing fetched on 2026-10-30 holds exactly 10 releases:
- the newest is 0.23.1-3317, released 2026-10-28;
- the oldest is 0.20.4-3116, released 2026-06-26;
- it includes 0.22.0, 0.21.x and 0.20.4, which are older than 0.22.1.

So the listing is a window of the latest 10 releases, not "every build", and the stated lower bound is wrong. The window turned over in about four months. Nothing shows whether a URL still answers once its build leaves the window. The jj pin points at a GitHub release asset, whose lifetime does not depend on later releases, so the comparison with jj does not carry over here.

Consequences:
- The Open Question ("stays at 0.23.1-3317 until a dogfood project needs newer") has an unstated horizon. When the URL stops answering, the `vcs` job fails on unrelated PRs.
- The failure is visible (`curl --fail` names the URL), but the design presents permanence as established, and nobody plans the bump.

*Fix:* state what the listing shows and carry the horizon into the Risk and the Open Question. Required Change 2.

**M3. Task 5.2 contradicts D5: it maps paths to CLI IDs and drops most of D5's checks.**

Task 5.2 says to "map paths to CLI IDs, run `but commit -b <branch> -F <msgfile> <ids>`, then verify the committed file set". The design says something different:
- D5 step 6 passes the normalized paths (`but commit -b <branch> -F <msgfile> --json <paths...>`).
- The Context records that "Short IDs change between calls, so names are the stable key."

IDs read from one `but status --json` call and passed to a second `but` call can name different objects, so this is exactly the misresolution the file-set check exists to catch. Each time it happens, `commit_mismatch` leaves a wrong commit on the branch for the user to undo.

Task 5.2 also leaves out these D5 steps, which the 5.1 tests ("Trailers kept", the parent and other-tip checks) will need:
- path normalization and `bad_path`;
- `nothing_to_commit`;
- the parent, message and other-tips checks.

*Fix:* align task 5.2 with D5. Required Change 3.

### Suggestions

- **S1. The Scoop corroboration does not cover the Linux `but`.** The Risk "The pinned hash is ours, not GitButler's" says "the same file Scoop installs". Scoop is a Windows package manager, and the listing's only Windows build is `GitButler_0.23.1_x64_en-US.msi`, so no Scoop manifest hashes the Linux ELF. The pinned hash has a single witness: the author's download on 2026-10-30. Say so plainly, for example: "The hash is trust-on-first-use from one download. Scoop hashes only the Windows installer from the same host." The decision itself still stands.
- **S2. Make a misplaced real-`but` test fail loudly in CI.** `SPECWRIGHT_REQUIRE_BUT=1` is set only in the `vcs` job. A real-`but` test added later outside `evals/vcs` would skip with `but not installed` in every CI job, and that skip "does not count as a failure". Consider exporting `SPECWRIGHT_REQUIRE_BUT=1` in every suite job while installing `but` only in `vcs`. `evals/runner/test_butenv.py` would clear the variable itself, as `test_ci_workflow.py:115` does for jj. Also reword the eval-runner requirement's "suites with GitButler tests" to "suites with tests that need a real `but`". As written, `pr-pair` (`test_as_gitbutler.py`, which uses a fake `but`) and `git-workflow` arguably match it.
- **S3. Version check and runner image.**
  - D10 derives the `but --version` check from `BUT_VERSION`, but task 2.2 hard-codes `0.23.1`. Derive it in the step, so a bump edits only `BUT_VERSION` and the hash.
  - The Context says the libraries are present on `ubuntu-latest`, but the workflow pins `ubuntu-24.04` (`evals.yml:31`). Name that image. A glibc symbol-version mismatch would surface at the `--version` check either way.
- **S4. Stale references.**
  - Task 1.1 points to "design.md M7", which does not exist.
  - Task 9.1 names `test_feedback_pass_ignores_other_and_preexisting_paths_gitbutler`, while the Test map row has `test_feedback_pass_ignores_other_and_preexisting_paths`.
  - D11 cites `finish.sh:447` for `git cat-file --filters`, but that read is at `finish.sh:199` and `433`; line 447 is `git rm -q --cached`.
  - The proposal's `delete-branch` bullet still says "once GitButler's target already holds the merge", where the spec now says the workspace base.

## Verdict

The CI change holds up against the listing and the existing jj step:
- the URL is real and versioned;
- the bytes are checked before they run;
- only the `vcs` job is affected.

The listing's description is wrong in one way that matters, though: it is a 10-release window, not a permanent archive (M2). A full pass also found that D8's squash-merge proof relies on a merge commit that none of the cleanup's GitHub reads return (M1), and that task 5.2 contradicts D5's path rule (M3). Each fix is a specific text edit, and none needs a new design decision.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **design.md D8 and D13; tasks 6.2 and 9.2:**
   - In D8, replace "The caller already reads that commit in the merged-PR lookup." with:
     > That commit is GitHub's `merge_commit_sha` for the merged PR. `pr-pair.sh`'s `norm_pr` (`pr-pair.sh:687-690`) gains `merge_commit_sha`, so `discover --state merged` and `cleanup-plan` carry it; today only the agent-merge result returns it (`pr-pair.sh:2120-2121`). The repo-local cleanup passes the `newest` merged PR's `merge_commit_sha`. When it is null, the delete judges the tip alone.
   - In D13 step 3, after `--merged-commit <sha>`, add "(the PR's `merge_commit_sha` from `cleanup-plan`'s PR data, omitted when null)".
   - In tasks 6.2 and 9.2, add "`norm_pr` carries `merge_commit_sha`; cleanup passes it as `--merged-commit`".
2. **design.md Context "Downloads", Risks and Open Questions:**
   - In "Downloads", replace "But every build stays downloadable at a versioned URL, listed by `https://app.gitbutler.com/api/downloads?channel=release` (builds back to 0.22.1-3215)." with:
     > But each build has a versioned URL. `https://app.gitbutler.com/api/downloads?channel=release` lists the latest 10 releases, each with a standalone Linux x86_64 `but`; on 2026-10-30 that was 0.23.1-3317 back to 0.20.4-3116 (released 2026-06-26). Whether a URL keeps answering after its build leaves that list is not known.
   - In the Risk "GitButler removes an old build from its release host", replace "Builds back to 0.22.1 are listed today." with "The listing holds only the latest 10 releases, about four months at the 2026 pace, so a pin that has left it may stop downloading."
   - In Open Questions, append: "A pin that has left the 10-release listing has no evidence of staying downloadable."
3. **tasks.md 5.2:** replace "map paths to CLI IDs, run `but commit -b <branch> -F <msgfile> <ids>`, then verify the committed file set equals the named changed paths, otherwise `commit_mismatch` (D5)" with "normalize the paths (`bad_path` on glob characters), stop with `nothing_to_commit` when no named path changed, run `but commit -b <branch> -F <msgfile> --json <paths...>` with the paths, never CLI IDs, then verify the parent, the committed file set, the message and every other branch's tip, otherwise `commit_mismatch` (D5)".

CHANGES_APPLIED: yes

## Rebuttals
