# Spec Delta

## ADDED Requirements

### Requirement: Local finish lists untagged versions from local tags
With `release.enabled` true and `finish: local`, `specwright-finish` SHALL read `release.sh untagged --local` once the change is on main, resolve no login and make no network call, and say that the list comes from local tags, to publish after `main` is pushed.

#### Scenario: Local finish with a github.com origin and no login
- **WHEN** `finish` is `local`, origin's fetch URL is on github.com, the run login is `none`, and the local merge moved `VERSION` to 0.5.0
- **THEN** finish runs `release.sh untagged --local`, resolves no login, runs no `git ls-remote` or other network call, and reports 0.5.0 as untagged from local tags, to publish after `main` is pushed
