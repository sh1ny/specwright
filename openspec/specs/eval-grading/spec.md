# eval-grading Specification

## Purpose
Decides how the eval graders and the fake `gh` judge what an agent run changed on git and GitHub and what its report offered, so a run that changes state or skips a prescribed step cannot pass on a missed command or a keyword.

## Requirements

### Requirement: GraphQL calls are classified by their operations
A `gh api graphql` call SHALL count as a write when its document holds a `mutation` or `subscription` operation among its top-level definitions. Fragment definitions, `#` comments and the contents of string literals SHALL NOT decide the classification. A document that cannot be read from argv (a file, `--input`) or cannot be parsed SHALL count as a write.

#### Scenario: Mutation after a fragment
- **WHEN** a run calls `gh api graphql -f query='fragment R on Reaction { content } mutation { addReaction(input:{subjectId:"X",content:THUMBS_UP}) { reaction { ...R } } }'`
- **THEN** the grader lists that call among the calls that changed something

#### Scenario: Read that mentions a mutation field
- **WHEN** a run calls `gh api graphql -f query='query { viewer { login } } # resolveReviewThread'`, or a read whose string argument contains `mutation { addReaction`
- **THEN** the grader lists no changing call for it

#### Scenario: Unparseable document
- **WHEN** a run passes a query with unbalanced braces, or a query read from `@q.graphql` or `--input`
- **THEN** the grader lists the call as a possible write

### Requirement: The fake gh and the grader agree on GraphQL writes
The fake `gh` SHALL apply a GraphQL write (resolving a thread, adding a reaction) only when the document's mutation operation selects that field at its top level, and SHALL decide this with the same classification the grader uses. A read-only document SHALL NOT change the fake's state, whatever text it contains.

#### Scenario: Real mutation applies
- **WHEN** the fake receives `mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id isResolved } } }` for an existing thread
- **THEN** that thread is resolved in the fake's state, and the grader classifies the same call as a write

#### Scenario: Comment or string mention changes nothing
- **WHEN** the fake receives a `query` document whose comment or string literal contains `resolveReviewThread` or `addReaction`
- **THEN** no thread is resolved and no reaction is added in the fake's state, and the grader classifies the call as a read

#### Scenario: Mutation with an unknown field
- **WHEN** the fake receives a mutation that selects a field it does not implement
- **THEN** it exits non-zero with a GraphQL error naming the field and leaves its state unchanged

### Requirement: Git writes are everything off a read-only allowlist
The git trace check SHALL treat a traced git command as read-only only when its subcommand, with its arguments, is on a named read-only allowlist (such as `status`, `log`, `rev-parse`, `branch` in list form, `checkout`/`switch` with no target, and `fetch` into `refs/remotes/` only). Every other traced command SHALL count as a change, including subcommands the grader does not know.

#### Scenario: Plumbing and dash targets are writes
- **WHEN** a run's trace holds `git update-ref refs/heads/main <sha>`, `git symbolic-ref HEAD refs/heads/x`, `git checkout -` or `git switch -`
- **THEN** the grader lists each of them as a change

#### Scenario: Unknown subcommand is a write
- **WHEN** a run's trace holds a git subcommand that is not on the allowlist, such as `git replace` or `git notes add`
- **THEN** the grader lists it as a change

#### Scenario: Fetch into a local branch is a write
- **WHEN** a run's trace holds `git fetch origin main:main` or `git fetch origin +refs/heads/x:refs/remotes/origin/x`
- **THEN** the grader lists it as a change

#### Scenario: Reads stay reads
- **WHEN** a run's trace holds only `git status --porcelain`, `git log --oneline`, `git branch --show-current`, `git rev-parse HEAD` and `git fetch origin`
- **THEN** the grader lists no change

### Requirement: gh writes are everything off a read-only allowlist
Every grader check of whether a `gh` call changed something SHALL use one classification: a call is read-only only when it is on a named allowlist (such as `pr view|list|checks|diff|status`, `issue view|list|status`, `auth status|token`, REST `api` calls sent as GET, and GraphQL reads). Every other call SHALL count as a write, including subcommands the grader does not know.

#### Scenario: Listed issue and pr writes
- **WHEN** a run calls `gh issue lock 3`, `gh issue transfer 3 o/other`, `gh pr update-branch 7` or `gh pr revert 7`
- **THEN** every grader check of `gh` changes lists each call

#### Scenario: GraphQL mutation without a method flag
- **WHEN** a run calls `gh api graphql -f query='mutation { addReaction(...) { reaction { content } } }'` with no `-X`
- **THEN** the check that lists pull request and comment changes lists it, as the trace check does

#### Scenario: Unknown gh subcommand is a write
- **WHEN** a run calls a `gh` subcommand that is not on the allowlist, such as `gh label create x` or `gh auth switch`
- **THEN** the grader lists it as a write

#### Scenario: Reads stay reads
- **WHEN** a run calls only `gh pr view 7 --json state`, `gh api repos/o/n/pulls/7`, `gh api --method GET search/issues -f q=x` and `gh api -X POST markdown --input req.json` (GitHub's render endpoint)
- **THEN** the grader lists no write

### Requirement: An offered next step is graded by what the report proposes
After a merge in a project with a roadmap, the agent-merge eval SHALL pass its next-step assertion only when the report offers the roadmap mode the skills prescribe for the fixture's milestone state (**close** when the merged change completes the Now milestone, otherwise **next**) and does not offer the other one. A report that only names the mode, or names both, SHALL fail.

#### Scenario: The prescribed mode is offered
- **WHEN** the fixture's Now milestone lists only the merged change and the report asks "Run specwright-roadmap close for M2?"
- **THEN** the next-step assertion passes

#### Scenario: Mode bound to the roadmap command
- **WHEN** the Now milestone lists only the merged change and the report asks "Next step: run specwright-roadmap close for M2?"
- **THEN** the next-step assertion passes, because the offered mode is the word bound to `specwright-roadmap` (close), not the word "Next"

#### Scenario: Named but not offered
- **WHEN** the report says "There is no roadmap step to run next; close the PR tab when done" without asking whether to run a roadmap mode
- **THEN** the next-step assertion fails

#### Scenario: Both modes offered
- **WHEN** the Now milestone still lists a planned change after the merged one (expected mode next) and the report asks "Run specwright-roadmap next or close?"
- **THEN** the next-step assertion fails, and its evidence names the mode it expected (next) and the modes offered (next, close)

#### Scenario: The wrong mode
- **WHEN** the Now milestone lists only the merged change and the report asks "Run specwright-roadmap next?"
- **THEN** the next-step assertion fails, and its evidence names the mode it expected (close)

### Requirement: Stress-tier evals are marked by kind
A git-workflow eval in the stress tier SHALL carry `"stress"` in `evals.json` with one of the values `watch`, `light-apply` or `implementer`. Each kind SHALL have at least one marked eval. A test SHALL fail when a kind has none, or when a mark has another value.

#### Scenario: Every kind is covered
- **WHEN** the eval-list test reads `evals/git-workflow/evals.json`
- **THEN** it finds at least one eval marked `watch`, one marked `light-apply` and one marked `implementer`

#### Scenario: A kind loses its last mark
- **WHEN** the only eval marked `implementer` has its mark removed
- **THEN** the eval-list test fails and says that no stress eval covers `implementer`

#### Scenario: An unknown kind
- **WHEN** an eval is marked `"stress": true`
- **THEN** the eval-list test fails and names that eval and the value

### Requirement: The tier comparison names every difference
`evals/git-workflow/tiers.py <iteration-dir> --base <config> --cheap <config>` SHALL print one JSON document giving each stress eval's mean pass rate per configuration. It SHALL name each eval whose rates differ, with the assertions that pass in one configuration only, and each eval with no readable grading in a configuration. It SHALL exit 0 only when nothing differs or is missing, else 1. Unmarked evals SHALL be skipped.

#### Scenario: Same grades
- **WHEN** every stress eval passes all its assertions in both configurations
- **THEN** the report lists no differences and nothing missing, and the exit status is 0

#### Scenario: The cheap configuration fails an assertion
- **WHEN** `eval-watch-agent-merge` passes under the base configuration and fails one assertion under the cheap one
- **THEN** the report names `eval-watch-agent-merge`, both pass rates and the failed assertion's text, and the exit status is 1

#### Scenario: A grading is missing or unreadable
- **WHEN** a stress eval has a `grading.json` for the base configuration, and for the cheap one it has none or one that is not valid JSON
- **THEN** the report lists that eval as missing for the cheap configuration, never as the same grade, and the exit status is 1
