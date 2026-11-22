# Spec Delta

## MODIFIED Requirements

### Requirement: Finish offers a release once the change is on main
With `release.enabled` true, once the change is on main (after the local merge, or after the PR is merged and cleanup finished), `specwright-finish` SHALL read `sw release untagged`. It SHALL offer `specwright-release` publish for each listed version oldest first, or with `release.auto` publish them oldest first, stopping at the first failure, before the roadmap offer. With none listed, or releases disabled, it SHALL NOT mention a release.

#### Scenario: Untagged version after a PR merge
- **WHEN** releases are enabled, `release.auto` is false, the merged PR moved `VERSION` to 0.5.0 and no `v0.5.0` tag exists
- **THEN** finish offers publish for 0.5.0, then the roadmap mode

#### Scenario: Auto release
- **WHEN** releases are enabled with `release.auto` true and the version on main has no tag
- **THEN** finish runs publish without asking, reports its result, then offers the roadmap mode

#### Scenario: An earlier version was left untagged
- **WHEN** 0.5.0 was merged and never published, and the PR that moved `VERSION` to 0.5.1 is merged
- **THEN** finish offers publish for 0.5.0, then 0.5.1

#### Scenario: Version already tagged
- **WHEN** the merged change did not bump the version and the current version already has its tag
- **THEN** finish offers no release

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false or missing
- **THEN** finish's report and offers contain no release step

#### Scenario: Auto publish fails
- **WHEN** `release.auto` is true and publish exits non-zero
- **THEN** finish reports the publish error, keeps the merge and cleanup it already did, and still offers the roadmap mode

### Requirement: Local finish lists untagged versions from local tags
With `release.enabled` true and `finish: local`, `specwright-finish` SHALL read `sw release untagged --local` once the change is on main, resolve no login and make no network call, and say that the list comes from local tags, to publish after `main` is pushed.

#### Scenario: Local finish with a github.com origin and no login
- **WHEN** `finish` is `local`, origin's fetch URL is on github.com, the run login is `none`, and the local merge moved `VERSION` to 0.5.0
- **THEN** finish runs `sw release untagged --local`, resolves no login, runs no `git ls-remote` or other network call, and reports 0.5.0 as untagged from local tags, to publish after `main` is pushed

### Requirement: A deferred archive's undo is planned by a script that runs nothing
When the deferred check stops on `VERDICT: DEFERRED`, finish SHALL run `sw finish undo-archive-plan` and show the undo `steps` it prints, without running them or making a commit, merge or push. The plan SHALL write no repo state but jj's snapshot and Git import; the GitButler probe's temp directory is outside it and removed. It SHALL print one JSON document: the facts found, `steps`, optional `after_rerun_steps`, and warnings. A runner of either list SHALL stop at its first failing step.

#### Scenario: Deferred archive found
- **WHEN** finish starts after a deferred change was archived
- **THEN** finish prints the plan's undo `steps`, and `git status --porcelain`, `git rev-parse HEAD` and every ref are the same after finish as before it on Git; on jj every working-tree file is the same, and refs and the operation log change only by jj's own snapshot and import

#### Scenario: Plan run on a dirty unrelated path in a resume on main
- **WHEN** the archive is committed on `bugfix/add-x`, finish resumes on `main`, and `main` has an uncommitted change to `README.md`
- **THEN** the plan exits non-zero with `dirty_tree`, names `README.md`, prints no steps, and every working-tree file is unchanged; on Git the index, HEAD and refs are unchanged too, and on jj only jj's own snapshot and import are recorded

#### Scenario: No archive of the change
- **WHEN** the plan runs for a change with no archive directory in the working tree and no add commit on the branch
- **THEN** it exits non-zero with `no_archive` and prints no steps

#### Scenario: Branch moved after the plan
- **WHEN** a commit is added to the branch after the plan was printed, and the user then runs its undo steps in order
- **THEN** the guard step exits non-zero, no commit is made, the index and working tree are unchanged, and no main spec is restored

#### Scenario: A jj plan with an unsnapshotted edit
- **WHEN** the undo is planned on a jj store whose working copy has an edit jj has not yet snapshotted
- **THEN** every file's bytes are unchanged after planning, and the only new operations in the operation log, read with `--ignore-working-copy`, are working-copy snapshots

#### Scenario: A jj plan with a pending Git ref import
- **WHEN** the undo is planned for resume bookmark `feat/add-x` on a colocated jj store after a plain `git fetch` moved the remote branch it tracks
- **THEN** every working-tree file's bytes are unchanged; separately, the operation log gains only jj's own import and snapshot operations, and `feat/add-x` and its `refs/heads/` mirror move, or `feat/add-x` becomes conflicted and the plan stops with `ambiguous_branch`

### Requirement: An archive-only push skips the code validate
Watch SHALL hand finish, and finish ship, the ready head of each repo (`ready head: <repo>=<sha>`). Before the push, ship SHALL run `sw review archive-only` in the planning repo against its ready head. When it reports `archive_only: true`, ship SHALL skip `pr.validate` for the planning repo, and for a code repo still at its ready head; `planning_store.validate` SHALL still run. Any other result, an error, or no ready head SHALL run `pr.validate`.

#### Scenario: Archive of a reviewed head
- **WHEN** watch reported head `h1` ready and handed `ready head: h1`, the change is archived as commit `h2` whose only change is the archive move and the synced main specs, and `pr.validate` is `make test`
- **THEN** ship pushes `h2` without running `make test`, and reports that validate was skipped for an archive-only push

#### Scenario: Store-backed archive
- **WHEN** the change is store-backed, the archive commit is on the store branch, `archive-only` in the store reports `true`, and `planning_store.validate` is `openspec validate --all --strict`
- **THEN** that command runs in the store before the push, a failure stops the push, and the code repo's `pr.validate` is skipped because its head is still the code ready head it was handed

#### Scenario: Archive commit with other files
- **WHEN** the archive commit also changes `src/app.dart`
- **THEN** `archive-only` reports `archive_only: false`, and `pr.validate` runs before the push

#### Scenario: No ready head
- **WHEN** the archive was started by hand, outside watch, so no ready head was handed over
- **THEN** `pr.validate` runs before the push

#### Scenario: Check fails to run
- **WHEN** `archive-only` exits 3 because git cannot read the commits
- **THEN** `pr.validate` runs before the push, and the report names the `archive-only` error
