# Spec Delta

## ADDED Requirements

### Requirement: VCS operations run in the project's sw
`vcs.sh` SHALL keep its path, arguments and output contract, and SHALL carry out every subcommand by resolving the project's `sw` with the shared resolver and running `sw vcs` with the same arguments. The project is found from `--code`, else `--repo`, else the current directory, with no Git command. Its stdout, stderr and exit status SHALL be those of `sw vcs`. No other implementation of the VCS operations SHALL remain in `vcs.sh`.

#### Scenario: Matching sw installed
- **WHEN** the project's `VERSION` reads `0.25.0`, the resolver finds a matching `sw` 0.25.0, and `vcs.sh state --repo <r> --role code` runs on a clean Git repo on main
- **THEN** stdout is the one JSON document `sw vcs state` printed, with `"ok": true`, `"backend": "git"` and `"on_main": true`, and the exit status is 0

#### Scenario: Project found from a subdirectory, without Git
- **WHEN** `vcs.sh state --repo <r>/sub/dir --role code` runs and `<r>` holds `.git` and `openspec/.specwright/VERSION`
- **THEN** the resolver reads `<r>/openspec/.specwright/VERSION` (the nearest directory above `sub/dir` holding a `.git` entry), and no `git` command ran before `sw` started

#### Scenario: Arguments reach sw unchanged
- **WHEN** `vcs.sh commit --repo <r> --role code --branch feat/a --message-file <m> -- "dir with space/a b.txt"` runs
- **THEN** `sw vcs` receives each argument byte for byte, and the commit holds exactly `dir with space/a b.txt`

#### Scenario: A stop keeps its exit status
- **WHEN** `vcs.sh push` is refused by the identity fence
- **THEN** the exit status is 3 and stdout is one JSON document with `"ok": false` and the fence's `error`, as before this change

### Requirement: A missing or mismatched sw stops every VCS operation
When the resolver stops, `vcs.sh` SHALL print one JSON document on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt` and holds the resolver's detail. It SHALL exit 1, run no `git`, `jj` or `but` command, and never fall back to another implementation, another version's binary or an `sw` on `PATH`. Without Python 3.8+ it SHALL instead print the `no_python` document `vcs.sh` printed before this change and exit 2.

#### Scenario: Binary missing
- **WHEN** the project's `VERSION` reads `0.25.0` and `<home>/.specwright/bin/0.25.0/` holds no `sw`
- **THEN** `vcs.sh state` exits 1, stdout is one JSON document with `"error": "sw_missing"` naming the expected path, and no Git command ran

#### Scenario: Interface mismatch
- **WHEN** the installed binary reports another `interface` than the skills expect
- **THEN** `vcs.sh branch-create --branch feat/a` exits 1 with `"error": "sw_missing"`, and no branch `feat/a` exists

#### Scenario: Project has no VERSION
- **WHEN** the code checkout has no `openspec/.specwright/VERSION`
- **THEN** `vcs.sh` exits 1 with `"error": "sw_missing"`, and the message says no installed version was found

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH` and a matching `sw` is installed
- **THEN** `vcs.sh state` exits 2, stdout is `{"ok":false,"error":"no_python","message":"vcs.sh needs python 3.8+"}` as before this change, and `sw` did not run

### Requirement: sw vcs keeps vcs.sh's output and exit-code contract
`sw vcs <sub>` SHALL accept the subcommands and options `vcs.sh` accepted before this change and SHALL print exactly one JSON document on stdout for each run, with the same fields, error codes and messages as `vcs.sh` for the same inputs. It SHALL exit 0 on success, 1 on a stop, 2 on a usage error and 3 on a network or fence refusal. An unexpected failure SHALL be the document `"error": "internal_error"` with exit 1, never a stack trace on stdout.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/vcs` suite and every other suite that runs `vcs.sh` run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

#### Scenario: Unknown subcommand
- **WHEN** `vcs.sh frobnicate --repo <r> --role code` runs
- **THEN** it exits 2 and stdout is one JSON document with `"ok": false` and `"error": "usage"`

### Requirement: sw vcs output bytes match vcs.sh
Each document `sw vcs` prints SHALL be byte for byte the one `vcs.sh` printed before this change for the same inputs: the same key order, `", "` and `": "` separators, raw UTF-8 text, U+2028 and U+2029 as six-character escapes. A name's bytes SHALL round-trip through arguments, directory listings, `git` and `jj` output and the document even when they are not valid UTF-8; `but` output is read as before.

#### Scenario: Line separators stay escaped
- **WHEN** a message or path in the output holds U+2028 or U+2029
- **THEN** the JSON document carries it as the six characters `\u2028` or `\u2029`, and every other non-ASCII character as UTF-8 text, as `vcs.sh` printed it before

#### Scenario: A non-UTF-8 name from a tool round-trips
- **WHEN** on Linux a tracked file's name holds the byte 0xFF and `vcs.sh state` reports it dirty
- **THEN** the `dirty_paths` entry is written with that byte, and a following `vcs.sh commit -- <that entry>` commits exactly that file

#### Scenario: A valid U+FFFD in a name is just a character
- **WHEN** a tracked file is named `a�.txt` (valid UTF-8) and a file whose name holds the byte 0xFF in the same place also exists, and `vcs.sh commit -- a�.txt` runs
- **THEN** the commit holds exactly `a�.txt`, and the other file is unchanged

#### Scenario: Tool input reaches the tool
- **WHEN** on Windows a jj commit names a directory holding a changed tracked file and an ignored file larger than `snapshot.max-new-file-size`
- **THEN** `git check-ignore -z --stdin` receives the oversized file's name, the commit succeeds as before this change, and no `path_not_tracked` stop occurs

### Requirement: sw vcs reads settings and fences identity through the existing scripts
Until those scripts are ported, `sw vcs` SHALL read the backend settings and the GitButler pinned settings by running `pr-pair.sh vcs` and `pr-pair.sh context` from the scripts directory of the `vcs.sh` that started it, and SHALL run every network command against a github.com remote through that directory's `as.sh`. It SHALL keep their arguments, the outputs it reads and their failures as before this change.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `vcs.sh state` runs
- **THEN** the backend is `jj`, as `pr-pair.sh vcs --code <code>` reported it

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `vcs.sh state` stops with the same `error` and `message` as before this change, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `vcs.sh state --repo <r> --role code` runs
- **THEN** `pr-pair.sh vcs` runs from that directory, the document reports `"backend": "jj"`, and the exit status is 0

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com and `vcs.sh push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** the push runs as `as.sh KintsugiBot git push ...` from the same scripts directory, and a refused fence exits 3 without pushing

## MODIFIED Requirements

### Requirement: A jj store passes the update's branch check
The install and update SHALL accept a store whose backend is `jj` and whose Git HEAD is detached. They SHALL read its current branch with the jj rule, using the downloaded copy's `sw-path.sh` to resolve the `sw` of the download's own `VERSION` and running its `sw vcs state` with the download's scripts directory, never the project's installed `sw`. They SHALL still refuse a store on no branch by that rule, SHALL refuse with `vcs_script_missing` when the downloaded copy lacks that script, and SHALL refuse with `sw_missing` when no matching `sw` for the download's version is installed.

#### Scenario: jj store on main
- **WHEN** `planning_store.vcs` is `jj`, main points at the store's `@-`, and the update runs
- **THEN** the update does not refuse the store for a detached HEAD

#### Scenario: Git store with a detached HEAD
- **WHEN** `planning_store.vcs` is `git` and the store's HEAD is detached
- **THEN** the update refuses the store as it does today

#### Scenario: Script missing from the download
- **WHEN** `planning_store.vcs` is `jj` and the downloaded copy has no backend script
- **THEN** the update refuses the store with `vcs_script_missing`, and swaps nothing

#### Scenario: Download's version, not the project's
- **WHEN** the project's `VERSION` reads `0.24.0`, the download's reads `0.25.0`, `sw` 0.24.0 and 0.25.0 are both installed, and the update reads a jj store's branch
- **THEN** the branch is read by `sw` 0.25.0

#### Scenario: No sw for the download's version
- **WHEN** `planning_store.vcs` is `jj` and no `sw` for the download's version is installed (a `main` download with no `mise run install-sw`)
- **THEN** the update refuses the store with `sw_missing` naming that version, and swaps nothing
