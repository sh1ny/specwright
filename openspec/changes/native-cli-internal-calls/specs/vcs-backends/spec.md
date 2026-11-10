## RENAMED Requirements

- FROM: `### Requirement: sw vcs reads settings and fences identity through the existing scripts`
- TO: `### Requirement: sw vcs reads settings and fences identity in process`

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
- **THEN** the document reports `"backend": "jj"`, and the exit status is 0

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `vcs.sh push --branch feat/a --login KintsugiBot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, with the same exit code as before this change, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** origin's fetch URL is on github.com, the scripts directory holds a recording `as.sh` sentinel, and `vcs.sh push --branch feat/a --login KintsugiBot` runs on Git
- **THEN** `git push` runs in the repo with KintsugiBot's verified token and the fence's transport settings, receives the same argument bytes as before this change, and the sentinel did not run

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
