# Spec Delta

## ADDED Requirements

### Requirement: Each repository selects one network remote
`remote` selects the code remote; `planning_store.remote` selects the store remote. Each SHALL default independently to `origin`. Specwright SHALL use the selected remote for fetch, push, remote-tracking refs, PR identity, release checks and explicit-remote pulls. It SHALL NOT substitute another remote or support cross-repository PRs.

#### Scenario: Code and store use different remote names
- **WHEN** the code settings select `fork` and the store settings select `plans`, and both repos also have `origin`
- **THEN** fetch and pull select `fork` and `plans` respectively, push writes only to those remotes, and PR discovery and creation target those repositories

#### Scenario: The store does not inherit the code's remote name
- **WHEN** `remote: upstream` is set but `planning_store.remote` is absent
- **THEN** store network operations use `origin`, while code network operations use `upstream`

#### Scenario: A selected remote is missing
- **WHEN** a fetch, pull or push needs the selected `publish` remote but only `origin` exists
- **THEN** the operation stops naming `publish` and does not contact `origin`

#### Scenario: Git main has a different upstream
- **WHEN** code selects `upstream` and the local main branch tracks `origin/main`
- **THEN** pull fast-forwards only from `upstream`'s main, without changing that upstream configuration

#### Scenario: Explicit origin is not the default pull
- **WHEN** `remote: origin` is supplied and local main tracks `other/main`
- **THEN** pull fast-forwards only from `origin/main`, without changing the upstream configuration

#### Scenario: jj reads main from a selected remote
- **WHEN** jj selects `upstream` and Specwright refreshes its main for a read
- **THEN** the read uses the fetched commit without moving either remote tracking ref or a local bookmark

## MODIFIED Requirements

### Requirement: The Git backend keeps today's commands
With the `git` backend, branch creation, switch, commit by named paths, `--no-ff` merge, branch deletion and commit subjects and trailers SHALL be unchanged. Fetch and push SHALL use the selected remote. Pull SHALL use that remote and main when the setting is explicit or the call specifies `--remote-branch`, otherwise retain the existing `git pull --ff-only` behaviour. Existing timeout behaviour SHALL remain.

#### Scenario: Git commit by name
- **WHEN** the backend is `git` and a task group commits `a.sh` and `b.sh` with a message file
- **THEN** the commands run are `git add -- a.sh b.sh` and `git commit -F <file> -- a.sh b.sh`, and no `jj` command runs

#### Scenario: Git push
- **WHEN** the backend is `git`, the remote and fence settings are omitted, and ship pushes with run login `code-bot`
- **THEN** the command run is the fenced `git push -u origin HEAD`, with no deadline added

#### Scenario: Git pull without a remote setting
- **WHEN** the remote setting is omitted and `sw vcs pull` runs without `--remote-branch`
- **THEN** Git keeps its branch's upstream selection through `git pull --ff-only`

#### Scenario: Git commit with nothing to commit
- **WHEN** the backend is `git` and the named paths have no changes
- **THEN** the commit fails as `git commit` fails today, and no other path is committed

### Requirement: Fetches for reading move no jj bookmark
On jj, read-only main fetches (gate, roadmap, ship and PR ancestry) SHALL write only objects and `FETCH_HEAD`, not a remote-tracking ref. Use the fetched commit, not `<remote>/<main>`: moving that ref can move a tracked bookmark. GitHub release proof MAY use an invocation-private ref instead, SHALL remove it immediately after reading the commit, and SHALL leave all bookmarks, tracking refs and `FETCH_HEAD` unchanged.

#### Scenario: Remote main ahead, main tracked
- **WHEN** local main tracks `main@origin`, origin's main has a new commit, and the gate refreshes main on jj
- **THEN** local main still points at `@-`, `refs/remotes/origin/main` is unchanged, the gate counts the repo on main, and the archive check reads the fetched commit

#### Scenario: Local main diverged before a read
- **WHEN** local main holds a local merge commit, origin's main moved, and roadmap status refreshes main on jj
- **THEN** no bookmark becomes conflicted, and status reads the fetched commit

#### Scenario: Release publish on jj with main tracked
- **WHEN** a colocated jj checkout tracks the selected GitHub remote's main and publish needs a release-main fetch
- **THEN** the release fetch reads its own private ref and removes it immediately; no bookmark, remote-tracking ref or `FETCH_HEAD` changes, the history reads use that fetched commit, and the notes list the merged PRs of the base branch by its name

### Requirement: The GitButler backend is probed before any `but` command
Before a `but` command, Specwright SHALL verify `.git/gitbutler/` and `gitbutler.project.targetRef` with Git reads. An explicit remote requires its `<main>` tracking ref; otherwise accept local main or the default tracking ref. Check `but --version` outside the repo for 0.23+. Fail before writes with `not_managed`, `target_mismatch`, `tool_missing`, `tool_version_unknown` or `tool_too_old`. Never run `but` setup, teardown or target commands.

#### Scenario: `but` missing
- **WHEN** `vcs` is `gitbutler` and `but` is not on PATH
- **THEN** the branch gate stops with `tool_missing`, no branch exists, and `.git/` is unchanged

#### Scenario: Repo not managed by GitButler
- **WHEN** `vcs` is `gitbutler` and the repo has no `.git/gitbutler/` directory
- **THEN** the step stops with `not_managed`, saying to open the repo with GitButler first, no `but` command ran inside the repo, `.git/gitbutler/` is still absent and `.git/config` is unchanged

#### Scenario: Target is another branch
- **WHEN** the repo's GitButler target is `refs/remotes/origin/develop` and `<main>` is `main`
- **THEN** the step stops with `target_mismatch`, naming both

#### Scenario: Target is on another remote
- **WHEN** `remote: upstream` is selected but the GitButler target is `refs/remotes/origin/main`
- **THEN** the step stops with `target_mismatch` and names `upstream/main` before running a `but` command

#### Scenario: An explicit remote cannot be verified from a local target
- **WHEN** `remote: upstream` is set and the GitButler target is only `refs/heads/main`
- **THEN** the step stops with `target_mismatch`, asks for the remote-tracking target, and does not start `but pull`

### Requirement: A GitButler push publishes only the change branch
A GitButler push SHALL push `refs/heads/<branch>` to the same-named branch on the selected remote, without force and without setting an upstream, under the project's GitHub identity policy. It SHALL never run `but push` or `but pr`. A push the remote rejects as non-fast-forward SHALL stop with `push_rejected` and SHALL NOT retry with force. The PR SHALL be opened for that branch alone with `gh pr create --head <branch>`.

#### Scenario: Ship with another branch applied
- **WHEN** `feat/b` has unpushed commits and ship runs for `feat/add-c`
- **THEN** only `refs/heads/feat/add-c` is updated on the remote, `feat/b` is not pushed, and one PR is opened, for `feat/add-c`

#### Scenario: Rewritten branch
- **WHEN** the change branch was rebased outside Specwright after its last push
- **THEN** the push stops with `push_rejected`, and the remote branch is unchanged

### Requirement: The GitButler pull never rebases another branch
A GitButler pull SHALL run `but pull` under the project's GitHub identity policy only when no branch other than the one being cleaned up is applied and no linked worktree exists. Otherwise it SHALL run no `but` write and report `pulled: false`, `pull_skipped`, and the applied branches and worktrees. A skipped pull SHALL NOT stop its caller. Steps that read main after a pull SHALL read the selected remote's fetched main on GitButler.

#### Scenario: Cleanup alone in the workspace
- **WHEN** the merged change branch is the only applied branch, the fence is enabled and cleanup pulls
- **THEN** `but pull` runs fenced, the local target moves to the selected remote's main, and the merged branch is no longer applied

#### Scenario: Another branch applied
- **WHEN** cleanup pulls while `feat/b` is applied
- **THEN** no `but pull` runs, `feat/b`'s commits are unchanged, and the result names `feat/b` with `pull_skipped`

#### Scenario: Linked worktree
- **WHEN** cleanup pulls while the merged branch is the only applied branch and a linked worktree exists
- **THEN** no `but pull` runs, and the result names the worktree with `pull_skipped`

#### Scenario: Finish after a skipped pull
- **WHEN** the change's PR merged on GitHub, `feat/b` is applied, and finish checks that main holds the archive
- **THEN** finish reads the archive on the fetched remote main, finds it, and does not report the repo as not done

### Requirement: sw vcs reads settings and fences identity in process
`sw vcs` SHALL read backend, main branch, login, connection and GitButler pinned settings in-process, with the rules of `sw pr vcs` and `sw pr context`. With fencing enabled, it SHALL resolve a missing login and fence network commands against the configured GitHub host, in-process. With fencing disabled it SHALL use the caller's transport credentials without a stored-account lookup. It SHALL start no other `sw` process, and keep existing outputs and exits with default settings.

#### Scenario: Settings read through pr-pair.sh
- **WHEN** `openspec/specwright.yaml` sets `vcs: jj` and `sw vcs state` runs
- **THEN** the backend is `jj`, as `sw pr vcs --code <code>` reports it, and no second `sw` process is started

#### Scenario: Unknown backend in the settings
- **WHEN** `openspec/specwright.yaml` sets `vcs: svn`
- **THEN** `sw vcs state` stops with the existing error and a message naming `svn`, and runs no `git`, `jj` or `but` write

#### Scenario: Scripts installed under a non-UTF-8 directory
- **WHEN** on Linux the skills are installed under a directory whose name holds the byte 0xFF, `openspec/specwright.yaml` sets `vcs: jj`, and `sw vcs state --repo <r> --role code` runs with a UTF-8 `<r>`
- **THEN** stdout is the usual state document with `"backend": "jj"`, no `not_utf8` stop occurs because `sw` reads no scripts directory, and the exit status is 0

#### Scenario: Unpinned settings stop a GitButler push
- **WHEN** `vcs` is `gitbutler`, an unassigned work-tree edit changes `openspec/specwright.yaml`, and `sw vcs push --branch feat/a --login code-bot` runs
- **THEN** it stops with `settings_not_pinned`, naming the file and the ref, and nothing is pushed

#### Scenario: Fenced push
- **WHEN** all effective push URLs target the configured GitHub host and `sw vcs push --branch feat/a --login code-bot` runs on Git with fencing enabled
- **THEN** `git push` runs in the repo with `code-bot`'s verified token and the fence's transport settings, and no second `sw` or `bash` process starts

#### Scenario: Refused fence
- **WHEN** the selected push URL is `https://tok@github.com/team/app.git` and fenced `sw vcs push --branch feat/a --login code-bot` runs on Git, jj or GitButler
- **THEN** the document has `"error": "fence_failed"`, its `message` starts with `as.sh:` and masks the userinfo as `***`, the exit status is 3, and no push ran

#### Scenario: Login resolved in process
- **WHEN** the selected remote is on the configured host, the active account on that host is `code-bot`, and `sw vcs fetch-main --repo <r> --role code` runs with fencing enabled and no `--login`
- **THEN** the fetch runs as `code-bot`, the document reports the fetched `ref`, and no second `sw` process starts

#### Scenario: No gh account to resolve
- **WHEN** the selected remote is on the configured host, no `gh` account is logged in there, and `sw vcs fetch-main --repo <r> --role code` runs with fencing enabled and no `--login`
- **THEN** the document has `"error": "fence_failed"` with the fence's message, the exit status is 3, and no fetch ran

#### Scenario: Store without a Specwright version
- **WHEN** a planning store has a selected GitHub remote but no installed `VERSION`, and a fenced `sw vcs pull --repo <store> --role store --code <code> --branch main --login store-bot` runs with a matching code `VERSION`
- **THEN** the version check reads the code `VERSION`, the pull runs in the store as `store-bot`, and the document is not `sw_mismatch`

#### Scenario: Fenced commands stay unbounded
- **WHEN** a fenced VCS fetch is running and a network time limit that applies only to the fence's `gh` lookups elapses
- **THEN** the VCS fetch can still complete successfully; the fence's credential and identity lookups retain their own bounds

#### Scenario: Non-GitHub remote runs unfenced
- **WHEN** all effective push URLs are outside the configured GitHub host and `sw vcs push --branch feat/a` runs
- **THEN** `git push` runs with the caller's environment and no fence lookup, and a failure is `git_network_error` with exit 3
