# Spec Delta

## MODIFIED Requirements

### Requirement: A jj store passes the update's branch check
The install and update SHALL accept a store whose backend is `jj` and whose Git HEAD is detached, and SHALL read its branch with the jj rule inside the running `sw update`, which is the download's own binary, never the project's installed `sw` and never a script. They SHALL still refuse a store on no branch.

#### Scenario: jj store on main
- **WHEN** `planning_store.vcs` is `jj`, main points at the store's `@-`, and the update runs
- **THEN** the update does not refuse the store for a detached HEAD

#### Scenario: Git store with a detached HEAD
- **WHEN** `planning_store.vcs` is `git` and the store's HEAD is detached
- **THEN** the update refuses the store as it does today

#### Scenario: Script missing from the download
- **WHEN** `planning_store.vcs` is `jj` and the download holds no shipped script
- **THEN** the update reads the store's branch in process, reports no `vcs_script_missing`, and goes on with the store checks

#### Scenario: Download's version, not the project's
- **WHEN** the project's `VERSION` reads `0.24.0`, the download's `sw` 0.25.0 runs the update, `sw` 0.24.0 is also installed, and the update reads a jj store's branch
- **THEN** the branch is read by the running `sw` 0.25.0, and no other `sw` process started

#### Scenario: No sw for the download's version
- **WHEN** `planning_store.vcs` is `jj`, the download's `sw` runs the update, and no `sw` for the project's installed version is in `<home>/.specwright/bin/`
- **THEN** the update reads the store's branch with the running `sw`, and does not refuse with `sw_missing` or `sw_mismatch`

### Requirement: On GitButler Specwright runs from wherever it was installed
With `vcs: gitbutler`, `sw vcs` SHALL run the same way whether the Specwright skill and agent copies are inside the code work tree or outside it, and whatever directory it is started from. Neither location SHALL be refused or reported as an error.

#### Scenario: Skills installed in the repo
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, and `<sw> vcs probe --repo <repo> --role code` runs from `<repo>/.claude/skills/specwright-pr/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`

#### Scenario: Skills installed at user level beside an in-repo copy
- **WHEN** `vcs` is `gitbutler`, GitButler manages the repo with main as its target, `<sw> vcs probe --repo <repo> --role code` runs from a directory outside the repo, and the work tree also holds `.claude/skills/specwright-pr/`
- **THEN** it exits 0 with `ok: true` and `backend: gitbutler`

#### Scenario: Started outside the repo without naming it
- **WHEN** `vcs` is `gitbutler` and `<sw> vcs probe` runs from a directory outside any repo with no `--repo` and no `--project`
- **THEN** it prints the `sw_mismatch` document saying no installed version was found, exits 1, and runs no `but` command

### Requirement: sw vcs reads settings and fences identity in process
`sw vcs` SHALL read the backend settings, the main branch and logins, and the GitButler pinned settings in-process, with the rules of `sw pr vcs` and `sw pr context`, starting no `pr-pair.sh`. It SHALL resolve a missing login and run every network command against a github.com remote through the identity fence in its own process, starting no `as.sh` and no second `sw`. It SHALL keep the outputs, stops and exit codes it gave before this change.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `sw vcs state` runs
- **THEN** the backend is `jj`, as `sw pr vcs --code <code>` reports it, and no other `sw` process was started: the same rules run in `sw vcs`

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `sw vcs state` stops with the same `error` as before this change and a `message` naming `svn`, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `sw vcs state --repo <r> --role code` runs with a UTF-8 `<r>`
- **THEN** stdout is the usual state document with `"backend": "jj"`, no `not_utf8` stop occurs because `sw` reads no scripts directory, and the exit status is 0

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `sw vcs push --branch feat/a --login KintsugiBot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, with the same exit code as before this change, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com and `sw vcs push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** `git push` runs in the repo with KintsugiBot's verified token and the fence's transport settings, receives the same argument values as before this change, and no second `sw` and no `bash` process started

#### Scenario: Refused fence
- **WHEN** origin's push URL is `https://tok@github.com/o/r.git` and `sw vcs push --branch feat/a --login KintsugiBot` runs on Git, jj or GitButler
- **THEN** the document has `"error": "fence_failed"`, a `message` that starts with `as.sh:` and masks the userinfo as `***`, the exit status is 3, and no push ran

#### Scenario: Login resolved in process
- **WHEN** origin is on github.com, the active gh account is KintsugiBot, and `sw vcs fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the fetch runs as KintsugiBot, the document reports the fetched `ref`, and no second `sw` process started

#### Scenario: No gh account to resolve
- **WHEN** origin is on github.com, no gh account is logged in, and `sw vcs fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the document has `"error": "fence_failed"` with the fence's message, the exit status is 3, and no fetch ran

#### Scenario: Store without a Specwright version
- **WHEN** a planning store whose origin is on github.com has no `openspec/.specwright/VERSION`, and `sw vcs pull --repo <store> --role store --code <code> --branch main --login store-bot` runs, with `<code>`'s `VERSION` matching the running `sw`
- **THEN** the version check reads `<code>`'s `VERSION`, the pull runs in the store as store-bot, and the document is not `sw_mismatch`

#### Scenario: Fenced commands stay unbounded
- **WHEN** `SPECWRIGHT_NET_DEADLINE` is 1 and a fenced `git fetch` against github.com takes 3 seconds before it succeeds
- **THEN** the document reports success, with no `deadline_exceeded`, while the fence's gh credential and identity lookups keep their own deadline

#### Scenario: Non-GitHub remote runs unfenced
- **WHEN** origin's fetch URL is not on github.com and `sw vcs push --branch feat/a` runs
- **THEN** `git push` runs with the caller's environment and no fence lookup, and a failure is `git_network_error` with exit 3

### Requirement: sw vcs documents keep their values and refuse non-UTF-8 names
Each document `sw vcs` prints SHALL parse to the same keys, key order and values `vcs.sh` printed for the same inputs. An argument that is not well-formed Unicode SHALL stop with the `bad_argument` document and exit 2 before any other work. A name that is not valid UTF-8, met in a directory listing or in `git` or `jj` output where `sw vcs` would report or act on it, SHALL stop the command before any write with `"error": "not_utf8"`, exit 1, and a `message` that shows each invalid byte as `\xHH` (U+FFFD for a walk-found name) and asks for a rename. `but` output is read as before.

#### Scenario: Line separators parse back
- **WHEN** a message or path in the output holds U+2028 or U+2029
- **THEN** the parsed JSON string holds that character

#### Scenario: A non-UTF-8 name from a tool stops by name
- **WHEN** on Linux, on the Git backend, a tracked file's name holds the byte 0xFF, the file is dirty, and `sw vcs state` runs
- **THEN** stdout is one JSON document with `"error": "not_utf8"` naming the file with `\xFF`, and the exit status is 1; a following Git `sw vcs commit` that names only other files commits them, and other backends keep their existing checks

#### Scenario: A valid U+FFFD in a name is just a character
- **WHEN** a tracked file is named `a�.txt` (valid UTF-8), no file name in the repo is invalid UTF-8, and `sw vcs commit -- a�.txt` runs
- **THEN** the commit holds exactly `a�.txt`

#### Scenario: A non-UTF-8 argument from the shim
- **WHEN** on Linux `sw vcs commit -- <name holding 0xFF>` runs
- **THEN** the document has `"error": "bad_argument"` naming that argument's position, the exit status is 2, and no `git` or `jj` command ran

#### Scenario: Tool input reaches the tool
- **WHEN** on Windows a jj commit names a directory holding a changed tracked file and an ignored file larger than `snapshot.max-new-file-size`
- **THEN** `git check-ignore -z --stdin` receives the oversized file's name, the commit succeeds as before this change, and no `path_not_tracked` stop occurs

## REMOVED Requirements

### Requirement: VCS operations run in the project's sw
**Reason**: `vcs.sh` is removed. Skills run `sw vcs` directly, so there is no shim to resolve `sw`, hand over arguments or find the project.
**Migration**: See native-cli "Skills run sw directly", "sw takes its arguments directly", "The project is chosen by --project, then the command's own argument" and "Retired script names map to sw commands". `sw vcs` keeps its output and exit codes under "sw vcs keeps vcs.sh's output and exit-code contract".

### Requirement: A missing or mismatched sw stops every VCS operation
**Reason**: There is no shim to print `sw_missing` or `no_python`. `sw vcs` checks the project's version itself, and a missing binary fails to start.
**Migration**: See native-cli "Project commands check the project's version" and "Skills run sw directly".
