# Review

## Metadata

- **Round:** 2
- **Prior round:** 1, APPROVE_WITH_CHANGES with M1 (D3 "bumped" defeated by merging main), M2 (subagent route overwrote `review.md`), M3 (D8 blamed the change for an invalid installed schema) and S1-S5. All were applied and re-checked, and the changes were marked applied. Commit 502db47 then amended design.md (the #97 diagram order, plus a new Flow & State Gaps entry), which voided that verdict.
- **Reviewer:** fresh-context subagent (Claude Code, `specwright-reviewer` role, Opus 5.5). Project skill loaded: `github-account-switch-race-fencing`. I applied it to the #93 decision (D2 removes the unfenced read; publish keeps the fenced one) and to the fenced fetch named in D3. I made no authenticated `gh` call for this round.
- **Reviewed:**
  - Change artifacts: `proposal.md`, `design.md` (whole document, plus `git show 502db47`), the six delta specs (`change-finish`, `debugging`, `install-update`, `planning-stores`, `releases`, `review-routes`), round 1 `review.md` and `tasks.md` (#97 rows and section 4).
  - ADRs: 0007, 0008, 0009, 0010 by reference, and 0011.
  - `scripts/update.sh`: the header contract for stage, swap, recover and finish; `do_plan`'s recover-first path; `do_stage`; `swap_store_prepare`; `store_busy_reason`; `dirty_paths`; `written_by_update`; `cmd_store_check` in both modes; `checkout_id`, `mk_group` and `build_groups`; `check_change`, `installed_note`, `inflight_entries`, `make_plan` and `cmd_swap_check`. These include the uncommitted working-tree diff.
  - `README.md`: the update prompt's plan, stage and swap steps, the refusal handling, and Step 7's `recover --rollback`.
  - `skills/specwright-review/scripts/review-run.sh`: `validate_design`, `codex_windows_sandbox`, `command_line`, the OMP `agent_end` reader with `MAX_EVENT_LINE`, `design_scratch`, and `record --scratch`/`--out`.
  - `skills/specwright-release/scripts/release.sh`: the `check --main` and `untagged --local` usage and dispatch.
  - `evals/update/test_store.py`: the new `TestStagingPerCheckout` tests, from the working-tree diff.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. #97: once two checkouts have each had a swap refused, rerunning the update prompt in either one never gets either update through. The new Flow & State Gaps entry says it does.**

The amendment says: "Each one's staging makes the store busy for the other, so neither swap runs. ... the user recovers one checkout (its own staging only) and the other then swaps." The code and the README do not do that.

- A refused swap keeps its staging and journal. `swap_store_prepare` (`update.sh:748-749`) releases the gate and exits 1 without removing anything. The `planning-stores` scenario "Another checkout's staging makes the store busy" requires this: "B's own staging remains for `recover`".
- The only documented way for a user to "recover" is to rerun the update prompt. README Step 4 says that on a refusal the prompt reports that nothing changed and STOPs (`README.md:230-235`). The next run's first `plan` runs `recover` (`README.md:198-201`, `do_plan`). That recover discards the leftover, and then the same run goes on to `stage`, which creates a new `.specwright-update-schemas-<id>` (`do_stage`, `update.sh:656-690`). Nothing in plan or stage checks for another checkout's staging; `store_busy_reason` is called only from `cmd_store_check`.

Timeline: A and B both swap and are refused. Each is refused by the other's staging, or both are refused because the store sat on a change branch. Both now have staging in the store.
1. The user follows A's busy message ("finish or recover it from that checkout") and reruns the prompt in B. B's recover discards `<idB>`, B stages `<idB>` again, and its swap is refused by A's leftover `<idA>`.
2. The user reruns the prompt in A. A's recover discards `<idA>`, A stages `<idA>` again, and its swap is refused by the new `<idB>`.

This repeats for as long as the user follows the prompt. The only exits are undocumented: a bare `update.sh recover` (the tests use it, `test_store.py` `self.ok(self.b, dl, "recover")`, but the user has only the prompt) or a manual `rm -rf`.

The trigger does not need a race. Two projects on one store that both try a workflow update while the store is on a change branch (a release day) both end up with a refused swap and a leftover staging directory. Before D7, B's stage pre-clean deleted the shared directory. That was #97's data loss, but it also kept this from looping. D7 trades that for a loop the design records as solved.

A related gap is not recorded anywhere. `cmd_store_check --mode rollback` uses `store_busy_reason` with `written_by_update`. So a foreign `<idB>` also refuses A's `recover --rollback` after a failed Step 7, until B is cleaned up, and B is cleaned up only through the loop above. The spec scenario "Discard after a refused swap keeps the other checkout's rollback copy" passes only because its B runs a bare `recover` first.

### Suggestions

- **S1 (D7, busy message).** Whatever M1's fix, make the busy message name an action that works from the prompt. Today it says "finish or recover it from that checkout", and in practice that means "rerun the update there". If M1's fix makes a refused swap discard its own staging, the remaining foreign staging can come only from a live or interrupted update in that checkout, and "rerun the update prompt in that checkout" is then accurate.
- **S2 (review-routes delta, carried over from the round-1 nit).** The scenario "Subagent design review without a verdict" still says the subagent "writes a `review.md`". Since D5 it writes a scratch result file, so name the scratch file to keep the scenario assertable as written.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **M1: `design.md` (D7, Failure & Visibility, the Flow & State Gaps entry "both checkouts staged before either swapped"), `specs/planning-stores/spec.md`.** Make the two-checkout case converge through the documented prompt.
   - Preferred: a swap refused before its first rename (any `store-check --mode swap` stop, `verify` or `swap-check` refusal) discards this update's own staging and journal before it exits, exactly as `recover`'s "swap not started → discarded" path would. With that, two refused checkouts leave the store clean, and the next prompt run in either one swaps.
   - Acceptable alternative: `plan` (and so `stage`) refuses before staging while another checkout's `.specwright-update-schemas-*` is untracked in the store, naming it. Keep the patch code-only path working when the schema is byte-identical.
   - Either way:
     - rewrite the Flow & State Gaps entry to describe the real convergence;
     - change the `planning-stores` scenario "Another checkout's staging makes the store busy" so that its THEN matches ("B's own staging is removed", or "B stages nothing");
     - add a scenario: "**WHEN** A and B both had a swap refused with their staging left in the store, and the user reruns the update prompt in A / **THEN** A's update swaps, or B's leftover is named and the next rerun in A swaps, with no step outside the prompt";
     - record that a foreign staging directory also refuses `recover --rollback` (the Failure & Visibility table), so a user whose Step 7 failed knows which checkout to clean up first.

**Re-check (round 2, reviewer):** I re-checked only M1 and the applied suggestions S1/S2 against commit dcbb344 (`design.md`, `specs/planning-stores/spec.md`, `specs/review-routes/spec.md`, with `tasks.md` for traceability). `openspec validate fix-m3-gaps --strict` passes.
- **M1: applied.** The preferred option is in D7: a swap refused before its first rename (busy store, in-flight changes that differ from the plan, failed verification) removes this update's staging directories and journal, as `recover` does for a swap that never started. The rejected alternative (refusing in `plan`/`stage`) is recorded with its reason. Each sub-item:
  - The Flow & State Gaps entry "both checkouts staged before either swapped" now describes the actual convergence: the first swap is refused and cleans up, the other swaps, and a later rerun is not refused for staging. This holds under the new rule, because a refused checkout no longer leaves a directory behind for the rerun loop to re-create.
  - The `planning-stores` requirement adds the rule. The THEN of "Another checkout's staging makes the store busy" now ends with "B's own staging and journal are removed" and names the rerun action. "Discard after a refused swap ..." moves the removal into B's refused swap, so it no longer depends on a bare `recover`.
  - New scenario "Both checkouts staged before either swapped". It starts one step earlier than the wording I asked for. I accept the author's reason: under the new rule, two refused swaps can no longer leave their staging behind. The scenario still asserts what I required: convergence through reruns of the prompt, with no step outside it ("a rerun of A's update after B finished is not refused because of staging").
  - Failure & Visibility has a row for the refused swap and a row for `recover --rollback` blocked by B's staging. The second row names B's directory and the path by which it clears: B's swap is refused by A's retained staging and removes B's own. That path is consistent with the new rule.
  - Tasks 4.1/4.2 and the test map carry the new scenario and the code change.
- **S1: applied.** The busy message in D7 and in task 4.2 reads `finish or recover it by rerunning the update in that checkout`, and the busy-store scenario asserts it.
- **S2: applied.** "Subagent design review without a verdict" now says the subagent "writes a scratch result file".

Every Required Change is applied. The verdict stays APPROVE_WITH_CHANGES, and the changes are now marked applied.

CHANGES_APPLIED: yes

## Rebuttals

- **M1 fixed, preferred option (the user's choice).** D7 now says a swap refused before its first rename (a busy store, changes in flight that differ from the plan, a failed verification) removes this update's staging directories and journal, as `recover` does for a swap that never started; the alternative is recorded as rejected there. The patch code-only path is not a refusal and is unchanged. Flow & State Gaps "#97, both checkouts staged before either swapped" describes the real convergence. `planning-stores`: the requirement text adds the rule; "Another checkout's staging makes the store busy" now ends with B's staging and journal removed; "Discard after a refused swap ..." has B's refused swap remove only its own; new scenario "Both checkouts staged before either swapped" (A refused and cleaned, B swaps, A's rerun not refused for staging). The requested scenario's starting state, two refused swaps that left their staging behind, can no longer arise, so the new scenario starts one step earlier. Failure & Visibility gains the refused-swap row and the `recover --rollback` row blocked by B's staging. Tasks 4.1/4.2 and the test map carry the new test.
- **S1 applied.** The busy message says `finish or recover it by rerunning the update in that checkout`.
- **S2 applied.** "Subagent design review without a verdict" names the scratch result file.
- **M4 applied, preferred option (round 3).** D3's commit clause is decided by the newest commit listed by `git log --no-merges --topo-order` that changed the primary version, counted only when it raised it (a version that is not semver: any change). The `releases` requirement sentence says so; new scenario "Bump reverted on the branch"; task 2.5 and the test map carry `test_bump_reverted_on_branch_passes` beside `test_version_file_edit_without_bump_passes`.
- **M5 applied (round 5).** "A refused design review leaves the earlier review file unchanged" says a design review that fails validation or passes the deadline leaves any earlier review file unchanged.
- **M6 applied (round 5).** The requirement is "The size bound applies to the answer", for every route: codex's last-message file, claude's printed output (its stdout is the answer), and OMP's final `agent_end` message; the three test-map rows are renamed.

## Re-check (round 3, D3 amendment)

**Reviewer:** fresh-context subagent (Claude Code, Opus 5.5). No project skill was named for this round. **Scope:** only the uncommitted D3 amendment (`git diff -- openspec/changes/fix-m3-gaps/`): the D3 bullet in `design.md`, the `releases` requirement sentence and the new scenario "Version file edited without a bump", task 2.5 and its test-map row. Read against `check_ahead_of`/`primary_at` (`skills/specwright-release/scripts/release.sh:587-618`) and `TestCheckMain` (`evals/release/test_release.py:670`).

What holds:
- **Review M1 scenario ("Main was merged into the branch after the duplicate landed") still refuses.** `feat/b`'s own bump commit is still listed by `--no-merges <ref>..HEAD`, and it reads 0.5.0 against its first parent's 0.4.2, so it counts. The merge of main is excluded by `--no-merges`, so its 0.5.0 never shows up as a "change" against the branch-side parent. The amendment does not weaken M1. The other D3 scenarios (duplicate, main ahead, bump ahead, no bump, main has no version) are decided by the merge-base rule or the early exit, and the amendment does not touch them.
- **First parent is a merge.** A non-merge commit made after merging main is compared with the merge result, which already carries main's version. A dependency-only edit there reads the same version and does not count. That is correct.
- **Glob primary entries.** `primary_at` gives `None` when the glob's files disagree. A commit that makes them disagree also makes the working tree fail `agree()` first (`version_files_disagree`), unless a later commit makes them agree again, and that later state is a real bump. I found no glob-only false refusal or false pass.
- **Consistency.** The design, the requirement sentence ("changed the primary file's version"), the new scenario, task 2.5 and the red test-map row agree with each other. The test already in the working tree (`test_version_file_edit_without_bump_passes`, which appends `channel: stable` to `VERSION` while the pattern `^(\d+\.\d+\.\d+)$` still reads one version) asserts the scenario as written.

**M4 (Moderate, new in round 3). A branch that bumps and then reverts the bump is still refused, which contradicts the scenario "Branch did not bump".** Under the amended rule, each listed commit is compared with its first parent. In bump-then-revert, commit X changes 0.4.2 to 0.5.0 and the revert Y changes 0.5.0 back to 0.4.2. Both "changed the primary file's version", so the branch counts as bumped. With `origin/main` at 0.5.0, `check --main` stops with `version_not_ahead_of_main` and tells the user to rerun `bump --to` above 0.5.0. That happens at ship, at the local merge, and at watch (no ready report, no merge). The branch's final state is the same as "Branch did not bump" ("leaves the version at 0.4.2 ... exits 0 ... carries no release of its own"). The rule that applies, though, is the requirement's commit clause, and the spec gives no scenario that settles which reading is right.

The trigger is realistic: a change that drops its release task, or a user who undoes an accidental bump, when main has moved past the reverted version. The only ways out are to publish a release the user decided against, or to rewrite branch history. The old rule ("any commit touched the file") had the same refusal, so this is not a regression. The amendment exists to stop counting edits that are not bumps, though, and this is the remaining case of that class.

**Required change (round 3).**
1. **M4: `design.md` D3, `specs/releases/spec.md`, `tasks.md` 2.5 and the test map.** Do one of the following.
   - Preferred: decide the commit clause by the **newest** listed commit that changed the version, and count it only when it raised the version (both semver, new > old; for a version that is not semver, any change counts, as now). List the commits with `--topo-order`, so that "newest" does not depend on commit dates.
     - The M1 merged-main case still refuses: X raised 0.4.2 to 0.5.0.
     - Bump-then-revert passes: Y lowered the version, and the merge base reads 0.4.2.
     - Bump then re-bump (0.5.0, then 0.6.0) still counts.
     - Add the scenario "Bump reverted on the branch" (**WHEN** the branch bumped 0.4.2 to 0.5.0, then reverted to 0.4.2, and `origin/main` is at 0.5.0 / **THEN** the check exits 0), plus a red test-map row and the test in task 2.5.
   - Acceptable: keep the rule and state the refusal explicitly. Add that scenario with a THEN of "refused; squash the bump and its revert out of the branch history", and say in D3's Failure & Visibility that this is a known refusal and how to clear it.

The verdict stays APPROVE_WITH_CHANGES. CHANGES_APPLIED is reset to no until M4 is applied.

## Re-check (round 3, M4)

**Reviewer:** fresh-context subagent (Claude Code, Opus 5.5). No project skill was named for this round. **Scope:** only M4, against commit 8dccd27 (`design.md` D3, `specs/releases/spec.md`, `tasks.md` 2.5 and the test map) and the uncommitted `own_bump`/`check_ahead_of` (`skills/specwright-release/scripts/release.sh:596-625`) with `TestCheckMain` (`evals/release/test_release.py`). `python -m pytest evals/release/test_release.py -k TestCheckMain`: 11 passed.

- **M4: applied, preferred option.** D3's commit clause now takes the newest commit listed by `git log --no-merges --topo-order` whose primary version differs from its first parent's, and counts it only when it raised the version. The requirement sentence says the same ("the newest of its own non-merge commits that changed the primary file's version raised it"). The new scenario "Bump reverted on the branch" has the THEN I asked for (exit 0). Task 2.5 and the test-map row name `test_bump_reverted_on_branch_passes`.
- **Implementation is consistent.** `check_ahead_of` adds `--topo-order` and passes the listed SHAs, newest first, to `own_bump`. That function skips commits whose version equals the parent's (the dependency-edit case), returns false when the newest change lowered the version (the revert), and returns true when it raised it, when the parent has no readable version, or when either side is not semver. The three cases I listed hold. Merged main: X (0.4.2 to 0.5.0) is the only listed change, so the branch is refused, and `test_duplicate_after_main_merged_in_refused` still passes. Bump-then-revert: Y is newest and lowered the version, so it passes. Re-bump: 0.5.0 to 0.6.0 is newest and raised it, so it counts. Both new tests assert exit 0 with version 0.4.2, as the scenarios state.
- **Nit, not blocking.** D3 and the requirement say "raised it" but do not carry the parenthetical from the required change: for a version that is not semver, any change counts. The code does that (`not (sv(mine) and sv(parent))`), and so does the M4 rebuttal. Adding the half-sentence to D3 would make that branch of the code traceable. Either way the outcome is a refusal, because the ahead check also needs semver.

M4 is applied. The verdict stays APPROVE_WITH_CHANGES, and every Required Change is now marked applied.

## Re-check (round 4)

**Reviewer:** fresh-context subagent (Claude Code, Opus 5.5). No project skill was named for this round. **Scope:** only the two uncommitted amendments (`git diff -- openspec/changes/fix-m3-gaps/`). The first is D8's `error` step, with the install-update scenario "OpenSpec fails during the installed check", tasks 5.1/5.2 and the test-map row, read against `check_change` and `installed_note` (`scripts/update.sh:1165-1229`), their callers `inflight_entries` (`:1266-1269`), `make_plan` (`:1716`) and `cmd_swap_check` (`:1914`), and `TestInstalledRecheck` (`evals/update/test_inflight.py`). The second is task 4.1's `test_second_claimer_names_owner` bullet, read against the test (`evals/update/test_store.py:113-134`), the scenario "Two projects claim at once" (`openspec/specs/planning-stores/spec.md:561-563`; the fix-m3-gaps delta does not modify it) and its test-map row in the archived `safe-update-lifecycle` tasks. I also checked the single-change exit paths of the installed OpenSpec 1.14.1 `status` command (`dist/commands/workflow/status.js`). I ran no tests.

**Amendment 1 (D8 `error` step): consistent, and safe for the target check.**
- **The target refusal is unchanged.** `inflight_entries` marks the entry invalid on any non-`None` result (`if r:`), whatever the step. It stores `r[1]`, the same error text as before, so `change_invalid` at the plan and `inflight_changed` at swap-check still fire with the same message prefix. Nothing else reads the step: `installed_note` is the only consumer of `r[0]`. Classifying a non-zero `openspec status` exit as `error` therefore only suppresses the installed note. That is the safe direction (an under-claim), and it is what D8's "or `openspec` errors ... makes no claim" requires.
- **A real installed-side failure is not hidden as `error`.** For `status --change <name> --json`, OpenSpec 1.14.1 sets a non-zero exit only by throwing, and it prints the JSON result only on success. So a non-zero `status` run never carries a result that says the change fails, which matches D8's definition of `error`. Genuine status findings (error-severity `status` items, or an artifact present while its dependency is not) come with exit 0 and are classified `status`. For `validate`, a non-zero run that reports `valid: true`, or a non-zero run with output it cannot parse, is classified `error`. A run whose item says invalid is classified `validate`. Both match D8.
- **Design, spec, tasks and code agree.** `installed_note` appends the note only when `r[0]` is in (`validate`, `status`). That excludes `schema` (the installed schema is invalid, M3) and `error`. The new scenario, the 5.1 test bullet, the 5.2 bullet ("never on an `error` step") and the test-map row all describe the same behaviour.
- **Nit, not blocking.** `test_no_installed_claim_when_openspec_errors` asserts only "fails validation against 0.6.0" and the absence of the note. That prefix also appears for an entry made invalid by an `OSError` ("could not read the change"), for example if the wrapper broke the target check too. The wrapper is limited to a cwd ending in `-installed`, and on this Python (3.14) `shutil.which` resolves `openspec.cmd`, so the test does exercise the intended path. Asserting a fragment of the real target error as well (for example `openspec status add-x` or `openspec validate add-x`) would make that explicit.

**Amendment 2 (`test_second_claimer_names_owner`): still covers its scenario.**
- **Under D7 this is the only reachable form of the race.** In this test, B stages as a claimer, A's claim then lands in `STORE`, and B's swap re-reads `STORE` under the gate lock. If A swapped while B's staging was visible, A's swap would be refused as busy (D7). If B staged after `STORE` existed, B would plan as `other` and never reach `store_claimed`. What remains possible is B staging while A's swap holds the lock, after A's busy check and before A writes `STORE`. The test reproduces exactly that, with a direct record write standing in for A's swap.
- **The THEN is still asserted.** B's swap stops with `store_claimed`, names owner A, does not mention uncommitted files, writes nothing to the store or to B's installed files, and releases the lock. The new assertions (B's staging and journal gone) also cover D7's refused-swap cleanup.
- **The "STORE names owner A" half comes from the fixture here.** It is still exercised by a real swap in `test_first_update_claims_store` (`test_store.py:96-109`), so no coverage is lost.

No new gap with a concrete consequence. The verdict stays APPROVE_WITH_CHANGES. Every Required Change remains applied.

## Re-check (round 5, requirement split)

**Reviewer:** fresh-context subagent (Claude Code, Opus 5.5). No project skill was named for this round. **Scope:** only the uncommitted split of three requirements (`git diff -- openspec/changes/fix-m3-gaps/`), compared with the committed deltas (`git show HEAD:openspec/changes/fix-m3-gaps/specs/{change-finish,releases,review-routes}/spec.md`) and the main specs (`openspec/specs/<cap>/spec.md`). I read `skills/specwright-review/scripts/review-run.sh:995-1045` to check what the moved sentences govern. `openspec validate fix-m3-gaps --strict` passes, and every requirement in the review-routes delta is now 479 characters or fewer.

What holds:
- **change-finish.** The committed MODIFIED text was main's text word for word, plus one sentence about `finish: local`, and its six other scenarios match main's. Dropping the MODIFIED block loses nothing. The ADDED "Local finish lists untagged versions from local tags" carries that sentence. Its extra clause, "to publish after `main` is pushed", comes from the scenario's THEN and from main's "Local finish publishes no tag without a push decision", so it adds no new rule. The scenario is filed under the requirement it exercises.
- **releases.** Same pattern. The committed MODIFIED text was main's text plus the `--local` sentences, and its four other scenarios match main's. The ADDED "Untagged versions can be read from local tags only" keeps both `--local` sentences, including "whenever it read local tags, including with no `origin` remote", and both `--local` scenarios.
- **review-routes MODIFIED.** The text is main's, with `exactly one` added for `CHANGES_APPLIED:`. The five scenarios match main's, except that "Subagent design review without a verdict" now names the scratch file (round 2's S2).
- **Verdict values.** "Design review verdict values are checked" keeps the allowed `VERDICT:` values and the `CHANGES_APPLIED:` pairing. "Naming the value" is already asserted by the scenarios. Its four scenarios all exercise a verdict or pairing being refused or accepted.
- **Scratch file.** "A refused design review leaves the earlier review file unchanged" keeps the scratch-file rule. "Kept and named in the report" matches the existing scenario and `test_record_out_refused_keeps_review_and_scratch`.
- **Test map.** The map and the delta scenarios are one-to-one: every delta scenario has exactly one row with the same capability, requirement and scenario name. Ten rows (six for "Finish offers a release once the change is on main", four for "Older untagged versions are published first") now name scenarios that exist only in main's specs. Those names still match main exactly, and the rows record tests that stay green. That is harmless, so no change is required for them. Drop them if the map should cover only the change's own scenarios.

**M5 (Moderate). A design review that passes the deadline is no longer required to leave the earlier review file unchanged.** The committed sentence was: "A route that ran but whose output fails validation, *or that passes the deadline*, SHALL be a failed review that stops the caller and leaves any earlier review file unchanged". The new rule says "A design review that fails validation SHALL leave any earlier review file unchanged". Nothing in the split says that a timed-out design review leaves `review.md` alone. The MODIFIED text and "Reviewer exceeds the deadline" only say the run stops with `status: timeout` and no other route runs. The code is fine today (`stop("timeout", ...)` at `review-run.sh:1004-1005` exits before any write). Once archived, though, the main spec would not forbid a timeout path from replacing a valid `review.md` with a partial one. The committed delta did forbid that.

**M6 (Moderate). The answer-not-stream size bound was narrowed from every route to OMP only.** The committed sentence was general: "The size bound applies to the review's answer, not to a route's event stream." The new requirement starts "For the OMP route". Codex's stdout is also an event stream (`review-run.sh:1008`, comment "codex's and omp's stdout are event streams; their answer is bounded below"), and the bound is applied to its `-o` last-message file (`:1013-1015`). With the split, the spec no longer requires that. A change that bounded codex's stream would refuse a large codex run with a small valid answer, which is the same failure this change fixes for OMP, and it would not contradict any spec text.

## Required Changes (round 5)

1. **M5: `specs/review-routes/spec.md`, "A refused design review leaves the earlier review file unchanged".** Restore the deadline case. For example: "A design review that fails validation or passes the deadline SHALL leave any earlier review file unchanged." This keeps the requirement under 500 characters. No new scenario or test-map row is needed.
2. **M6: `specs/review-routes/spec.md`, "The OMP size bound applies to the answer".** Make it cover every route again. For example, rename it to "The size bound applies to the answer" with the text: "The 2 MiB output bound SHALL apply to the review's answer (codex's last-message file, claude's printed result, OMP's final message of the last `agent_end` event), not to a route's event stream. An OMP stream with no `agent_end` event SHALL fail validation." Rename the three `tasks.md` test-map rows to match. The OMP scenarios stay under it.

The verdict stays APPROVE_WITH_CHANGES. CHANGES_APPLIED is reset to no until M5 and M6 are applied.

## Re-check (round 5, M5 and M6)

**Reviewer:** fresh-context subagent (Claude Code, Opus 5.5). No project skill was named for this round. **Scope:** only M5 and M6 and their test-map rows, in the uncommitted `specs/review-routes/spec.md` and `tasks.md` (`git diff -- openspec/changes/fix-m3-gaps/`), read against `skills/specwright-review/scripts/review-run.sh:1003-1020`. `openspec validate fix-m3-gaps --strict` passes.

- **M5: applied.** "A refused design review leaves the earlier review file unchanged" now opens with "A design review that fails validation or passes the deadline SHALL leave any earlier review file unchanged". That brings back the deadline case the committed delta had. It matches the code: `stop("timeout", ...)` at `:1003-1004` exits before any write.
- **M6: applied.** The requirement is now "The size bound applies to the answer" and covers every route. It names codex's last-message file, claude's printed output and OMP's final `agent_end` message, and says the bound does not apply to a route's event stream. "Claude's printed output" is accurate. The claude route's stdout is its answer, and the code bounds the whole stdout (`:1007`). Codex's `-o` file is bounded at `:1013`. The `agent_end` rule is kept, and the three OMP scenarios sit under the renamed requirement.
- **Test map: matches.** The three OMP rows now name "review-routes → The size bound applies to the answer". No row or delta header still uses the old name "The OMP size bound applies to the answer". The other renamed rows also match their requirements in the delta. Those are the verdict-values rows, the scratch-file rows, the releases `--local` rows and the change-finish local row.

No new gap. The verdict stays APPROVE_WITH_CHANGES. Every Required Change is now applied, so CHANGES_APPLIED is set to yes.
