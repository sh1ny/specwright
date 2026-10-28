# Proposal

## Why

The M4 reviews left seven open eval gaps. Two of them are false passes, where a run that changed state can still pass: a GraphQL mutation sent with `-X GET` is graded as a read (#119), and a `git fetch` that stores a ref auto-follows tags but is graded as a read (#121). The others are false fails (#122, #123, #124), or places where the fake `gh` is looser than GitHub (#125). The suites also take about two and a half hours on Windows, almost all of it spent starting processes (#127), so they rarely run in full. This change serves M5 - Commits and VCS backends. It advances the exit criteria "every issue in the changes below is closed by a merged PR, with a regression test in `evals/`", "the six named eval suites pass" and "each eval suite's wall time on Windows is measured before and after `fix-eval-gaps`, and the total is lower", and it ships as release 0.9.1.

## What Changes

- **GraphQL by endpoint (#119):** the grader sends every `gh api` call whose endpoint is `graphql` through the GraphQL classification, whatever its method and wherever its options stand (`gh api -X GET graphql -f query='mutation{...}'` is a write).
- **Fetch that stores a ref is a write (#121):** a traced `git fetch` that passes today's checks (no `+`, no `tag`, destinations only under `refs/remotes/`) counts as read-only only with `--no-tags`/`-n`, a `--dry-run`, or when every refspec it names has no destination (`git fetch origin main`, `git fetch origin refs/tags/v1`). A fetch with no refspec, with `--all`/`--multiple`, or with a `src:dst` refspec auto-follows tags and is a write. Checked on git 2.55 (see design). The `git fetch --update-head-ok` that `git pull` runs as its own child is judged as part of that pull, not on its own, so the finish skill's guarded refresh stays allowed.
- **Quiet branch list and tag verify are reads (#122, #123):** `git branch -q --list` / `--quiet --list` and `git tag -v <tag>` / `--verify <tag>` are read-only.
- **operationName decides what runs (#124):** when a `gh api graphql` call names `-f operationName=<name>`, the grader classifies only the operations with that name, as the fake executes only that one. A name that matches nothing is still a write (fail-closed).
- **Duplicate operation names fail (#125):** the fake `gh` rejects a document in which the named operation appears more than once, as GitHub does, and leaves its state unchanged.
- **Fewer process launches (#127):**
  - each fixture repo shape is built once per test process and copied for each test instead of rebuilt;
  - the fake `gh` runs in the test process where the test calls it directly, with no script in between;
  - a standard-library runner, `evals/run.py`, runs each test file as its own process in parallel and prints each suite's wall time.

  `evals/timings.md` records each suite's Windows wall time after the change against the #127 figures (2026-10-26, same machine) as the before column, and every test keeps its assertions.

## Capabilities

### New Capabilities

- `eval-runner`: how the eval suites are run as a whole. Each test file is its own process, run in parallel; the result is a single pass or fail with each suite's wall time; and the before/after timing record.

### Modified Capabilities

- `eval-grading`: GraphQL detection by endpoint whatever the method (#119). A fetch that may store refs or tags is a write, with the pull-child rule (#121). Quiet branch listing and tag verification are reads (#122, #123). The executed operation (`operationName`) decides GraphQL classification (#124). The fake rejects duplicate operation names (#125).

## Impact

- Code: `evals/git-workflow/grade.py` (`gh_read_only`, `graphql_read_only`, `git_read_only` fetch, branch and tag rules, `changing_git`, `refresh_exceptions`), `evals/fakes/gh.py` (`cmd_graphql_evidence`, plus an in-process entry point that leaves the CLI behaviour unchanged).
- Test infrastructure: the fixture builders in `evals/git-workflow/fixtures.py`, `evals/finish/fixtures.py`, `evals/update/fixtures.py`, `evals/release/fixtures.py` and the pr-pair helpers (a build-once cache), `evals/pr-pair/test_fake_gh.py` (in-process calls), the new `evals/run.py`, and `evals/timings.md`.
- Tests: new regression tests in `evals/git-workflow/test_grade.py` and `evals/pr-pair/test_fake_gh.py` for each issue; `test_real_traces_of_reads_are_reads` and the "reads stay reads" lists are updated for the fetch rule.
- Docs: `README.md` and `CONTRIBUTING.md` name `python evals/run.py` next to the per-suite `unittest discover` commands, which keep working.
- No skill, script or schema text changes. Skill scripts fetch with `--no-tags`, or with a refspec that has no destination. The one `src:dst` fetch, `release.sh`'s tag fetch, is graded as a write under both rules, so the tighter rule changes no grade of a skill script's fetch.
- Version: 0.9.1 (patch). This change is eval tooling only, with no change to what an installed project runs.

## Release Notes

0.9.1 closes the eval gaps left by M4. The grader no longer passes a run that wrote through a GraphQL mutation sent as GET or through a tag-following fetch; a few git reads and a GraphQL query that `operationName` picks from beside a mutation stop counting as writes; and the fake `gh` rejects duplicate operation names as GitHub does. A new parallel runner cuts the six eval suites from about 8,260 s to about 5,000 s on Windows, with every test kept.

### Added
- `evals/run.py` runs the eval suites with each test file as its own parallel process and prints each suite's wall time; `evals/timings.md` records the Windows times before and after (#127)

### Changed
- The eval fixtures build each repo shape once and copy it for each test, and the fake `gh` tests call it in-process, so each test starts fewer processes (#127)

### Fixed
- A `gh api graphql` call with options before the endpoint, such as `-X GET`, is classified by its GraphQL operations, so a mutation sent that way is a write (#119)
- A `git fetch` that stores refs (no refspec, `--all`/`--multiple`, or a `src:dst` refspec) without `--no-tags` is graded as a write, because it follows tags; the child fetch of `git pull` is judged with the pull (#121)
- `git branch -q --list` and `git branch --quiet --list` are graded as reads (#122)
- `git tag -v <tag>` and `git tag --verify <tag>` are graded as reads (#123)
- The grader classifies only the GraphQL operation that `operationName` selects, matching the fake (#124)
- The fake `gh` rejects a document with several operations of the requested name and changes nothing, as GitHub does (#125)
