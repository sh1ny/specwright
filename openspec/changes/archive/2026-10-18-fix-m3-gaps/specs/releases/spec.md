# Spec Delta

## ADDED Requirements

### Requirement: Untagged versions can be read from local tags only
With `--local`, `release.sh untagged` SHALL read local tags only, make no network call, and say in its output that the list comes from local tags. Its output SHALL say so whenever it read local tags, including with no `origin` remote.

#### Scenario: Local tags only
- **WHEN** `v0.4.2` exists locally, origin points at an unreachable URL, main's version is 0.5.0, and `untagged --local` runs
- **THEN** it exits 0, lists 0.5.0, reports that the list comes from local tags, and starts no `git ls-remote`

#### Scenario: Local read with a local-only tag
- **WHEN** `v0.5.0` exists only locally (its push failed) and `untagged --local` runs with main at 0.5.0
- **THEN** it lists nothing, and its output still says the list comes from local tags, so origin may lack a tag it counted

### Requirement: A bumped version is greater than main's before it merges
`release.sh check --main <ref>` SHALL refuse, before any write, a branch that bumped (its version differs from its merge base with `<ref>`, or the newest of its own non-merge commits that changed the primary file's version raised it) to a version not greater than `<ref>`'s, naming both versions and saying to bump again. No readable version at `<ref>` SHALL pass.

#### Scenario: Two changes bump to the same version
- **WHEN** branches `feat/a` and `feat/b` both start at 0.4.2 and bump to 0.5.0, `feat/a` has merged, and ship runs for `feat/b` with `origin/main` at 0.5.0
- **THEN** `check --main origin/main` exits non-zero naming 0.5.0 on the branch and on `origin/main`, nothing is pushed, and the message says to bump `feat/b` again

#### Scenario: Main moved past the bump
- **WHEN** the branch bumped from 0.4.2 to 0.5.0 and `origin/main` is at 0.6.0
- **THEN** the check exits non-zero naming 0.5.0 and 0.6.0

#### Scenario: Bump still ahead
- **WHEN** the branch bumped from 0.4.2 to 0.5.0 and `origin/main` is still at 0.4.2
- **THEN** the check exits 0 and reports version 0.5.0

#### Scenario: Version file edited without a bump
- **WHEN** a change branch edits the primary file but leaves its version at 0.4.2, and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0: an edit that keeps the version is not a bump

#### Scenario: Bump reverted on the branch
- **WHEN** a change branch bumped 0.4.2 to 0.5.0, a later commit set it back to 0.4.2, and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0: the branch carries no bump

#### Scenario: Branch did not bump
- **WHEN** a change branch leaves the version at 0.4.2 and `origin/main` has moved to 0.5.0
- **THEN** the check exits 0 and refuses nothing, since the branch carries no release of its own

#### Scenario: Main was merged into the branch after the duplicate landed
- **WHEN** `feat/a` and `feat/b` both bumped 0.4.2 to 0.5.0, `feat/a` merged, and `origin/main` was then merged into `feat/b`
- **THEN** `check --main origin/main` exits non-zero naming 0.5.0 on the branch and on `origin/main`, and says to bump again

#### Scenario: Main has no version yet
- **WHEN** the branch adds `VERSION` at 0.1.0 with `release.enabled`, and `origin/main` has no `VERSION` file
- **THEN** the check exits 0 and reports version 0.1.0

### Requirement: Ship, local merge and watch check the version against main
With `release.enabled` true, `specwright-pr` ship SHALL run `check --main origin/<main>` after a fenced fetch of main and before any push; `specwright-finish` SHALL run `check --main <main>` before the local merge; and watch SHALL run it against a refreshed `origin/<main>` before it reports a PR ready or merges it. A refusal SHALL stop that step.

#### Scenario: Ship of a duplicate version
- **WHEN** `feat/a` merged at 0.5.0 and ship runs for `feat/b`, which also bumped 0.4.2 to 0.5.0
- **THEN** ship pushes nothing and opens no PR, and reports the 0.5.0 refusal

#### Scenario: Main merged a duplicate while the PR waited
- **WHEN** a PR bumped to 0.5.0 passed ship, another PR to 0.5.0 merged afterwards, and watch is about to report the first PR ready
- **THEN** watch runs the check against refreshed `origin/main`, reports the duplicate 0.5.0, and neither reports ready nor merges

#### Scenario: Local merge of a duplicate version
- **WHEN** `finish` is `local`, local main already holds a merge at 0.5.0, and the branch also bumped 0.4.2 to 0.5.0
- **THEN** finish stops before `git merge`, main is unchanged, and the report names 0.5.0

#### Scenario: Releases disabled
- **WHEN** `release.enabled` is false and two branches carry the same `VERSION` edit
- **THEN** ship, the local merge and watch run no version check
