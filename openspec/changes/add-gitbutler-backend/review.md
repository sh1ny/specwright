# Review

## Metadata

- **Round:** 5
- **Prior round:** Round 4: APPROVE_WITH_CHANGES with no Critical and 3 Moderate findings (the squash-merge commit's source, the download listing's window, task 5.2 against D5). Its 3 Required Changes were re-checked and recorded as applied. That verdict was voided when apply ran feasibility tasks 1.1-1.4, check 1.3 failed as specified, and the author amended design.md (D5 steps 6-8, D8's base, the archive-commit gap, the Risks results) and tasks.md (task 5.2). This is a new full round.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:**
  - Change artifacts under `openspec/changes/add-gitbutler-backend/`: proposal.md, design.md, tasks.md, specs/vcs-backends/spec.md, specs/eval-runner/spec.md, review.md (rounds 1-4), and the uncommitted amendments (`git diff -- openspec/changes/add-gitbutler-backend/`).
  - Feasibility evidence (read, not run): `%TEMP%/specwright-add-gitbutler-backend/feas/feas.py` (checks 1.1-1.4) and `feas13.py` (the four archive and delete scenarios after check 1.3 failed).
  - Source: `skills/specwright-pr/scripts/vcs.sh` (the Git `commit`, `delete-branch`, `pull` and `push` branches, 380-470), `skills/specwright-commit/SKILL.md` (path naming, Reconcile), `skills/specwright-finish/SKILL.md:14` (archive paths), the `docs/adr/` list and ADR 0017's scope line.
  - The effective Git config on this machine: `git config --show-origin --get-all core.autocrlf` (read-only).
  - Project skills named in the request: none.

### The amendments, checked against the evidence

- **Check 1.3 (D5 steps 6-8, the archive gap).** `feas.py:check_1_3` names `openspec/changes/c1/` (only rename sources after the move), the archive directory and the spec. That is the call the design says fails with "Could not find uncommitted change", so the failure matches the script. `feas13.py` then shows the alternatives: `arch_dest_only` (the new directory and spec only), `arch_files` (files changed while moved), `del_dir` and `del_file`. The new rule follows from them: step 6 passes to `but` only the named paths that cover a listed `filePath`, and step 8 still holds the commit to every named path with `--no-renames`. With finish's exact paths (`skills/specwright-finish/SKILL.md:14`), `c1/` is dropped from `but`'s arguments, the rename commits the deletions, and `diff-tree --no-renames` then lists D under `c1/` and A under `archive/`, all inside the named paths. A finish that forgot `c1/` stops with `commit_mismatch`. The rule holds whichever addition GitButler pairs a deleted delta spec with, because the check is by path set, not by rename pairing.
- **Check 1.2 (D8's base).** `feas.py:check_1_2` reads `gitbutler/target`, `mergeBase`, `origin/main` and `targetRef` before, after `git fetch` and after `but pull`. D8 now names `mergeBase.commitId` and drops `gitbutler/target`, which the State table no longer relies on either.
- **Check 1.4 (pull fence).** `feas.py:check_1_4` tests both an `insteadOf` redirect through `GIT_CONFIG_*` and an env-provided credential helper over HTTP against the logging server. The Risk now records that the fence holds, so the `unfenced` fallback goes. No spec or task depended on the fallback beyond task 1.4's conditional.
- **Check 1.1 (network).** The local commands made no fetch, forge or `gh` call; the one outbound request was GitButler's usage metrics, following the user's own `but config metrics`. Task 1.1's stop condition is literally met ("any call is recorded"), but the Risk's purpose was ADR 0008 and the Git-write boundary, and a telemetry call carries neither a Git credential nor a forge write. I accept the author's reading: no D5 or `as.sh` change follows. The evals isolate app data and turn metrics off, so CI sends nothing.
- **Task 5.2** matches the new D5 steps 6-8.

### Required Changes re-check

Checked against `git diff -- openspec/changes/add-gitbutler-backend/design.md openspec/changes/add-gitbutler-backend/tasks.md` and the current design.md and tasks.md (2026-10-30).

- **RC1 (design.md Risks "Line endings", Open Questions): applied as written.** The old last sentence ("gets `but`'s error as `but_error`") is gone. The Line endings item now carries the required text word for word: only `branch delete` was seen failing, `but pull` untested with `autocrlf` on and open until the dogfood run, `vcs.sh` keeps `but_error` and adds the `hint: core.autocrlf is true; GitButler checkouts can conflict on line endings` text, and the README states the limit. Open Questions has the new first item, worded as required.
- **RC2 (tasks.md 6.1, 6.2, Test map): applied as written.** 6.2 ends with "; a failed `but` write in a repo whose effective `core.autocrlf` is `true` adds the autocrlf hint to `but_error` (design.md Risks, Line endings)". 6.1 names `test_but_error_names_autocrlf` with "a fake failing `but` is enough". The Test map has a red row under "A GitButler branch is deleted only once merged" in `evals/vcs/test_gitbutler_delete.py`.
- **RC3 (tasks.md 2.2, 3.3): applied as written.** 2.2's `butenv.py` description now reads "isolated GitButler app data with metrics disabled, `GIT_CONFIG_NOSYSTEM=1` and `core.autocrlf=false`". 3.3 adds "and the GitButler limits: `core.autocrlf=true` (design.md Risks, Line endings)" to the README documentation. The design's Line endings item names the same `butenv.py` settings, so the task and the design agree.
- **Applied suggestions (S1, S3, S4): no inconsistency introduced.**
  - S1: D5 step 3 now judges from step 1's `uncommittedChanges` "as in step 6" and says step 7 never runs with an empty path list. The renumbered steps line up: step 3 points to step 6 (the coverage filter) and step 7 (the `but commit` run), the CLI-ID paragraph now says "between steps 2 and 7", and the archive-commit gap still points to "D5 step 6" for leaving rename sources out. No other step reference in design.md, tasks.md or the specs uses the old numbers. Task 5.2's "when no named path changed" is less precise than step 3, but it cites D5, which governs.
  - S3: task 5.1 lists the three archive cases (all renamed unchanged, some changed while moved, only the new directory named → `commit_mismatch`).
  - S4: task 1.3's Verify now says the result is recorded in design.md's archive-commit gap and that D5 follows it. The archive-commit gap holds that result.
- **Note (non-blocking).** The new Test map row's Scenario column holds a description ("`but` write fails with `core.autocrlf=true` (design.md Risks, Line endings)") instead of a scenario from specs/vcs-backends/spec.md, since the spec has no autocrlf scenario. RC2 asked for this row, and no eval in the repo checks that Scenario cells name spec scenarios. So nothing breaks, and the row traces to the design's Risk.

## Findings

### Critical (blocking)

None.

### Moderate

**M1. `core.autocrlf=true`, the Git for Windows default and this user's own config, breaks `but branch delete`, and the design neither documents it for users nor knows which other `but` writes it breaks.**

The Risks "Line endings" item records that with `core.autocrlf=true` in system config, `but branch delete` failed with "1 conflict prevents checkout", and says a user's Windows workspace "gets `but`'s error as `but_error`". Three things follow from the evidence.

- This is the user's configuration, not a corner case. `git config --show-origin --get-all core.autocrlf` on this machine prints `file:F:/scoop/apps/git/2.55.0.4/etc/gitconfig true`, and the dogfood projects are built with Specwright on this machine. The M5 criterion's dogfood run will meet this path.
- Only `branch delete` was seen failing, and the rest is unknown. Every run in `feas.py` uses `GIT_ENV` with `GIT_CONFIG_NOSYSTEM=1` and clones with `core.autocrlf=false` (`feas.py:32-34, 66`), so no recorded check exercised `autocrlf=true`. In `check_1_1` the delete comes before `but pull`, and `but(...)` raises on failure (`check=True`), so in the failing run `but pull` never ran. `but pull` checks out the rebased workspace too, and it is cleanup's main path for removing the branch (D7: when alone, the pull removes the integrated branch and the delete reports `already_deleted`). So on a Windows workspace the common cleanup step may fail as well, and nothing in the design says so.
- Nothing tells the user. The README tasks (3.3, 5.3, 10.2) cover the setting, hooks and skill install, but not line endings. The proposal's Release Notes and the spec say nothing. A user sees a raw `but_error` about a checkout conflict at cleanup, after the PR merged, with the branch still applied and its commits in the shared work tree.

The evals cannot catch this. CI runs on Linux, and `butenv.py` turns the system config off (D10, Risks).

*Fix:* see Required Changes 1-3. Make the failure named and documented. Leave `but pull` under `autocrlf` as an explicitly open point for the dogfood run instead of an implied pass. Have task 2.2 carry the `butenv.py` settings the design already relies on.

### Suggestions

- **S1. Tie D5 step 3 to step 6's coverage rule.** Step 3 ("no named path has an uncommitted change") and step 6 ("covers at least one `uncommittedChanges[].filePath`") should use the same test. If an implementer judged step 3 from Git's view instead, where a rename source is a changed path, a commit naming only rename sources would pass step 3, step 6 would filter every path out, and step 7 would run `but commit -b <branch>` with no paths. The Context says that commits everything in the workspace, and the step-8 check would only find it after the write. The spec already says "never without paths". One sentence in step 3 ("judged from step 1's `uncommittedChanges`, as in step 6"), plus the line "step 7 never runs with an empty path list", closes it. The same edit makes the spec's `nothing_to_commit` wording ("named paths unchanged") match what happens to a named rename source.
- **S2. Name the half-named rename case.** A task that `git mv`s `src/a.py` to `src/b.py` and names only `src/b.py` commits only the addition on Git (`vcs.sh` runs `git add -- <paths>` and `git commit -- <paths>`). On GitButler the rename commits the deletion of `src/a.py` too, and step 8 then stops with `commit_mismatch` after the write, with the commit left on the branch. That is safe, but a pre-write check would be kinder if `but status --json` carries a rename's previous path. Otherwise add one line to Flow & State Gaps saying the stop is expected, and have `specwright-commit` name both sides of a move.
- **S3. Cover the mixed archive in `test_archive_commit_names_exact_paths`.** `feas13.py` never passes `c1/` to `but` when it covers both `removed` entries (files changed while moved) and rename sources. That is the case where step 6 keeps `c1/` in the arguments. Add it to the 5.1 test with the pure-rename case and the "only the new directory named" `commit_mismatch` case.
- **S4. Task 1.3's text.** Its Verify ("`git show --stat` lists only those paths") failed by design. When apply ticks it, the result recorded in the archive-commit gap is the evidence. Consider rewording the task's Verify to "the result is recorded in design.md's archive-commit gap", so a ticked task does not claim a check that failed.

## Verdict

The amendments follow the feasibility evidence. The rename-source rule in D5 is the right shape: `but` gets only paths it can resolve, and the Git-read check still holds the commit to every named path. D8's base and the pull fence now rest on scripted checks instead of assumptions. One Moderate finding remains. On Windows with `core.autocrlf=true`, the Git for Windows default and this user's own config, `but branch delete` is known to fail, and `but pull` is untested, with no user-facing word and no named error. The fix is text and an error mapping, and needs no new design decision.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **design.md, Risks "Line endings":** replace the last sentence ("A user's Windows workspace with `autocrlf` on gets `but`'s error as `but_error`.") with:
   > Only `branch delete` was seen failing. `but pull`, which also checks out the workspace, was not run with `autocrlf` on, so whether cleanup's pull works there is open until the dogfood run. When a `but` write fails and the repo's effective `core.autocrlf` is `true`, `vcs.sh` keeps `but_error` and adds `hint: core.autocrlf is true; GitButler checkouts can conflict on line endings` to the message. The README states this limit under the GitButler setup.

   Add the same open point to Open Questions: "Whether `but pull` and `but branch delete` work in a workspace with `core.autocrlf=true`; the dogfood run on Windows answers it."
2. **tasks.md 6.2:** after "and the `merge` stop (D6, D7, D8)", add: "; a failed `but` write in a repo whose effective `core.autocrlf` is `true` adds the autocrlf hint to `but_error` (design.md Risks, Line endings)". Add a matching test name to task 6.1, for example `test_but_error_names_autocrlf` (a fake failing `but` is enough), with a Test map row under "A GitButler branch is deleted only once merged".
3. **tasks.md 2.2 and 3.3:**
   - In 2.2, extend the `butenv.py` description to "(scratch repo set up by `but`, local bare remote, fake `gh`, isolated GitButler app data with metrics disabled, `GIT_CONFIG_NOSYSTEM=1` and `core.autocrlf=false`, skip or fail per `SPECWRIGHT_REQUIRE_BUT`)".
   - In 3.3, add "and the GitButler limits: `core.autocrlf=true` (Risks, Line endings)" to the README documentation.

CHANGES_APPLIED: yes

## Rebuttals
