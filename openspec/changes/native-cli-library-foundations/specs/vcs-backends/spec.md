## RENAMED Requirements

- FROM: `### Requirement: sw vcs output bytes match vcs.sh`
- TO: `### Requirement: sw vcs documents keep their values and name bytes`

## MODIFIED Requirements

### Requirement: sw vcs keeps vcs.sh's output and exit-code contract
`sw vcs <sub>` SHALL accept the subcommands and options shipped callers pass and SHALL print exactly one JSON document on stdout for each run, with the same parsed fields, error codes and messages as `vcs.sh` for the same inputs, except that the wording of a usage error is free. It SHALL exit 0 on success, 1 on a stop, 2 on a usage error and 3 on a network or fence refusal. An unexpected failure SHALL be the document `"error": "internal_error"` with exit 1, never a stack trace on stdout.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** the `evals/vcs` suite and every other suite that runs `vcs.sh` run in CI on Linux, Windows and macOS against the `sw` built from the tree
- **THEN** every test passes with its assertions unchanged from before this change, apart from assertions on stdout bytes, which compare the parsed value instead, and on usage wording, which check the `usage` error and exit 2

#### Scenario: Unknown subcommand
- **WHEN** `vcs.sh frobnicate --repo <r> --role code` runs
- **THEN** it exits 2 and stdout is one JSON document with `"ok": false` and `"error": "usage"`

### Requirement: sw vcs documents keep their values and name bytes
Each document `sw vcs` prints SHALL parse to the same keys, key order and values as the one `vcs.sh` printed for the same inputs. A name's bytes SHALL round-trip through arguments, directory listings, `git` and `jj` output and the document even when they are not valid UTF-8; `but` output is read as before.

#### Scenario: Line separators stay escaped
- **WHEN** a message or path in the output holds U+2028 or U+2029
- **THEN** the parsed JSON string holds that character

#### Scenario: A non-UTF-8 name from a tool round-trips
- **WHEN** on Linux a tracked file's name holds the byte 0xFF and `vcs.sh state` reports it dirty
- **THEN** the `dirty_paths` entry is written with that byte, and a following `vcs.sh commit -- <that entry>` commits exactly that file

#### Scenario: A valid U+FFFD in a name is just a character
- **WHEN** a tracked file is named `a�.txt` (valid UTF-8) and a file whose name holds the byte 0xFF in the same place also exists, and `vcs.sh commit -- a�.txt` runs
- **THEN** the commit holds exactly `a�.txt`, and the other file is unchanged

#### Scenario: Tool input reaches the tool
- **WHEN** on Windows a jj commit names a directory holding a changed tracked file and an ignored file larger than `snapshot.max-new-file-size`
- **THEN** `git check-ignore -z --stdin` receives the oversized file's name, the commit succeeds as before this change, and no `path_not_tracked` stop occurs
