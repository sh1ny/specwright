# Bootstrap on a scratch clone (task 8.9)

Run on 2026-11-06 from the uncommitted working tree of branch `feat/native-cli-vcs` (tree `VERSION` 0.24.0). Scratch clone: `%TEMP%\claude-ncv-bootstrap` (`git clone` of the checkout, then the working tree's uncommitted files copied over it). Its `openspec/.specwright/VERSION` was seeded with `0.22.0` (this repository's own stamp, copied from the checkout: the file is git-ignored, not tracked), so `plan` reported `from` 0.22.0, `to` 0.24.0, kind `workflow`. `mise trust` was run in the clone first. The clone was deleted afterwards.

## Commands and exit status

Every command ran in the clone's root, in the order of `CONTRIBUTING.md`'s bootstrap section.

| # | Command | Exit status |
|---|---|---|
| 1 | `bash scripts/update.sh --code . --skills .claude/skills --agents claude=.claude/agents --download . --ref feat/native-cli-vcs plan` | 0 |
| 2 | same options, `stage` | 0 |
| 3 | same options, `swap` | 0 |
| 4 | `openspec schema validate specwright` (Step 7 check) | 0 |
| 5 | `diff -r skills .claude/skills --exclude=__pycache__` (Step 7 check) | 0 |
| 6 | `diff -r agents/claude .claude/agents` (Step 7 check) | 0 |
| 7 | `cp VERSION openspec/.specwright/VERSION` | 0 |
| 8 | same `update.sh` options, `finish` | 0 |
| 9 | `mise run install-sw` | 0 |
| 10 | `bash skills/specwright-pr/scripts/sw-path.sh --code .` | 0 |

Steps 5 and 6 printed nothing: the installed skills and agents equal the tree's. Step 4 printed `Schema 'specwright' is valid`.

## `finish` output

```json
{
  "ok": true,
  "interface": 2,
  "installed": "0.24.0",
  "unchanged": false,
  "subcommand": "finish",
  "state": "done",
  "from": "0.22.0",
  "to": "0.24.0",
  "ref": "feat/native-cli-vcs",
  "kind": "workflow",
  "role": "none",
  "files": 41,
  "inflight_checked": true,
  "inflight": [
    {
      "name": "native-cli-vcs",
      "source": "working tree",
      "status": "validated",
      "validated_against": "0.24.0"
    }
  ],
  "warnings": [],
  "groups": [
    {
      "id": "skills-1",
      "kind": "skills",
      "dir": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/.claude/skills",
      "staging": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/.claude/.specwright-update-skills",
      "targets": 8
    },
    {
      "id": "agents-1-claude",
      "kind": "agents",
      "dir": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/.claude/agents",
      "staging": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/.claude/.specwright-update-agents",
      "targets": 3
    },
    {
      "id": "schema",
      "kind": "schema",
      "dir": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/openspec/schemas",
      "staging": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/openspec/.specwright-update-schemas",
      "targets": 1
    },
    {
      "id": "record",
      "kind": "record",
      "dir": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/openspec/.specwright",
      "staging": "C:/Users/bgshi/AppData/Local/Temp/claude-ncv-bootstrap/openspec/.specwright-update-record",
      "targets": 1
    }
  ],
  "finished": true
}
```

It reports `state: done` and `finished: true`, and `installed` reads `0.24.0` after the stamp.

## `mise run install-sw` output

```
[build] $ dart run tool/build.dart
Generated: c:\users\bgshi\appdata\local\temp\claude-ncv-bootstrap\cli\build\sw.exe
C:\Users\bgshi\AppData\Local\Temp\claude-ncv-bootstrap\cli\build\sw.exe
[install-sw] $ bash scripts/install-sw.sh
C:/Users/bgshi/.specwright/bin/0.24.0/sw.exe
Finished in 5.17s
```

## `sw-path.sh --code .` output

```
C:/Users/bgshi/.specwright/bin/0.24.0/sw.exe
```

The path it printed is the one `install-sw` placed: `<user home>/.specwright/bin/0.24.0/sw.exe` (`C:/Users/bgshi/.specwright/bin/0.24.0/sw.exe`), because no `SPECWRIGHT_HOME` was set.
