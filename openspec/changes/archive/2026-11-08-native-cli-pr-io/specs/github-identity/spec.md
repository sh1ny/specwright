# Spec Delta

## ADDED Requirements

### Requirement: The fence runs in the project's sw
`as.sh` SHALL keep its path, arguments and contract, and SHALL carry out every call, `--resolve` included, by resolving the project's `sw` with the shared resolver and running `sw as`. The project is found from the current directory, up to the first directory holding a `.git` entry, with no Git command. No other implementation of the fence SHALL remain in `as.sh`.

#### Scenario: Fenced gh call with a matching sw
- **WHEN** the project's `VERSION` reads `0.28.0`, the resolver finds a matching `sw` 0.28.0, `sh1ny` has a gh credential, and `as.sh sh1ny gh api user --jq .login` runs inside the project
- **THEN** stdout is `sh1ny`, the exit status is 0, and `gh` saw `GH_TOKEN` set to `sh1ny`'s token

#### Scenario: Resolve through sw
- **WHEN** the active github.com account is `KintsugiBot` and `as.sh --resolve` runs
- **THEN** stdout is exactly `KintsugiBot` and a newline, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `as.sh sh1ny git push` runs in a repo whose `origin` push URL is `https://tok@github.com/o/r.git`
- **THEN** the exit status is 3, stderr names the remote with the userinfo masked as `***`, and `git push` did not run, as before this change

### Requirement: A missing or mismatched sw stops every fenced call
When the resolver stops, `as.sh` SHALL print one JSON document on stdout with `"ok": false`, `"error": "sw_missing"` and a `message` that starts with `sw missing or mismatched: rerun the install prompt` and holds the resolver's detail, copy the resolver's stderr to stderr, and exit 1. It SHALL run no `gh` call and not the fenced command, and SHALL never fall back to another implementation, another version's binary or an `sw` on `PATH`.

#### Scenario: Binary missing
- **WHEN** the project's `VERSION` reads `0.28.0`, `<home>/.specwright/bin/0.28.0/` holds no `sw`, and `as.sh sh1ny gh pr comment 5 --body-file b` runs
- **THEN** the exit status is 1, stdout is one JSON document with `"error": "sw_missing"` naming the expected path, and no `gh` command ran

#### Scenario: Resolve with no sw
- **WHEN** no matching `sw` is installed and `as.sh --resolve` runs
- **THEN** the exit status is 1, not 3, and stdout holds the `sw_missing` document, never a login

#### Scenario: No Python
- **WHEN** no `python3` or `python` 3.8+ is on `PATH`
- **THEN** `as.sh` exits 2 with `as.sh: no_python: needs python 3.8+ for its bounded gh calls` on stderr, as before this change, and `sw` did not run

### Requirement: The fenced command keeps the caller's stdin, arguments and exit status
The handoff from `as.sh` to `sw as` SHALL not read the caller's stdin, so the fenced command reads the same stdin `as.sh` was given. The command SHALL receive each argument byte for byte, start in the directory `as.sh` started in, and its exit status SHALL be `as.sh`'s. A command ended by a signal SHALL end `as.sh` with status 128 plus the signal number, the status a bash caller saw before this change. A command that cannot be found SHALL give exit 127 with its name on stderr.

#### Scenario: Credential fill reads stdin through the fence
- **WHEN** `as.sh sh1ny git credential fill` runs with `protocol=https`, `host=github.com` and a blank line on stdin
- **THEN** stdout holds `username=x-access-token` and `password=` followed by `sh1ny`'s verified token, and the exit status is 0

#### Scenario: Argument bytes and exit status pass through
- **WHEN** `as.sh sh1ny bash -c 'printf %s "$1"; exit 7' x 'a "b" $c'` runs
- **THEN** stdout is exactly `a "b" $c` and the exit status is 7

#### Scenario: Command not found
- **WHEN** `as.sh sh1ny no-such-tool` runs after the identity check passes
- **THEN** the exit status is 127 and stderr names `no-such-tool`

#### Scenario: A bounded caller stops the fence
- **WHEN** `pr-pair.sh` runs `as.sh <login> git fetch` under its deadline and the fetch hangs past it
- **THEN** the bounded runner stops `as.sh`'s whole process tree, the fenced `git` included, and reports `deadline_exceeded`

#### Scenario: A signal to the fence reaches the command
- **WHEN** on Linux or macOS a fenced command is running and `as.sh`'s process receives SIGINT, SIGTERM or SIGHUP
- **THEN** the fenced command receives the same signal, and `as.sh` ends with the command's exit status

### Requirement: The fence's handoff leaves no file behind and holds no token
The records `as.sh` hands to `sw as` SHALL be written to a file only the current user can read, SHALL hold the scripts directory, the bash path and `as.sh`'s arguments and never a token, and SHALL be deleted by `sw as` before any `gh` call or the fenced command runs. When `sw as` cannot read or delete the file, it SHALL stop with exit 3 and run nothing.

#### Scenario: Handoff file gone before the command runs
- **WHEN** `as.sh sh1ny bash -c 'ls "$TMPDIR"'` runs with `TMPDIR` set to an empty directory
- **THEN** the listing the fenced command prints is empty, and the directory is empty after `as.sh` ends

#### Scenario: Handoff file unreadable
- **WHEN** `sw as --args-file <f>` runs and `<f>` does not exist
- **THEN** `sw as` exits 3 with a message naming the handoff on stderr, and no `gh` call and no command ran

### Requirement: sw as keeps as.sh's contract
`sw as`, run through the `as.sh` shim, SHALL accept what `as.sh` accepted before this change and SHALL keep its refusals, messages, exit codes, environment rules, the saved `AS_SH_ORIG_*` values, the git transport settings and the credential helper. Its own `gh` lookups SHALL keep their deadline and size bound, report `deadline_exceeded` or `response_too_large` with exit 3, and hold the token only in memory.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `as.sh` tests in `evals/pr-pair` (`test_as_sh.py`, `test_as_jj.py`, `test_as_gitbutler.py`) and the `evals/vcs` tests that fence network calls run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change

#### Scenario: Exit codes
- **WHEN** `as.sh` runs with no arguments, with a login and no command, with `--resolve x`, and with a userinfo push URL
- **THEN** the exit statuses are 1, 2, 2 and 3, as before this change

#### Scenario: A hung token lookup
- **WHEN** `gh auth token --user sh1ny` does not answer before the deadline
- **THEN** `as.sh sh1ny gh api user` exits 3 with `as.sh: deadline_exceeded: gh auth token --user sh1ny` on stderr, and the fenced command did not run

#### Scenario: A nested fence keeps the outer originals
- **WHEN** `GH_HOST=corp.example` is set and `as.sh sh1ny bash as.sh sh1ny env` runs
- **THEN** the inner command's environment has `AS_SH_ORIG_GH_HOST=corp.example` and no `GH_HOST`

### Requirement: sw as verifies the token it hands over
The identity check SHALL verify the token read for `<login>`, with that token in `gh`'s environment, and never the active account. In this change `sw as` SHALL take its arguments only from the shim's handoff file: anything else on its own command line SHALL be a usage stop with exit 2 and no `gh` call.

#### Scenario: A configured account that is not the active one
- **WHEN** the active github.com account is `KintsugiBot`, `sh1ny` also has a gh credential, and `as.sh sh1ny gh api user --jq .login` runs
- **THEN** stdout is `sh1ny` and the exit status is 0

#### Scenario: A token that belongs to another login
- **WHEN** the active account is `sh1ny`, and `gh auth token --user sh1ny` returns a token that `gh api user` resolves to `KintsugiBot`
- **THEN** `as.sh sh1ny gh api user` exits 3 with `as.sh: token resolves to 'KintsugiBot', expected 'sh1ny'; refusing` on stderr, and the fenced command did not run

#### Scenario: Direct arguments are refused in this change
- **WHEN** `sw as sh1ny gh api user` runs without the shim
- **THEN** the exit status is 2 with a usage line on stderr, and no `gh` call was made
