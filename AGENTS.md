# Agent rules for this repository

These rules cover the evals in `evals/`. `CLAUDE.md` imports this file. It is not installed into projects: the install copies skills, schema and templates only.

## Running evals

- During a change, run `python evals/run.py --changed main`. It runs only the suites and test files that `evals/suites.json` maps the changed paths to (committed, staged, unstaged and untracked). Use `python evals/run.py --list-suites` to see the suites.
- Do not run every suite locally during a change. The CI workflow `.github/workflows/evals.yml` runs every suite on Linux for each pull request, one job per suite. Rely on it.
- Run every suite locally (`python evals/run.py`) only at a milestone close.
- A change that touches a path the map does not cover runs every suite. That is the safe default, not a fix.

## Keeping the map covering

- When you add a tracked file, add a rule for it to `evals/suites.json`, or list it in `no_eval` if no suite can break on it.
- `evals/runner` has a test that fails when a tracked file is uncovered, a rule names a missing suite or test file, or a `no_eval` pattern overlaps a rule. Run it after adding files.
