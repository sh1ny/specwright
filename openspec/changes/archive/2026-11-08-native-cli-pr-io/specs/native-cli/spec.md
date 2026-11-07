# Spec Delta

## MODIFIED Requirements

### Requirement: Commands resolve as the shell would find them
`sw run --bounded` SHALL find the command on `PATH` itself. On Windows it SHALL also try each `PATHEXT` extension in order, so `.exe`, `.cmd` and `.bat` shims (the eval fakes of `gh` and the reviewer CLIs included) resolve. A name containing a path separator SHALL be used as given. On POSIX an empty `PATH` entry (leading, trailing, or between two colons) SHALL mean the current directory, searched in its position, as the shell and `execvp` search it. On Windows empty entries SHALL be dropped.

#### Scenario: A .cmd shim on Windows
- **WHEN** on Windows `PATH` holds a directory with `gh.cmd` and no `gh.exe`, and `sw run --bounded -- gh api user` runs
- **THEN** `gh.cmd` runs with the arguments `api user` and its output and status come through

#### Scenario: A name that resolves nowhere
- **WHEN** neither the bare name nor any `PATHEXT` variant exists on `PATH`
- **THEN** `sw` exits 127 and names the command on stderr

#### Scenario: An empty POSIX PATH entry is the current directory
- **WHEN** on Linux or macOS `PATH` is `:/usr/bin`, the current directory holds an executable `./tool`, `/usr/bin` holds another `tool`, and `sw run --bounded -- tool` runs
- **THEN** `./tool` runs, as `bash -c tool` would run it, and not `/usr/bin/tool`

#### Scenario: The empty entry keeps its position
- **WHEN** on Linux or macOS `PATH` is `/usr/bin:`, both `/usr/bin/tool` and `./tool` exist, and `sw run --bounded -- tool` runs
- **THEN** `/usr/bin/tool` runs

#### Scenario: No empty entry, no current directory
- **WHEN** on Linux or macOS `PATH` is `/usr/bin` with no empty entry, only `./tool` exists, and `sw run --bounded -- tool` runs
- **THEN** `sw` exits 127 and names `tool` on stderr
