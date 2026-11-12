# Spec Delta

## ADDED Requirements

### Requirement: Feedback records interoperate across the port on UTF-8 paths
Native pass operations SHALL preserve record keys, version-2 JSON, LF encoding, ownership, legacy migration and exclusive publication. Interrupted or foreign-owned state SHALL retain the existing recovery result; the port SHALL NOT start a new pass beside an unreadable record or silently adopt another owner. A state-directory or home value that is not valid UTF-8 SHALL stop the call with `"error": "not_utf8"`, exit 1, before any record is read or written.

#### Scenario: Native plan resumes an existing record
- **WHEN** the frozen script writes a record and native pass-plan reads it with equivalent snapshots, local history and owner
- **THEN** the native plan returns the same resume rows, owner state and completion decision, without starting a new pass

#### Scenario: Script plan reads a native record
- **WHEN** native pass-write writes a record and the frozen script reads it
- **THEN** the script reads the same intent, owner and state, with UTF-8/LF contents and the same record key

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

## MODIFIED Requirements

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
- **WHEN** a direct fenced read receives empty arguments, shell metacharacters or long Windows values
- **THEN** the invoked tool receives the same argument values as through the old script, with no shell started, without expansion, truncation or credential values in diagnostics

#### Scenario: A non-UTF-8 path argument is refused
- **WHEN** a direct fenced read is handed a POSIX path argument holding non-UTF-8 bytes
- **THEN** the workflow stops with `"error": "not_utf8"` and exit 1 before any credential lookup, and the tool does not run

#### Scenario: Unbounded VCS calls remain unbounded
- **WHEN** a workflow's VCS state or plan call takes longer than the configured network deadline but completes
- **THEN** the workflow receives its result without a newly introduced deadline_exceeded stop

## REMOVED Requirements

### Requirement: Feedback records interoperate across the port
**Reason**: Feedback no longer keeps raw non-UTF-8 bytes from `SPECWRIGHT_STATE_DIR` or `HOME`; such a value stops with `not_utf8` (decision S4).
**Migration**: Replaced by "Feedback records interoperate across the port on UTF-8 paths". Set `SPECWRIGHT_STATE_DIR` or `HOME` to a UTF-8 path.
