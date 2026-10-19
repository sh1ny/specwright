# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 gave APPROVE_WITH_CHANGES (C1, M1-M4). A re-check run accepted all five Required Changes and set CHANGES_APPLIED to yes. That verdict was voided by an apply-time amendment to specs/releases/spec.md, proposal.md and the tasks.md test map.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness; route: subagent)
- **Reviewed:** proposal.md, design.md, specs/{change-finish,design-review-gate,project-planning,releases}/spec.md, tasks.md (test map and task notes), and the amendment diff (`git diff HEAD -- openspec/changes/fix-deferral-followups/`). Also the main spec openspec/specs/releases/spec.md ("A bumped version is greater than main's before it merges"), ADR 0010 (no conflict), skills/specwright-release/scripts/release.sh (`Unreadable`, `primary_at`, `own_bump`, `check_ahead_of`, `cmd_check`), evals/release/test_release.py (TestCheckMain, including `unreadable_base` and the three new tests), and evals/git-workflow/test_specs_strict.py. For the other parts, I spot-checked skills/specwright-finish/scripts/finish.sh (guard before checkout, after_rerun merge list, refusals) and skills/specwright-finish/SKILL.md (allowed-tools, Resume A fact, step 0). The change-finish, design-review-gate and project-planning deltas and design.md are byte-identical to what round 1 reviewed, so I relied on round 1 for them after confirming that the implementation and evals match. I did not re-read ADRs 0001-0003 in full, because round 1's reading of them is unaffected by the amendment.
- **Evidence runs:**
  - `openspec validate fix-deferral-followups --strict`: valid.
  - `test_specs_strict.py` on the working tree: OK.
  - The HEAD copy of the change archived into a temp copy of openspec/ fails `validate --specs --strict` on `releases` ("Requirement text is very long (>500 characters)"), so the amendment's reason holds.
  - `python -m unittest discover evals/release`: 112 OK.
  - `python -m unittest discover evals/finish`: 26 OK.
  - A temp-repo reproduction of M1 below, built with evals/release/fixtures.py.
- **Re-check (same round, new run):** fresh-context subagent re-checked Required Changes 1 and 2 only, against the working-tree specs/releases/spec.md, design.md (D5 `own_bump` bullet), proposal.md (#103 bullet and Capabilities line) and tasks.md (test map row and task 3.3). `openspec validate fix-deferral-followups --strict`: valid. Both changes are satisfied; task 3.3's code is not implemented yet, as expected at this stage.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. "A commit whose own version is unreadable SHALL decide nothing" makes the walk skip a hand-made revert of a bump. A branch with no release is then refused, and the refusal says to bump again.**

The amendment moved this sentence from design D5 into a normative SHALL in the new releases requirement. `own_bump` implements it at release.sh:621 (`if isinstance(mine, Unreadable) or mine == parent: continue`). It works together with the round-1 rule that a commit whose version is in its unreadable parent's set is skipped. Together, the two rules let the walk pass over the commit that actually changed the version:

- base and branch tip are both 0.4.2, and `origin/main` is at 0.5.0;
- c1 bumps to 0.5.0;
- c2 reverts it by hand but leaves `VERSION` as `0.4.2\n0.4.2\n`;
- c3 removes the duplicate.

`check_ahead_of` sees base == version and walks. c3 is skipped (0.4.2 is in c2's set), c2 is skipped (its own version is unreadable), and c1 "raised" 0.4.2 to 0.5.0, so the branch counts as bumped.

I reproduced this in temp repos with the release fixtures. With a clean revert, the check exits 0. With the duplicate revert, it exits 1 with `version_not_ahead_of_main`: "this branch bumped to 0.4.2, which is not greater than origin/main's 0.5.0 ... Rerun bump --to with a version greater than 0.5.0".

That is the same class of bug as #103: an unreadable reading turns into a false refusal. Here the refusal's advice would make the user ship a release the branch never meant to make. It also contradicts the unchanged main requirement's definition of a bump: "the newest of its own non-merge commits that changed the primary file's version raised it". c2 changed the version (0.5.0 is not among the versions it matched) and did not raise it. A duplicate line in `VERSION` is how #103 arose, so a sloppy hand revert that leaves one is a realistic path.

The new SHALL also has no scenario and no test. No TestCheckMain case puts an unreadable version on a branch commit, so the current behaviour is not pinned either way.

Fix: apply the parent-side rule to the commit's own side as well. A commit whose own version is unreadable is no change when its parent's version is among the versions the commit matched (or both are unreadable). Otherwise it changed the version, and it counts as a bump only when every semver it matched is greater than the parent's version. In the reproduction, c2 then returns False, so the check passes. A bump written twice and then de-duplicated still counts: the bump commit's set {0.5.0} is greater than 0.4.2, and the de-duplicate commit is skipped.

### Suggestions

**S1.** The eight "A bumped version is greater than main's before it merges" rows in the test map now point at a requirement this change no longer touches. The schema says extra tests need no row, and task 3.2 re-runs them anyway, so they can stay. Keep them deliberately, as the regression net for D5, and don't treat them as scenarios of this change.

**S2.** On its own, the main requirement's wording "its version differs from its merge base" reads as if an unreadable base always differs. The new requirement corrects this, but only a reader of both requirements sees that. The 500-character limit rules out an edit there. Optionally, start the new requirement with "When deciding whether a branch bumped (see "A bumped version is greater than main's before it merges"), ..." so a reader can find the link.

**Amendment otherwise verified.**
- Splitting the unreadable rules into an ADDED requirement and leaving the main requirement as it is gives the same behaviour as round 1's MODIFIED text, and it passes strict validation, which the HEAD version did not.
- The proposal's Capabilities line matches the delta.
- The three moved test-map rows name existing, passing tests.
- `check_ahead_of`'s base rule (release.sh:645) and the parent rule in `own_bump` (:625-629) match the requirement's second sentence.
- Round-1 re-check notes 1-3 are implemented: the guard runs before checkout (finish.sh:307-315), after_rerun merges only re-synced specs (:362-382), and the own_bump middle case returns False.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) specs/releases/spec.md, requirement "An unreadable version is not absent": replace "A commit whose own version is unreadable SHALL decide nothing, and the walk SHALL go on to older commits." with: "A commit whose own version is unreadable SHALL be no change when its parent's version is among the versions it matched, or the parent is also unreadable. Otherwise it SHALL count as a bump only when every version it matched is greater than its parent's." Add the scenario "Bump reverted through an unreadable version":
   - WHEN the branch bumps 0.4.2 to 0.5.0, a later commit sets `VERSION` back to `0.4.2` twice, a still later one removes the duplicate, and `origin/main` is at 0.5.0;
   - THEN `check --main origin/main` exits 0 and reports version 0.4.2.

   Make the same edit to the `own_bump` bullet of design.md D5 and to the last sentence of the #103 bullet in proposal.md.
2. (M1) tasks.md: add a test-map row for the new scenario (`TestCheckMain.test_bump_reverted_through_unreadable_passes`, starting `red`) and a task that writes it, then changes `own_bump` in release.sh (the `isinstance(mine, Unreadable)` branch at :621) to the rule in change 1. Verify: the new test passes, and so do the existing `test_unreadable_base_dedupe_is_no_bump`, `test_repair_then_bump_refused_when_behind` and `test_repair_and_bump_in_one_commit_refused`.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1 (Required Change 1):** fixed, with one placement change. The required sentences are used word for word. Added to the "An unreadable version is not absent" requirement, they bring its text to 534 characters, which fails `openspec validate --strict` (the 500-character limit this round's amendment was made for). So they form a second ADDED requirement in specs/releases/spec.md, "An unreadable commit changes the version only when its parent is not among its versions" ("In the history walk of `release.sh check --main <ref>`, a commit whose own version is unreadable SHALL be no change ..."), together with the scenario "Bump reverted through an unreadable version". design.md D5's `own_bump` bullet and proposal.md's #103 bullet carry the same rule, and proposal.md's Capabilities line names both new requirements. `openspec validate fix-deferral-followups --strict` passes, and so does `openspec validate --specs --strict` after a scratch archive (18 passed). One reading to confirm: "every version it matched is greater than its parent's" is read as needing at least one matched version, so a commit that leaves the file matching nothing is not a bump. That case is not a raise, and the walk then reads it as a change that is not a bump (no release).
  **Accepted by reviewer:** the required sentences appear word for word in the second ADDED requirement (specs/releases/spec.md:20-21), with the scenario "Bump reverted through an unreadable version" (:23-25) as required. Splitting it out instead of extending the first requirement is acceptable: the rule is unchanged, strict validation passes, and the requirement's title states the rule. design.md D5's `own_bump` bullet (:88) and the last sentence of proposal.md's #103 bullet (:25) carry the same rule, and the Capabilities line (:37) names both requirements. The "at least one matched version" reading is accepted: a commit that leaves the file matching nothing has not raised anything, and reading it as a change without a bump agrees with the main requirement's definition of a bump. Implementation note for task 3.3: Python's `all()` is True on an empty set, so the code has to require a non-empty set explicitly to match this reading.
- **M1 (Required Change 2):** fixed in tasks.md. The test map has the row `TestCheckMain.test_bump_reverted_through_unreadable_passes` (red), and task 3.3 writes that test, confirms it fails with `version_not_ahead_of_main`, changes the `isinstance(mine, Unreadable)` branch of `own_bump`, and verifies the named tests and the whole `evals/release` suite.
  **Accepted by reviewer:** tasks.md:48 has the row with status `red`, and task 3.3 (tasks.md:81) writes the test, confirms the `version_not_ahead_of_main` failure first, changes the `isinstance(mine, Unreadable)` branch of `own_bump` to the rule in change 1, and verifies the three named tests plus the full suite. Task 3.3 is still unchecked; that is expected, since this change asked for the task, not the code.
- **S1:** kept as suggested. The eight rows stay deliberately, as the regression net for D5.
- **S2:** not applied. With the split, a link sentence would bring the first new requirement close to the limit again, and both requirements already open by naming `release.sh check --main <ref>`.
