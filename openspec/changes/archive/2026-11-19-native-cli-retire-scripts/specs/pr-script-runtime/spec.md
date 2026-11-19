# Spec Delta

## ADDED Requirements

### Requirement: sw pr ignores an inherited GH_REPO
Every `gh` call that one of the nineteen `sw pr` subcommands makes, account-scoped calls such as `gh api user` and `gh auth token` included, SHALL run with `GH_REPO` removed from its environment. Each repository-scoped call SHALL also name its repository (`--repo` or `repos/<owner>/<name>/...`), so an inherited `GH_REPO` never picks the repository. `sw` does this itself, as the `pr-pair.sh` shim's `unset GH_REPO` did.

#### Scenario: GH_REPO not set
- **WHEN** `GH_REPO` is not set and `<sw> pr discover --repo o/store --branch feat/a` runs
- **THEN** every `gh` call names `o/store` and the PR list is that repository's

#### Scenario: Inherited GH_REPO names the code repo
- **WHEN** `GH_REPO` is `o/code` and `<sw> --project <code> pr discover --repo o/store --branch feat/a` runs in the store
- **THEN** every repository-scoped `gh` call targets `o/store`, no `gh` call sees `GH_REPO`, the account lookups (`gh auth token`, `gh api user`) included, and no PR of `o/code` is listed

### Requirement: Cleanup commands name the code project
Every `sw` command that `sw pr cleanup-plan` prints for a repository, the branch check and the fenced pull included, SHALL start with the running `sw`'s absolute path and a leading `--project <code>`, keep that repository as its working directory and keep every other argument unchanged.

#### Scenario: Store cleanup after merge
- **WHEN** a store-backed change's PRs merged and `<sw> pr cleanup-plan` runs
- **THEN** the store's branch-check and fenced pull commands each start with the running `sw`'s path and `--project <code>`, and their `cwd` is the store

#### Scenario: Store with no VERSION runs a printed command
- **WHEN** a printed store branch-check command runs in a store that has no `openspec/.specwright/VERSION`
- **THEN** `sw` checks the code checkout's `VERSION`, the check runs in the store, and the result is not `sw_mismatch`

## MODIFIED Requirements

### Requirement: Feedback records interoperate across the port on UTF-8 paths
Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner. A state-directory or home value that is not valid UTF-8 SHALL stop the call with `"error": "not_utf8"`, exit 1, before any record is read or written.

#### Scenario: Native plan resumes an existing record
- **WHEN** native pass-plan reads a record the frozen script wrote, kept as recorded bytes captured before the scripts were removed, with equivalent snapshots, local history and owner
- **THEN** the native plan returns the same resume rows, owner state and completion decision, without starting a new pass

#### Scenario: Script plan reads a native record
- **WHEN** native pass-write writes a record
- **THEN** it is UTF-8 with LF line ends under the same record key, its generated owner id, write time, checkout and host are checked for form and against the run, and its intent, owner and state equal the fixture the frozen script read before the scripts were removed, once those generated fields are normalized

#### Scenario: Non-UTF-8 POSIX state directory stops by name
- **WHEN** a POSIX feedback call uses a process state-directory environment value containing non-UTF-8 path bytes
- **THEN** it returns `"error": "not_utf8"` with exit 1 and a `message` that names `SPECWRIGHT_STATE_DIR` and asks for a UTF-8 path, and no record is read or created in any directory

#### Scenario: Injected environment does not inherit an ambient directory
- **WHEN** a call supplies an explicit environment while the process has a different state-directory value
- **THEN** feedback path selection uses only the supplied environment, including its missing or empty values

#### Scenario: Non-UTF-8 POSIX home stops by name
- **WHEN** a POSIX feedback call has no nonempty process state-directory value and a process `HOME` containing non-UTF-8 bytes
- **THEN** it returns `"error": "not_utf8"` with exit 1 and a `message` that names `HOME`, and no record is read or created

#### Scenario: Process state override does not need a home
- **WHEN** a POSIX feedback call has a nonempty process state-directory value and `HOME` is unset
- **THEN** the record is located under the state directory and the call does not stop for a missing home

#### Scenario: Missing home refuses without choosing a directory
- **WHEN** a POSIX process feedback call has a missing or empty state-directory value and `HOME` is unset or empty
- **THEN** it returns internal_error with exit 1, creates no record and uses no substitute directory

#### Scenario: A non-UTF-8 state directory never falls back to a default
- **WHEN** a POSIX pass plan has a non-UTF-8 process state-directory value and a head record exists in the default state directory
- **THEN** the plan returns `"error": "not_utf8"` with exit 1 and does not read the default directory's record

#### Scenario: Concurrent writers publish one record
- **WHEN** two valid pass-write calls race for the same record
- **THEN** exactly one complete record is published, and the losing call reports the frozen script's refusal rather than overwriting it

#### Scenario: Legacy migration and held lock remain safe
- **WHEN** a matching legacy record is migrated and a later adopt call finds the record lock already held
- **THEN** migration retains the record identity and contents, and adopt reports record_busy without changing the owner or removing the lock

#### Scenario: Unreadable record blocks a new pass
- **WHEN** a new-key record or a sole matching legacy record contains truncated JSON
- **THEN** `pass plan`, `pass adopt` and `pass done` return record_unreadable; `pass write` returns record_unreadable for a sole legacy record and record_exists for a new-key record; and the file is left in place


### Requirement: Prerequisites are stated and checked at install
The README prerequisites and install Step 1 SHALL list `git` as the core requirement and `gh` 2.48+ as a requirement of the PR skills. They SHALL list no bash, no POSIX userland and no Python for Specwright's own work. Install SHALL check each listed tool. A missing `git` SHALL stop the install. A missing PR requirement SHALL be reported as `PR workflow not ready: <missing>` without blocking the install. `specwright-pr` SHALL state the same dependencies.

#### Scenario: All prerequisites present
- **WHEN** install runs where `git` and `gh` 2.48 are available, and no `bash`, `python3` or `python` is on `PATH`
- **THEN** Step 1 passes and the final report shows no `PR workflow not ready` line

#### Scenario: git missing
- **WHEN** install runs where `git` is not on `PATH`
- **THEN** the install stops at Step 1 and tells the user to install `git`

#### Scenario: Python missing
- **WHEN** install runs where neither `python3` nor `python` is on `PATH`, and `git` is present
- **THEN** Step 1 passes and the install asks for no Python

#### Scenario: gh missing
- **WHEN** install runs where `gh` is missing or older than 2.48, and `git` is present
- **THEN** the install completes and its report includes `PR workflow not ready: gh 2.48+`

#### Scenario: No bash or Python prerequisite in the docs
- **WHEN** the README prerequisites, install Step 1 and `specwright-pr` are searched for the tools they require
- **THEN** none names bash, a POSIX userland or Python as a requirement

### Requirement: PR snapshots and replies run in the project's sw
`sw pr snapshot` and `sw pr reply` SHALL keep the scripts' arguments and output contracts and run in the project's `sw` after its version check. A leading `--project <code-checkout>` SHALL select only the project whose `VERSION` is checked. Stdout, stderr and exit status SHALL be `sw`'s; no other implementation SHALL remain.

#### Scenario: Snapshot with a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `<sw> as sh1ny <sw> pr snapshot 12 --repo o/r` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** the project's `VERSION` matches and `<sw> pr reply 12 thread <thread-id> <root-id> body.md --resolve --repo o/r` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `<sw> pr reply 12 comment <id> missing.md --repo o/r` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made

#### Scenario: Store-started snapshot selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, the code project `<code>` matches the running `sw`, and `<sw> --project <code> as store-bot <sw> --project <code> pr snapshot 7 --repo o/store` runs inside the store
- **THEN** the snapshot of `o/store` PR 7 is printed, its gh calls run in the store with store-bot's token, and `--project` reaches the subcommand neither as an argument nor as the repository

#### Scenario: Store-started reply selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, and `<sw> --project <code> pr reply 7 comment <id> body.md --repo o/store` runs inside the store with `<code>` matching the running `sw`
- **THEN** one reply is posted on `o/store` PR 7 and the exit status is 0

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `<sw> --project <code> pr snapshot 7` names a project whose `VERSION` differs from the running `sw`, and the current directory's project matches
- **THEN** stdout is one `sw_mismatch` document, the exit status is 1, no `gh` call was made, and no other binary was used

#### Scenario: Malformed project prefix
- **WHEN** `<sw> --project` is given without a value or with an empty value before `pr reply`
- **THEN** `sw` stops with a usage error, exit 2, and makes no `gh` call

### Requirement: The ported pr-pair subcommands keep the script's contracts
`sw pr identity`, `vcs`, `tier`, `context` and `policy` SHALL accept the argument forms shipped callers use, print a JSON line with the same parsed fields and values, and exit with the same status for the same settings files, repositories and GitHub answers, apart from the native-cli JSON, input and option differences. That covers the settings problems, the reviewer-config bytes (apart from `"format": 2`), path and digest, the GitButler pin, and the policy checks.

#### Scenario: Policy's remote settings read is strict
- **WHEN** `policy` reads a settings file from the remote and the settings reader refuses it, or it holds a duplicate key, or a section has the wrong shape
- **THEN** `policy` stops with `lookup_failed` and merges nothing, and never decides from a best-effort parse

#### Scenario: Git Bash path forms
- **WHEN** on Windows Git Bash runs a subcommand with a directory or snapshot file given as `/c/work/repo`
- **THEN** `sw` receives `C:/work/repo`, converted by Git Bash, reads that repository or file, and a path it reports is in the `C:/` form

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/pr-pair` and `evals/vcs` tests that run these five subcommands run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from the format migration (D10): the expected `"format"` value, the reviewer-config digests and content-addressed paths derived from it, and the format refused by the config check; the regex dialect cases (pr-evidence); assertions on free text, which check its prefix instead (see the message-text requirement); assertions on stdout bytes, which compare the parsed value instead; and the settings cases `native-cli-yaml-settings` changed, which assert the value read or the stop reported. The native-cli JSON/input and option differences have explicit outcome tests; every other field, error code and exit status is compared exactly

#### Scenario: Differential run against the frozen script
- **WHEN** the parity eval runs each case of each subcommand through `sw pr`, against the repositories and fake-gh state the case builds, and compares it with the record the frozen `pr-pair.sh` produced for that case, captured in the commit before the scripts were removed
- **THEN** `sw pr` exits with the recorded status and makes the recorded `gh` calls for inputs retained by the native-cli contract; documented JSON/input and option refusals keep their explicit difference tests. Stderr lines match the record up to each line's prefix, and stdout parses to the recorded JSON value apart from free text compared by its prefix, `reviewer_config` digests and paths, which name `sw pr`'s own `"format": 2` file, the listed settings differences with their own outcome tests, and `cleanup-plan`'s printed commands, which this change moves from `bash .../as.sh`, `vcs.sh` and `pr-pair.sh` to `<sw> --project <code> ...`: their decisions, guards, order and `gh` calls match the record, and their argv, working directory and project selection are asserted on their own. Records hold no paths of the machine that made them. A run-generated feedback owner id in `pass write` stdout is checked to equal the owner in the record that run wrote and is then replaced by a placeholder before the comparison, and persisted write and adopt times are checked against the run, as the live matrix did. Fixture commits are made with a pinned author, committer and dates, so their ids repeat across runs and `lacking[].sha` is compared exactly; the final fake-gh state and each written comment body are recorded and compared byte for byte

#### Scenario: A malformed settings file names its line
- **WHEN** `openspec/specwright.yaml` holds a tab in its indentation on line 7 and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with `"error": "bad_setting"` and a `message` naming `line 7`, and prints no settings values

#### Scenario: Settings not pinned on GitButler
- **WHEN** `vcs` is `gitbutler`, the work-tree `openspec/specwright.yaml` differs from the one committed on `feat/a`, and `pr-pair.sh context --code <code> --branch feat/a` runs
- **THEN** it exits 1 with `"error": "settings_not_pinned"`, naming the file and the ref, as before this change

### Requirement: Snapshots evaluate reviewers through sw
`sw pr snapshot` SHALL check the `--reviewer-config` file in its own process before any `gh` call. It SHALL decide reviewer states by running its own binary as `sw pr reviewers` under the deadline, byte bound and temp-file rules `reviewers.py` ran under, and SHALL read that child's document by parsing it. It SHALL start no Python evaluator and run no interpreter probe.

#### Scenario: Reviewer states decided in sw
- **WHEN** `<sw> pr snapshot 12 --reviewer-config cfg.json` runs and `cfg.json` lists `chatgpt-codex-connector[bot]` as a reviewer that has posted its report
- **THEN** that login's `reviewers` entry has the state `reviewers.py` decided before this change, `reviewer_config` holds the file's digest, and no `reviewers.py` process was started

#### Scenario: A pattern that backtracks past the deadline
- **WHEN** a reviewer's `report.ignore` backtracks on a comment body for longer than the evaluator's deadline
- **THEN** the evaluation is stopped at the deadline, stderr holds the line `bounded: deadline_exceeded: reviewers.py python3`, the poll fails, and no evaluator process or material file is left

#### Scenario: Bad reviewer config
- **WHEN** `cfg.json` is not valid JSON and `<sw> pr snapshot 12 --reviewer-config cfg.json` runs
- **THEN** the exit status is 2, stderr holds one line prefixed `reviewers.py:` that says the file is not valid JSON, no `gh` call was made, and no child `sw` was started for the check

#### Scenario: No Python on PATH
- **WHEN** `<sw> pr snapshot` runs directly with failing `python` and `python3` first on `PATH` and a reviewer config
- **THEN** the snapshot and its reviewer states are printed with exit 0, neither interpreter ran, and stderr holds no `no_python` line

#### Scenario: Evaluator output that is not a document
- **WHEN** the `sw pr reviewers` child exits 0 but its stdout does not parse as one JSON document
- **THEN** the poll fails with exit 1 and prints no snapshot built from that output

### Requirement: All pr-pair subcommands run in the project's sw
`sw pr` SHALL run all nineteen subcommands itself, after the project's version check. Its stdout, stderr and exit status SHALL be its own; no embedded Python implementation SHALL remain. With a matching version, a missing or unknown subcommand SHALL return the usage JSON and exit 2.

#### Scenario: Context with a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `<sw> pr context --code <code>` runs in a repo-local project
- **THEN** stdout is one JSON line with `"ok": true`, the code repo's `login`, `main` and `reviewer_config`, and the exit status is 0

#### Scenario: Discovery runs natively
- **WHEN** the project's `VERSION` matches and `<sw> pr discover --repo o/r --branch feat/a` runs
- **THEN** it returns the same normalized PR list and exit status as the frozen script's record

#### Scenario: Identity of a store from the code checkout
- **WHEN** the code project matches the running `sw`, the store checkout has no `openspec/.specwright/VERSION`, and `<sw> pr identity <store toplevel>` runs from the code checkout
- **THEN** stdout is one JSON line with the store's `<owner>/<name>` from its `origin`, and the exit status is 0

#### Scenario: Missing subcommand
- **WHEN** the project's `VERSION` matches and `<sw> pr` runs with no subcommand
- **THEN** it returns the usage JSON listing all nineteen subcommands and exits 2

#### Scenario: Unknown subcommand
- **WHEN** the project's `VERSION` matches and `<sw> pr not-a-command` runs
- **THEN** it returns the same usage JSON and exit 2, without making a GitHub call or writing state

### Requirement: Native workflow integration calls every ported operation in process
Native PR workflow code SHALL call ported settings, fence and VCS operations directly, the non-Git branch-check's VCS fetch-main included. It SHALL retain target-repo checks, per-call credentials, environment restoration and existing bounds. Reads previously bounded as a whole SHALL share that budget. Unbounded VCS reads and planning SHALL stay unbounded.

#### Scenario: Internal scripts are not launched
- **WHEN** workflow calls need VCS state or plans and fenced reads, with no shipped script on disk
- **THEN** no second `sw` and no script is launched for those operations, and the workflow returns the expected result

#### Scenario: Nested VCS fetch runs the fence in process
- **WHEN** non-Git branch-check with --code invokes native VCS fetch-main for a store that has no `openspec/.specwright/VERSION`
- **THEN** login resolution (when no --login was given) and the fetch run in process in the store's directory as the store's login, no second `sw` is launched, and the result is not `sw_mismatch`

#### Scenario: Fenced read uses one deadline
- **WHEN** pass-plan performs a fenced Git read, credential checks consume part of its existing outer budget, and the Git command then hangs with a descendant
- **THEN** the remaining budget limits execution, the descendant is terminated, and pass-plan reports deadline_exceeded with exit 3 and its existing unknown fields

#### Scenario: Rounds reports an outer read deadline as unreadable
- **WHEN** a rounds remote_contains read exceeds its enclosing deadline
- **THEN** rounds returns ok true with remote_unreadable and the same unpushed and round results as the frozen script's record

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
- **WHEN** a direct fenced read receives empty arguments, shell metacharacters or long Windows values
- **THEN** the invoked tool receives the same argument values as through the old script, with no shell started, without expansion, truncation or credential values in diagnostics

#### Scenario: A non-UTF-8 path argument is refused
- **WHEN** on Linux `sw pr rounds` is started with a `--code` argument holding non-UTF-8 bytes in its argument list
- **THEN** the exit status is non-zero, stdout is empty, no credential lookup ran and the tool does not run (native-cli "Arguments sw cannot represent are refused")

#### Scenario: Unbounded VCS calls remain unbounded
- **WHEN** a workflow's VCS state or plan call takes longer than the configured network deadline but completes
- **THEN** the workflow receives its result without a newly introduced deadline_exceeded stop

## REMOVED Requirements

### Requirement: Pass records can be written on Python 3.8
**Reason**: Specwright no longer needs Python, and the `pr-pair.sh` shim and its Python probe are deleted. `pass write` already writes its record in `sw`.
**Migration**: See "Feedback records interoperate across the port on UTF-8 paths" for the record format, and the native-cli requirement "Commands run with no scripts and no interpreters".

### Requirement: A missing or mismatched sw stops PR snapshots and replies
**Reason**: The shims and their resolver are deleted, so there is no `sw_missing` or `no_python` stop. `sw pr snapshot` and `sw pr reply` check the project's version themselves.
**Migration**: See the native-cli requirements "Project commands check the project's version" and "Skills run sw directly".

### Requirement: A missing or mismatched sw stops every pr-pair invocation
**Reason**: `pr-pair.sh`, its resolver and its Python check are deleted. Every `sw pr` subcommand checks the project's version before any GitHub call or state write.
**Migration**: See the native-cli requirements "Project commands check the project's version" and "Skills run sw directly".

### Requirement: Workflow shims select a binary project explicitly
**Reason**: There are no shims. The leading `--project` selector is now a global `sw` option.
**Migration**: See the native-cli requirement "The project is chosen by --project, then the command's own argument", and "Cleanup commands name the code project" here.
