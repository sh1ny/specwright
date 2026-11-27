# Spec Delta

## MODIFIED Requirements

### Requirement: The project is chosen by --project, then the command's own argument
A project command SHALL take an optional leading `--project <code checkout>` to choose the `VERSION` to check. For `sw as` and GitHub-aware `sw pr` commands it SHALL also select the code project's connection settings. It SHALL change neither the working directory, target repositories nor login. Without it the project SHALL be the code-checkout argument (`--code`, else `--repo` for `vcs`, `--dir` for `release` and `finish`), else the current directory, walked up to the first `.git`. An undo plan's relative `--code` starts at the `--dir` root.

#### Scenario: A store-started call
- **WHEN** the current directory is a planning store with no `VERSION` and `sw --project <code checkout> pr pair-state ...` runs
- **THEN** `sw` checks the code checkout's `VERSION`, and the subcommand runs with the store as its working directory and its own arguments unchanged

#### Scenario: Store-started call without --project
- **WHEN** the same call runs without `--project` and without `--code`
- **THEN** it prints the `sw_mismatch` document saying no installed version was found in the store, exits 1, and does no other work

#### Scenario: Two leading --project options
- **WHEN** a call starts with `--project a --project b`
- **THEN** `sw` stops with a usage error, exit 2, and does no other work

#### Scenario: A relative --code in the undo planner
- **WHEN** `sw finish --dir <store> undo-archive-plan ... --code ../code` runs from outside the store
- **THEN** the version checked is that of `../code` taken from the store's root, not from the current directory

### Requirement: The project root is found from the physical path
For every project command, `sw` SHALL resolve an existing version-check start (`--project`, `--code` or `--dir`, else the current directory) to its physical path, symbolic links resolved, before looking upward for the checkout whose `VERSION` it checks. A nonexistent start SHALL keep its given form. When the selected project supplies `sw as` or `sw pr` with connection settings, those settings SHALL come from the same checkout as the version check, never from a different target repository.

#### Scenario: A project path through a link and `..`
- **WHEN** on POSIX `sw --project /A/link/.. vcs state --repo /C --role code` runs, `link` points to `/B/subdir`, and only `/B`'s `VERSION` matches the running `sw`
- **THEN** the version check reads `/B`, the command proceeds, and the state document's `head` is `/C`'s

#### Scenario: Stale settings in a shared store do not choose its GitHub host
- **WHEN** `sw --project <code> as store-bot ...` runs inside a planning store with competing settings on disk in the store and the code project specifies `github.example.com`
- **THEN** the command runs inside the store but credential lookup and verification use `github.example.com`, not the store's settings
