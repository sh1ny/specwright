# Spec Delta

## ADDED Requirements

### Requirement: An unreadable version is not absent
In `release.sh check --main <ref>`, a primary file that exists but does not read exactly one version SHALL be unreadable, which is not absent. An unreadable merge base or parent SHALL count as a bump only when the branch's or commit's version is not among the versions it matched.

#### Scenario: Merge base repeats the version
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, the branch's only commit on it removes the duplicate and keeps `0.4.2`, and `origin/main` has moved to 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.4.2: the branch did not bump

#### Scenario: Bump after a repair of an unreadable version
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, one branch commit removes the duplicate, a later one bumps to 0.5.0, and `origin/main` is at 0.5.0
- **THEN** the check exits non-zero with `version_not_ahead_of_main`, naming 0.5.0 on the branch and on `origin/main`

#### Scenario: One commit repairs and bumps
- **WHEN** the merge base's `VERSION` holds `0.4.2` twice, the branch's only commit on it writes `0.5.0` once, and `origin/main` is at 0.5.0
- **THEN** the check exits non-zero with `version_not_ahead_of_main`, naming 0.5.0 on the branch and on `origin/main`

### Requirement: An unreadable commit changes the version only when its parent is not among its versions
In the history walk of `release.sh check --main <ref>`, a commit whose own version is unreadable SHALL be no change when its parent's version is among the versions it matched, or the parent is also unreadable. Otherwise it SHALL count as a bump only when every version it matched is greater than its parent's.

#### Scenario: Bump reverted through an unreadable version
- **WHEN** the branch bumps 0.4.2 to 0.5.0, a later commit sets `VERSION` back to `0.4.2` twice, a still later one removes the duplicate, and `origin/main` is at 0.5.0
- **THEN** `check --main origin/main` exits 0 and reports version 0.4.2
