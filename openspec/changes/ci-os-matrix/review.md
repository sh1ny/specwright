# Review

## Metadata

- **Round:** 2
- **Prior round:** 1, APPROVE_WITH_CHANGES with M1-M4 applied and re-checked (CHANGES_APPLIED: yes). That verdict was voided by the apply-time amendment to D2 after GitHub Actions run 41221380333.
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer), re-check of Required Changes M1-M3 only (and the suggestions the author marked applied)
- **Reviewed:** openspec/changes/ci-os-matrix/review.md (round 2 findings, Required Changes, Rebuttals); proposal.md, design.md (D2 and its amendment sub-bullets, D3, Failure & Visibility), specs/eval-runner/spec.md, tasks.md (test map row "A test starts bash by bare name", tasks 4.2-4.6, Extra tests line); `git diff HEAD -- openspec/changes/ci-os-matrix/`. Source used as evidence: evals/vcs/vcs_test_support.py:18-51 (`bash_path_env`), evals/vcs/test_git_backend.py:19-48,74-76,131-132 (`self.env`, `record_baseline`), evals/vcs/jjenv.py:29-47 (`find_bash`), evals/runner/test_ci_workflow.py:158,301,327-333 and its uncommitted diff, the uncommitted `.github/workflows/evals.yml` diff (`but` digest step), a grep of `"bash"` outside list/tuple displays and of `shutil.which("bash")` in `evals/**/*.py` (18 lines). Installed project skills named by the request: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. The scan as defined misses real launch sites, and the scenario and task 4.2 do not match it.** The amended D2 and task 4.2 define the check as "a call whose argument list starts with the string constant `"bash"`". The 50 `["bash"` literals counted from the first run fall into three groups:
- **Caught.** The literal is written inline as a call's first argument, e.g. `subprocess.run(["bash", ...])` in evals/finish/fixtures.py:206.
- **Launched but missed.** The argv is built in a variable or passed through a helper, then started:
  - `args = ["bash", ...]` → `subprocess.run(args)` (evals/finish/test_undo_plan.py:135-138);
  - `cmd = ["bash", ...]` → `subprocess.run(cmd)` (evals/pr-pair/test_pr_pair.py:2159-2165);
  - `argv = ["bash", "-c", ...]` → `subprocess.run(argv)` (evals/update/fixtures.py:426-427);
  - `self.ls_remote(cwd, ["bash", AS_SH, ...])`, where the list is the second argument and `ls_remote` calls `subprocess.run(argv)` (evals/pr-pair/test_as_sh.py:131,153,160).

  These still run `System32\bash.exe` on Windows, and `test_repo_has_no_bare_bash` passes anyway.
- **Never started by Python.** These literals are expected values or payloads:
  - the expected argv `fenced_pull` and the comparison `c[:1] == ["bash"]` (test_pr_pair.py:2658,2661);
  - `argv[0]` is asserted to equal `"bash"` and then dropped (test_gitbutler_flows.py:52,64,253);
  - payloads that `as.sh` runs inside bash, where MSYS PATH lookup applies (test_as_sh.py:168,230,452).

  Rewriting them to `bashexe.bash()` would break those assertions.

So "naming the 50 call sites from the first run" (task 4.2) cannot be the red result of either reading. A call-argument scan names fewer and passes with the missed group unfixed. A scan of every list literal names all 50, false positives included, and needs a way to exempt them. The spec scenario ("starts a process whose argument list begins with the bare name `"bash"`") covers the missed group, so the design's mechanism does not meet its own scenario. No `shell=True`, `os.exec*` or `"bash -c …"` string launch exists in `evals/` today (grep), so those forms are not a current gap.

*Re-check: resolved.* D2's third amendment sub-bullet now flags "every list or tuple display whose first element is the string constant `"bash"`, wherever it appears", with the single exemption `# bare-bash: not started` on the display's line. Task 4.2 matches it word for word and lists all five synthetic cases (inline call, argv in a variable, argv as a later helper argument, marked expected value passes, same value unmarked fails), and its red result is now "naming every `["bash"` display (50 lines in 21 files)". The test map row names `evals/runner/test_bare_bash.py` with `test_bare_bash_call_is_named, test_repo_has_no_bare_bash`, status red, which is right before 4.2 runs. The spec scenario is unchanged and the mechanism now meets it. The remaining non-display uses of `"bash"` in the tree are positional arguments that `as.sh` execs inside bash (test_as_sh.py:260,523,529) or loop/assert values (git-workflow/fixtures.py:1226, test_gitbutler_flows.py:52,232); none is a Python launch, so the scan does not need to see them.

**M2. `bash()` is described two ways, and its Windows fallback can return the WSL launcher it exists to avoid.** D2 says `bash()` resolves on Windows from `GIT_BASH`, then Scoop, then `Program Files\Git\bin\bash.exe`, "then `shutil.which`", and also says it "is `jjenv.find_bash()` moved". `find_bash` (evals/vcs/jjenv.py:29-47) has no `shutil.which` fallback on Windows and returns `None`. If the fallback is added, it brings the defect back:
- A default Git for Windows install puts `Git\cmd`, not `Git\bin`, on the user PATH. `System32` is on the system PATH.
- So on a contributor machine where Git is not in one of the listed places, `shutil.which("bash")` returns `C:\Windows\System32\bash.exe`. A per-user install in `%LOCALAPPDATA%\Programs\Git` is one such case, and `find_bash` does not list that location.

The design also does not say what a call site does when `bash()` returns `None`. The existing guards (`@unittest.skipUnless(shutil.which("bash"), "needs bash")` in test_grade.py, test_as_sh.py, test_as_jj.py and others) still ask `shutil.which`. On such a machine a guard passes, then `subprocess.run([None, ...])` raises `TypeError` instead of skipping. Three copies of the resolver already exist (jjenv.py:29, test_ci_workflow.py:19 `git_bash`, test_settings.py:24 `bash`). `git_bash() or "bash"` at test_ci_workflow.py:158,301 falls back to the bare name, and neither scan reading flags it, because the first element is a `BoolOp`.

*Re-check: resolved.* D2's first sub-bullet now gives one behaviour: off Windows `shutil.which("bash")`; on Windows the first existing file among `GIT_BASH`, Scoop's Git, `%ProgramFiles%`/`%ProgramFiles(x86)%\Git\bin\bash.exe` and `%LOCALAPPDATA%\Programs\Git\bin\bash.exe`, then `shutil.which("bash")` only when the result is not under `%SystemRoot%` or a `WindowsApps` folder, otherwise `None`. "`jjenv.find_bash()` moved and extended, and `jjenv` re-exports it" no longer contradicts the fallback. The duplicate resolvers and every `... or "bash"` fallback are removed (D2 first sub-bullet, task 4.3). The second sub-bullet and 4.3 move every "needs bash" skip guard to `bashexe.bash()`, so a machine with no Git Bash skips. See S6 for a few non-guard `shutil.which("bash")` sites that 4.3's wording does not list by kind.

**M3. Task 4.5's upstream branch leaves the Windows job red.** If the `0xC0000005` cause is in Git for Windows, 4.5 says "file it upstream and record the evidence on #145". It does not give the crashing tests an `#<n>` skip on Windows, which is the route D9 and the proposal require for a filed failure. The exit criterion needs every job green on this PR. The Workflow follow-up also closes #145 after merge, so a skip naming #145 would point to a closed issue. Nothing says what happens if the crash does not reproduce locally with the module alone, although the task depends on reproducing it.

*Re-check: resolved.* Task 4.5 now records the root cause and the code bears it out. On Windows `bash_path_env` (evals/vcs/vcs_test_support.py:22-44) converts every PATH entry with `cygpath -u` and joins them with `:`, which is a PATH only bash can read. `TestGitBackend.setUp` merges that PATH into `self.env` (test_git_backend.py:23), and `record_baseline` passes `self.env` to `jjenv.real_git()`, the native `git.exe` (test_git_backend.py:42-43). The push, fetch and pull baselines (lines 106, 161, 193) are the ones where git spawns helpers, which fits the three crashing tests. The task asks for a native PATH for native git "there" and for a check of "the module for other native launches that get the POSIX PATH"; lines 74-76 (`raw_env = {**self.env, ...}`) and 131-132 are two such launches, and the wording covers them. The fallback branch is the one M3 asked for: if it still fails because of Git for Windows, or stops reproducing locally, file an issue in this repository linking any upstream report and the CI evidence, and skip on Windows with that `#<n>` (D7/D9). Either path leaves the Windows `vcs` job green on this PR, with no skip naming #145. The regression check (the three failing tests) is listed in the Extra tests line.

### Suggestions

**S1.** The amendment did not reach the proposal. Its Impact → Evals list does not name `evals/bashexe.py`, `evals/runner/test_bare_bash.py`, the bash-3.2 check (4.4) or the `scripts/update.sh` fix. "Comes before any other `bash` on PATH" in What Changes now reads as the whole mechanism. Add one bullet. The Release Notes `### Fixed` can wait for 5.1 as planned.

*Re-check: addressed.* Impact → Evals names `evals/bashexe.py`, `test_bare_bash.py` and `test_bash3.py` (proposal.md:45). The `scripts/update.sh` fix itself is still named only in task 4.4; that is fine for Impact if the 5.1 Release Notes `### Fixed` mentions it.

**S2.** The new scenario sits under "CI runs every suite on Linux, Windows and macOS", but that requirement's body says nothing about how evals start bash. Add one sentence to the requirement body, for example "Evals SHALL start bash by the absolute path of Git Bash on Windows, never by the bare name", so the scenario follows from a SHALL.

*Re-check: addressed.* The requirement body ends "On Windows, every `bash` a job or an eval starts SHALL be Git for Windows' Git Bash; an eval SHALL NOT start bash by its bare name."

**S3.** Task 4.3 says "a rule for it in `evals/suites.json`" without naming suites. `evals/bashexe.py` will be imported by almost every suite (finish, git-workflow, pr-pair, release, review-routes, update, vcs, runner). Name them, as the `evals/vcs/**` rule does, so `run.py --changed` stays correct for anyone who still uses it.

*Re-check: partly addressed.* 4.3 now says "naming every suite that imports it", which states the rule but does not list the suites; the rebuttal's "4.3 names the suites" overstates it. Acceptable, since the importers are only known once 4.3 routes the sites.

**S4.** Task 4.4's bash-4 list (`mapfile`, `readarray`, associative arrays, `${x,,}`/`${x^^}`) covers the one site in shipped scripts today (scripts/update.sh:324, by grep). Adding `declare -n`/`local -n`, `wait -n`, `[[ -v`, `${x@Q}` and `&>>`/`|&` costs one regex each and catches the next one. Also name the test file (e.g. `evals/runner/test_bash32.py`) so the map test and the "Extra tests" line can point to it.

*Re-check: mostly addressed.* 4.4 names `evals/runner/test_bash3.py` and adds `typeset -A`, `${x,}`/`${x^}`, `coproc`, `|&`, `&>>` and `declare -n`/`local -n`. `wait -n` (bash 4.3), `[[ -v` (4.2) and `${x@Q}` (4.4) are still absent; adding them stays optional. The Extra tests line says "the bash-3.2 check of shipped scripts (4.4)" rather than the file name; minor.

**S5.** Scope against D9: the group-4 additions stay within its bound. The 50-site edit is mechanical, in eval helpers, and specified by the amended D2. 4.4 is a one-line shipped-script fix plus a lint test. 4.5 is open-ended, but M3's fix gives it D9's issue route. The uncommitted triage fixes (Python digest in the `but` step, `.resolve()` of the macOS temp dir, test_instructions.py needles following D8) are small and each has its test. A nit: the comment in `test_install_steps_check_digests_without_sha256sum` says macOS has "a BSD sha256sum without --check", while design Context says "macOS has no sha256sum". Make them agree.

*Re-check: addressed.* The macOS log line `usage: sha256sum [-bctwz] [files ...]` is the usage of the BSD `md5`-family `sha256sum`: it exists, takes a short `-c`, and rejects GNU's long `--check`. So the code comment (test_ci_workflow.py:328) is the accurate one. D3 (design.md:63) now says "macOS's BSD `sha256sum` has no `--check`", the proposal says the check "does not depend on `sha256sum --check`, which macOS's BSD `sha256sum` lacks", and no "macOS has no sha256sum" remains. design.md:21 still says the current step "checks with `sha256sum --check`", which correctly describes the starting state. The `but` step's Python digest check matches D3's jj check, and the new test asserts neither install step contains `sha256sum`.

**S6. (new, from the M2 re-check)** D2's second sub-bullet says "every eval that starts bash from Python uses it", but task 4.3 lists only the duplicate resolvers, `... or "bash"` fallbacks and skip guards. Other `shutil.which("bash")` sites that pick the bash to start are neither display literals (so `test_bare_bash.py` cannot see them) nor in 4.3's list:
- evals/pr-pair/record_markdown.py:34 (`bash = shutil.which("bash")`, then `subprocess.run([bash, AS_SH, ...])`);
- evals/pr-pair/test_bounded.py:369,397,414,438 (`os.environ.get("BASH") or shutil.which("bash")`, and `shutil.which("bash") or shutil.which("sh")`);
- evals/git-workflow/fixtures.py:1225 (`msys(shutil.which("bash") or "bash")` written into the `bin/bash` shim; the `or "bash"` part is covered, the `shutil.which` part is not).

In CI these resolve to Git's bash, because `GITHUB_PATH` puts `Git\bin` first, so the exit criterion is not at risk. On the contributor machine D2 describes (`Git\cmd` on PATH, WSL installed), they still pick `System32\bash.exe`. Add "and every other `shutil.which("bash")` used to pick the bash to start" to 4.3. Optionally, have `test_bare_bash.py` also flag `shutil.which("bash")` outside `evals/bashexe.py`.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) In design D2 (third sub-bullet of the amendment), task 4.2 and the test map row, define the scan so that it catches launches through variables and helpers:
   - The scan flags every `ast.List`/`ast.Tuple` display whose first element is the constant `"bash"`, wherever it appears.
   - A site is exempt only with an explicit inline marker on its line, such as `# bare-bash: not started` (or one named exemption list in the test), for expected-argv values and `as.sh` payloads. The marker list is reviewed like any other code.
   - 4.2's synthetic tests cover:
     - an inline call;
     - an argv held in a variable and then run;
     - an argv passed to a helper as a later argument;
     - an exempted expected value, which passes;
     - the same value without the marker, which fails.
   - Replace "naming the 50 call sites" with "naming every `["bash"` literal (50 lines in 21 files on the first run), and then each one is either routed through `bashexe.bash()` or marked".
   - Keep the spec scenario as written. With this scan the mechanism meets it.

   **Applied, re-checked.** D2's third amendment sub-bullet, task 4.2 and the test map row (`test_bare_bash_call_is_named, test_repo_has_no_bare_bash`).
2. (M2) In design D2's first amendment sub-bullet and task 4.3, make `bash()` one exact behaviour:
   - Either drop "then `shutil.which`" on Windows, so it stays `find_bash` moved, or keep a `shutil.which` fallback that rejects any path under `%SystemRoot%` and `WindowsApps`.
   - Add `%LOCALAPPDATA%\Programs\Git\bin\bash.exe` to the candidates.
   - State that `bash()` returns `None` when no Git Bash is found, and that every "needs bash" guard uses `bashexe.bash()` instead of `shutil.which("bash")`, so such a machine skips rather than raising `TypeError`.
   - In 4.3, replace the duplicate resolvers (`test_ci_workflow.git_bash`, `test_settings.bash`) and the `git_bash() or "bash"` fallbacks with `bashexe.bash()`.

   **Applied, re-checked.** Kept the `shutil.which` fallback with the `%SystemRoot%`/`WindowsApps` rejection, added `%LOCALAPPDATA%\Programs\Git\bin\bash.exe`, `None` when none is found, guards on `bashexe.bash()`; D2's first and second sub-bullets and task 4.3. (S6 suggests widening 4.3's list to the remaining non-guard `shutil.which("bash")` sites.)
3. (M3) In task 4.5, for the "cause is in Git for Windows" branch and for "does not reproduce locally": file an issue in this repository that links the upstream report and the CI evidence, and skip the affected tests on Windows with that `#<n>` in the reason (D7/D9). The Windows `vcs` job is then green on this PR, and the skip names an issue that stays open after #145 closes.

   **Applied, re-checked.** Task 4.5 carries that branch. The root cause has since been found (a POSIX-form PATH handed to native `git.exe` by `record_baseline`; minimal repro in the task), so 4.5 now fixes the test harness and keeps the issue-and-skip branch as the fallback. The code confirms the cause (vcs_test_support.py:22-44, test_git_backend.py:23,42-43).

CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **M1** fixed: D2 third sub-bullet (every list/tuple display starting with `"bash"`, `# bare-bash: not started` marker), task 4.2 (five synthetic cases, "every `["bash"` display"), test map row. — accepted by reviewer.
- **M2** fixed: D2 first and second sub-bullets (one exact `bash()` behaviour, `%LOCALAPPDATA%` candidate, System32/WindowsApps rejection, `None`, guards), task 4.3 (duplicate resolvers and `or "bash"` fallbacks removed). — accepted by reviewer.
- **M3** fixed: task 4.5 (repo issue plus `#<n>` Windows skip as the fallback branch; root cause recorded). — accepted by reviewer.
- **Suggestions:** proposal Impact names the three new files; the CI requirement gains a SHALL sentence for Git Bash and bare names; 4.3 names the suites for `evals/bashexe.py`; 4.4 widens the bash-4 list and names `evals/runner/test_bash3.py`; the `sha256sum` wording: the CI log shows macOS has a BSD `sha256sum` without `--check` (`usage: sha256sum [-bctwz]`), so the code comment stands and the design and proposal wording were corrected. — accepted by reviewer (S3 and S4 partly; see their re-check lines).
