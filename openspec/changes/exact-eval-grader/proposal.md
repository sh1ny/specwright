# Proposal

## Why

The eval graders decide "nothing on git or GitHub changed" with lists of known writes and keyword matches. A run can therefore change state, or skip the step it was asked to take, and still pass. Three known gaps show this: #74, #76 and #87. M4's last change, `add-cheap-tier`, measures a cheaper model by these grades, so the grades have to be exact first.

This change serves **M4 - Cost tier** (change 5 of 6, release 0.7.3). It advances these exit criteria: "the grader evals show GraphQL mutations and every listed git and `gh` write classified as writes (anything off the read-only allowlist counts as a write), and the agent-merge eval fails a reply that names the next step without offering it"; "each code fix has a regression test in `evals/`"; and the criterion that the named eval suites pass.

## What Changes

- **GraphQL classified by parsing (#74).** A `gh api graphql` call is classified by the operation types of its document's top-level definitions. Fragments, comments and string contents are ignored, so a mutation that follows a fragment counts as a write. The grader and the fake `gh` (`evals/fakes/gh.py`) share one classifier. The fake applies `resolveReviewThread` and `addReaction` only when a mutation operation selects them, so a read that merely mentions them in a comment or string changes no state.
- **Writes classified by a read-only allowlist (#76).** The git trace check and the `gh` call check name the commands that only read. Everything else counts as a possible write. This newly catches `git update-ref`, `symbolic-ref`, `checkout -` and `switch -`, as well as `gh issue delete|lock|unlock|pin|unpin|transfer`, `gh pr lock|unlock|revert|update-branch`, and any other subcommand not on the list.
- **One `gh` write classifier.** `pr_mutations` in `evals/git-workflow/grade.py` reads a GraphQL mutation without `-X` as a GET. It is folded into the same allowlist classifier, so every grader that asks "did a `gh` call change anything" gets the same answer.
- **The agent-merge eval checks a real offer (#87).** The `eval-watch-agent-merge` fixture gets a roadmap whose Now milestone holds the change. The assertion passes only when the report offers exactly the roadmap mode the skills prescribe (**close** when the merge finishes the Now milestone, otherwise **next**), not when the words "next" or "close" merely appear.
- Version 0.7.3 (a fix, per the pre-1.0 rule).

No skill text changes. Only the evals and their fakes change.

## Capabilities

### New Capabilities

- `eval-grading`: how the eval graders and the fake `gh` decide what a run changed and what its report offered. This covers write classification of git and `gh` calls, GraphQL operation parsing shared by the grader and the fake, and grading an offered next step by what is proposed rather than by keywords.

### Modified Capabilities

None. `pr-merge` already requires watch to offer one roadmap mode after an agent merge ("close when the Now milestone is then done, else next"). This change only makes the eval check that requirement.

## Impact

- `evals/git-workflow/grade.py`: `changing_git`, `changing_gh`, `gql_queries`, `pr_mutations` and the agent-merge next-step assertion.
- `evals/fakes/gh.py`: GraphQL write dispatch (`cmd_graphql_evidence`).
- A new shared GraphQL-operation helper under `evals/fakes/`, imported by the grader and the fake.
- `evals/git-workflow/fixtures.py`: `build_watch_merge` writes a roadmap for `eval-watch-agent-merge`. `evals/git-workflow/evals.json` updates that eval's assertion text.
- Tests: `evals/git-workflow/test_grade.py` and `evals/pr-pair/test_fake_gh.py` gain regression tests.
- Release files: `VERSION`, the README badge and `metadata.version` in `skills/*/SKILL.md` move to 0.7.3.
