# Proposal

## Why

The code work in a change now takes a small part of its time. Most of the time goes to eval runs: the six suites take about 83 minutes on Windows even after `fix-eval-gaps`, every test builds and deletes throwaway git repos on the developer's SSD, and a change runs every suite whatever it touched. Most changes touch one skill or script, so most of that run checks code that did not change. This change serves M5 (Commits and VCS backends), so the four changes after it get faster cycles. It advances the exit criteria "a change runs only the eval suites its changed paths map to, and a GitHub Actions workflow runs every eval suite on Linux for each pull request and passes on the PR that adds it" and "the six named eval suites pass". It ships as release 0.9.2.

## What Changes

- **Changed paths pick the suites:** `evals/suites.json` maps repository path patterns to the eval suites, or single test files, that exercise them. `python evals/run.py --changed <base>` collects the paths changed since the merge base with `<base>`, committed, staged, unstaged and untracked, and runs only the suites they map to. It prints which suites it chose and why.
  - A changed path no pattern matches runs every suite (fail-closed).
  - A path listed as needing no eval (ADRs, for example) runs nothing.
  - No suite selected → the runner says so and exits 0.
  - A runner test fails when a tracked file matches no pattern, so the map cannot fall behind silently.
- **Full runs move to CI:** `.github/workflows/evals.yml` runs every eval suite on Linux for each pull request, one job per suite, with the pinned OpenSpec CLI. The suite list comes from `python evals/run.py --list-suites`, so a new suite needs no workflow edit. PR watch already waits for checks and handles a failing one, so no skill changes. A full local run is left for a milestone close.
- **Linux passes:** any suite failure that shows up only on Linux is fixed in this change. No test is skipped or weakened to get a green run.
- **Instructions say which run when:** a new tracked `AGENTS.md` (read by Codex and OMP, and imported by a one-line `CLAUDE.md` for Claude Code) tells agents working on this repository to run `python evals/run.py --changed main` during a change, and to run every suite only at a milestone close. `CONTRIBUTING.md` says the same and describes `evals/suites.json` and the CI workflow. `openspec/config.yaml` is git-ignored here, so it cannot carry the rule.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `eval-runner`: adds path-based suite selection (`--changed`), the path map and its coverage check, and the CI workflow that runs every suite on Linux for each pull request.

## Impact

- Code: `evals/run.py` (`--changed`), new `evals/suites.json`, new `.github/workflows/evals.yml`. Linux-only fixes may touch eval fixtures, fakes or tests.
- Tests: `evals/runner/test_run.py` (selection, fail-closed, no-suite exit), and a new map coverage test in `evals/runner`.
- Docs and instructions: new `AGENTS.md` and `CLAUDE.md` at the repository root (not installed into projects), `CONTRIBUTING.md`, `README.md` if it names the eval commands, and the Evals row of `openspec/architecture.md`.
- No skill, script, schema or template text changes. Installed projects run nothing new; only this repository's development workflow changes.
- Version: 0.9.2 (patch). Like 0.9.1, it changes eval tooling only.

## Release Notes

0.9.2 sizes eval runs to the change and moves full runs to CI. `python evals/run.py --changed main` runs only the eval suites the changed paths map to, a GitHub Actions workflow runs every suite on Linux for each pull request, and the suites now pass on Linux. Installed projects see no change: only this repository's eval tooling and contributor instructions changed.

### Added
- `python evals/run.py --changed <base>` runs only the eval suites that `evals/suites.json` maps the changed paths to. A path the map does not cover runs every suite.
- A GitHub Actions workflow runs every eval suite on Linux for each pull request.

### Changed
- `CONTRIBUTING.md` and the new `AGENTS.md` (imported by `CLAUDE.md`) say to run the changed suites during a change and every suite at a milestone close.

### Fixed
- The eval suites' fake `gh` and helper shims run the test's own Python interpreter, so the suites pass on a Linux host that has no `python` command.
