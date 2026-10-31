# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| eval-runner → The runner runs each test file as its own process | All files pass | evals/runner/test_run.py | test_all_files_pass (asserts `0 skipped` in the suite line) | green |
| eval-runner → The runner runs each test file as its own process | Skips are counted per suite | evals/runner/test_run.py | test_skips_are_counted_per_suite | green |
| eval-runner → The runner runs each test file as its own process | A file fails | evals/runner/test_run.py | test_a_failing_file_is_reported_and_kept | green |
| eval-runner → The runner runs each test file as its own process | Unknown suite | evals/runner/test_run.py | test_unknown_suite_exits_2 | green |
| eval-runner → The runner runs each test file as its own process | A file's process crashes | evals/runner/test_run.py | test_a_crashing_file_is_reported | green |
| eval-runner → The runner runs each test file as its own process | A file times out | evals/runner/test_run.py | test_a_timed_out_file_tree_is_stopped | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | All suites pass | evals/runner/test_workflow.py | test_workflow_runs_each_listed_suite_on_three_oses | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | A suite fails | evals/runner/test_workflow.py | test_one_failing_suite_does_not_cancel_the_others | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | A suite fails on one OS | evals/runner/test_workflow.py | test_job_name_and_fail_fast_cover_each_os | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | A new suite appears | evals/runner/test_workflow.py | test_matrix_comes_from_list_suites | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | The suite list cannot be read | evals/runner/test_workflow.py | test_suite_jobs_need_the_list_job | green |
| eval-runner → Windows jobs and evals start Git Bash | Windows runs the POSIX userland of Git Bash | evals/runner/test_workflow.py | test_steps_run_under_bash_with_git_usr_bin_first_on_windows | green |
| eval-runner → Windows jobs and evals start Git Bash | A test starts bash by bare name | evals/runner/test_bare_bash.py | test_bare_bash_call_is_named, test_repo_has_no_bare_bash | green |
| eval-runner → CI runs every suite on Linux, Windows and macOS for each pull request | A job runs past its timeout | evals/runner/test_workflow.py | test_job_and_run_timeouts_are_per_os | green |
| eval-runner → The instructions say which suites to run when | Both files carry the rule | evals/runner/test_agent_instructions.py | test_agents_and_contributing_carry_the_rule | green |
| eval-runner → The instructions say which suites to run when | One file drops the rule | evals/runner/test_agent_instructions.py | test_a_file_without_the_rule_is_named | green |
| eval-runner → The instructions say which suites to run when | A file brings back a local suite run | evals/runner/test_agent_instructions.py | test_a_local_suite_run_is_named | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | CI run | evals/runner/test_ci_workflow.py | test_workflow_installs_pinned_jj_on_each_os | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Checksum mismatch | evals/runner/test_ci_workflow.py | test_workflow_checks_jj_sha256_before_use (per OS row) | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Runner with no pinned archive | evals/runner/test_ci_workflow.py | test_unknown_runner_fails_before_download | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Local run without jj | evals/runner/test_jjenv.py | test_jj_missing_skips_with_reason | green |
| eval-runner → Suites that need jj run with a pinned jj in CI | Required but missing | evals/runner/test_jjenv.py | test_jj_missing_required_fails | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | CI run | evals/runner/test_ci_workflow.py | test_workflow_installs_pinned_but_for_vcs_on_linux_only | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | macOS and Windows jobs | evals/runner/test_ci_workflow.py | test_but_requirement_is_set_on_linux_only | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Upstream released a new version | evals/runner/test_ci_workflow.py | test_workflow_pins_but_build_url | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Downloaded bytes differ | evals/runner/test_ci_workflow.py | test_workflow_checks_but_sha256_before_use | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Local run without `but` | evals/runner/test_butenv.py | test_but_missing_skips_with_reason | green |
| eval-runner → Suites that need GitButler run with a pinned `but` in CI | Required but missing | evals/runner/test_butenv.py | test_but_missing_required_fails | green |
| eval-runner → A test skipped on one OS names its issue | A per-OS skip with its issue | evals/runner/test_platform_skips.py | test_os_skip_naming_an_issue_passes | green |
| eval-runner → A test skipped on one OS names its issue | A mechanism that exists on one OS only | evals/runner/test_platform_skips.py | test_platform_prefixed_skip_passes | green |
| eval-runner → A test skipped on one OS names its issue | A per-OS skip with neither | evals/runner/test_platform_skips.py | test_os_skip_with_neither_is_named | green |
| eval-runner → A test skipped on one OS names its issue | A skip inside an OS branch | evals/runner/test_platform_skips.py | test_skiptest_inside_os_branch_is_named | green |

Extra tests (no scenario row): `evals/runner/test_ci_workflow.py` `test_version_pin_files_check_out_lf` (design D6) and `test_install_steps_check_digests_without_sha256sum` (4.6); the bash-3.2 check of shipped scripts (4.4); the `test_git_backend` crash regression test (4.5). From the 4.6 triage: `test_schema_files_check_out_lf` (`evals/runner/test_ci_workflow.py`), `test_resolved_bash_keeps_the_callers_path_first` (`evals/runner/test_bare_bash.py`), and in `evals/update/test_update.py` `TestStaleLockRaceBsdMv` (the stale-lock races with a `mv` that has no `-T`) and `test_lock_a_third_run_took_before_the_put_back_is_kept`. Integration: the real matrix run in group 4 is the end-to-end check of every CI scenario above.

## 1. Runner: skipped counts and the per-OS skip scan

- [x] 1.1 Write `test_skips_are_counted_per_suite` and extend `test_all_files_pass` to expect `K skipped` in the suite line (design D10). Run `python -m unittest evals/runner/test_run.py` and see both fail on the missing field.
- [x] 1.2 In `evals/run.py`, read `skipped=N` from each file's closing `OK (...)`/`FAILED (...)` line, sum it per suite and print `suite: F files, T tests, K skipped, S.Ss`. Update the module docstring's output line. Verify `test_run.py` passes and flip both rows green.
- [x] 1.3 Write `evals/runner/test_platform_skips.py` (design D7). It holds an AST scan of `evals/**/test_*.py` for `skipIf`/`skipUnless` (decorator or call), `self.skipTest` and `raise unittest.SkipTest` under a condition that reads `os.name`, `sys.platform` or `platform.system`. A reason passes when it matches `#\d+` or starts with `platform:`. Add the four scenario tests on synthetic sources in a temp dir, plus `test_repo_skips_pass` over the real tree. Run it and see `test_repo_skips_pass` fail, naming the six existing sites (`test_bounded.py:242,253,446`, `test_review_run.py:1033,1072`, `test_pr_reply.py:209-210`).
- [x] 1.4 Prefix those six reasons with `platform: ` without changing their conditions. Add a rule for `evals/runner/test_platform_skips.py` to `evals/suites.json` if `evals/runner/**` does not already cover it. Verify `python -m unittest evals/runner/test_platform_skips.py evals/runner/test_suite_map.py` passes and flip the four rows green.

## 2. Workflow: OS matrix, Git Bash, per-OS jj, Linux-only `but`, pin files

- [x] 2.1 File the GitHub issue for the macOS/Windows `but` gap, as KintsugiBot with the fenced `gh`. It says that GitButler ships a standalone `but` only for Linux (the manifest platforms in design Context), that GitButler tests skip on macOS and Windows CI, and what would close it. Verify by recording the issue number in the PR notes for 2.6.
- [x] 2.2 Write the failing workflow tests in `evals/runner/test_workflow.py`:
  - `test_workflow_runs_each_listed_suite_on_three_oses`: `matrix.os` holds exactly `ubuntu-24.04`, `windows-latest` and `macos-latest`, and `runs-on: ${{ matrix.os }}`.
  - `test_job_name_and_fail_fast_cover_each_os`: the job name holds both suite and os, and `fail-fast: false`.
  - `test_steps_run_under_bash_with_git_usr_bin_first_on_windows`: `defaults.run.shell: bash`, and a step `if: runner.os == 'Windows'` writes Git's `usr\bin` and then `bin` to `GITHUB_PATH` and logs `command -v bash cygpath sed` and Python's `shutil.which('bash')`.
  - `test_job_and_run_timeouts_are_per_os`: `matrix.include` gives each OS a `timeout` and a `run_timeout`, used by `timeout-minutes` and `--timeout`.

  Remove the Linux-only `test_workflow_runs_each_listed_suite_on_linux`. Update the module docstring. Run `python -m unittest evals/runner/test_workflow.py` and see the new tests fail.
- [x] 2.3 Write the failing tests in `evals/runner/test_ci_workflow.py`:
  - `test_workflow_installs_pinned_jj_on_each_os`: for `Linux/X64`, `macOS/ARM64` and `Windows/X64` (set through `RUNNER_OS`/`RUNNER_ARCH`), the fake `curl` is asked for that row's asset URL, a local `.tar.gz` or `.zip` fixture is unpacked, and `jj`/`jj.exe` runs. Each row's pinned digest appears in the step:
    - `fce0271158e665ceb82dc66c5eb95b1728649094e9133074f3b5baece345fc08` (Linux);
    - `43daa37ce0f9716cdf6fb65a29cbcae74a3160aef048cf3cb3d166d41cb4ab58` (macOS arm64);
    - `c42316b10df04611bc65029a18bcb2d92636edddb6871d511f7bb4233e999b83` (Windows x64).
  - `test_workflow_checks_jj_sha256_before_use`, extended per row: a mismatch fails and nothing is unpacked or run.
  - `test_unknown_runner_fails_before_download`: `Linux/ARM64` fails naming the pair, and `curl` is never called.
  - `test_workflow_installs_pinned_but_for_vcs_on_linux_only`: the `but` step's `if` is `matrix.suite == 'vcs' && runner.os == 'Linux'`. It replaces `test_workflow_installs_pinned_but_for_vcs_only` and keeps its install and version-mismatch checks.
  - `test_but_requirement_is_set_on_linux_only`: no job-level `SPECWRIGHT_REQUIRE_BUT`; a step `if: runner.os == 'Linux'` appends `SPECWRIGHT_REQUIRE_BUT=1` to `GITHUB_ENV`.
  - `test_version_pin_files_check_out_lf`: `git check-attr eol` reports `lf` for `OPENSPEC_VERSION`, `JJ_VERSION`, `BUT_VERSION` and `VERSION`.

  Run `python -m unittest evals/runner/test_ci_workflow.py` and see each fail for the missing behaviour.
- [x] 2.4 Edit `.github/workflows/evals.yml` (design D1-D5):
  - Add the `os` matrix with per-OS `include` timeouts (Linux 45/1200, macOS 60/1800, Windows 120/3600), `fail-fast: false`, `runs-on: ${{ matrix.os }}` and the job name `${{ matrix.suite }} (${{ matrix.os }})`.
  - Set `defaults.run.shell: bash` and add the Windows PATH step first.
  - Move the Python setup steps before jj.
  - Rewrite `Install pinned jj` as the `case "$RUNNER_OS/$RUNNER_ARCH"` table, with the `hashlib` check before unpacking (`tar`, or `python -m zipfile -e`).
  - Give the `but` step the Linux condition and a comment naming the 2.1 issue.
  - Replace the job-level `SPECWRIGHT_REQUIRE_BUT` with the Linux-only `GITHUB_ENV` step.
  - Use the matrix timeouts.

  Verify that `test_workflow.py` and `test_ci_workflow.py` pass on this machine (Git Bash), and flip their rows green.
- [x] 2.5 Add `*VERSION text eol=lf` to `.gitattributes` and run `git add --renormalize OPENSPEC_VERSION JJ_VERSION BUT_VERSION VERSION`. Verify `test_version_pin_files_check_out_lf` passes, and that `git ls-files --eol` shows `w/lf` for the four files after a fresh checkout of them.
- [x] 2.6 Re-run the unchanged green rows' tests: `test_one_failing_suite_does_not_cancel_the_others`, `test_matrix_comes_from_list_suites`, `test_suite_jobs_need_the_list_job`, `test_workflow_pins_but_build_url`, `test_workflow_checks_but_sha256_before_use`, `test_jjenv.py` and `test_butenv.py`. Verify they pass.

## 3. Instructions: CI first, no local suite runs

- [x] 3.1 Rewrite `evals/runner/test_agent_instructions.py` (design D8):
  - Both `AGENTS.md` and `CONTRIBUTING.md` must name `.github/workflows/evals.yml`, the single-module run (`python -m unittest evals/<suite>/test_`), the map test (`evals/runner/test_suite_map.py`) and `milestone close`.
  - `CLAUDE.md` must import `AGENTS.md`.
  - `test_a_file_without_the_rule_is_named` is updated for the new needles.
  - A new `test_a_local_suite_run_is_named` fails naming the file and command when `AGENTS.md`, `CONTRIBUTING.md` or `README.md` holds `python evals/run.py --changed main` or `python -m unittest discover evals/`.

  Run it and see it fail on today's text.
- [x] 3.2 Rewrite the AGENTS.md "Running evals" section, the CONTRIBUTING.md testing section (line 42 and the per-area bullets at 44-51; keep the Python 3.8 note naming `test_pass_write_on_python38`) and `README.md:629`:
  - During a change, rely on the CI matrix.
  - Locally, run only the module you are writing, red then green, and the map test after adding a tracked file.
  - At a milestone close, a green `gh workflow run evals.yml --ref main` run on the closing head of `main`.

  Update the evals row of `openspec/architecture.md` ("on Linux" → the three OSes). Verify `test_agent_instructions.py` passes and flip its three rows green.
- [x] 3.3 In `openspec/roadmap.md`, change this change's M6 line from "a pinned, checksummed jj and `but` per OS" to a pinned, checksummed jj per OS with `but` on Linux only, naming the 2.1 issue. Verify by `git diff openspec/roadmap.md` showing only that line.

## 4. First matrix runs: triage and measured timeouts

- [x] 4.1 Push the branch with `[vcs] push` through the fence (no PR yet) and run `gh workflow run evals.yml --ref chore/ci-os-matrix` as KintsugiBot. Collect each job's result, wall time, slowest file and the `K skipped` per suite and OS. Verify the run's jobs list shows all 3 × suites jobs.
- [x] 4.2 Write `evals/runner/test_bare_bash.py` (amended D2): an `ast` scan of every `evals/**/*.py` that flags every list or tuple display whose first element is the string constant `"bash"`, failing with `<file>:<line>`, unless its line carries `# bare-bash: not started`. Synthetic-source tests (`test_bare_bash_call_is_named`) cover an inline call, an argv held in a variable and then run, an argv passed to a helper as a later argument, a marked expected value (passes) and the same value unmarked (fails). Add `test_repo_has_no_bare_bash` over the real tree. Run it and see the repo test fail, naming every `["bash"` display (50 lines in 21 files on the first run).
- [x] 4.3 Add `evals/bashexe.py` with `bash()` as amended D2 states (`jjenv.find_bash()` moved and extended; `jjenv` re-exports it; `None` when no Git Bash is found on Windows). Add a rule for it to `evals/suites.json` naming every suite that imports it. Route each display 4.2 names through `bashexe.bash()`, or mark it `# bare-bash: not started` when it is never started. Replace `test_ci_workflow.git_bash`, `test_settings.bash`, every `... or "bash"` fallback and every `shutil.which("bash")` skip guard with `bashexe.bash()`, and the bash-picking `shutil.which("bash")` calls the scan cannot see (`evals/pr-pair/record_markdown.py:34`, `evals/pr-pair/test_bounded.py:369,397,414,438`, `evals/git-workflow/fixtures.py:1225`). The `evals/suites.json` rule names each suite whose files import it (finish, git-workflow, pr-pair, release, review-routes, runner, update, vcs, as the routing turns out). Verify `python -m unittest evals/runner/test_bare_bash.py evals/runner/test_suite_map.py evals/runner/test_jjenv.py` passes and flip its row green; the next dispatch run verifies the routed suites.
- [x] 4.4 Fix `scripts/update.sh`'s `mapfile` (bash 4) so it runs on macOS's bash 3.2. First write `evals/runner/test_bash3.py`: it fails, naming file and line, when a shipped bash script (`scripts/*.sh`, `skills/*/scripts/*.sh`) uses a bash-4-only feature (`mapfile`, `readarray`, `declare -A`/`local -A`/`typeset -A`, `${x,,}`/`${x^^}`/`${x,}`/`${x^}`, `coproc`, `|&`, `&>>`, `declare -n`/`local -n`, `wait -n`, `[[ -v`, `${x@Q}` and the other `@` transformations). See it fail on today's tree, then fix every site it names and verify it passes.
- [x] 4.5 Fix the `test_git_backend` `0xC0000005` crash that CI reproduced on Windows. Root cause found during the amendment: on Windows `bash_path_env()` builds a POSIX-form PATH (`/usr/bin:/mingw64/bin:/c/...`) for bash, and `record_baseline` hands it to native `git.exe`, which crashes spawning its pack helpers for `push`/`fetch` (a minimal repro passes with the native PATH and crashes with the POSIX one). Give native `git` a native PATH there, and check the module for other native launches that get the POSIX PATH. The three failing tests are the regression check: verify `test_git_backend.py` passes locally, where it reproduces. If it still fails and the cause is in Git for Windows, or it stops reproducing locally, file an issue in this repository that links any upstream report and the CI evidence, and skip the affected tests on Windows with that `#<n>` in the reason (D7/D9).
- [x] 4.6 Triage each remaining failing job and each suite whose skipped count differs between OSes (design D9). For each finding, either:
  - fix it with a regression test in its suite, verified red then green by that module locally where it reproduces and by the next CI run; or
  - file an issue and give the skip an `#<n>` reason, which `test_platform_skips.py` accepts.

  The first run's other fixes go here: `test_instructions.py` still required `unittest discover evals/update` in the docs; the `but` step used GNU `sha256sum --check` (`test_install_steps_check_digests_without_sha256sum`); the review-routes tests compared unresolved macOS temp paths. Verify with a dispatch run in which every job passes.
- [x] 4.7 If a job or file runs past its timeout, follow the design's Risks steps in order: raise the timeouts toward the 360-minute cap, then split. Splitting a suite across matrix jobs changes the "one job per suite and OS" requirement and `run.py`'s targets. Before doing it, stop and amend the spec delta, then rerun the design review. Verify with a dispatch run in which every job passes.
- [x] 4.8 Set each OS's `timeout` and `run_timeout` to about 1.5 × the measured slowest job and slowest file, rounded up. Record the measurements in a CI section of `evals/timings.md`, in a form that `test_timings.py`'s suite-row pattern does not match. Verify that `python -m unittest evals/runner/test_timings.py evals/runner/test_workflow.py` passes and a final dispatch run is all green.

## 5. Release 0.12.1

- [ ] 5.1 Run `release.sh bump --to 0.12.1`. Rewrite the summary of the proposal's `## Release Notes` to describe the whole release, including any fixes from group 4 in `### Fixed`. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/ci-os-matrix/proposal.md`.

## Workflow follow-up

- Pre-ship review, then open the PR. The PR's own matrix run must be all green: that is the milestone's exit criterion for this change.
- After merge, close #145 with the result of the `test_git_backend` crash triage.
