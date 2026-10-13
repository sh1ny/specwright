# github-identity Specification

## Purpose
Decides which GitHub account every Specwright `gh` call and GitHub git network call authenticates as, so a concurrent `gh auth switch` or an inherited credential can never make a run act as another account.

## Requirements

### Requirement: Every GitHub call of a run is fenced to the run login
Every `gh` call and every git network call to a github.com remote that a Specwright skill or script makes SHALL run through the identity fence for the run login of its repository. The fence SHALL resolve that login's token for the one process, verify it resolves to that login, and stop the step (exit 3) when it cannot. Specwright SHALL never run `gh auth switch`.

#### Scenario: Configured login
- **WHEN** `github.login` is `code-bot`, the active `gh` account is `sh1ny`, and ship pushes and opens the PR
- **THEN** the push and every `gh` call authenticate with `code-bot`'s token, and no call uses `sh1ny`'s

#### Scenario: Token resolves to someone else
- **WHEN** the token `gh` returns for the run login verifies as another account
- **THEN** the fence exits 3 naming both logins, the command does not run, and the step stops without falling back to another account

### Requirement: An empty login is resolved once per run
With no login configured for a repository (`github.login` empty, or `planning_store.login` falling back to it), a run SHALL resolve the active `gh` account once, before its first GitHub call, and use it as the run login for every later call. A run is the chain of workflow steps started by one user request in one session; a step invoked by another step receives the caller's run login and never resolves again, and stops and asks when it cannot find the login it was handed.

#### Scenario: Switch mid-run
- **WHEN** `github.login` is empty, the active account is `sh1ny` when ship starts, and another process runs `gh auth switch` to `other-bot` after the push
- **THEN** the PR is opened and the review requests posted with `sh1ny`'s token, and no call of the run uses `other-bot`'s

#### Scenario: Switch during watch
- **WHEN** `github.login` is empty, ship resolved `sh1ny` and handed off to watch, another process switches to `other-bot`, and watch then runs feedback and archive
- **THEN** replies, thread resolutions, review re-requests and the archive push all use `sh1ny`'s token, and no step resolves the login again

#### Scenario: Handed-off step without its run login
- **WHEN** a step invoked by another step (watch → feedback) cannot find the run login it was handed
- **THEN** it stops before any GitHub call and asks the user, and does not resolve the active account

#### Scenario: No active account in a step that needs GitHub
- **WHEN** `github.login` is empty, `gh` has no logged-in account for github.com, and ship, watch, feedback or finish cleanup starts
- **THEN** the run stops before its first GitHub call with a message naming `gh auth login`, `github.login`, and that `GH_TOKEN`/`GITHUB_TOKEN` are not used to pick the login, and makes no GitHub call

#### Scenario: No gh account in a step that accepts local refs
- **WHEN** `github.login` is empty, `gh` is missing or has no account, and the branch gate refreshes main, or roadmap status reads main
- **THEN** the failed resolution counts as a fence refusal: the step reports `local refs only (no gh account)` and continues on local refs

#### Scenario: Ambient token variables do not choose the login
- **WHEN** `github.login` is empty and `GH_TOKEN` in the environment belongs to `env-bot` while the active account is `sh1ny`
- **THEN** the run login is `sh1ny`, and no call authenticates with `env-bot`'s token

### Requirement: Login fallbacks end at the run login
Every setting that names an account and is empty (`planning_store.login`, `github.review_request.login`, `pr.request_as`) SHALL fall back through its documented chain and, where the chain ends empty, to the run login of that repository. No call SHALL use the active `gh` account unfenced.

#### Scenario: Review requests with every login empty
- **WHEN** `github.login`, `review_request.login` and `pr.request_as` are all empty, the run login resolved to `sh1ny`, and ship posts a review request
- **THEN** the request is posted fenced with `sh1ny`'s token

#### Scenario: Store login empty
- **WHEN** `planning_store.login` and `github.login` are empty and a store-backed change ships
- **THEN** the store push and store PR calls use the code repo's run login, resolved once for the run

#### Scenario: Fallback login has no credential
- **WHEN** `review_request.login` is empty, `pr.request_as` is `sh1ny`, and `gh` has no token for `sh1ny`
- **THEN** posting the request stops with exit 3 naming `sh1ny`, and it is not posted as the run login or the active account instead

#### Scenario: Store reads with both logins empty
- **WHEN** `planning_store.login` and `github.login` are empty, the store's `origin` fetch URL carries a token, and `rounds` reads the store remote
- **THEN** `rounds` exits 3, and no request reaches the store's server

### Requirement: Main refreshes and pulls from GitHub are fenced
The `git fetch` and `git pull` calls a workflow makes against a remote whose fetch URL is on github.com, whatever its push URLs (the branch gate's main refresh, roadmap status, init and close, finish and PR cleanup, and the commands `pr-pair.sh cleanup-plan` emits) SHALL run through the fence with the repository's run login. When the fence refuses, a step that already treats a failed fetch as "local refs only" SHALL report that and continue; any other step SHALL stop.

#### Scenario: Cleanup pull after merge
- **WHEN** a store-backed change's PRs merged and `cleanup-plan` lists each repo's commands
- **THEN** each `git pull --ff-only` command it emits runs through the fence with that repo's login, and none runs as plain `git`

#### Scenario: Branch gate fetch over SSH
- **WHEN** a local-mode project's `origin` is `git@github.com:o/r.git` and the branch gate refreshes main
- **THEN** the fenced fetch is refused, the gate says the check used local refs only, and it continues with local refs

#### Scenario: Origin that pushes to a fork
- **WHEN** `origin` fetches from `https://github.com/o/r.git` and pushes to `https://github.com/o/fork.git`, and the branch gate refreshes main
- **THEN** the fetch runs through the fence with the run login, not with ambient git credentials

#### Scenario: Post-merge pull refused
- **WHEN** finish cleans up after a merged PR and the fenced `git pull --ff-only` exits non-zero
- **THEN** finish stops, deletes no branch, and shows the error

### Requirement: The post-merge PR check is fenced
`specwright-finish` SHALL check whether a branch's PR merged with a fenced call naming the repository, never with an unfenced `gh pr view`.

#### Scenario: Merged PR check with a login set
- **WHEN** `github.login` is `code-bot`, the active account is `sh1ny`, and finish checks the branch's PR state
- **THEN** the check authenticates with `code-bot`'s token and names `--repo <owner>/<name>`

#### Scenario: Check cannot authenticate
- **WHEN** the fence exits 3 during the post-merge check
- **THEN** finish stops and does not treat the PR as merged or unmerged

### Requirement: Credentials in a URL are refused
The fence SHALL refuse a command (exit 3, before the command runs) when a github.com URL git could use has userinfo (a token, a password, or a bare username, which cannot be told apart from a token): a remote's fetch URL or any push URL after `insteadOf`/`pushInsteadOf` rewriting, a rewrite that applies to a github.com URL, or a URL argument. URLs for other hosts are not checked. The message SHALL name the remote and URL kind with the credential masked; no configuration SHALL change.

#### Scenario: Credential-free HTTPS URL
- **WHEN** `origin` is `https://github.com/o/r.git` and a fenced git command asks git's credential system for `https://github.com`
- **THEN** git receives username `x-access-token` and the run login's verified token

#### Scenario: Token in the fetch URL
- **WHEN** `origin`'s fetch URL is `https://x-access-token:tok@github.com/o/r.git` and a fenced `git fetch origin main` runs
- **THEN** the fence exits 3, no request reaches the server, the message masks `tok`, and the remote URL is unchanged

#### Scenario: Token in one of several push URLs
- **WHEN** `origin` has the fetch URL `https://github.com/o/r.git` and two push URLs, the second `https://u:tok@github.com/o/r.git`, and a fenced `git push` runs
- **THEN** the fence exits 3 before any push, naming the second push URL with the token masked

#### Scenario: Credential added by a URL rewrite
- **WHEN** `url.https://u:tok@github.com/.insteadOf` is `https://github.com/` and a fenced `git fetch` runs against `https://github.com/o/r.git`
- **THEN** the fence exits 3 and no request reaches the server

#### Scenario: Token in the username slot
- **WHEN** `origin` is `https://ghp_abc123@github.com/o/r.git` (a token with no `:`) and a fenced `git fetch` runs
- **THEN** the fence exits 3 before any request, with the token masked

#### Scenario: Git pointed at another repository
- **WHEN** a fenced git command passes `-C`, `--git-dir` or `--work-tree` before its subcommand, so it would read another repository's remotes and rules, whatever their URLs
- **THEN** the fence exits 3 before the command runs and says to run it from inside that repository

#### Scenario: Username without a secret
- **WHEN** `origin` is `https://someone@github.com/o/r.git`
- **THEN** the fence exits 3 the same way, since a bare username cannot be told apart from a token, and the message says to remove the userinfo because the fence supplies the credential

#### Scenario: Credential rule for another host
- **WHEN** a global rule `url.https://oauth2:tok@gitlab.com/.insteadOf` is `https://gitlab.com/`, `origin` is `https://github.com/o/r.git`, and a fenced `gh api repos/o/r` and a fenced `git fetch origin main` run
- **THEN** neither is refused, and both authenticate with the run login's verified token

### Requirement: Fenced calls target github.com only
Inside the fence, `gh` SHALL target github.com with the verified token whatever the inherited environment says: inherited `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` SHALL not reach the fenced command or the fence's own identity check.

#### Scenario: Enterprise host in the environment
- **WHEN** the environment has `GH_HOST=enterprise.example` and `GH_ENTERPRISE_TOKEN` belonging to `ent-bot`, and a fenced `gh api repos/o/r` runs as `code-bot`
- **THEN** the call goes to github.com with `code-bot`'s token, and no call goes to `enterprise.example`

#### Scenario: Host variables set but empty
- **WHEN** `GH_HOST` is set to an empty string
- **THEN** fenced calls go to github.com with the verified token, as without it

### Requirement: Non-GitHub remotes stay outside the fence
A git network call to a remote that is not on github.com SHALL run as git normally runs it, unfenced, since no GitHub identity is involved; the PR flow SHALL keep refusing such a remote before publishing.

#### Scenario: Local mode with a self-hosted remote
- **WHEN** `finish: local` and `origin` is `https://git.example.com/o/r.git`, and the branch gate refreshes main
- **THEN** the fetch runs with the user's normal git credentials, and the gate does not report a fence refusal

#### Scenario: PR mode with a non-GitHub origin
- **WHEN** `finish: pr` and `origin` is `https://git.example.com/o/r.git`, and ship starts
- **THEN** ship stops before any push with the `not-github` identity error
