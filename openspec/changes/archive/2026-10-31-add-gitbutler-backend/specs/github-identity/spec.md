## ADDED Requirements

### Requirement: GitButler pulls are fenced like git
`but pull` against a remote whose fetch URL is on github.com SHALL run through the identity fence for the repository's run login, with the same transport rules as `git`: the pinned token for github.com only, SSH disabled and no prompt. The fence SHALL refuse every other `but` subcommand, and any `but` option that selects another directory or repository (`-C`, `--current-dir`), with exit 3.

#### Scenario: Cleanup pull
- **WHEN** `github.login` is `code-bot`, the active `gh` account is `sh1ny`, and cleanup runs `but pull` in a GitButler repo
- **THEN** the fetch authenticates with `code-bot`'s token, and no call uses `sh1ny`'s

#### Scenario: Other `but` subcommand
- **WHEN** the fence is asked to run `but push feat/x`
- **THEN** it exits 3 saying only `but pull` is fenced, and nothing runs

#### Scenario: Directory option
- **WHEN** the fence is asked to run `but -C ../other pull`
- **THEN** it exits 3 saying the option selects another repository, and nothing runs
