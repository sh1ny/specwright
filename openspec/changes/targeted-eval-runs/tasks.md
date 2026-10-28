# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| eval-runner → Changed paths select the suites | Renamed, deleted and untracked paths count | evals/runner/test_changed.py | `test_renamed_deleted_and_untracked_paths_count` | green |
| eval-runner → Changed paths select the suites | A change to one skill script | evals/runner/test_changed.py | `test_one_mapped_path_runs_only_its_suite` | green |
| eval-runner → Changed paths select the suites | A rule that targets one test file | evals/runner/test_changed.py | `test_a_file_target_runs_only_that_file` | green |
| eval-runner → Changed paths select the suites | An uncommitted file counts | evals/runner/test_changed.py | `test_an_unstaged_change_counts` | green |
| eval-runner → Changed paths select the suites | A path the map does not cover | evals/runner/test_changed.py | `test_an_uncovered_path_runs_every_suite` | green |
| eval-runner → Changed paths select the suites | Only paths that need no eval | evals/runner/test_changed.py | `test_only_no_eval_paths_run_nothing_and_exit_0` | green |
| eval-runner → Changed paths select the suites | A base that does not resolve | evals/runner/test_changed.py | `test_an_unknown_base_exits_2`, `test_a_base_with_no_merge_base_exits_2` | green |
| eval-runner → Changed paths select the suites | Suites named together with --changed | evals/runner/test_changed.py | `test_changed_with_suite_names_exits_2` | green |
| eval-runner → The suite map covers every tracked file | A complete map | evals/runner/test_suite_map.py | `test_every_tracked_file_is_covered_once` (live repo) | green |
| eval-runner → The suite map covers every tracked file | A new file no pattern covers | evals/runner/test_suite_map.py | `test_an_uncovered_file_is_named` | green |
| eval-runner → The suite map covers every tracked file | A pattern names a missing suite or file | evals/runner/test_suite_map.py, evals/runner/test_changed.py | `test_a_missing_target_is_named`, `test_changed_exits_2_on_a_missing_target` | green |
| eval-runner → The suite map covers every tracked file | A no-eval pattern overlaps a rule | evals/runner/test_suite_map.py, evals/runner/test_changed.py | `test_a_no_eval_overlap_is_named`, `test_a_rule_wins_over_an_overlapping_no_eval` | green |
| eval-runner → The suite map covers every tracked file | A path under a removed suite | evals/runner/test_changed.py | `test_a_path_under_a_removed_suite_runs_every_suite` | green |
| eval-runner → CI runs every suite on Linux for each pull request | All suites pass | evals/runner/test_workflow.py | `test_workflow_runs_each_listed_suite_on_linux` (structure); the PR's first green run is checked in Workflow follow-up | red |
| eval-runner → CI runs every suite on Linux for each pull request | A suite fails | evals/runner/test_workflow.py | `test_one_failing_suite_does_not_cancel_the_others` (`fail-fast: false`, the run step's exit code is the job's) | red |
| eval-runner → CI runs every suite on Linux for each pull request | A new suite appears | evals/runner/test_run.py, evals/runner/test_workflow.py | `test_list_suites_prints_every_suite_as_json`, `test_matrix_comes_from_list_suites` | red |
| eval-runner → CI runs every suite on Linux for each pull request | The suite list cannot be read | evals/runner/test_workflow.py | `test_suite_jobs_need_the_list_job` | red |
| eval-runner → The instructions say which suites to run when | Both files carry the rule | evals/runner/test_agent_instructions.py | `test_agents_and_contributing_carry_the_rule` | red |
| eval-runner → The instructions say which suites to run when | One file drops the rule | evals/runner/test_agent_instructions.py | `test_a_file_without_the_rule_is_named` | red |

## 1. Suite list and map model

- [x] 1.1 Write failing tests: `test_list_suites_prints_every_suite_as_json` in `evals/runner/test_run.py` (scratch `--root` with two suites and `fakes`), and the map validation tests in `evals/runner/test_suite_map.py` (`test_an_uncovered_file_is_named`, `test_a_missing_target_is_named`, `test_a_no_eval_overlap_is_named`) against a scratch map and file list. Verify each fails because `--list-suites` and the map checks do not exist yet.
- [x] 1.2 Implement `--list-suites` (JSON array of `find_suites`, exit 0, no test run), and the map model in `evals/run.py`, stdlib only (design D2):
  - loading `<root>/suites.json`, exiting 2 on unreadable or invalid JSON with the file and the parse error named;
  - `**`/`*` pattern translation;
  - union matching, with the built-in `evals/<suite>/` and shared-harness rules;
  - `no_eval` used only for unmatched paths;
  - suite and `suite/test_*.py` targets, validated against the root.

  Expose a coverage check the map test calls with a file list. Verify the 1.1 tests pass and flip their rows green.

## 2. `--changed` selection

- [x] 2.1 Write failing tests in `evals/runner/test_changed.py`. Each builds a scratch git repository holding an `evals/` root with fake suites (passing files that write a marker naming themselves) and a `suites.json`, and runs `run.py --root <that root> --changed main`; never the live checkout (design D3). Cover every `test_changed.py` row of the test map, including `test_changed_exits_2_on_a_missing_target`, `test_a_rule_wins_over_an_overlapping_no_eval`, and that a selected suite plus one of its files runs that file once. Verify they fail because `--changed` does not exist.
- [x] 2.2 Implement `--changed <base>` (design D3):
  - git commands run in `git -C <root> rev-parse --show-toplevel`;
  - the merge base, then `git diff --name-only -z --no-renames <mb>` plus `git ls-files -z --others --exclude-standard`;
  - exit 2 on an unknown base, no merge base, combined suite names or a missing target;
  - print each selected target with its paths, or `no eval suite covers these changes` and exit 0;
  - an uncovered path selects every suite;
  - run the selected suites and single files through the existing parallel/SERIAL runner, a file deduplicated into its suite.

  Update the module docstring's usage and exit codes. Verify `python -m unittest discover evals/runner` passes and flip the 2.1 rows green.

## 3. The real map

- [x] 3.1 Write `evals/suites.json` for this repository (design D2):
  - derive each rule with `grep` across the suites for the repo paths they read (`skills/**`, `schemas/**`, `templates/**`, `scripts/**`, `agents/**`, `README.md`, `CONTRIBUTING.md`, `VERSION`, `OPENSPEC_VERSION`);
  - send `openspec/**` to `git-workflow/test_specs_strict.py`;
  - send `evals/git-workflow/fixtures.py` and any other cross-suite import to the importing suites too;
  - send `evals/timings.md` and `skills/specwright-pr/scripts/bounded.py` to `runner` (plus the suites whose scripts use it);
  - put only paths no suite reads in `no_eval`, each checked by `grep`.

  Add `test_every_tracked_file_is_covered_once` to `evals/runner/test_suite_map.py`, running the coverage check over `git ls-files` of the live repo. Verify it passes and flip its row green. Then check that `python evals/run.py --changed main` on this branch prints a sensible selection.

## 4. CI workflow

- [ ] 4.1 Check the current major versions of `actions/checkout`, `actions/setup-python` and `actions/setup-node`, and Python 3.8 availability on the chosen Ubuntu image, against their docs (ctx7), and note them in the commit body. Write failing tests in `evals/runner/test_workflow.py`, using stdlib text checks on `.github/workflows/evals.yml`:
  - the `pull_request` and `workflow_dispatch` triggers and `permissions: contents: read`;
  - a list job running `python evals/run.py --list-suites`;
  - suite jobs that `needs:` it, with a matrix from its output and `fail-fast: false`;
  - `fetch-depth: 0` plus a local `main` created only when missing (`git show-ref --verify --quiet refs/heads/main || git branch main origin/main`, review S5);
  - the OpenSpec CLI installed from `OPENSPEC_VERSION`;
  - `SPECWRIGHT_PY38` pointing at a 3.8 interpreter;
  - `python evals/run.py --timeout 2400 ${{ matrix.suite }}`, and `timeout-minutes: 120` (design D4 Timeouts; the Resource Bounds row's "60 min" is a leftover, review S6).

  Verify they fail because the file does not exist.
- [ ] 4.2 Write `.github/workflows/evals.yml` per design D4 (concurrency per PR with `cancel-in-progress`, ubuntu runner, git identity and `init.defaultBranch main`). Verify the 4.1 tests pass and flip their rows green.

## 5. Agent and contributor instructions

- [ ] 5.1 Write failing tests in `evals/runner/test_agent_instructions.py`:
  - `AGENTS.md` and `CONTRIBUTING.md` each name `python evals/run.py --changed main`, the CI workflow and the milestone close;
  - `CLAUDE.md` holds the line `@AGENTS.md`;
  - a missing rule names the file.

  Verify they fail because `AGENTS.md` and `CLAUDE.md` do not exist.
- [ ] 5.2 Write `AGENTS.md` (this repository's agent rules: targeted runs during a change, CI for every suite on each PR, a full local run only at a milestone close, `evals/suites.json` kept covering new files) and `CLAUDE.md` (`@AGENTS.md`). Rewrite the eval section of `CONTRIBUTING.md` around `--changed`, the map and CI. Update `README.md` where it names eval commands, and the Evals row of `openspec/architecture.md`. Verify `python -m unittest discover evals/runner` passes, flip the 5.1 rows green, and run `python evals/run.py --changed main` (which now includes `git-workflow` for the README and CONTRIBUTING text tests) green.

## 6. Linux run

- [ ] 6.1 In WSL, install nothing, run from a clone of this branch in `/dev/shm/<dir>` with `TMPDIR` under `/dev/shm` (design D6), run `python3 evals/run.py`, and record each suite's result and per-file times. Remove the clone afterwards. Sort the failures:
  - those caused by a tool WSL lacks (OpenSpec CLI, Python 3.8) are listed for CI;
  - each other failure is a Linux defect: fix it test-first, and re-run the failing suite in WSL until it passes.

  If a fix grows beyond test, fixture or fake adjustments (a real POSIX product defect), stop and ask the user whether to fix it here or file it.
- [ ] 6.2 Check the timeouts against the 6.1 per-file times: no file may normally take more than half of `--timeout` (design Risks). Adjust `--timeout`/`timeout-minutes` and the 4.1 tests if needed. Verify `python -m unittest discover evals/runner` passes.

## 7. Release

- [ ] 7.1 Run `release.sh bump --to 0.9.2` and rewrite the summary of the proposal's `## Release Notes` to describe the whole release. Verify with `release.sh check` and `release.sh notes --proposal openspec/changes/targeted-eval-runs/proposal.md`, both exit 0.

## Workflow follow-up

- On the PR's first CI run: every suite check passes. Read the logs for skipped tests and account for each; only platform-only skips (Windows job objects, the Windows argument transport) are expected (design D6). A failure is handled as a watch CI round.
- Record the CI wall time per suite and the per-file maximum in the PR description. Lower `--timeout`/`timeout-minutes` from them if they sit far below the limits.
- Review S7 (the note on "Suite wall times are recorded" paraphrases the requirement): no artifact edit after review; the archive's spec sync is unaffected.
