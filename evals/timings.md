# Eval suite wall times

Wall time of each eval suite run on its own, before and after the parallel runner and the fixture cache (change
`fix-eval-gaps`, design D8). `evals/runner/test_timings.py` checks this record.

- **Before:** the figures in [#127](https://github.com/sh1ny/specwright/issues/127), measured on this machine at the M4 close
  (2026-10-26), each suite run with `python -m unittest discover evals/<suite>`. No new before run was made.
- **After:** measured 2026-10-27, each suite run on its own with `python evals/run.py <suite>` (default `--jobs`, 24), one
  suite after another, with no other build, test or eval load from this work on the machine. Other agents were running.
- **Machine:** Intel Core i7-13700K (24 logical CPUs), 64 GB RAM, Windows 11 Pro 10.0.26300, git 2.55.0.windows.4,
  Python 3.14.4.

| Suite | Before (s) | Before tests | After (s) | After tests |
|---|---|---|---|---|
| pr-pair | 3725 | 559 | 2077 | 585 |
| update | 2607 | 95 | 1052 | 97 |
| review-routes | 729 | 157 | 737 | 165 |
| git-workflow | 716 | 323 | 535 | 338 |
| release | 348 | 118 | 477 | 173 |
| finish | 134 | 41 | 118 | 47 |
| Total | 8259 | 1293 | 4996 | 1405 |

The after run does more work than the before run: 0.8.1, 0.9.0 and this change added 112 tests to these suites.

Not faster: review-routes, release. Each runs a timing-sensitive file in `SERIAL` (`evals/run.py`) after the rest
of the suite, so it has only two files and gains little from running files at once: review-routes `test_review_run.py`,
release `test_release.py` (which also gained 55 tests since #127).

The `runner` suite (`evals/runner`, new in this change) has no before figure; it is excluded from both totals.

## Test IDs

`python evals/run.py --ids` for the six suites, compared with `openspec/changes/fix-eval-gaps/test-ids-base.txt` (the
IDs at the base commit, unittest loader discovery only): 1377 base IDs, 1405 now. Every base test ID is present.
28 IDs are new.

## The `vcs` suite (change `add-jj-backend`)

The `vcs` suite (`evals/vcs`, new in `add-jj-backend`) has no before figure and stays out of the table and totals above.
Measured 2026-10-30 with `python evals/run.py --jobs 2 vcs` (`--jobs 2`, not the default 24, because other agents were using
the machine; the other suites' figures above used the default), once, after group 7 added `test_pair.py` and `test_flows.py`.

| Suite | Wall (s) | Files | Tests | Jobs |
|---|---|---|---|---|
| vcs | 685.8 | 15 | 56 | 2 |

The run reported `1 of 15 files failed`: `test_git_backend.py` (3 of its 6 tests), where real `git` exited `0xC0000005` under
`GIT_TRACE` in `record_baseline`, before any Specwright code ran. It fails the same way when run on its own; the time counts the
whole suite, failed file included. The slowest files are the two flow tests (about 230 to 250 s each on their own), which build
a real jj repository and run Specwright's `git` calls through a logging shim.
