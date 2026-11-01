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
The git trace check SHALL treat a traced git command as read-only only when its subcommand, with its arguments, is on a named read-only allowlist (such as `status`, `log`, `rev-parse`, `branch` in list form with or without `-q`/`--quiet`, `tag` listing or `-v`/`--verify`, `checkout`/`switch` with no target, and a `fetch` that stores no ref). Every other traced command SHALL count as a change, including subcommands the grader does not know.

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
- **WHEN** a run's trace holds only `git status --porcelain`, `git log --oneline`, `git branch --show-current`, `git rev-parse HEAD`, `git fetch origin main` and `git fetch --no-tags origin`
- **THEN** the grader lists no change

#### Scenario: Quiet branch listing is a read
- **WHEN** a run's trace holds `git branch -q --list` or `git branch --quiet --list 'feat/*'`
- **THEN** the grader lists no change

#### Scenario: Tag verification is a read
- **WHEN** a run's trace holds `git tag -v v1.0.0` or `git tag --verify v1.0.0`
- **THEN** the grader lists no change

#### Scenario: Quiet flag does not hide a branch write
- **WHEN** a run's trace holds `git branch -q feat/x` or `git branch -q -D feat/x`
- **THEN** the grader lists it as a change

#### Scenario: Verify flag does not hide a tag write
- **WHEN** a run's trace holds `git tag -v -d v1.0.0` or `git tag -f -v v1.0.0`
- **THEN** the grader lists it as a change

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

### Requirement: A fetch that stores refs is a write
A traced `git fetch` SHALL be read-only only when all its options are read-only, no refspec has `+` or the `tag` keyword, every destination is under `refs/remotes/`, and also it passes `--no-tags`/`-n` or `--dry-run`, or it names a refspec, has no `--all`/`--multiple`, and no refspec has a destination. Any other fetch SHALL count as a change, since git follows tags into `refs/tags/`. The `fetch --update-head-ok` a `git pull` traces as its own child SHALL be judged with that pull.

#### Scenario: Default refspec follows tags
- **WHEN** a run's trace holds `git fetch origin`, `git fetch`, `git fetch --all`, `git fetch --multiple origin upstream` or `git fetch origin refs/heads/x:refs/remotes/origin/x`, each without `--no-tags`
- **THEN** the grader lists each of them as a change

#### Scenario: No tags does not excuse a branch or tag write
- **WHEN** a run's trace holds `git fetch --no-tags origin main:main` or `git fetch -n origin tag v1`
- **THEN** the grader lists each of them as a change

#### Scenario: No tags or no destination stays a read
- **WHEN** a run's trace holds `git fetch --no-tags origin`, `git fetch -n --all`, `git fetch origin main`, `git fetch origin refs/tags/v1` or `git fetch --dry-run origin`
- **THEN** the grader lists no change

#### Scenario: Pull's own child fetch
- **WHEN** a run's trace holds `git pull --ff-only` followed by the `git fetch --update-head-ok` and `git merge --ff-only FETCH_HEAD` that the pull runs
- **THEN** the guarded-refresh check allows all three, and the plain change check lists the pull and the merge but not the child fetch

#### Scenario: Update-head-ok without a pull
- **WHEN** a run's trace holds `git fetch --update-head-ok origin` with no `git pull` before it
- **THEN** the grader lists it as a change

### Requirement: GraphQL calls are found by their endpoint
The grader SHALL classify a `gh api` call whose endpoint is `graphql` (with or without a leading `/`) by its GraphQL operations, whatever its HTTP method and wherever its options stand before or after the endpoint. The REST rule (GET is a read) SHALL NOT apply to it.

#### Scenario: Mutation sent as GET
- **WHEN** a run calls `gh api -X GET graphql -f query='mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ id } } }' -f threadId=T`
- **THEN** every grader check of `gh` changes lists the call, and the fake resolves the thread, so the two agree

#### Scenario: Query with options before the endpoint
- **WHEN** a run calls `gh api --paginate graphql -f query='{ viewer { login } }'` or `gh api --hostname github.com /graphql -f query='query { viewer { login } }'`
- **THEN** the grader lists no write for it

#### Scenario: Unreadable document after an option
- **WHEN** a run calls `gh api -X GET graphql --input q.json`
- **THEN** the grader lists the call as a possible write

### Requirement: Only the executed GraphQL operation is classified
When a `gh api graphql` call passes an `operationName` field, the grader SHALL classify only the document's operations with that name, as the fake executes only that operation. When no operation has that name the call SHALL count as a write. Without `operationName`, every operation in the document SHALL be classified.

#### Scenario: Named query beside a mutation
- **WHEN** a run calls `gh api graphql -f query='query Q { viewer { login } } mutation M { addReaction(input:{subjectId:"X",content:THUMBS_UP}) { reaction { content } } }' -f operationName=Q`
- **THEN** the grader lists no write for it, and the fake's state is unchanged

#### Scenario: Named mutation
- **WHEN** the same document is sent with `-f operationName=M`
- **THEN** the grader lists the call as a write

#### Scenario: Unknown operation name
- **WHEN** the document is sent with `-f operationName=Missing`
- **THEN** the grader lists the call as a possible write, and the fake exits non-zero with `Unknown operation named 'Missing'` and leaves its state unchanged

### Requirement: The fake gh rejects duplicate operation names
The fake `gh` SHALL fail a GraphQL document in which more than one operation has the requested `operationName`, with the error `GraphQL: There are multiple operations named '<name>'.` and a non-zero exit, and SHALL execute none of them, as GitHub does.

#### Scenario: Two mutations with the same name
- **WHEN** the fake receives `mutation M { resolveReviewThread(input:{threadId:"T"}) { thread { id } } } mutation M { addReaction(input:{subjectId:"X",content:THUMBS_UP}) { reaction { content } } }` with `-f operationName=M`
- **THEN** it exits non-zero with `GraphQL: There are multiple operations named 'M'.`, no thread is resolved and no reaction is added

#### Scenario: One operation with the name
- **WHEN** the fake receives a document with `query Q { viewer { login } }` and `mutation M { resolveReviewThread(input:{threadId:"T"}) { thread { id } } }`, with `-f operationName=M`, for an existing thread `T`
- **THEN** it resolves thread `T` and exits 0

### Requirement: Store-group pair evidence names the trailers it checks
The grader's `eval-store-group-code-half` and `eval-store-group-store-half` checks SHALL list in their evidence each commit's subject together with its parsed `Specwright-Task` trailers, for both the code and the store commits, as `eval-store-apply-groups` does.

#### Scenario: Only the trailers fail
- **WHEN** the code and store group 1 commits have the right subjects and ticks but no `Specwright-Task` trailers
- **THEN** `eval-store-group-code-half` fails and its evidence shows each commit's subject with an empty task list

#### Scenario: Trailers present
- **WHEN** both group 1 commits carry trailers for 1.1, 1.2 and 1.3
- **THEN** the check passes and its evidence shows `['1.1', '1.2', '1.3']` for each commit

### Requirement: The fake gh state file is replaced whole
Every write of the fake `gh` state file (by the fake `gh`, `snapfix`, or a test helper script) SHALL go to a temporary file in the same directory and then be renamed over the state file. A rename that the OS refuses because a reader holds the file SHALL be retried for up to 5 s, then fail with an error naming the file. A reader SHALL never see an empty or partial file.

#### Scenario: Reader during a write
- **WHEN** one thread reads the state file in a loop while another writes it 200 times
- **THEN** every read parses as JSON and equals one of the written states

#### Scenario: Rename held off
- **WHEN** the rename is refused for longer than 5 s
- **THEN** the write fails with an error naming the state file, and the previous state file is unchanged

### Requirement: A fake gh read never rewrites the state
The fake `gh` SHALL write the state file only when a call changed the state (a mutation, or a `once` failure being used up). A call that only reads SHALL leave the file untouched, so a background watcher's polls cannot overwrite a concurrent test's change.

#### Scenario: Watcher polls while the test mutates
- **WHEN** a test changes the state through `snapfix.mutate` while a watcher's `gh api graphql` read is in flight
- **THEN** the read writes nothing, and the test's change is still in the state file afterwards

#### Scenario: A mutation still saves
- **WHEN** a fake `gh` call adds a PR comment
- **THEN** the state file holds the comment after the call

### Requirement: Every seeded PR body for an issue check has a recorded rendering
Every merged PR body that a git-workflow fixture seeds for the closed-check SHALL be among the bodies the markdown recorder renders and the recordings coverage test checks. The coverage test SHALL fail for a seeded body with no recording.

#### Scenario: Finish fixtures' body
- **WHEN** the finish fixtures seed PR #7 with `Adds greet and farewell.\n\nCloses #12`
- **THEN** `markdown.json` has a recording for it, and `pr-pair.sh closed-check` against that fixture exits with the issue's state instead of `GitHub state unknown: no recorded rendering`

#### Scenario: A new fixture body without a recording
- **WHEN** a fixture seeds a merged PR body that has no recording
- **THEN** the recordings coverage test fails and names that body
