# Spec Delta

## ADDED Requirements

### Requirement: PR evidence is scoped to its GitHub host
Watch ownership, head cutoff and feedback records SHALL separate GitHub hosts. Pair state, merge policy and feedback SHALL match each supplied snapshot to its expected host, repo and PR number before using its evidence. Existing github.com watch and feedback records SHALL remain readable without migration.

#### Scenario: Identical PR coordinates on two hosts
- **WHEN** github.com and `github.example.com` both contain `team/app` PR 7 and Specwright watches both
- **THEN** each watcher can claim its own PR, and each one reads only its own cutoff and feedback evidence

#### Scenario: Snapshot from the wrong host
- **WHEN** pair state receives a snapshot with the correct repository slug, PR number and head SHA but a URL on another host
- **THEN** it requests a refresh and does not count the snapshot toward readiness

#### Scenario: Wrong PR evidence does not authorize merge or feedback
- **WHEN** a policy or feedback check receives a snapshot for the right commit and reviewer rules but another host, repository or PR number
- **THEN** the snapshot does not authorize merge or supply a feedback action, and the workflow requests fresh evidence of the expected PR

### Requirement: Reply mutations verify the addressed PR item
Before reacting to, replying to or resolving an item addressed by ID, `sw pr reply` SHALL verify that the item belongs to the specified PR on the configured host. An unreadable or mismatched item SHALL stop before mutation.

#### Scenario: A thread and its root belong to the target PR
- **WHEN** the target-host query verifies that the thread and root comment belong to the named PR and the revision is unchanged
- **THEN** the reply targets that thread on that PR and can resolve it after the successful reply

#### Scenario: An ID belongs to a different PR
- **WHEN** a supplied item ID exists on the configured host but belongs to another PR
- **THEN** the command reports the mismatch and posts no reply or reaction and resolves nothing

## MODIFIED Requirements

### Requirement: PR snapshots and replies run in the project's sw
`sw pr snapshot` and `sw pr reply` SHALL run in the project's verified `sw`. `--project` selects the code settings and version, not the target checkout or repo. Use an explicit `--repo` on the configured GitHub host; when omitted, resolve the target checkout's role-selected remote, not a `gh` default repo. Refuse an unusable selected remote. Keep the arguments and output contracts except for these target checks.

#### Scenario: Snapshot with a matching sw
- **WHEN** the project's `VERSION` matches the running `sw` and `<sw> as reviewer-bot <sw> pr snapshot 12 --repo team/app` runs against a PR with one unresolved thread
- **THEN** stdout is one JSON line listing that thread with its `id`, `rev` and body, and the exit status is 0

#### Scenario: Reply with a matching sw
- **WHEN** the project's `VERSION` matches and `<sw> pr reply 12 thread <thread-id> <root-id> body.md --resolve --repo team/app` runs
- **THEN** one reply is posted whose body is the file's bytes followed by `<!-- specwright:handled <thread-id> resolve -->`, the thread is resolved, and the exit status is 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `<sw> pr reply 12 comment <id> missing.md --repo team/app` runs and `missing.md` does not exist
- **THEN** the exit status is 4, stderr names the body file, and no `gh` call was made

#### Scenario: Store-started snapshot selects the code project
- **WHEN** a planning store has no `openspec/.specwright/VERSION`, the matching code project configures `github.example.com`, and `<sw> --project <code> as store-bot <sw> --project <code> pr snapshot 7 --repo team/plans` runs inside the store
- **THEN** the snapshot of `team/plans` PR 7 is printed, and its `gh` calls run in the store with `store-bot`'s token and the configured host

#### Scenario: Store-started reply selects the code project
- **WHEN** a planning store has no installed `VERSION` and `<sw> --project <code> pr reply 7 comment <id> body.md --repo team/plans` runs inside the store with a matching code project configured for `github.example.com`
- **THEN** one reply is posted only on `github.example.com/team/plans` PR 7 and the exit status is 0

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `<sw> --project <code> pr snapshot 7` names a project whose `VERSION` differs from the running `sw`, and the current directory's project matches
- **THEN** stdout is one `sw_mismatch` document, the exit status is 1, no `gh` call was made, and no other binary was used

#### Scenario: Malformed project prefix
- **WHEN** `<sw> --project` is given without a value or with an empty value before `pr reply`
- **THEN** `sw` stops with a usage error, exit 2, and makes no `gh` call

#### Scenario: The same PR number exists on another remote
- **WHEN** `remote: publishing` selects `team/app` and `origin` points at `team/old` on the same host, both have PR 7, and snapshot and reply omit `--repo`
- **THEN** snapshot reads `team/app` PR 7 and a reply changes only that PR; `team/old` receives no request

#### Scenario: A numeric branch name is not a PR number
- **WHEN** the current branch is `123`, its open PR in the selected repository is number 7, and PR 123 has a different head branch
- **THEN** `sw pr snapshot` without a PR number or URL reads PR 7, not PR 123

#### Scenario: Store snapshot infers its planning remote
- **WHEN** a store-started snapshot with `--project <code>` omits `--repo` and the project selects `planning_store.remote: plans`
- **THEN** it reads the store PR from `plans`, not from either checkout's `origin` or the code project's selected code remote

#### Scenario: Selected remote is unusable and no repo is given
- **WHEN** a repo-scoped snapshot or reply omits `--repo` and the selected remote is missing or does not identify one GitHub repository
- **THEN** it reports the unusable remote before querying or mutating a PR and does not fall back to `gh`'s default repository
