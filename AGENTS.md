# Agent rules for this repository

These rules cover the evals in `evals/`. `CLAUDE.md` imports this file. It is not installed into projects: the install copies skills, schema and templates only.

## Running evals

- During a change, rely on the CI workflow `.github/workflows/evals.yml`. It runs every suite on Linux, Windows and macOS for each pull request. Do not run a whole suite locally.
- Locally, run only the test module you are writing, red then green: `python -m unittest evals/<suite>/test_<x>.py`.
- After you add a tracked file, run the map test: `python -m unittest evals/runner/test_suite_map.py`.
- At a milestone close, rely on a green `gh workflow run evals.yml --ref main` run on the closing head of `main`. Do not run every suite locally.

## Keeping the map covering

- When you add a tracked file, add a rule for it to `evals/suites.json`, or list it in `no_eval` if no suite can break on it.
- `evals/runner` has a test that fails when a tracked file is uncovered, a rule names a missing suite or test file, or a `no_eval` pattern overlaps a rule. Run it after adding files.
