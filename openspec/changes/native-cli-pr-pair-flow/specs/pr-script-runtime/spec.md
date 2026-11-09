## MODIFIED Requirements

### Requirement: Pass records can be written on Python 3.8
The `pr-pair.sh` shim SHALL still accept Python 3.8 at its existing prerequisite check. `pass write` SHALL write its record through `sw`, as UTF-8 JSON with LF line endings and atomic replacement, without executing embedded Python. The script's prerequisite probe stays until runtime retirement.

#### Scenario: Pass write on Python 3.8
- **WHEN** the only Python on `PATH` is 3.8, a matching `sw` is installed and a valid store-backed `pass write` runs
- **THEN** the script exits 0 with `"ok": true`, and the record file exists, parses as JSON and contains no CR bytes

#### Scenario: No Python 3.8 available to the test
- **WHEN** the minimum-runtime test finds no Python 3.8 interpreter
- **THEN** it reports that interpreter check as skipped, and an always-run test verifies native pass-write dispatch and UTF-8/LF records without relying on embedded Python source

### Requirement: Message text of the ported subcommands may be reworded
Free text in dispatched `sw pr` commands and `reviewers` MAY be reworded after stable prefixes. Other representations MAY change with their consuming skills when explicit contract tests prove the same workflow outcomes. Identity, mutation guards, ownership and recovery SHALL remain intact. Retained interfaces keep their existing values/statuses; persisted records remain interoperable. Incidental Python formatting and parser quirks SHALL NOT require byte-for-byte replicas.

#### Scenario: A reworded stop keeps its code
- **WHEN** `pr-pair.sh policy` reads a default-branch settings file whose content is not valid base64
- **THEN** stdout has `"error": "lookup_failed"` and the exit status is 3, as before this change, and `message` starts with `merge policy unknown: unreadable openspec/specwright.yaml at <ref>:`

#### Scenario: Workflow error keeps structured values
- **WHEN** native `ensure-pr` finds an open PR targeting another base
- **THEN** it returns `wrong_base` with the same PR and base values and exit status as the frozen script, without creating a PR

## REMOVED Requirements

### Requirement: pr-pair settings and policy subcommands run in the project's sw

**Reason:** The temporary five-command migration boundary is replaced by complete native dispatch.

**Migration:** Use the unchanged script entry point with a matching sw for all commands; see Requirement: All pr-pair subcommands run in the project's sw.

### Requirement: A missing or mismatched sw stops the ported pr-pair subcommands

**Reason:** The temporary five-command migration boundary is replaced by complete native dispatch.

**Migration:** Use the unchanged script entry point with a matching sw for all commands; see Requirement: A missing or mismatched sw stops every pr-pair invocation.

## ADDED Requirements

### Requirement: All pr-pair subcommands run in the project's sw
`pr-pair.sh` SHALL keep its path and arguments and dispatch all nineteen subcommands to the project's matching `sw`. Its stdout, stderr and exit status SHALL be those of `sw`; no embedded Python implementation SHALL remain. The five existing native entry points SHALL stay supported. With a matching binary, missing and unknown commands SHALL retain the script's usage JSON and exit 2.

#### Scenario: Context with a matching sw
- **WHEN** a matching `sw` is installed and `pr-pair.sh context --code <code>` runs in a repo-local project
- **THEN** stdout is one JSON line with `"ok": true`, the code repo's `login`, `main` and `reviewer_config`, and the exit status is 0, as before this change

#### Scenario: Discovery runs natively
- **WHEN** a matching `sw` is installed and `pr-pair.sh discover --repo o/r --branch feat/a` runs
- **THEN** the shim runs the native discovery command and returns the same normalized PR list and exit status as the frozen script

#### Scenario: Identity of a store from the code checkout
- **WHEN** a matching `sw` is installed for the code project, the store checkout has no `openspec/.specwright/VERSION`, and `pr-pair.sh identity <store toplevel>` runs from the code checkout
- **THEN** stdout is one JSON line with the store's `<owner>/<name>` from its `origin`, and the exit status is 0, as before this change

#### Scenario: Missing subcommand
- **WHEN** a matching `sw` is installed and `pr-pair.sh` runs with no arguments
- **THEN** it returns the usage JSON listing all nineteen subcommands and exits 2

#### Scenario: Unknown subcommand
- **WHEN** a matching `sw` is installed and `pr-pair.sh not-a-command` runs
- **THEN** it returns the same usage JSON and exit 2, without making a GitHub call or writing state

### Requirement: A missing or mismatched sw stops every pr-pair invocation
When resolution fails, every `pr-pair.sh` invocation SHALL return one JSON line with `"ok": false`, `"error": "sw_missing"` and a message beginning `sw missing or mismatched: rerun the install prompt`, and exit 1. It SHALL make no GitHub call, write no workflow state and never fall back to embedded Python or another binary. The existing Python prerequisite check SHALL still precede resolution.

#### Scenario: Policy with no sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh policy --repo o/r --head <sha> --snapshot code=s.json` runs
- **THEN** the exit status is 1, stdout is one JSON line with `"error": "sw_missing"`, and no `gh` call was made

#### Scenario: Workflow command needs matching sw
- **WHEN** no matching `sw` is installed and `pr-pair.sh branch-check --dir <d> --branch feat/a --main main` runs
- **THEN** it exits 1 with `sw_missing`, without reading or deleting the branch

#### Scenario: Matching binary permits dispatch
- **WHEN** a matching `sw` is installed and a valid branch-check invocation runs
- **THEN** it returns the native branch-check result rather than `sw_missing`

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH` and `pr-pair.sh context --code <code>` runs
- **THEN** it exits 2 with its `no_python` JSON line, as before this change, and `sw` did not run


### Requirement: Native PR workflow commands preserve their effects
The fourteen newly native commands SHALL preserve product workflow outcomes, effects, mutation sequencing, identity and recovery. Producer/consumer representations MAY change together with explicit contract tests and documented differences. The frozen script is comparison evidence, not a byte-format mandate. Printed commands SHALL execute in the intended cwd with correct arguments/login. Failed or limited reads SHALL retain unknown/unreadable/refusal decisions without speculative mutation.

#### Scenario: Every workflow command has differential coverage
- **WHEN** differential cases run discovery, expected-set, creation, closing checks, linking, pair-state, rounds, all four pass operations, cleanup, branch-check, merge, delete-remote and item-issues through both implementations
- **THEN** workflow decisions, effects, identity, mutation guards and recovery agree, including success and failure cases for each command; any representation difference has explicit producer/consumer contract coverage

#### Scenario: Unknown read permits no follow-on mutation
- **WHEN** discovery or an issue-state read fails or exceeds its deadline or byte bound
- **THEN** the native command retains the frozen script's error, unknown fields and exit status, and makes no follow-on create, merge or delete call

#### Scenario: Merge is attempted once then read back
- **WHEN** the merge request is cut off after GitHub accepted it
- **THEN** the command makes one merge request and a read-back, returning the merged result when confirmed, or unknown when the read-back fails, without a second merge request

#### Scenario: Moved remote branch is retained
- **WHEN** delete-remote finds that the branch no longer points to the supplied merged head
- **THEN** it reports the moved state and performs no delete request

#### Scenario: Rendered closing lines preserve code boundaries
- **WHEN** closing-check reads a rendered description containing code spans, code blocks, entities and closing-list prose
- **THEN** `intended`, `missing`, `extra` and `status` describe the issues and state from standard HTML5 interpretation, text rendered as code is not an intended issue, and a code span between references ends the closing list

#### Scenario: Malformed table text follows HTML5 interpretation
- **WHEN** closing prose is extracted from malformed HTML `Fixes <table>#1</table>`
- **THEN** issue 1 in the description's own repository is an intended closing reference under HTML5 tree construction

### Requirement: Feedback records interoperate across the port
Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner.

#### Scenario: Native plan resumes an existing record
- **WHEN** the frozen script writes a record and native pass-plan reads it with equivalent snapshots, local history and owner
- **THEN** the native plan returns the same resume rows, owner state and completion decision, without starting a new pass

#### Scenario: Script plan reads a native record
- **WHEN** native pass-write writes a record and the frozen script reads it
- **THEN** the script reads the same intent, owner and state, with UTF-8/LF contents and the same record key

#### Scenario: Concurrent writers publish one record
- **WHEN** two valid pass-write calls race for the same record
- **THEN** exactly one complete record is published, and the losing call reports the frozen script's refusal rather than overwriting it

#### Scenario: Legacy migration and held lock remain safe
- **WHEN** a matching legacy record is migrated and a later adopt call finds the record lock already held
- **THEN** migration retains the record identity and contents, and adopt reports record_busy without changing the owner or removing the lock

#### Scenario: Unreadable record blocks a new pass
- **WHEN** a new-key record or a sole matching legacy record contains truncated JSON
- **THEN** `pass plan`, `pass adopt` and `pass done` return record_unreadable; `pass write` returns record_unreadable for a sole legacy record and record_exists for a new-key record; and the file is left in place

### Requirement: Feedback record locks and fallback publication stay exclusive
Write SHALL publish exclusively; adopt and done SHALL hold their own record lock and never remove another call's lock. Native locks SHALL be exclusively created files at the existing `.lock` path; legacy lock directories SHALL still block and SHALL never be removed automatically. A failed hard link MAY fall back to exclusive creation that refuses an occupied destination. An ordinary failure after that creation SHALL remove only the file the request created.

#### Scenario: Concurrent mutations acquire one lock
- **WHEN** two adopt or done calls race for the same record while the winning call holds its lock
- **THEN** exactly one call holds the lock, the other reports record_busy without changing the record, and only the holder releases the lock

#### Scenario: Native and legacy locks exclude each other
- **WHEN** a native call finds a legacy lock directory, or a legacy script call finds a native lock file at the same `.lock` path
- **THEN** the second call refuses the held lock and leaves it untouched; native cleanup removes only its own created file

#### Scenario: Interrupted SDK publication stays recoverable
- **WHEN** the SDK fallback is interrupted after exclusive creation but before opening or finishing the record
- **THEN** the empty or partial record remains in place, `pass write` refuses with record_exists, and `pass plan`, `pass adopt` and `pass done` return record_unreadable

#### Scenario: Fallback permission failure leaves no record
- **WHEN** the publication fallback exclusively creates a POSIX record and setting its private permissions fails
- **THEN** the error is reported, no record content was written, only the created file is removed, and a later `pass write` can create the record

### Requirement: Native workflow integration preserves caller boundaries
Native PR workflow code SHALL call ported settings, fence and VCS operations directly, except the existing non-Git branch-check to VCS fetch-main fence hop until native-cli-internal-calls. It SHALL retain target-repo checks, per-call credentials, environment restoration and existing bounds. Reads previously bounded as a whole SHALL share that budget. Unbounded VCS reads and planning SHALL stay unbounded.

#### Scenario: Internal scripts are not launched
- **WHEN** workflow calls need VCS state or plans and fenced reads, and the handoff scripts directory contains recording as.sh and vcs.sh sentinels
- **THEN** neither sentinel runs, no second sw is launched for those operations, and the workflow returns the expected result

#### Scenario: Nested VCS fetch retains its temporary fence hop
- **WHEN** non-Git branch-check with --code invokes native VCS fetch-main for a store
- **THEN** only that nested fence path may invoke as.sh and sw as, each as.sh call in it (login resolution when no --login was given, then the fetch) receives --project with the resolved --code directory, the target cwd and login remain the store's, and the other workflow paths do not gain script launches

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

### Requirement: Workflow shims select a binary project explicitly
`pr-pair.sh` SHALL accept one leading `--project <code-checkout>` prefix for exact-version binary selection, consume it before native dispatch and preserve cwd and remaining arguments. Without it, current project discovery SHALL remain. Store callers and emitted cleanup commands SHALL name the code project where discovery cannot resolve it; every other printed argument and cwd SHALL remain unchanged.

#### Scenario: Workflow command starts in a store
- **WHEN** a store without VERSION runs pr-pair.sh --project <code> discover with a matching binary for the selected code project
- **THEN** discovery runs natively with cwd still the store, and the prefix is not passed as a workflow command argument

#### Scenario: Cleanup commands carry the explicit project
- **WHEN** cleanup-plan emits store branch-check and fenced pull commands
- **THEN** each shim needing binary resolution carries --project <code>, preserves the store cwd, and retains every other command argument

#### Scenario: Selected project cannot resolve a binary
- **WHEN** the explicit project has no usable matching binary even though another sw is available from cwd or PATH
- **THEN** the shim returns sw_missing with exit 1, performs no GitHub call and never falls back to the other binary

#### Scenario: Malformed project prefix is refused
- **WHEN** the leading --project prefix lacks a nonempty value or is repeated as a leading selector
- **THEN** after the existing Python prerequisite check, the shim returns usage exit 2 before resolution, authentication or state changes
