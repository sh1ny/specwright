# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 1 gave APPROVE_WITH_CHANGES (C1, M1-M4), and a re-check accepted all five Required Changes. Round 2 was run because an apply-time amendment split the unreadable rules into an ADDED releases requirement. It gave APPROVE_WITH_CHANGES (M1, the unreadable-commit rule), and a re-check accepted that too (CHANGES_APPLIED yes). Round 3 runs because an owner-approved behaviour-change amendment voided that verdict. The amendment came from the PR #108 review (Codex P2, round 5) and adds a parent-set bump rule to "An unreadable version is not absent".
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness; route: subagent). No project skills were named for this review.
- **Reviewed:**
  - The amendment diff (`git diff HEAD -- openspec/changes/fix-deferral-followups/`): specs/releases/spec.md, the `own_bump` bullet of design.md D5, and in proposal.md the #103 bullet and the Capabilities line. In tasks.md, the new test-map row and task 3.4.
  - The full proposal.md, design.md (D5 in full), tasks.md, specs/releases/spec.md and the previous review.md.
  - The main spec openspec/specs/releases/spec.md, requirement "A bumped version is greater than main's before it merges" and its eight scenarios.
  - In skills/specwright-release/scripts/release.sh: `Unreadable` (:592), `primary_at` (:599), `own_bump` (:615-645) and `check_ahead_of` (:648-668).
  - In evals/release/test_release.py: `TestCheckMain` (:670-888), including `unreadable_base` and the unreadable tests through `test_bump_through_unreadable_then_main_merged_refused`, which is present in the working tree.
  - The review template.
  - The change-finish, design-review-gate and project-planning deltas are outside the amendment, so I relied on rounds 1-2 for them.
- **Evidence runs:**
  - `openspec validate fix-deferral-followups --strict`: valid. Requirement text lengths: 434 ("An unreadable version is not absent") and 309 (the unreadable-commit requirement), both under 500.
  - `TestCheckMain.test_bump_through_unreadable_then_main_merged_refused` on the current release.sh: FAILED. This is the expected red, since task 3.4's code is not written yet.
  - Temp repos built with evals/release/fixtures.py were run against three scripts: the current release.sh, a scratch copy patched to the amended rule, and a scratch copy patched to the fix in Required Change 1. Results, as (exit code, error):

    | Case | current | amended | fix |
    | --- | --- | --- | --- |
    | Codex case (0.4.2, then 0.4.2+0.5.0, then 0.5.0, then merge main at 0.5.0) | 0, passes | 1, `version_not_ahead_of_main` | 1, `version_not_ahead_of_main` |
    | Broken main base repaired on both sides (M1 a) | 0 | 1, `version_not_ahead_of_main` | 0 |
    | Same, after merging main | 0 | 1, `version_not_ahead_of_main` | 0 |
    | Stray lower line added and then removed on the branch (M1 b) | 0 | 1, `version_not_ahead_of_main` | 0 |

  - `RELEASE_SH=<fix copy> python -m unittest discover evals/release`: 116 tests OK. That includes every existing `TestCheckMain` row and the new task 3.4 test. No repository file other than this review was edited; the scratch copies live in a temp directory.
- **Re-check (round 3, new run):** I checked Required Changes 1-4 against the working tree (`git diff HEAD -- openspec/changes/fix-deferral-followups/`). All four are applied. RC1: the requirement text matches word for word (476 characters), the Codex scenario is unchanged, and the two new scenarios match. RC2: the D5 `own_bump` bullet is rewritten as a whole, not as a one-sentence swap. On substance it carries the required text, keeps the "lower one" and "greater than every semver" rules for an unreadable version on `<ref>`, and judges the unreadable-commit rule against the same looked-past version, as the spec's "in place of that parent" requires. The "This covers each case" line names the three new cases. RC3: the proposal's #103 bullet and `releases` Capabilities line carry the required wording. RC4: tasks.md has the two new test-map rows and the rewritten task 3.4, which includes the docstring update. `openspec validate fix-deferral-followups --strict` reports the change valid. In the implementation, `judged_parent` and `own_bump` in release.sh match the amended spec, and the docstring is updated (S1). However, `python -m unittest discover evals/release` gives 118 tests with 1 failure: `test_main_base_repaired_on_both_sides_passes` exits 1 with `version_files_disagree`. This is a defect in the test fixture, not in the rule. The test writes only `VERSION`, so README.md and the SKILL.md files stay at 0.4.2. In a scratch copy that uses `fx.set_version(self.work, "0.5.0")` for both repair commits, the test passes on both the working-tree and the HEAD release.sh. The other two new tests pass, and the Codex test fails on HEAD as it should. So the design artifacts are complete, but the task 3.4 checkbox and the green test-map rows are not yet true (see Rebuttals).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The parent-set bump rule refuses branches that carry no release. One of them is the repair branch the amendment means to protect.**

The amended sentence reads: "An unreadable parent SHALL count as a bump only when the commit's version is not among the versions it matched, or is the greatest of them while a lower one is among them too." It does not say where the parent sits. In the history walk, the parent of the branch's first version-changing commit is the merge base itself, or some other commit on `<ref>`. The rule therefore reaches back into main's history, and the deliberately unchanged merge-base rule protects nothing.

a. **A broken main base, repaired on both sides, is refused.** main's `VERSION` lists `0.4.2` and `0.5.0`. The branch forks there and repairs the file to `0.5.0`, and main later repairs it to `0.5.0` too.
   - `check_ahead_of` sees an unreadable base whose set holds 0.5.0, so it is not bumped by the base rule (release.sh:658), and the walk runs.
   - The repair commit's parent is that same unreadable base. 0.5.0 is the greatest of {0.4.2, 0.5.0} and a lower one is present, so the commit counts as a bump. The check refuses with "Rerun bump --to with a version greater than 0.5.0".
   - Merging main first changes nothing, because `ref..HEAD` still lists the repair commit.
   - This contradicts the stated reason for leaving the merge-base rule unchanged ("a broken main base later fixed on both sides must not refuse a repair branch"). It also contradicts D5's own Rejected bullet, which turns down a rule that "would refuse a branch whose whole purpose is to repair that file".

b. **A stray lower line, added and then removed on the branch, is refused.** main and the branch are both at 0.5.0 and the branch never bumps. One commit leaves `VERSION` as `0.5.0\n0.4.2\n` by mistake, and a later commit removes the stray line.
   - The base is readable and equal to the branch's version, so the walk runs.
   - The newest commit keeps the greatest of its unreadable parent's set while a lower one is present, so it counts as a bump, and the check refuses a branch whose version never moved.
   - This is the mirror of round 2's M1, a sloppy hand edit that leaves an extra line, and the main requirement's definition of a bump excludes it: "the newest of its own non-merge commits that changed the primary file's version raised it". No commit changed the version from 0.5.0.

Both are false refusals of the same class as #103. Each refusal tells the user to bump again, which would ship a release the branch never meant to make. The temp-repo runs above reproduce both under the amended rule. On the current code both pass.

The root cause is that the amended rule guesses, from the parent's set alone, whether the unreadable state added the higher version or the lower one. When the unreadable parent is a branch commit, the walk can avoid guessing. It can look past the run of unreadable branch commits to the version before them. If that version is readable, it settles the question: compared with 0.4.2 the commit raised the version (the Codex case), and compared with 0.5.0 nothing changed (case b). Only when that run reaches `<ref>` while still unreadable is the set rule needed, and there the merge-base rule's no-guess reading (case a) is the intended one.

A scratch implementation in `own_bump` passes all 116 release evals and gives the expected result in all four temp-repo cases. It walks first parents from `c^` while the version is unreadable and the commit is not an ancestor of `<ref>` (`git merge-base --is-ancestor`), then treats what it reaches in place of the parent, which means `<ref>` must be passed in. It also keeps the round-2 cases unchanged:
- "Bump reverted through an unreadable version" compares 0.4.2 with 0.5.0, so it is no bump.
- `test_bump_reverted_by_lower_of_unreadable_set` compares 0.5.0 with 0.6.0, so it is no bump.
- `test_dedupe_to_highest_of_unreadable_set_keeps_bump` finds equal versions, so the walk goes on and finds the bump to 0.6.0.

**What the amendment gets right.** It closes the Codex false pass. Before the change, the dedupe commit was skipped as the "greatest" of its parent's set, and the unreadable commit was skipped because its parent was among its versions. `check --main` therefore passed a duplicate 0.5.0. The new scenario states this case correctly and should stay as written. Apart from M1, the rest of the amendment is consistent:
- The requirement text is 434 characters and validates under `--strict`.
- The main requirement and its eight scenarios are untouched and unaffected. None of them puts an unreadable version on a parent, and the eight test rows still pass under the fix.
- The second new requirement and its scenario are unaffected.
- The proposal's #103 bullet and Capabilities line, the D5 bullet, and task 3.4 all state the same rule as the spec.

### Suggestions

**S1.** Task 3.4 should also update the `own_bump` docstring (release.sh:616-621) and the "This covers each case" line in D5, so that both describe the parent rule that ships. Today the docstring still says "no change when its version is the greatest semver".

**S2.** (Carried from round 2.) The eight "A bumped version is greater than main's before it merges" rows in the test map remain the regression net for D5. They are worth keeping, and this round's fix is checked against them.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) specs/releases/spec.md, requirement "An unreadable version is not absent".
   - Replace the requirement text with the following (476 characters):

     "In `release.sh check --main <ref>`, a primary file that exists but does not read exactly one version SHALL be unreadable, which is not absent. An unreadable merge base, or an unreadable parent on `<ref>`, SHALL count as a bump only when the branch's or commit's version is not among the versions it matched. A commit whose parent is unreadable and on the branch SHALL be judged against its nearest first-parent ancestor that is readable or on `<ref>`, in place of that parent."

   - Keep the scenario "Bump made through an unreadable version" as it is.
   - Add the scenario "Broken main version repaired on both sides":
     - WHEN the merge base's `VERSION` lists `0.4.2` and `0.5.0`, the branch's only commit on it keeps `0.5.0`, and `origin/main` has since repaired it to 0.5.0;
     - THEN `check --main origin/main` exits 0 and reports version 0.5.0.
   - Add the scenario "Stray version line added and removed":
     - WHEN the branch starts at 0.5.0, one commit adds a `0.4.2` line to `VERSION`, a later one removes it, and `origin/main` is at 0.5.0;
     - THEN the check exits 0 and reports version 0.5.0.
2. (M1) design.md D5, `own_bump` bullet: replace the sentence "When its version is the greatest semver in that set, it is a bump when a lower one is among them (...), else skipped." with the following text:

   "A commit whose parent is unreadable and not on `<ref>` is judged against its nearest first-parent ancestor that is readable or on `<ref>`, in place of that parent (PR #108 review, round 5): a bump made through an unreadable version counts, and a stray line added and then removed does not. When that ancestor is on `<ref>` and unreadable, a commit whose version is the greatest semver in its set is skipped."

   Keep the "lower one" and "greater than every semver" sentences for that last case.
3. (M1) proposal.md: in the #103 bullet and the `releases` Capabilities line, replace "an unreadable parent only when it is not among them, or is the greatest of them while a lower one is among them too" (and the Capabilities wording of the same rule) with "an unreadable parent on main the same way, and a commit whose unreadable parent is on the branch is judged against the nearest readable version before it".
4. (M1) tasks.md:
   - Add two test-map rows under "An unreadable version is not absent", each starting `red`: `TestCheckMain.test_main_base_repaired_on_both_sides_passes` and `TestCheckMain.test_stray_version_line_removed_passes`.
   - Rewrite task 3.4. Write the three tests and confirm that the Codex test fails on the current release.sh. Then change `own_bump`, which needs `<ref>` passed in from `check_ahead_of`: when the parent is unreadable, walk first parents while the version is unreadable and the commit is not an ancestor of `<ref>`, and judge the commit against what that walk reaches. Update the docstring (S1).
   - Verify: the two pass-tests already pass on the current code, so record them as guards against the round-5 rule (they fail under it; see Evidence runs). The Codex test and the full `python -m unittest discover evals/release` must pass. Flip the three rows green.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

Prior rounds, condensed (still in force):
- **Round 1 (C1, M1-M4):** all fixed and accepted by the reviewer on re-check. The design's M4 note, "a version outside the unreadable set is still a change", is the basis for D5.
- **Round 2 M1 (unreadable commit rule):** fixed as a second ADDED requirement, because the 500-character limit ruled out extending the first one. Accepted by the reviewer. Also accepted: the reading that a commit matching no version is a change but not a bump, which the code implements by requiring a non-empty set (release.sh:628-629).
- **Round 2 S1:** kept. The eight main-requirement test rows remain the D5 regression net (S2 above).
- **Round 2 S2:** not applied, by the author's choice (requirement length). Still moot.

Round 3:
- **M1: fixed, and accepted by the reviewer on re-check.** The spec, design, proposal and tasks follow Required Changes 1-4.
- **Author-facing note (implementation, not part of this verdict):** `TestCheckMain.test_main_base_repaired_on_both_sides_passes` (evals/release/test_release.py:874-885) fails today with `version_files_disagree`. Its two repair commits write only `VERSION`, so the other version files stay at 0.4.2. Use `fx.set_version(self.work, "0.5.0")` followed by `fx.commit(...)` for both commits, then rerun `python -m unittest discover evals/release`. Until that passes, task 3.4 is not done and its row is not green.
- **Author on the note:** fixed. Both repair commits now call `fx.set_version(self.work, "0.5.0")` and commit with `git commit -am`. The three task 3.4 tests pass, and so does the full `python -m unittest discover evals/release`.
