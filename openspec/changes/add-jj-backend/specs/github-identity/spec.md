# Spec Delta

## ADDED Requirements

### Requirement: jj network commands are fenced like git
`jj git push` and `jj git fetch` against a remote whose fetch URL is on github.com SHALL run through the identity fence for the repository's run login, with the same transport rules as `git`: the pinned token for github.com only, SSH disabled and no prompt. The fence SHALL refuse a jj command that selects another repository or config (`-R`, `--repository`, `--config`, `--config-file`), with exit 3.

#### Scenario: Push on jj
- **WHEN** `github.login` is `code-bot`, the active `gh` account is `sh1ny`, and ship pushes a bookmark with `jj git push`
- **THEN** the push authenticates with `code-bot`'s token, and no call uses `sh1ny`'s

#### Scenario: Repository option
- **WHEN** the fence is asked to run `jj -R ../other git push`
- **THEN** it exits 3 saying the option selects another repository, and nothing runs

#### Scenario: Config override
- **WHEN** the fence is asked to run `jj --config git.executable-path=/tmp/x git fetch`
- **THEN** it exits 3, and nothing runs

#### Scenario: Other jj subcommand
- **WHEN** the fence is asked to run `jj bookmark set feat/x -r @-`
- **THEN** it exits 3 saying only `jj git push` and `jj git fetch` are fenced, and nothing runs
