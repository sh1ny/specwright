# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

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
