# Spec Delta

## MODIFIED Requirements

### Requirement: The fenced command keeps the caller's stdin, arguments and exit status
The handoff from `as.sh` to `sw as` SHALL not read the caller's stdin, so the fenced command reads the same stdin `as.sh` was given. The command SHALL be started with no shell between `sw` and it, SHALL receive each argument value unchanged, start in the directory `as.sh` started in, and its exit status SHALL be `as.sh`'s. An argument that is not valid UTF-8 SHALL be refused by name before the identity check, with exit 2. A command ended by a signal SHALL end `as.sh` with status 128 plus the signal number, the status a bash caller saw before this change. A command that cannot be found SHALL give exit 127 with its name on stderr.

#### Scenario: Credential fill reads stdin through the fence
- **WHEN** `as.sh sh1ny git credential fill` runs with `protocol=https`, `host=github.com` and a blank line on stdin
- **THEN** stdout holds `username=x-access-token` and `password=` followed by `sh1ny`'s verified token, and the exit status is 0

#### Scenario: Argument bytes and exit status pass through
- **WHEN** `as.sh sh1ny bash -c 'printf %s "$1"; exit 7' x 'a "b" $c'` runs
- **THEN** stdout is exactly `a "b" $c` and the exit status is 7

#### Scenario: A non-UTF-8 argument is refused
- **WHEN** on Linux `as.sh sh1ny git add -- <name holding 0xFF>` runs
- **THEN** it exits 2 with one stderr line starting `as.sh:` that names the argument with the byte shown as `\xFF` and asks for a rename, no token is read and `git` does not run

#### Scenario: Command not found
- **WHEN** `as.sh sh1ny no-such-tool` runs after the identity check passes
- **THEN** the exit status is 127 and stderr names `no-such-tool`

#### Scenario: A bounded caller stops the fence
- **WHEN** `pr-pair.sh` runs `as.sh <login> git fetch` under its deadline and the fetch hangs past it
- **THEN** the bounded runner stops `as.sh`'s whole process tree, the fenced `git` included, and reports `deadline_exceeded`

#### Scenario: A signal to the fence reaches the command
- **WHEN** on Linux or macOS a fenced command is running and `as.sh`'s process receives SIGINT, SIGTERM or SIGHUP
- **THEN** the fenced command receives the same signal, and `as.sh` ends with the command's exit status
