## MODIFIED Requirements

### Requirement: PR snapshots and replies run in the project's sw
`pr-snapshot.sh` and `pr-reply.sh` SHALL keep their paths, arguments and output contracts, and SHALL carry out every call by resolving the project's `sw` with the shared resolver and running `sw pr snapshot` and `sw pr reply`. Each SHALL accept one optional leading `--project <code-checkout>` that selects the project for resolution and nothing else. Without it, the project is found from the current directory, up to the first directory holding a `.git` entry, with no Git command. Their stdout, stderr and exit status SHALL be those of `sw`. No other implementation SHALL remain in either script.

#### Scenario: Snapshot with a matching sw
- **WHEN** a matching `sw` is installed and `as.sh sh1ny bash pr-snapshot.sh 12 --repo o/r` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** a matching `sw` is installed and `pr-reply.sh 12 thread <thread-id> <root-id> body.md --resolve --repo o/r` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `pr-reply.sh 12 comment <id> missing.md --repo o/r` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made, as before this change

#### Scenario: Store-started snapshot selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, a matching `sw` is installed for the code project `<code>`, and `as.sh store-bot bash pr-snapshot.sh --project <code> 7 --repo o/store` runs inside the store
- **THEN** the snapshot of `o/store` PR 7 is printed, its gh calls run in the store with store-bot's token, and `--project` reaches `sw` neither as an argument nor as the repository

#### Scenario: Store-started reply selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, and `pr-reply.sh --project <code> 7 comment <id> body.md --repo o/store` runs inside the store with a matching `sw` for `<code>`
- **THEN** one reply is posted on `o/store` PR 7 and the exit status is 0

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `pr-snapshot.sh --project <code> 7` names a project with no matching `sw`, and the current directory's project has one
- **THEN** stdout is one `sw_missing` document, the exit status is 1, no `gh` call was made, and the other binary was not used

#### Scenario: Malformed project prefix
- **WHEN** `pr-reply.sh --project` is given without a value, with an empty value, or with a second leading `--project`
- **THEN** after the existing Python prerequisite check, the script prints a usage line on stderr, exits with its usage status (2 for `pr-snapshot.sh`, 4 for `pr-reply.sh`) and makes no `gh` call

### Requirement: Snapshots evaluate reviewers through sw
`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe; the `pr-snapshot.sh` shim keeps its own prerequisite check until `native-cli-retire-scripts`.

#### Scenario: Reviewer states decided in sw
- **WHEN** `pr-snapshot.sh 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and no `reviewers.py` process was started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `pr-snapshot.sh 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check

#### Scenario: No Python on PATH
- **WHEN** `sw pr snapshot` runs through its handoff with failing `python` and `python3` first on `PATH` and a reviewer config
- **THEN** the snapshot and its reviewer states are printed with exit 0, neither interpreter ran, and stderr holds no `no_python` line

#### Scenario: Evaluator output that is not a document
- **WHEN** the `sw pr reviewers` child exits 0 but its stdout does not parse as one JSON document
- **THEN** the poll fails with exit 1 and prints no snapshot built from that output

## REMOVED Requirements

### Requirement: Native workflow integration preserves caller boundaries
**Reason**: Its one exception, the non-Git branch-check fetch-main fence hop through `as.sh`, ends with this change.
**Migration**: Replaced by "Native workflow integration calls every ported operation in process", which keeps every other guarantee and scenario.

## ADDED Requirements

### Requirement: Native workflow integration calls every ported operation in process
Native PR workflow code SHALL call ported settings, fence and VCS operations directly, the non-Git branch-check's VCS fetch-main included. It SHALL retain target-repo checks, per-call credentials, environment restoration and existing bounds. Reads previously bounded as a whole SHALL share that budget. Unbounded VCS reads and planning SHALL stay unbounded.

#### Scenario: Internal scripts are not launched
- **WHEN** workflow calls need VCS state or plans and fenced reads, and the handoff scripts directory contains recording as.sh and vcs.sh sentinels
- **THEN** neither sentinel runs, no second sw is launched for those operations, and the workflow returns the expected result

#### Scenario: Nested VCS fetch runs the fence in process
- **WHEN** non-Git branch-check with --code invokes native VCS fetch-main for a store that has no `openspec/.specwright/VERSION`, and the handoff scripts directory contains a recording as.sh sentinel
- **THEN** login resolution (when no --login was given) and the fetch run in process in the store's directory as the store's login, the sentinel does not run, and the result is not sw_missing

#### Scenario: Fenced read uses one deadline
- **WHEN** pass-plan performs a fenced Git read, credential checks consume part of its existing outer budget, and the Git command then hangs with a descendant
- **THEN** the remaining budget limits execution, the descendant is terminated, and pass-plan reports deadline_exceeded with exit 3 and its existing unknown fields

#### Scenario: Rounds reports an outer read deadline as unreadable
- **WHEN** a rounds remote_contains read exceeds its enclosing deadline
- **THEN** rounds returns ok true with remote_unreadable and the same unpushed and round results as the frozen script

#### Scenario: Nested fence lookup limit retains refusal mapping
- **WHEN** a rounds fenced read has a nested credential or identity lookup reach its own smaller deadline before the outer budget expires
- **THEN** it retains the fence_refused result and exit 3 rather than converting the nested limit to remote_unreadable

#### Scenario: Direct VCS failures retain wrapper mapping
- **WHEN** a direct VCS state or plan call returns an exit-2 stop with additional fields
- **THEN** its workflow caller preserves the frozen script's exit-1 mapping and error/message fields without adding the native stop's extra fields

#### Scenario: Another repository is checked under its own identity
- **WHEN** a command started in repo A needs a GitHub read in repo B under another login
- **THEN** it checks B's remotes, uses B's verified per-call credential, leaves the parent environment and later login unchanged, and refuses before networking if B's URL contains credentials

#### Scenario: Non-GitHub transport restores the original environment
- **WHEN** a workflow started under a GitHub fence reads a non-GitHub remote
- **THEN** the child receives the restored pre-fence transport environment without the GitHub token, as in the frozen script

#### Scenario: Command arguments remain exact
- **WHEN** a direct fenced read receives empty arguments, shell metacharacters, long Windows values or non-UTF-8 POSIX path bytes
- **THEN** the invoked tool receives the same argument bytes as through the old script, without expansion, truncation or credential values in diagnostics

#### Scenario: Unbounded VCS calls remain unbounded
- **WHEN** a workflow's VCS state or plan call takes longer than the configured network deadline but completes
- **THEN** the workflow receives its result without a newly introduced deadline_exceeded stop
