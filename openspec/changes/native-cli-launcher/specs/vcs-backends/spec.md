# Spec Delta

## ADDED Requirements

### Requirement: Directory walks list files in sorted order
Where `sw vcs` lists the files under a directory, it SHALL list them itself, without `find` or a shell, skipping `.git` and `.jj` directories and links, and SHALL produce the same set of files in order of their UTF-8 bytes on every OS. A directory it cannot read SHALL be skipped, as before. A name that is not valid UTF-8 on disk SHALL stop the walk with `not_utf8`, even beside a valid look-alike name, naming the file with U+FFFD for each invalid sequence.

#### Scenario: The same order on every OS
- **WHEN** a jj commit names a directory holding `b.txt`, `A.txt`, `a/z.txt` and `é.txt`, on Linux, Windows and macOS
- **THEN** the walk reports `A.txt`, `a/z.txt`, `b.txt`, `é.txt` in that order on each OS, and no `find` or shell process ran

#### Scenario: An unreadable directory in the walk
- **WHEN** on Linux or macOS the named directory holds a subdirectory without read permission and a readable file beside it
- **THEN** the walk reports the readable file, skips the subdirectory, and the commit proceeds as before this change

#### Scenario: A non-UTF-8 name in the walk
- **WHEN** on Linux the named directory holds a file whose name holds the byte 0xFF
- **THEN** the command stops with `"error": "not_utf8"` naming that file with the byte shown as U+FFFD, exit 1, and nothing is committed

#### Scenario: A non-UTF-8 name beside its look-alike
- **WHEN** on Linux the named directory holds a file `a\xFF.txt` (raw byte 0xFF) of 2 MiB over `snapshot.max-new-file-size` and a small file `a�.txt` whose name holds a valid U+FFFD
- **THEN** the command stops with `"error": "not_utf8"`, exit 1, and nothing is committed; the walk never reports the small file twice in place of the large one

#### Scenario: A valid U+FFFD name alone in the walk
- **WHEN** on Linux the named directory holds only a file whose name holds a valid U+FFFD
- **THEN** the walk reports that file under its name and no `not_utf8` stop occurs

### Requirement: sw vcs documents keep their values and refuse non-UTF-8 names
Each document `sw vcs` prints SHALL parse to the same keys, key order and values `vcs.sh` printed for the same inputs. A name that is not valid UTF-8, met in an argument, a directory listing, or `git` or `jj` output where `sw vcs` would report or act on it, SHALL stop the command before any write with `"error": "not_utf8"`, exit 1, and a `message` that shows each invalid byte as `\xHH` (U+FFFD for a walk-found name) and asks for a rename. `but` output is read as before.

#### Scenario: Line separators parse back
- **WHEN** a message or path in the output holds U+2028 or U+2029
- **THEN** the parsed JSON string holds that character

#### Scenario: Line separators stay escaped
- **WHEN** a message or path in the output holds U+2028 or U+2029
- **THEN** the parsed JSON string holds that character

#### Scenario: A non-UTF-8 name from a tool stops by name
- **WHEN** on Linux, on the Git backend, a tracked file's name holds the byte 0xFF, the file is dirty, and `vcs.sh state` runs
- **THEN** stdout is one JSON document with `"error": "not_utf8"` naming the file with `\xFF`, and the exit status is 1; a following Git `vcs.sh commit` that names only other files commits them, and other backends keep their existing checks

#### Scenario: A valid U+FFFD in a name is just a character
- **WHEN** a tracked file is named `a�.txt` (valid UTF-8), no file name in the repo is invalid UTF-8, and `vcs.sh commit -- a�.txt` runs
- **THEN** the commit holds exactly `a�.txt`

#### Scenario: A non-UTF-8 argument from the shim
- **WHEN** on Linux `vcs.sh commit -- <name holding 0xFF>` runs
- **THEN** the document has `"error": "not_utf8"`, the exit status is 1, and no `git` or `jj` command ran

#### Scenario: Tool input reaches the tool
- **WHEN** on Windows a jj commit names a directory holding a changed tracked file and an ignored file larger than `snapshot.max-new-file-size`
- **THEN** `git check-ignore -z --stdin` receives the oversized file's name, the commit succeeds as before this change, and no `path_not_tracked` stop occurs

## MODIFIED Requirements

### Requirement: sw vcs reads settings and fences identity in process
`sw vcs` SHALL read the backend settings, the main branch and logins, and the GitButler pinned settings in-process, with the rules of `sw pr vcs` and `sw pr context`, starting no `pr-pair.sh`. It SHALL resolve a missing login and run every network command against a github.com remote through the identity fence in its own process, starting no `as.sh` and no second `sw`. It SHALL keep the outputs, stops and exit codes it gave before this change.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `vcs.sh state` runs
- **THEN** the backend is `jj`, as `pr-pair.sh vcs --code <code>` reports it, and no `pr-pair.sh` process was started: the same rules run in `sw`

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `vcs.sh state` stops with the same `error` as before this change and a `message` naming `svn`, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `vcs.sh state --repo <r> --role code` runs
- **THEN** stdout is one JSON document with `"error": "not_utf8"` and a `message` that shows the directory with the byte as `\xFF` and asks to install under a UTF-8 path, the exit status is 1, and no `git`, `jj` or `but` command ran

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `vcs.sh push --branch feat/a --login KintsugiBot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, with the same exit code as before this change, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com, the scripts directory holds a recording `as.sh` sentinel, and `vcs.sh push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** `git push` runs in the repo with KintsugiBot's verified token and the fence's transport settings, receives the same argument values as before this change, and the sentinel did not run

#### Scenario: Refused fence
- **WHEN** origin's push URL is `https://tok@github.com/o/r.git` and `vcs.sh push --branch feat/a --login KintsugiBot` runs on Git, jj or GitButler
- **THEN** the document has `"error": "fence_failed"`, a `message` that starts with `as.sh:` and masks the userinfo as `***`, the exit status is 3, and no push ran

#### Scenario: Login resolved in process
- **WHEN** origin is on github.com, the active gh account is KintsugiBot, the scripts directory holds a recording `as.sh` sentinel, and `vcs.sh fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the fetch runs as KintsugiBot, the document reports the fetched `ref`, and the sentinel did not run

#### Scenario: No gh account to resolve
- **WHEN** origin is on github.com, no gh account is logged in, and `vcs.sh fetch-main --repo <r> --role code` runs without `--login`
- **THEN** the document has `"error": "fence_failed"` with the fence's message, the exit status is 3, and no fetch ran

#### Scenario: Store without a Specwright version
- **WHEN** a planning store whose origin is on github.com has no `openspec/.specwright/VERSION`, and `vcs.sh pull --repo <store> --role store --code <code> --branch main --login store-bot` runs with a matching `sw` installed for `<code>`
- **THEN** the pull runs in the store as store-bot, and the document is not `sw_missing`

#### Scenario: Fenced commands stay unbounded
- **WHEN** `SPECWRIGHT_NET_DEADLINE` is 1 and a fenced `git fetch` against github.com takes 3 seconds before it succeeds
- **THEN** the document reports success, with no `deadline_exceeded`, while the fence's gh credential and identity lookups keep their own deadline

#### Scenario: Non-GitHub remote runs unfenced
- **WHEN** origin's fetch URL is not on github.com and `vcs.sh push --branch feat/a` runs
- **THEN** `git push` runs with the caller's environment and no fence lookup, and a failure is `git_network_error` with exit 3

## REMOVED Requirements

### Requirement: sw vcs documents keep their values and name bytes
**Reason**: `sw` no longer carries file names that are not valid UTF-8; it stops with `not_utf8` and asks for a rename (decision S1).
**Migration**: Replaced by "sw vcs documents keep their values and refuse non-UTF-8 names". Rename any tracked file whose name is not valid UTF-8.
