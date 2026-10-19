# Proposal

## Why

Shipping `record-review-dispositions` (0.7.0, PR #104) left three gaps:

- **#106:** `specwright-finish` step 0 undoes a deferred archive with hand-written prose. Review rounds 5-8 on PR #104 each found a repo state the prose got wrong: the wrong commit taken for the archive commit, restore groups blocking a revert, uncommitted artifact edits lost, and a revert of the archive commit conflicting with later fixes. Two more cases were filed on the issue: later amendments are lost by revert-and-rerun, and a re-added archive has several add commits. The evals are regexes on wording, so every round passed them.
- **#105:** roadmap **next** skips a parked change, but **close** has no matching rule. A parking change is never archived, so if it is listed as a change of a milestone, that milestone can never close.
- **#103:** `release.sh check --main` reads an unreadable primary version at the merge base (a repeated `0.4.2`) as absent. A branch that only removes the duplicate then counts as bumped and can be refused with `version_not_ahead_of_main`, although it never changed the version.

This is change 3 of **M4 - Cost tier** (release 0.7.1). It comes before the cost-tier work because 0.7.0 already ships the undo text it replaces. It advances these exit criteria: every issue in the milestone's changes is closed by a merged PR, and each code fix has a regression test in `evals/`; `evals/git-workflow` and `evals/release` pass; each change ships as its own release.

## What Changes

- **Undo plan script (#106).** A new `skills/specwright-finish/scripts/finish.sh undo-archive-plan`. It reads the real repo state and prints, in one JSON document, an undo script that stops at its first failing command. It runs nothing, so finish still runs no restore itself. The undo it plans is one new forward commit, never a revert chain, a reset or a force-push:
  - it moves each archive copy back to `changes/<name>/`, carrying later amendments and uncommitted edits;
  - it restores the main specs the archive touched to their content before the archive;
  - before any restore, it saves copies of those main specs, with their later amendments (committed or not). For a bulk archive, an after-rerun script archives the other changes again and merges the amendments back with `git merge-file`, before finish commits.

  It finds the archive commit as the **newest** commit that added the archive directory, so an archive that was reverted and archived again is undone once. It covers uncommitted and committed archives, single and bulk archives (an uncommitted bulk archive's members are found from the untracked archive directories), and a resume on the branch or on `<main>`. Unrelated paths in later commits are never touched.
- **Step 0 shrinks** to: stop on `VERDICT: DEFERRED`, run the plan script, show its scripts, and make no commit, merge or push.
- **Resume's A fact** names the newest add commit, not the oldest, everywhere finish finds A by `--diff-filter=A`.
- **Behavioural evals** build each state as a temp git repo, apply the printed plan, and assert three things: the tree matches the pre-archive state, no user edit is lost, and an amendment survives the undo and a rerun archive.
- **Parked changes are never milestone changes (#105).** The roadmap skill says that a parking change is never listed in a milestone's Changes. If **next**, **close** or **status** find one listed, they report it as parked, neither start it nor count it done, and stop. Removing it from Changes is the user's planning edit.
- **Unreadable is not absent (#103).** `release.sh` tells an unreadable primary version apart from a missing one. An unreadable merge base or parent counts as a bump only when the version is not among the versions it matched. So removing a duplicate `0.4.2` is no bump, and a hand edit from a duplicate `0.4.2` to `0.5.0` still is. A commit whose own version is unreadable is no change when its parent's version is among the versions it matched (or the parent is unreadable too), and otherwise a bump only when every version it matched is greater than its parent's.
- Release 0.7.1 (patch): `VERSION`, the README badge and the skill `metadata.version` fields.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `change-finish`: Resume finds A as the newest add commit. A new requirement covers the deferred-archive undo plan: it is computed by a plan-only script that is never run by finish, it is a single forward commit, and it loses no amendment or uncommitted edit.
- `design-review-gate`: "A deferred review never ships code" stops listing `git revert` and three restore groups. Its scenarios now point at the plan script's forward undo.
- `project-planning`: a new requirement, next to "A parked change is never resumed": a parking change is never listed as a milestone change, and it says what **next**, **close** and **status** do when one is listed.
- `releases`: two new requirements next to "A bumped version is greater than main's before it merges", which stays as it is. "An unreadable version is not absent": an unreadable merge base or parent counts as a bump only when the version is not among the versions it matched. "An unreadable commit changes the version only when its parent is not among its versions": the same rule for a commit whose own version is unreadable.

## Impact

- New: `skills/specwright-finish/scripts/finish.sh` (bash wrapping Python, one JSON document per run, like `release.sh` and `pr-pair.sh`). It is installed with the skill folder, as the other skills' scripts are.
- `skills/specwright-finish/SKILL.md`: step 0, Resume's A fact, and `allowed-tools`, which gains `Bash(bash *)`.
- `skills/specwright-roadmap/SKILL.md`: the parking-change note, **next** step 3, **close** step 1 and **status**.
- `skills/specwright-release/scripts/release.sh`: `primary_at`, `own_bump` and `check_ahead_of`.
- `openspec/specs/` deltas for the four capabilities above.
- Tests: a new `evals/finish/` with behavioural undo tests against real temp repos; `evals/release/test_release.py` (an unreadable merge base, and an unreadable parent in the walk); and `evals/git-workflow/test_instructions.py`, whose old step-0 wording tests are replaced by tests for the new step 0 text and the roadmap parked rule.
- No new configuration key and no dependency change.
