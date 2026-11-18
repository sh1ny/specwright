# Spec Delta

## ADDED Requirements

### Requirement: sw as verifies the token for its login
The identity check SHALL verify the token read for `<login>`, with that token in `gh`'s environment, and never the active account. `sw as` SHALL take its login and command as its own arguments.

#### Scenario: A configured account that is not the active one
- **WHEN** the active github.com account is `KintsugiBot`, `sh1ny` also has a gh credential, and `<sw> as sh1ny gh api user --jq .login` runs
- **THEN** stdout is `sh1ny` and the exit status is 0

#### Scenario: A token that belongs to another login
- **WHEN** the active account is `sh1ny`, and `gh auth token --user sh1ny` returns a token that `gh api user` resolves to `KintsugiBot`
- **THEN** `<sw> as sh1ny gh api user` exits 3 with `as.sh: token resolves to 'KintsugiBot', expected 'sh1ny'; refusing` on stderr, and the fenced command did not run

#### Scenario: Old handoff flag
- **WHEN** `<sw> as --args-file <path>` runs
- **THEN** `sw` stops with a usage error naming the unknown option, exit 2, reads no file and makes no `gh` call

### Requirement: sw as keeps GH_REPO out of the fenced command
`sw as` SHALL remove `GH_REPO` from the environment of the command it fences, and of its own credential and identity lookups, so a fenced `gh` call acts only on the repository it names.

#### Scenario: GH_REPO set by the caller
- **WHEN** `GH_REPO=other/repo` is set and `sw as sh1ny gh pr view 5 --repo o/r` runs
- **THEN** the fenced `gh` sees no `GH_REPO` and reads `o/r`'s PR 5

#### Scenario: A fenced call that names no repository
- **WHEN** `GH_REPO=other/repo` is set and `sw as sh1ny gh pr view 5` runs in a checkout of `o/r`
- **THEN** `gh` resolves the repository from the checkout's remote, not from `other/repo`

## MODIFIED Requirements

### Requirement: The fence runs in the project's sw
`sw as` SHALL be the only identity fence and SHALL run after the project's version check. A leading `--project <code-checkout>` SHALL select only the project whose `VERSION` is checked; it SHALL NOT change the working directory, the target repository, the login or stdin. `sw as --resolve` SHALL run the same way. There SHALL be no fallback fence implementation.

#### Scenario: Fenced gh call with a matching sw
- **WHEN** the project's `VERSION` reads `0.28.0`, the running `sw` is 0.28.0, sh1ny has a gh credential, and `<sw> as sh1ny gh api user --jq .login` runs inside the project
- **THEN** stdout is `sh1ny`, the exit status is 0, and gh saw `GH_TOKEN` set to sh1ny's token

#### Scenario: Resolve through sw
- **WHEN** the active github.com account is KintsugiBot and `<sw> as --resolve` runs in a project of the same version
- **THEN** stdout is exactly `KintsugiBot` and a newline, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `<sw> as sh1ny git push` runs in a repo whose origin push URL is `https://tok@github.com/o/r.git`
- **THEN** the exit status is 3, stderr names the remote with userinfo masked as `***`, and `git push` did not run

#### Scenario: Fenced store call selects the code project
- **WHEN** a store without `VERSION` runs `<sw> --project <code> as store-bot git credential fill` with caller input, and `<code>` matches the running `sw`
- **THEN** the command starts in the store, receives the same input, and uses store-bot's verified token; the selector is not passed on as a login or command argument

#### Scenario: Selected project does not change target validation
- **WHEN** the selected code project has safe remotes but the caller's store has a github.com remote containing credentials
- **THEN** the fence refuses before the command runs, naming the store remote with credentials masked

#### Scenario: Resolve in a project of another version
- **WHEN** the project's `VERSION` differs from the running `sw` and `<sw> as --resolve` runs
- **THEN** the exit status is 1, not 3, stdout holds the `sw_mismatch` document and never a login, and no `gh` call ran

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `<sw> --project <code> as sh1ny gh api user` names a project whose `VERSION` differs from the running `sw`, while the current directory's project matches and another `sw` is on `PATH`
- **THEN** stdout holds the `sw_mismatch` document, the exit status is 1, no identity lookup or command ran, and no other binary was used

#### Scenario: Malformed fence project prefix is refused
- **WHEN** the leading `--project` has no value or an empty value before `as`
- **THEN** `sw` exits 2 with a usage error before any credential lookup or command execution

### Requirement: The fenced command keeps the caller's stdin, arguments and exit status
`sw as` SHALL read none of the caller's stdin itself; stdin SHALL reach the fenced command. The fenced command SHALL start with no shell before it, in the directory `sw as` started in, with each argument value unchanged, and its exit status SHALL be `sw as`'s. A signal SHALL end `sw as` with 128 plus its number. A command not found SHALL give exit 127 with its name on stderr.

#### Scenario: Credential fill reads stdin through the fence
- **WHEN** `<sw> as sh1ny git credential fill` runs with `protocol=https`, `host=github.com` and a blank line on stdin
- **THEN** stdout holds `username=x-access-token` and `password=` followed by `sh1ny`'s verified token, and the exit status is 0

#### Scenario: Argument bytes and exit status pass through
- **WHEN** `<sw> as sh1ny bash -c 'printf %s "$1"; exit 7' x 'a "b" $c'` runs
- **THEN** stdout is exactly `a "b" $c` and the exit status is 7

#### Scenario: A non-UTF-8 argument is refused
- **WHEN** on Linux `<sw> as sh1ny git add -- <name holding 0xFF>` runs
- **THEN** it prints the `bad_argument` document naming that argument's position, exits 2, reads no token, and `git` does not run

#### Scenario: Command not found
- **WHEN** `<sw> as sh1ny no-such-tool` runs after the identity check passes
- **THEN** the exit status is 127 and stderr names `no-such-tool`

#### Scenario: A bounded caller stops the fence
- **WHEN** `sw run --bounded` runs `<sw> as <login> git fetch` under a deadline and the fetch hangs past it
- **THEN** the bounded runner stops `sw as`'s whole process tree, the fenced `git` included, and reports `deadline_exceeded`

#### Scenario: A signal to the fence reaches the command
- **WHEN** on Linux or macOS a fenced command is running and `sw as`'s process receives SIGINT, SIGTERM or SIGHUP
- **THEN** the fenced command receives the same signal, and `sw as` ends with the command's exit status

### Requirement: sw as keeps as.sh's contract
`sw as` SHALL accept what `as.sh` accepted and SHALL keep its refusals, messages, exit codes, environment rules, the saved `AS_SH_ORIG_*` values, the git transport settings and the credential helper. Its own `gh` lookups SHALL keep their deadline and size bound, report `deadline_exceeded` or `response_too_large` with exit 3, and hold the token only in memory.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the fence tests in `evals/pr-pair` (`test_as_sh.py`, `test_as_jj.py`, `test_as_gitbutler.py`) and the `evals/vcs` tests that fence network calls run `sw as` directly in CI on Linux, Windows and macOS
- **THEN** every test passes with its stdout, stderr and exit-status assertions as they were for `as.sh`, apart from the removed `sw_missing`, `no_python` and handoff cases

#### Scenario: Exit codes
- **WHEN** `<sw> as` runs with no arguments, with a login and no command, with `--resolve x`, and with a userinfo push URL
- **THEN** the exit statuses are 1, 2, 2 and 3, as `as.sh` gave

#### Scenario: A hung token lookup
- **WHEN** `gh auth token --user sh1ny` does not answer before the deadline
- **THEN** `<sw> as sh1ny gh api user` exits 3 with `as.sh: deadline_exceeded: gh auth token --user sh1ny` on stderr, and the fenced command did not run

#### Scenario: A nested fence keeps the outer originals
- **WHEN** `GH_HOST=corp.example` is set and `<sw> as sh1ny <sw> as sh1ny env` runs
- **THEN** the inner command's environment has `AS_SH_ORIG_GH_HOST=corp.example` and no `GH_HOST`

## REMOVED Requirements

### Requirement: A missing or mismatched sw stops every fenced call
**Reason**: `as.sh`, its resolver and its Python check are deleted, so there is no `sw_missing` or `no_python` stop. `sw as` checks the project's version itself and runs no `gh` call and no command when it differs.
**Migration**: See the native-cli requirements "Project commands check the project's version" and "Skills run sw directly".

### Requirement: The fence's handoff leaves no file behind and holds no token
**Reason**: The handoff file is gone. `sw as` takes its arguments directly, so no file is written and none holds a token.
**Migration**: See the native-cli requirement "sw takes its arguments directly". "sw as keeps as.sh's contract" still keeps the token only in memory.

### Requirement: sw as verifies the token it hands over
**Reason**: Its rule that `sw as` takes arguments only from the shim's handoff file is reversed: `sw as` now takes its arguments directly.
**Migration**: See "sw as verifies the token for its login" and the native-cli requirement "sw takes its arguments directly".
