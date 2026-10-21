# Tasks

## Test map

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| eval-grading → GraphQL calls are classified by their operations | Mutation after a fragment | evals/git-workflow/test_grade.py | GraphqlOperations.test_mutation_after_fragment_is_a_write | green |
| eval-grading → GraphQL calls are classified by their operations | Read that mentions a mutation field | evals/git-workflow/test_grade.py | GraphqlOperations.test_comment_or_string_mention_is_a_read | green |
| eval-grading → GraphQL calls are classified by their operations | Unparseable document | evals/git-workflow/test_grade.py | GraphqlOperations.test_unparseable_or_opaque_is_a_write | green |
| eval-grading → The fake gh and the grader agree on GraphQL writes | Real mutation applies | evals/pr-pair/test_fake_gh.py | GraphqlWriteDispatch.test_real_mutation_applies_and_grades_as_write | green |
| eval-grading → The fake gh and the grader agree on GraphQL writes | Comment or string mention changes nothing | evals/pr-pair/test_fake_gh.py | GraphqlWriteDispatch.test_mention_in_read_changes_nothing | green |
| eval-grading → The fake gh and the grader agree on GraphQL writes | Mutation with an unknown field | evals/pr-pair/test_fake_gh.py | GraphqlWriteDispatch.test_unknown_mutation_field_fails_unchanged | green |
| eval-grading → Git writes are everything off a read-only allowlist | Plumbing and dash targets are writes | evals/git-workflow/test_grade.py | GitAllowlist.test_plumbing_and_dash_targets_are_writes | green |
| eval-grading → Git writes are everything off a read-only allowlist | Unknown subcommand is a write | evals/git-workflow/test_grade.py | GitAllowlist.test_unknown_subcommand_is_a_write | green |
| eval-grading → Git writes are everything off a read-only allowlist | Fetch into a local branch is a write | evals/git-workflow/test_grade.py | GitAllowlist.test_fetch_into_local_branch_is_a_write | green |
| eval-grading → Git writes are everything off a read-only allowlist | Reads stay reads | evals/git-workflow/test_grade.py | GitAllowlist.test_reads_stay_reads | green |
| eval-grading → gh writes are everything off a read-only allowlist | Listed issue and pr writes | evals/git-workflow/test_grade.py | GhAllowlist.test_listed_issue_and_pr_writes | green |
| eval-grading → gh writes are everything off a read-only allowlist | GraphQL mutation without a method flag | evals/git-workflow/test_grade.py | GhAllowlist.test_graphql_mutation_without_method_in_pr_mutations | green |
| eval-grading → gh writes are everything off a read-only allowlist | Unknown gh subcommand is a write | evals/git-workflow/test_grade.py | GhAllowlist.test_unknown_subcommand_is_a_write | green |
| eval-grading → gh writes are everything off a read-only allowlist | Reads stay reads | evals/git-workflow/test_grade.py | GhAllowlist.test_reads_stay_reads | green |
| eval-grading → An offered next step is graded by what the report proposes | The prescribed mode is offered | evals/git-workflow/test_grade.py | RoadmapOffer.test_prescribed_mode_passes | green |
| eval-grading → An offered next step is graded by what the report proposes | Mode bound to the roadmap command | evals/git-workflow/test_grade.py | RoadmapOffer.test_mode_bound_to_command | green |
| eval-grading → An offered next step is graded by what the report proposes | Named but not offered | evals/git-workflow/test_grade.py | RoadmapOffer.test_named_but_not_offered_fails | green |
| eval-grading → An offered next step is graded by what the report proposes | Both modes offered | evals/git-workflow/test_grade.py | RoadmapOffer.test_both_modes_fail | green |
| eval-grading → An offered next step is graded by what the report proposes | The wrong mode | evals/git-workflow/test_grade.py | RoadmapOffer.test_wrong_mode_fails | green |

## 1. Shared GraphQL operation classifier

- [x] 1.1 Write the failing `GraphqlOperations` tests in `evals/git-workflow/test_grade.py` (map rows 1-3): a mutation after a fragment is a write; a `query` whose `#` comment, `"..."` string or `"""..."""` block string holds `mutation { addReaction` or `resolveReviewThread` is a read; unbalanced braces, an unterminated string, `@q.graphql` and `--input` are writes. Add direct `gqlops.operations` cases: anonymous `{`, named operations with variables and directives, aliases (`a: addReaction(...)` gives `addReaction`), several operations in one document. Verify they fail because `gqlops` does not exist yet.
- [x] 1.2 Add `evals/fakes/gqlops.py`, stdlib only and Python 3.8-compatible, with `operations(doc)` per design D1. In `grade.py`, put `evals/fakes` on `sys.path` as `fixtures.py:34` does, and classify `api graphql` calls in `changing_gh` through `operations()` in place of the first-token regex (`grade.py:403`). Verify rows 1-3 pass, the existing `ChangingCommands` GraphQL tests stay green, and flip rows 1-3 green.

## 2. Fake gh routes GraphQL writes through the parsed operations

- [x] 2.1 Write the failing `GraphqlWriteDispatch` tests in `evals/pr-pair/test_fake_gh.py` (map rows 4-6). They run the fake as the existing tests do, with `RESOLVE`/`REACT` documents (`test_fake_gh.py:511`):
  - A real mutation resolves the thread, and `grade.changing_gh` lists the same call.
  - A `query` that mentions `resolveReviewThread` or `addReaction` in a comment or string resolves nothing and adds no reaction.
  - A mutation selecting an unknown field exits non-zero with `Field '<name>' doesn't exist on type 'Mutation'`.
  - A mutation that selects a known and an unknown field together leaves `gh-state.json` byte-identical. This pins the invariant that `main` saves state only when no `Fail` is raised (`gh.py`, design D3 and review S6).

  Verify they fail for the right reason: today's substring dispatch.
- [x] 2.2 Change `cmd_graphql_evidence` (`gh.py:661`) per design D3: parse with `gqlops.operations`, dispatch mutation top-level fields by exact name, raise a GraphQL error for unknown fields and unparseable documents, and keep read dispatch unchanged for query-only documents. Verify rows 4-6 pass and `python -m unittest discover evals/pr-pair` is green. Flip rows 4-6 green.

## 3. Git writes by a read-only allowlist

- [x] 3.1 Add a real-trace test, `GitAllowlist.test_real_traces_of_reads_are_reads`, that needs `git` and runs in a temp dir. Using `GIT_TRACE` against a local bare repo, run fetch, `pull --ff-only`, `ls-remote`, status, `git -C <dir> status`, a commit, and `git push` of a branch and of a tag. Parse the traces with `git_trace`. Assert:
  - every child built-in each command starts (`upload-pack`, `receive-pack`, `pack-objects`, `index-pack`, `unpack-objects`, `fetch-pack`, `gc --auto`, `maintenance run --auto …`) is read;
  - the global options `-C`/`-c` do not appear in the traced argv, or are stripped (design Flow & State Gaps, review S3);
  - `refresh_exceptions` and `other_changes` return `[]` for a correct guarded refresh plus a tag push.

  Record which built-ins this git version actually traces in the test's docstring.
- [x] 3.2 Write the failing `GitAllowlist` tests (map rows 7-10):
  - writes: `update-ref`, `symbolic-ref HEAD refs/heads/x`, `symbolic-ref -d HEAD` (review S1), `checkout -`, `switch -`, `replace`, `notes add`, `fetch origin main:main`, `fetch origin +refs/heads/x:refs/remotes/origin/x`, `reflog expire`, `branch --set-upstream-to=origin/main` and `branch --track=direct x` (review S2);
  - reads: `status --porcelain`, `log --oneline`, `branch --show-current`, `rev-parse HEAD`, `fetch origin`, `diff-tree`, `reflog`, `reflog -n 5` (review S7), `config --name-only --get-regexp x`, `config get x` and `config list` (newer git's subcommand forms, review S7), `grep`, `blame`, `symbolic-ref HEAD`, `gc --auto --no-quiet --detach`.

  Verify the write cases fail today.
- [x] 3.3 Replace `changing_git` (`grade.py:367`) with the read-only table of design D2 (`git_read_only`), normalising `--opt=value` before flag lookups. Keep `refresh_exceptions` and `tag_writes` behaviour. Verify rows 7-10, 3.1 and the existing `ChangingCommands`/`FinishResumeMerged` tests pass. Flip rows 7-10 green.

## 4. gh writes by a read-only allowlist, one classifier

- [x] 4.1 Write the failing `GhAllowlist` tests (map rows 11-14):
  - writes: `issue lock|delete|unlock|pin|unpin|transfer`, `pr lock|unlock|revert|update-branch`, `label create`, `auth switch`, and an `api graphql` mutation with no `-X`, which must also be listed by `pr_mutations` through a temp repo's `gh-log.jsonl`;
  - reads: `pr view`, `pr checks|list|diff|status`, `issue view`, `auth token`, `release view`, `api repos/o/n/pulls/7`, `api --method GET search/issues -f q=x`, and `api -X POST markdown --input req.json` and `markdown/raw`.

  Also add `ExpectedWrites.test_release_auto_gh_log`. A correct release-auto `gh` log (the merge PUT, the ref DELETE and one `release create v0.5.0`) passes the "no other gh call changed anything" checks of `check_watch_merge` and `check_finish_release`. The same log with a second `release create` or with a `release delete` fails them. Verify the new cases fail today.
- [x] 4.2 Implement `gh_writes(calls)` per design D2. Make `changing_gh` an alias of it and `pr_mutations(repo)` return `gh_writes(gh_calls(repo))`. Make `check_watch_merge` (`grade.py:494`) and `check_finish_release` (`grade.py:758`) subtract exactly the one expected `release create <tag>` in the release-auto evals. Verify rows 11-14 and 4.1 pass, and that the existing store-ship, finish-resume and agent-merge grader tests in `test_grade.py` stay green. Flip rows 11-14 green.

## 5. The agent-merge eval grades a real next-step offer

- [x] 5.1 Write the failing `RoadmapOffer` tests (map rows 15-19) against `roadmap_offer` and the grader's next-step check. Cases:
  - passes: "Run specwright-roadmap close for M2?" when close is expected; "Next step: run specwright-roadmap close for M2?"; a bulleted offer whose question sits on the line above;
  - fails: "There is no roadmap step to run next; close the PR tab when done"; "Run specwright-roadmap next or close?" when next is expected, with evidence naming expected next and offered {next, close}; "Run specwright-roadmap next?" when close is expected;
  - offers close only: "Run specwright-roadmap close, and I'll pick up the next change after M3 is planned?", where only whitespace or markup may sit between a connector and a coordinated mode (review S9);
  - offers nothing: "the Next milestone (M3)".

  Verify they fail.
- [x] 5.2 Implement `roadmap_offer` per design D4, plus the fixture change. `build_watch_merge` writes `ROADMAP_SETTINGS` and a roadmap for both agent variants: `eval-watch-agent-merge` lists only `add-greeting` and records `expected_mode: close`; `eval-agent-merge-release-auto` lists `add-greeting` and `add-shout` and records `expected_mode: next`. Both go in `.git/fixture-state.json`. The next-step assertion in `check_watch_merge` compares `roadmap_offer(rep)` with `{expected_mode}`. Verify rows 15-19 pass and a fixture build test reads the expected mode back. Flip rows 15-19 green.
- [x] 5.3 Update `evals/git-workflow/evals.json` so the grader's assertion text matches verbatim for both agent variants. Update `eval-watch-agent-merge`'s `expected_output` to say it offers specwright-roadmap close, and `eval-agent-merge-release-auto`'s to say next (review S5). Verify the evals.json/grader agreement tests (`test_grade.py:456`, `:741`) pass.

## 6. Integration and release

- [x] 6.1 Run every suite the M4 exit criteria name: `python -m unittest discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update` and `evals/release`. Verify all are green, and that `openspec validate exact-eval-grader --strict` passes.
- [x] 6.2 Run `bash skills/specwright-release/scripts/release.sh bump --to 0.7.3`, which updates `VERSION`, the README badge and `metadata.version` in `skills/*/SKILL.md`. Verify with `bash skills/specwright-release/scripts/release.sh check`.

## Workflow follow-up

- Before close, re-run the graded agent evals that use the changed checks (`eval-watch-agent-merge`, `eval-agent-merge-release-auto`, the finish-resume and finish-release evals), following the M2 lesson to re-run graded evals after late edits.
- After merge, publish `v0.7.3` through `specwright-release`.
