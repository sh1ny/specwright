# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code harness; route: subagent)
- **Re-check (same round, new run):** fresh-context subagent (route: subagent) re-checked only Required Changes 1-5 against design.md, proposal.md, specs/change-finish/spec.md, specs/releases/spec.md and `release.sh` (`primary_at`, `own_bump`, `check_ahead_of`, lines 587-632). All five are satisfied; see Rebuttals and Re-check Notes.
- **Reviewed:** proposal.md, design.md, specs/change-finish/spec.md, specs/design-review-gate/spec.md, specs/project-planning/spec.md, specs/releases/spec.md; skills/specwright-finish/SKILL.md (Resume, step 0, steps 1-3), skills/specwright-roadmap/SKILL.md (next, close, status, Rules), skills/specwright-release/scripts/release.sh (header, Stop/emit, primary_at, own_bump, check_ahead_of, cmd_check, cmd_bump), evals/release/test_release.py (TestCheckMain), main specs openspec/specs/{change-finish,design-review-gate,project-planning,releases}/spec.md, openspec/roadmap.md (M4). ADRs 0001, 0002, 0003, 0010 taken from design.md's ADR section; no conflict found with what it cites. GitHub issues #103, #105, #106 not read; the proposal was relied on. No referenced stores.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

**C1. The plan's safety depends on stopping at the first failed command, but `commands[]` is a list of separate shell lines with no stop-on-failure.**
D2 says that each entry in `commands` is "one shell line for the user to run in order". It also says the guard makes "a plan made against another state fail before it writes anything", and the Failure table says "No commit exists before step 4". Both claims hold only if nothing after a failed line runs. The design's own `warnings` tell the user to "run the commands in one go". A user who pastes the block into an interactive shell has no `set -e`, so a failed line does not stop the next one:
- If the guard `test ... = <head>` fails (the branch moved), steps 2-5 still run against the wrong state. The mechanism ledger says this guard exists to prevent exactly that silent wrong commit.
- If a step-3 index command fails (for example `read-tree --prefix` refusing an existing entry), step 4 `git commit` still commits the partly built index.
- If step 2 fails (the `mkdir` or the `>` redirect into `<git-dir>/specwright-undo/...`), step 5 `git restore --source=<A>^ --worktree -- <modified>` still runs and drops the user's uncommitted main-spec edits. The patch that was the only copy of those edits was never written. This is the T6 data loss the change is meant to remove.

The fix is to make a failure stop everything after it. Either emit the plan as one script that runs under `set -e` (a single `commands` string, or the lines written to a file in `<backup_dir>` and run with `bash -e`), or chain every writing line to the guard and to the line before it with `&&`. Pin this with an eval.

### Moderate

**M1. `git apply --3way` after the rerun fails with "does not match index", so the bulk "Amendment survives the rerun" path does not work as designed.**
`git apply --3way` implies `--index` unless `--cached` is given. `--index` requires the working tree and the index to match for every path the patch touches. In `after_rerun`, the bulk archive is rerun without the deferred change, which is an uncommitted `openspec archive`. That rewrites `specs/a/spec.md` in the working tree only, while the index still holds the undo commit's `A^` content. The apply then refuses before any merge, so the amendment is never re-applied. The spec scenario "Amendment survives the rerun" would fail, or pass only in an eval that commits the rerun first. The design has to fix the order. One way: rerun the archive, let finish make its step-3 archive commit, then run `git apply --3way <patch>`, then commit the re-applied amendments in their own commit. Staging the rerun's main specs before the apply also works. The behavioural eval has to apply the patch against the same state a real rerun leaves (uncommitted, or committed by step 3 as the design chooses), not a hand-staged tree.

**M2. Step 2 is left out when the diff is empty at plan time, but the design counts on step 2 to catch edits made later.**
D2 includes `git diff --binary <A> -- <main specs> > amendments.patch` "only when that diff is non-empty at plan time". Flow & State Gaps then says that "uncommitted edits made after the plan are covered by step 2, which reads the working tree when it runs". When the diff was empty at plan time, the plan has no step 2. A main-spec edit the user makes between the plan and running it is then dropped for good by step 5's `git restore --worktree`, and the HEAD/branch guard does not notice it. Always emit step 2 (an empty patch costs nothing), or make the guard also check that `git diff --quiet <A> -- <main specs>` still holds.

**M3. Uncommitted bulk archives have no way to find their members.**
The CLI takes one `--change` and one `--archived-name`. For a committed archive the members come from A. For an uncommitted one, no commit groups them, and the design never says how the script finds the other changes of the bulk run. The design-review-gate scenario "Bulk archive that included a deferred change" is not limited to committed archives, and finish step 0 already checks "every one" of a bulk archive. If the script undoes only the deferred member, it restores the shared main spec, which drops the other member's sync, and leaves that member's copy in `changes/archive/`. That member then looks archived, but its spec content is gone, and a rerun no longer finds it to archive. Let `--change`/`--archived-name` repeat (finish knows the bulk set), or derive the members from the untracked archive directories and list them in `warnings`. Add an uncommitted-bulk scenario to the change-finish delta.

**M4. D5 misses a branch that repairs the unreadable version and bumps it in the same commit.**
Under D5, a commit whose parent version is unreadable "decides nothing", and an unreadable base gives `bumped = False`. Take a base `VERSION` of `0.4.2\n0.4.2\n` and one hand-edited branch commit that writes `0.5.0`. A hand edit is the only route here, because `cmd_bump` refuses an unreadable tree (`release.sh:654-656`). The walk skips that commit, `own_bump` returns False, and with `origin/main` at 0.5.0 the check passes. That lets through the duplicate release that "A bumped version is greater than main's" exists to stop. Read an unreadable version as the set of versions it matches, so that a commit (or a base) whose readable version is not in its unreadable parent's matched set counts as a bump. That still passes #103's "remove the duplicate, keep 0.4.2" case. Add the one-commit repair-and-bump scenario to the releases delta and to `TestCheckMain`.

### Suggestions

**S1.** The proposal's Capabilities section says `project-planning` modifies "A parked change is never resumed", but the delta ADDs a new requirement, "A parking change is never a milestone change". The ADDED form is fine, since the existing requirement still holds for unlisted parked changes. Align the proposal text.

**S2.** D3 checks that HEAD's tree still holds the archive directory only inside the script. Resume's A fact (SKILL.md:23) still treats a found add commit as a live archive even when its newest add was reverted. Step 0 then reads `git show <branch>:.../review.md` for a path that is gone. This gap existed before this change and is not made worse by it. One clause in the A fact, matching the script's `no_archive` rule, would close it.

**S3.** For a bulk archive, the undo commit subject `<type>(<change-name>): undo archive of deferred change` names only one change. Name the members, as the step-3 bulk archive commit does, so a later Resume subject match stays unambiguous.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (C1) design.md D2 and the Failure table: state that the plan's commands run so that any failure stops all later commands. Either `commands` is emitted as one `set -e` script (or written to a file in `<backup_dir>` and run with `bash -e`), or every writing line is chained with `&&` after the guard. specs/change-finish/spec.md: add a scenario where the guard fails (HEAD moved after the plan) and the THEN asserts that no commit is made, the working tree and index are unchanged, and no main spec is restored.
2. (M1) design.md D2 `after_rerun`: fix the order so `git apply --3way` runs against a state where index and working tree agree for the patched main specs. For example, after finish's step-3 archive commit of the rerun, followed by a commit of the re-applied amendments. Say which commit the amendments land in. specs/change-finish/spec.md "Amendment survives the rerun": state the order in the WHEN.
3. (M2) design.md D2 step 2 and Flow & State Gaps: always emit the patch step (or add a guard that `git diff --quiet <A> -- <main specs>` still holds whenever the step was left out), so an edit made after the plan is never restored away unsaved.
4. (M3) design.md D1/D2: define how members of an uncommitted bulk archive are found (repeatable `--change`/`--archived-name`, or derived from the untracked archive directories and listed in `warnings`). specs/change-finish/spec.md: add an "Uncommitted bulk archive with a deferred member" scenario.
5. (M4) design.md D5 and specs/releases/spec.md: an unreadable parent or base SHALL NOT hide a bump. A commit whose readable version is not among the versions its unreadable parent matches counts as a bump. Add the scenario: base `VERSION` holds `0.4.2` twice, one branch commit writes `0.5.0`, `origin/main` at 0.5.0 → exit non-zero with `version_not_ahead_of_main`.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **C1 (Required Change 1):** fixed. design.md D1 adds `script` and `after_rerun`, each one bash text that starts with `set -euo pipefail`. D2 step 1 adds a guard for the branch, HEAD and a clean index. The Failure table's `script` row covers a failure at each step. specs/change-finish adds the scenario "Branch moved after the plan". **Accepted by reviewer:** D1 makes both scripts single `set -euo pipefail` texts, D2 step 1 guards branch, HEAD and index before any write, and the Failure table covers a failure at each step.
- **M1 (Required Change 2):** fixed. design.md D2 "Re-applying amendments" saves `base/` and `amended/` copies and replaces `git apply --3way` with `git merge-file`, which works in the working tree. The order is: `openspec archive <member> --yes` (CLI), then merge-file, then finish, which commits the amendments inside the new archive commit. The spec scenario "Amendment survives the rerun" states that order. **Accepted by reviewer:** `git merge-file <current> <base> <other>` writes the merge of base->other into the working-tree file and does not read the index, so the index/working-tree mismatch is gone. With current = the rerun's file, base = `A:<f>` and other = the amended copy, only the amendments are carried over. The `-L rerun -L archived -L amended` labels are in current/base/other order. The amendments land in finish's new archive commit (D2).
- **M2 (Required Change 3):** fixed. design.md D2 step 2 always saves the copies when the script runs, with no condition. Flow & State Gaps is updated to match. **Accepted by reviewer:** the copies are taken when the script runs, for every main spec that step 5 restores, so an edit made after the plan is saved before it is restored.
- **M3 (Required Change 4):** fixed. design.md D1 **Members** derives an uncommitted bulk archive's members from the untracked archive directories whose change directory is tracked at HEAD and missing from the working tree, and lists them in `warnings`. specs/change-finish adds the scenario "Uncommitted bulk archive with a deferred member". **Accepted by reviewer.**
- **M4 (Required Change 5):** fixed. design.md D5: an `Unreadable` value carries its set of matched versions, and a version outside that set is a bump. specs/releases adds a sentence to the requirement and the scenario "One commit repairs and bumps". **Accepted by reviewer:** with base {0.4.2} and branch 0.5.0, `check_ahead_of` counts a bump (0.5.0 is not in the set) and refuses against 0.5.0. #103's case (0.4.2 is in the set) still falls through to `own_bump`, which skips the repair commit and returns False.
- **Suggestions:** the proposal's project-planning bullet now says it is a new requirement. A bulk undo commit's subject names every member (D2 step 4). The check that Resume's newest add is still in HEAD is older than this change and stays out of scope; the script checks it (D3).

## Re-check Notes

These are not Required Changes. Handle them during apply and pin them in the evals.

- **after_rerun and main specs only the deferred member touched.** `amended[]` can list a main spec that only the deferred member synced. A later commit amending the deferred change's own new capability spec is the likely case. For a spec only that member *created*, step 5 removes it and the rerun does not bring it back, so `git merge-file` finds no `<current>` file. It fails with an error rather than conflict markers, and `set -e` stops the script after `openspec archive` has already run, with the remaining files not merged. For a spec only that member modified, the merge applies amendments written against content the rerun no longer has. Limit `after_rerun`'s merge list to main specs that the rerun's members sync, and leave the others saved with the single-archive warning (D2).
- **Guard after checkout.** When the resume runs on another branch, `git checkout <branch>` runs before the guard. If the guard then fails, the working tree is left on `<branch>`. Nothing is lost, but the "Branch moved after the plan" THEN ("working tree unchanged") holds only for a run already on the branch. State this in the scenario or the warning.
- **own_bump middle case.** D5 says a commit whose unreadable parent's set does not contain its version counts as a bump when the version is greater than every semver in the set. It leaves open what happens when the version is outside the set but not greater than all of it (for example a parent of `0.4.2` and `0.6.0`, then `0.5.0`): does the walk stop with False, or go on? Make it explicit in the code. Either answer still satisfies the requirement's "only when".
