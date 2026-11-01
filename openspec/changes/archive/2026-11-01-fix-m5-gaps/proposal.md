# Proposal

## Why

M5 left eight gaps open, each filed as an issue. Some are wrong behaviour:
- the release skill points store-backed projects at a proposal path that does not exist (#133);
- a repeated task id hides a ticked task's commit (#143);
- under `vcs: gitbutler`, a sibling branch or an unassigned edit in the shared work tree can replace Specwright's own scripts or its settings (#150, #151).

The rest break or weaken the evals:
- the fake `gh` state file can be read half-written, failing tests at random on CI (#134);
- a timed-out test file leaves nested sessions running on Linux and macOS (#136);
- a grader's evidence leaves out what it checked (#144);
- three finish evals reach a render the fake `gh` has no recording for (#146).

This change is the second change of M6 - Packs. It closes these gaps before the pack work starts. It advances the exit criteria "every issue in the changes below is closed by a merged PR, and each code fix has a regression test in `evals/`" and "every eval CI job passes on each later M6 PR", and it ships as release 0.12.3.

## What Changes

- **Release skill names the proposal by role (#133):** `specwright-release`'s `## Release notes` section runs `release.sh notes --proposal <proposal.md>`. It says the file is the change's proposal in the planning repo, which in a store-backed project is the store. It no longer names `openspec/changes/<change>/proposal.md` under the code checkout.
- **Repeated task ids stop the coverage check (#143):** `task-cover.sh` exits 2 with `duplicate_task_ids` when `tasks.md` holds a task id on more than one tracked line, and it names the ids. It never attaches commits to one of the lines and reports the other as uncovered.
- **Store-group evidence shows the trailers (#144):** the grader's `eval-store-group-code-half` and `eval-store-group-store-half` evidence lists each commit's parsed `Specwright-Task` trailers next to its subject, as `eval-store-apply-groups` already does.
- **The fake `gh` state is never seen half-written (#134):** the fake `gh`, `snapfix` and the test helper scripts write the state file to a temp file and then rename it into place, retrying for a bounded time while Windows holds the target open. A reader never sees an empty or partial file, and a call that only reads no longer rewrites the file, so a watcher's poll cannot undo a test's change.
- **A timed-out file's nested sessions are stopped on POSIX (#136):** when the eval runner stops a test file, it also stops every session the file started through `bounded.py`. The runner turns this on through a test-only environment variable. PR and release scripts that run outside the runner behave exactly as today.
- **Finish eval PR bodies have recordings (#146):** the merged-PR bodies that the git-workflow finish fixtures seed join the bodies the markdown recorder renders and the recordings coverage test checks, and the missing rendering is recorded. Evals 53, 54 and 57 then reach the closed-check result instead of `GitHub state unknown`.
- **GitButler needs Specwright installed outside the repo (#150):** with `vcs: gitbutler`, every `vcs.sh` call stops with `scripts_in_workspace` when Specwright's scripts run from inside the code repo's work tree. `update.sh` refuses a skills or agents target inside the work tree of a GitButler project. The README install prompt says so.
- **GitButler stops on any unpinned settings edit (#151):** with `vcs: gitbutler`, the change's settings are taken only from what the change branch has committed. Every `pr.validate` run (ship, feedback, a watch CI fix) and every read of the merge settings (watch, finish) takes the settings from `pr-pair.sh context --branch <b>` right before it uses them. Cleanup after the merge uses `--after-merge`, which compares against the merged branch's tip while it is still applied, else GitButler's target ref. `vcs.sh push` checks again. Each stops with `settings_not_pinned` when `openspec/specwright.yaml` in the work tree differs from the committed copy. Branch reads and the change's own commits are not stopped, so a change can still commit its own settings edit. This covers a committed sibling edit, an assigned edit, an unassigned edit (the case that was missed) and a file the branch never committed.
- **BREAKING (GitButler only):** a GitButler project whose Specwright skills are installed inside the repo, or whose settings are not committed on the change branch, now stops until it is fixed. Git and jj projects are unaffected.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `releases`: the bump task and the release skill name the proposal by its role in the planning repo, and checking a store-backed proposal reads it in the store (#133).
- `task-commits`: a tasks.md with a repeated task id stops the coverage check (#143).
- `eval-grading`: store-group pair evidence names the trailers it checks (#144). The fake `gh` state file is replaced whole, and only by a call that changed it (#134). Every PR body that a fixture seeds for an issue check has a recorded rendering (#146).
- `eval-runner`: a stopped test file's nested sessions are stopped too, on every OS (#136).
- `vcs-backends`: the GitButler probe refuses scripts run from inside the work tree (#150), and the settings are pinned to the change branch tip, for watch too (#151).
- `install-update`: an update refuses in-repo skill and agent targets for a GitButler project (#150).

## Impact

- **Skills and scripts:**
  - `skills/specwright-release/SKILL.md`
  - `skills/specwright-commit/scripts/task-cover.sh` and its header
  - `skills/specwright-pr/scripts/vcs.sh` (probe, `require_settings_pinned`)
  - `skills/specwright-pr/scripts/pr-pair.sh` (`context`)
  - `skills/specwright-pr/scripts/bounded.py` and its two byte-identical copies (a test-only spawn record)
  - `scripts/update.sh`
  - the GitButler lines of `skills/specwright-branch/SKILL.md` and `README.md`
- **Eval tooling:**
  - `evals/run.py`
  - `evals/fakes/gh.py`
  - `evals/pr-pair/snapfix.py`
  - `evals/pr-pair/closing_bodies.py`
  - `evals/pr-pair/fixtures/markdown.json` (one new recorded entry)
  - `evals/git-workflow/grade.py`
  - `evals/git-workflow/fixtures.py`
  - the GitButler fixtures, which commit the settings on the branch instead of hiding them
- **Tests:** a regression test for each issue, in `evals/release/test_skill_text.py`, `evals/git-workflow/test_task_cover.py`, `evals/git-workflow/test_grade.py`, `evals/pr-pair/test_fake_gh.py`, `evals/runner/test_run.py`, `evals/pr-pair/test_pr_pair.py`, `evals/vcs/test_gitbutler_*.py` and `evals/update/`.
- **ADR:** ADR 0014 is kept. The spawn record is a `SPECWRIGHT_TEST_*` hook, and POSIX spawning is unchanged. ADR 0018 is not edited. Design decides whether the GitButler trust rule needs a new ADR.
- **Recording:** one read-only GitHub markdown render as KintsugiBot (`record_markdown.py`).
- **Version:** 0.12.3 (patch).

## Release Notes

0.12.3 closes the gaps left by M5. The release skill no longer points store-backed projects at a proposal path that does not exist. A repeated task id stops the coverage check instead of hiding a ticked task. Under `vcs: gitbutler`, Specwright must be installed outside the repo, and an unpinned settings edit stops the run. The eval tooling no longer reads the fake `gh` state half-written or leaves nested sessions behind on a timeout, and the finish evals have the recordings they need.

### Changed
- With `vcs: gitbutler`, Specwright's scripts must run from an install outside the code repo, and `update.sh` refuses in-repo skill and agent targets for such a project. Copies committed on main stop every step, so remove them by hand through GitButler (#150)

### Fixed
- `specwright-release` names the change's proposal in the planning repo, so a store-backed project checks the right file (#133)
- `task-cover.sh` stops with `duplicate_task_ids` when tasks.md repeats a task id, instead of reporting the ticked line as uncovered (#143)
- With `vcs: gitbutler`, any settings edit not committed on the change branch, unassigned edits included, stops ship and watch with `settings_not_pinned` (#151)
- The store-group grader evidence lists each commit's task trailers (#144)
- The fake `gh` replaces its state file whole, so a concurrent test never reads it half-written (#134)
- The eval runner stops the nested sessions of a timed-out test file on Linux and macOS (#136)
- The git-workflow finish fixtures' PR body has a recorded rendering, so evals 53, 54 and 57 reach the closed-check result (#146)
