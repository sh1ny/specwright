# Spec Delta

## MODIFIED Requirements

### Requirement: sw vcs reads settings and fences identity through the existing scripts
`sw vcs` SHALL read the backend settings, the main branch and logins, and the GitButler pinned settings in-process, with the rules of `sw pr vcs` and `sw pr context`, starting no `pr-pair.sh`. It SHALL run every network command against a github.com remote through the `as.sh` in the scripts directory of the `vcs.sh` that started it. It SHALL keep the outputs, stops and exit codes it gave before this change.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `vcs.sh state` runs
- **THEN** the backend is `jj`, as `pr-pair.sh vcs --code <code>` reports it, and no `pr-pair.sh` process was started: the same rules run in `sw`

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `vcs.sh state` stops with the same `error` as before this change and a `message` naming `svn`, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `vcs.sh state --repo <r> --role code` runs
- **THEN** the document reports `"backend": "jj"`, and the exit status is 0

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `vcs.sh push --branch feat/a --login KintsugiBot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, with the same exit code as before this change, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com and `vcs.sh push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** the push runs as `as.sh KintsugiBot git push ...` from the same scripts directory, and a refused fence exits 3 without pushing
