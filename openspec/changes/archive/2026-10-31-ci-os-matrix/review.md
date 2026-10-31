# Review

## Metadata

- **Round:** 3
- **Prior round:** 2, APPROVE_WITH_CHANGES with M1-M3 applied and re-checked (CHANGES_APPLIED: yes). Apply-time edits voided it: the spec split in d2ffbea, and uncommitted edits to design D2, the tasks "Extra tests" line and the proposal's Release Notes.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Reviewed:** openspec/changes/ci-os-matrix/proposal.md, design.md, specs/eval-runner/spec.md, tasks.md, review.md (round 2); openspec/specs/eval-runner/spec.md; `git diff 78105b2 -- openspec/changes/ci-os-matrix/`; `git log -1 d2ffbea`; `openspec validate ci-os-matrix --strict` (valid; the longest requirement body is 482 characters, and the new "Windows jobs and evals start Git Bash" body is 192). Source used as evidence: evals/bashexe.py, evals/runner/test_bare_bash.py (run locally: 3 tests OK), evals/vcs/vcs_test_support.py (`bash_path_env`, uncommitted diff), evals/vcs/jjenv.py (diff), evals/vcs/test_git_backend.py (diff, `native_env`), scripts/update.sh (`claim_stale_lock`, `jload_raw`), evals/update/test_update.py (`RACE_SHIM`, `TestStaleLockRace`, `TestStaleLockRaceBsdMv`), .gitattributes, .github/workflows/evals.yml (working tree and diff), evals/timings.md (CI matrix section), evals/runner/test_timings.py (`ROW`), evals/runner/test_ci_workflow.py (`test_schema_files_check_out_lf`), evals/suites.json (diff), evals/git-workflow/fixtures.py and evals/pr-pair/test_bounded.py (diffs), and a grep of `shutil.which("bash")` and `GIT_BASH` across the tree. Installed project skills named by the request: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

None.

**Spec split: no SHALL lost.** Round 2's CI requirement ended "On Windows, every `bash` a job or an eval starts SHALL be Git for Windows' Git Bash; an eval SHALL NOT start bash by its bare name." Both clauses now open the ADDED requirement "Windows jobs and evals start Git Bash" in the same terms ("a CI job" for "a job"). Its two scenarios moved over word for word, and both test-map rows were renamed to match. The CI requirement keeps every other SHALL and its five other scenarios unchanged. The main spec's `CI runs every suite on Linux for each pull request` is still renamed and then modified under its new name. The split adds one clause: "it SHALL start the bash that `evals/bashexe.py` resolves". This narrows the requirement and does not reverse it, and the tree already complies: outside `bashexe.py`, a grep finds `shutil.which("bash")` only in a synthetic fixture string in test_platform_skips.py:130 and in a needle in test_workflow.py:81. Calling it a clarification is reasonable. See S1 for how it is tested.

**D2 as amended against evals/bashexe.py.** The order matches. `GIT_BASH` comes first, then `usr\bin\bash.exe` under Scoop (`%SCOOP%` and `%USERPROFILE%\scoop`), `%ProgramFiles%`, `%ProgramFiles(x86)%` and `%LOCALAPPDATA%\Programs\Git`. After those comes `shutil.which("bash")`, rejected under `%SystemRoot%` or a `WindowsApps` path part, and then `None`. Off Windows it returns `shutil.which("bash")`, and `jjenv.find_bash = bashexe.bash` is the re-export. The stated reason is the `bin\bash.exe` launcher putting `/mingw64/bin:/usr/bin` ahead of the caller's PATH. The module docstring gives the same reason, and `test_resolved_bash_keeps_the_callers_path_first` asserts the property directly. `bash_path_env()` now derives `git_root` from either `<git>\usr\bin` or `<git>\bin` and excludes `<git>\bin` from the passed-through PATH, as D2 says. The `test_git_backend` fix (`native_env`, the native PATH for `real_git()` at all three launch sites) matches task 4.5's root cause.

**Tasks, design and spec agree.** The test-map rows name the new requirement. The Extra tests line lists the 4.6 additions, and each exists in the working tree: `test_schema_files_check_out_lf`, `test_resolved_bash_keeps_the_callers_path_first`, `TestStaleLockRaceBsdMv` and `test_lock_a_third_run_took_before_the_put_back_is_kept`. The `schemas/** text eol=lf` rule falls under D6's "an `eol=lf` rule … with a regression test". The `claim_stale_lock` change without `-T` is a small shipped-script fix with a regression test, inside D9's bound. The CI section of timings.md has 3-cell OS rows and 2-cell timeout rows, so `test_timings.py`'s 4-value `ROW` pattern cannot match them, as the State table requires.

### Suggestions

**S1. The added spec clause has no check of its own.** The new requirement says an eval "SHALL start the bash that `evals/bashexe.py` resolves". Its scenario and `test_bare_bash.py` only catch displays that start with the constant `"bash"`. If a future eval writes `bash = shutil.which("bash")` (round 2's S6 pattern), it passes every test. On a Windows machine with WSL and only `Git\cmd` on PATH, that bash is the WSL launcher, which is exactly what the requirement forbids. Either have `test_bare_bash.py` flag `shutil.which("bash")` (and `os.environ["BASH"]`) outside `evals/bashexe.py`, and add a scenario for it, or drop the clause back to the round-2 wording.

**S2. D2 says "`GIT_BASH` if set". The code uses it only if the file exists** (bashexe.py:35-38 treats it as one more candidate). It also accepts a `GIT_BASH` that names `bin\bash.exe`, the launcher D2 says `bash()` "is not". vcs_test_support.py:31 already expects that case. The old `find_bash` candidates all pointed at `bin\bash.exe`, so a contributor who set `GIT_BASH` to match them gets the launcher. With it, the second run's failures come back: the update shims, the race shim and the pr-pair fakes do not run, and `test_pr_snapshot.py` hangs. Only `test_resolved_bash_keeps_the_callers_path_first` in the runner suite catches this, and per AGENTS.md a contributor runs only their own module locally. Either map a `GIT_BASH` that ends in `\bin\bash.exe` to its sibling `usr\bin\bash.exe`, or reword D2 to "`GIT_BASH` when it exists (it should name `usr\bin\bash.exe`)". The same applies to the `shutil.which` fallback when only `Git\bin` is on PATH.

**S3. One `... or "bash"` fallback remains** despite D2 ("every `... or "bash"` fallback go[es]") and task 4.3: evals/git-workflow/fixtures.py:1226 has `msys(bashexe.bash() or "bash")`. It writes the real bash into the `bin/bash` shim. If the fallback were used, the shim would exec `bash` from PATH, which is the shim itself. Today it is reachable only when no bash is found. Drop the fallback and have the caller skip, or note in D2 that this site is exempt.

**S4. D5 says the job timeout is about 1.5 × the slowest job. The rule recorded in evals/timings.md is different:** `timeout` = `run_timeout` + 5 min, so the runner stops a hung file before Actions does. The numbers satisfy D5 (for example Linux: 15 min against 1.5 × 376 s ≈ 10 min), but the recorded rule is not the one the design states. Add one sentence to D5 at the next amendment. On its own this does not justify a re-review.

**S5. Release Notes.** Task 5.1 already plans a rewrite. When it is done:
- "puts back a lock another run took while it was replacing a stale one without GNU `mv -T`" reads as if the other run lacked `mv -T`. Consider "now puts back, on macOS too (BSD `mv` has no `-T`), a lock that another run took while this run was replacing a stale one".
- `schemas/** text eol=lf` changes how shipped schema files check out on Windows, so it may deserve a `### Fixed` line.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

CHANGES_APPLIED: n/a

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->
