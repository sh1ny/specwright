# Spec Delta

## ADDED Requirements

### Requirement: GitHub connection settings keep the fenced public default
`github.host` SHALL name the GitHub hostname for the project and its planning store, default `github.com`. `github.fence` SHALL be a boolean, default `true`. An invalid connection setting SHALL stop the operation that uses it before network access or publication, naming the key. Neither setting SHALL change Git or GitHub CLI configuration on disk.

#### Scenario: Existing settings
- **WHEN** neither new key is set and ship uses a github.com HTTPS remote
- **THEN** it uses the stored and verified run credential for github.com, and SSH remains disabled within the fence

#### Scenario: Invalid host or fence value
- **WHEN** `github.host` contains a URL rather than a hostname, or `github.fence` is not a boolean
- **THEN** the command that needs GitHub stops naming the invalid key before starting GitHub network access or publishing

### Requirement: Ambient authentication is an explicit opt-out
With `github.fence: false`, Specwright SHALL use the caller's Git and `gh` credentials without stored-account lookup or fence transport overrides. It SHALL still target the configured GitHub host and explicit repository for PRs and releases. Named account and review-poster settings SHALL stop the workflow before publication, naming the key and telling the user to remove it or re-enable fencing. A fenced failure SHALL NOT fall back to ambient authentication.

#### Scenario: SSH transport and an environment token only
- **WHEN** `github.fence: false`, the selected remote uses SSH, the caller has a working SSH key and `gh` has only the environment token for the configured host
- **THEN** Git fetch and push can use the SSH key and the PR can be opened and watched with the environment token, without `gh auth token --user` or `gh auth login`

#### Scenario: Token-only HTTPS automation
- **WHEN** `github.fence: false`, Git's HTTPS credentials are already configured and `gh` has an environment token but no stored account
- **THEN** ship uses those credentials and makes no attempt to resolve a stored account

#### Scenario: A named identity conflicts with ambient authentication
- **WHEN** `github.fence: false` and `github.login`, `planning_store.login`, `github.review_request.login` or `pr.request_as` names an account
- **THEN** the GitHub workflow stops before network access, names the conflicting setting and says to remove it or re-enable fencing; no request is posted as an unintended account

#### Scenario: SSH remains disabled by the default fence
- **WHEN** the selected remote uses SSH and `github.fence` is omitted
- **THEN** a GitHub push cannot use ambient SSH credentials and ship reports the fence or transport refusal instead of bypassing it

### Requirement: Fenced calls target the configured GitHub host
Fenced discovery, identity verification and repository operations SHALL use `github.host`. The fence SHALL ignore caller host and token overrides and supply the verified token in the variable `gh` uses for that host. Its Git credential helper SHALL supply that token only for HTTPS to the configured host. Caller-supplied host or token variables SHALL NOT redirect fenced operations.

#### Scenario: Enterprise host in the environment with default settings
- **WHEN** the environment has `GH_HOST=github.example.com` and `GH_ENTERPRISE_TOKEN` belonging to another account, and a fenced call runs with the default settings
- **THEN** the call goes to github.com with the verified github.com token, and no call targets `github.example.com`

#### Scenario: Host variables set but empty
- **WHEN** `GH_HOST` is set to an empty string
- **THEN** the configured GitHub host remains the target, exactly as when `GH_HOST` is unset

#### Scenario: Fenced Enterprise ship and watch
- **WHEN** `github.host: github.example.com`, the selected remote is an HTTPS URL on that host, and a different `GH_HOST` or token is inherited
- **THEN** stored-token lookup, identity verification, PR creation and watch target `github.example.com`; Git uses the verified token for that host and the inherited token is not used

#### Scenario: Another host requests the credential
- **WHEN** a fenced Git credential request names a different host or a non-HTTPS protocol
- **THEN** the helper gives it no credential

### Requirement: Push authentication follows the actual destinations
With fencing enabled, a VCS push SHALL inspect every effective push URL in the Git environment it will launch, including indexed rewrites. Exclusively on-host pushes SHALL be fenced and exclusively off-host pushes plain. Failed reads, mixed host classes, or a change between preflight and execution targets SHALL stop before push. A PR workflow SHALL stop when the actual Git destination and expected PR repository differ. A fence refusal SHALL NOT retry unfenced.

#### Scenario: A non-GitHub fetch URL has a GitHub push URL
- **WHEN** the selected remote fetches from an internal Git mirror but the effective push URLs all target the configured GitHub host
- **THEN** the VCS push uses that host's verified identity, and a fence refusal launches no push

#### Scenario: GitHub fetch and non-GitHub push
- **WHEN** the selected remote fetches from the configured GitHub host but every effective push URL is elsewhere
- **THEN** the VCS push uses the caller's Git credentials without querying a stored GitHub account

#### Scenario: Push destinations need incompatible authentication
- **WHEN** a fenced-mode VCS push would use both GitHub and non-GitHub push URLs, or the effective push URLs cannot be read
- **THEN** the push stops before launch and reports the remote and reason without printing secrets

#### Scenario: Indexed URL rewrites survive fenced publication
- **WHEN** an indexed `insteadOf` or `pushInsteadOf` rule makes the selected remote's fetch and push agree on another GitHub repository without using a URL credential
- **THEN** a fenced ship pushes to that repository and opens its PR there, never writing a ref to another repository or retaining any indexed authentication override

#### Scenario: Launched Git would differ from the PR plan
- **WHEN** the expected PR target is one repository but the effective destination under fenced dispatch config differs, or cannot be confirmed
- **THEN** the workflow refuses before launching the push, leaves both remote refs unchanged, and opens no PR

## MODIFIED Requirements

### Requirement: Every GitHub call of a run is fenced to the run login
With fencing enabled, every `gh` call and every Git network call to the configured GitHub host that a Specwright workflow makes SHALL run under the repository's fenced run login. The fence SHALL resolve that login's token for the one process, verify it resolves to that login, and stop the step (exit 3) when it cannot. Specwright SHALL never run `gh auth switch`, including when fencing is disabled.

#### Scenario: Configured login
- **WHEN** fencing is enabled, `github.login` is `code-bot`, the active `gh` account is `other-user`, and ship pushes and opens the PR
- **THEN** the push and every `gh` call authenticate with `code-bot`'s token, and no call uses `other-user`'s

#### Scenario: Token resolves to someone else
- **WHEN** the token `gh` returns for the run login verifies as another account
- **THEN** the fence exits 3 naming both logins, the command does not run, and the step stops without falling back to another account

### Requirement: An empty login is resolved once per run
With fencing enabled, a user-started run SHALL bind its configured login or resolve the active `gh` account on the configured host once, before its first GitHub call. A step invoked by another step SHALL receive that bound login or an explicit deferred-first-lookup handoff from the same run. An absent handoff SHALL stop before any GitHub call; it SHALL NOT choose an account from settings or the active session. Ambient mode SHALL NOT perform a stored-account lookup.

#### Scenario: Switch mid-run
- **WHEN** `github.login` is empty, the active account is `first-user` when ship starts, and another process switches to `other-bot` after the push
- **THEN** the PR is opened and the review requests posted with `first-user`'s token, and no call of the run uses `other-bot`'s

#### Scenario: Switch during watch
- **WHEN** `github.login` is empty, ship resolved `first-user` and handed off to watch, another process switches to `other-bot`, and watch then runs feedback and archive
- **THEN** replies, thread resolutions, review re-requests and the archive push all use `first-user`'s token, and no step resolves the login again

#### Scenario: Handed-off step without its run login
- **WHEN** a fenced step invoked by another step receives neither a bound run login nor an explicit deferred first lookup, and both a configured and an active account are available
- **THEN** it reports the missing handoff before any GitHub call and uses neither account

#### Scenario: Deferred first login is handed to ship
- **WHEN** a user-started run hands permission for its first GitHub lookup to ship, which first inspects the local code and store, and discovery is needed
- **THEN** ship binds the configured account or resolves the active account once and hands the bound login, not deferred permission, to later steps

#### Scenario: No active account in a step that needs GitHub
- **WHEN** local inspection establishes a required GitHub operation, fencing is enabled, `github.login` is empty and `gh` has no logged-in account on the configured host
- **THEN** the run stops before PR discovery or publication, naming the configured host, `gh auth login`, `github.login`, and that environment tokens do not pick the fenced login; local inspection is allowed

#### Scenario: No gh account in a step that accepts local refs
- **WHEN** the fence is enabled, `github.login` is empty, `gh` is missing or has no account, and the branch gate refreshes main or roadmap status reads main
- **THEN** the failed resolution counts as a fence refusal: the step reports `local refs only (no gh account)` and continues on local refs

#### Scenario: Ambient token variables do not choose the login
- **WHEN** `github.login` is empty and the inherited token for the configured host belongs to `env-bot` but its active `gh` account is `first-user`
- **THEN** the run login is `first-user`, and no fenced call authenticates with `env-bot`'s token

### Requirement: Login fallbacks end at the run login
With fencing enabled, every empty account setting (`planning_store.login`, `github.review_request.login`, `pr.request_as`) SHALL fall back through its documented chain and, where the chain ends empty, to the repository's run login. No fenced workflow call SHALL use the active `gh` account unfenced.

#### Scenario: Review requests with every login empty
- **WHEN** `github.login`, `review_request.login` and `pr.request_as` are all empty and the run login resolved to `first-user`
- **THEN** ship posts the review request fenced with `first-user`'s token

#### Scenario: Feedback uses the login already bound for each repo
- **WHEN** a fenced feedback pass is handed a run login different from `github.login`, the store has its own login, and neither role has a review poster override
- **THEN** the pass plans and deduplicates requests using the handed-off login for code and the bound store login for the store

#### Scenario: Store login empty
- **WHEN** `planning_store.login` and `github.login` are empty and a store-backed change ships fenced
- **THEN** the store push and store PR calls use the code repo's run login, resolved once for the run

#### Scenario: Fallback login has no credential
- **WHEN** `review_request.login` is empty, `pr.request_as` is `review-user`, and `gh` has no token for that user
- **THEN** posting the request stops with exit 3 naming that user, and it is not posted as the run login or the active account instead

#### Scenario: Store reads with both logins empty
- **WHEN** `planning_store.login` and `github.login` are empty, the selected store remote's fetch URL on the configured GitHub host carries a token, and a fenced VCS fetch runs for the store
- **THEN** the fence refuses the fetch, and no request reaches the store's server

### Requirement: Main refreshes and pulls from GitHub are fenced
With fencing enabled, a workflow's `git fetch` and `git pull` SHALL be fenced using the fetch URL of the remote the command actually uses, whatever its push URLs. An omitted-setting Git pull SHALL keep Git's upstream selection and classify that transport. When the fence refuses, a step that accepts local refs SHALL report that and continue; any other step SHALL stop.

#### Scenario: Cleanup pull after merge
- **WHEN** a store-backed change's PRs merged and `cleanup-plan` lists each repo's commands with fencing enabled
- **THEN** a planned pull uses the explicit remote or Git's default upstream as appropriate and applies the fence to the actual GitHub target with that repo's login

#### Scenario: Branch gate fetch over SSH
- **WHEN** a project's selected remote is `git@github.com:team/app.git` and the branch gate refreshes main with the default fence
- **THEN** the fenced fetch is refused, the gate says the check used local refs only, and it continues with local refs

#### Scenario: Origin that pushes to a fork
- **WHEN** the selected remote fetches from `https://github.com/team/app.git` and pushes to `https://github.com/other/app.git`, and the branch gate refreshes main
- **THEN** the fetch runs through the fence with the run login, not with ambient Git credentials

#### Scenario: Post-merge pull refused
- **WHEN** finish cleans up after a merged PR and the fenced pull exits non-zero
- **THEN** finish stops, deletes no branch, and shows the error

#### Scenario: The legacy upstream is on the configured GitHub host
- **WHEN** the remote setting is omitted, `origin` is not on GitHub, and the branch's upstream is on the configured GitHub host
- **THEN** `git pull --ff-only` is fenced with that host's verified token; if the fence refuses, no pull launches and Git uses no ambient credential

#### Scenario: The legacy upstream is not on the configured GitHub host
- **WHEN** the remote setting is omitted, `origin` is on GitHub and the branch's upstream is on another host
- **THEN** `git pull --ff-only` uses the caller's Git credentials and performs no stored GitHub credential lookup

### Requirement: The post-merge PR check is fenced
`specwright-finish` SHALL check whether a branch's PR merged by naming the GitHub host and repository under the project's GitHub identity policy. With fencing enabled it SHALL NOT use an unfenced `gh pr view`.

#### Scenario: Merged PR check with a login set
- **WHEN** fencing is enabled, `github.login` is `code-bot`, the active account is `other-user`, and finish checks the branch's PR state
- **THEN** the check authenticates with `code-bot`'s token and names the selected repository

#### Scenario: Check cannot authenticate
- **WHEN** the authenticated post-merge check fails
- **THEN** finish stops and does not treat the PR as merged or unmerged

### Requirement: Credentials in a URL are refused
The fence SHALL refuse a command (exit 3) when a URL of the configured GitHub host that Git could use has userinfo: a fetch or push URL after rewriting, a rewrite that applies to a URL on that host, or a URL argument. URLs for other hosts are not fenced. The message SHALL name the remote and URL kind with the userinfo masked; no configuration SHALL change.

#### Scenario: Credential-free HTTPS URL
- **WHEN** the selected remote is `https://github.example.com/team/app.git`, `github.host` is `github.example.com`, and a fenced operation requests that host's HTTPS credentials
- **THEN** Git receives username `x-access-token` and the run login's verified Enterprise token

#### Scenario: Token in the fetch URL
- **WHEN** the selected remote's fetch URL is `https://x-access-token:tok@github.com/team/app.git` and a fenced fetch runs
- **THEN** the fence exits 3, no request reaches the server, the message masks `tok`, and the remote URL is unchanged

#### Scenario: Token in one of several push URLs
- **WHEN** a selected remote has a safe fetch URL and two push URLs, the second `https://u:tok@github.com/team/app.git`, and a fenced push runs
- **THEN** the fence exits 3 before any push, naming the second push URL with the token masked

#### Scenario: Credential added by a URL rewrite
- **WHEN** a rewrite for `https://github.example.com/` adds userinfo and the configured GitHub host is `github.example.com`
- **THEN** the fence exits 3 before the fetch and no request reaches the server

#### Scenario: Token in the username slot
- **WHEN** the selected remote is `https://token@github.com/team/app.git` and a fenced fetch runs
- **THEN** the fence exits 3 before any request, with the token masked

#### Scenario: Git pointed at another repository
- **WHEN** a fenced Git command passes `-C`, `--git-dir` or `--work-tree` before its subcommand, so it would read another repository's remotes and rules
- **THEN** the fence exits 3 before the command runs and says to run it from inside that repository

#### Scenario: Username without a secret
- **WHEN** the selected remote is `https://someone@github.com/team/app.git`
- **THEN** the fence exits 3 because a bare username cannot be told apart from a token, and the message says to remove the userinfo because the fence supplies the credential

#### Scenario: Credential rule for another host
- **WHEN** a global rewrite adds userinfo to `https://git.example.com/` and the selected remote and configured host are on github.com
- **THEN** the fence does not refuse the unrelated rule, and `gh` and Git still authenticate with the verified github.com token

### Requirement: Non-GitHub remotes stay outside the fence
A Git network call to a remote not on the configured GitHub host SHALL use normal Git credentials. The PR flow SHALL NOT publish to a remote that is not on the configured GitHub host.

#### Scenario: Local mode with a self-hosted remote
- **WHEN** `finish: local`, `github.host` is unset and the selected remote is `https://git.example.com/team/app.git`
- **THEN** the branch gate's fetch runs with normal Git credentials, and the gate does not report a fence refusal

#### Scenario: PR mode with a non-GitHub origin
- **WHEN** a code PR is required and the selected code remote's host is not the configured GitHub host
- **THEN** ship stops before any push with the `not-github` identity error

### Requirement: The trailing-dot host is github.com
The fence, credential helper and PR identity checks SHALL match the configured host case-insensitively and treat a final DNS dot as equivalent. A host prefixed by the configured name but with additional DNS labels SHALL NOT match. The existing `ssh.github.com` transport alias SHALL remain valid when `github.com` is configured.

#### Scenario: Token in a trailing-dot URL
- **WHEN** the selected remote is `https://user:tok@github.com./team/app.git` with the default host and a fenced fetch runs
- **THEN** the fence exits 3 before any request, the message masks `tok`, and the remote URL is unchanged

#### Scenario: Trailing-dot URL argument or rewrite
- **WHEN** a fenced Git command gets a URL argument with userinfo and host `GitHub.Example.COM.` or a rewrite adding that URL, and the configured host is `github.example.com`
- **THEN** the fence exits 3 before the command runs

#### Scenario: Credential-free trailing-dot URL
- **WHEN** a fenced Git command asks for the HTTPS credentials of `github.example.com.` with `github.host: github.example.com`
- **THEN** Git receives username `x-access-token` and the verified token for that host

#### Scenario: Look-alike host
- **WHEN** the credential helper is asked for `github.com.example.org`, or a remote with userinfo is on that host, and the configured host is github.com
- **THEN** the helper gives no credential, and the URL is not refused as a github.com URL

#### Scenario: Trailing-dot store remote
- **WHEN** a store's fetch URL is `https://github.com./team/plans.git` and a fenced `sw pr` operation reads it
- **THEN** the store read is fenced as a GitHub remote, never with the caller's unfenced Git

### Requirement: Unfenced git keeps the caller's enterprise host settings
When a fenced workflow runs plain Git against a remote that is not on the configured GitHub host, Git SHALL see the caller's original `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` values or their original absence. Fenced commands and identity checks SHALL see only the fence's host and credential environment.

#### Scenario: Enterprise store read by rounds
- **WHEN** the local-only PR workflow reaches `rounds` for a store on `github.example.com` under the default github.com host
- **THEN** it reports the manual handoff; `rounds` does not read that store or invoke its credential helper

#### Scenario: Explicit fetch for another host
- **WHEN** the caller has `GH_HOST=github.example.com` and `GH_ENTERPRISE_TOKEN`, the selected remote is on that host, the Git helper is `gh auth git-credential`, and a VCS fetch explicitly targets that remote under the default github.com fence
- **THEN** the plain Git call sees the caller's original host and token settings and the fetch succeeds

#### Scenario: Variables were unset
- **WHEN** the caller had none of the three variables and a VCS fetch targets a remote outside the configured GitHub host
- **THEN** Git runs without those variables and nothing is left from the fence

#### Scenario: Fenced calls stay on github.com
- **WHEN** the caller has `GH_HOST=github.example.com` and `GH_ENTERPRISE_TOKEN`, and the run fences `gh` and a github.com fetch with the default host
- **THEN** neither call receives the caller's host or Enterprise token settings and both use the verified github.com credential

### Requirement: jj network commands are fenced like git
With fencing enabled, `jj git fetch` SHALL use the fence when the effective fetch URL is on the configured GitHub host. `jj git push` SHALL use the same effective push-destination policy as Git. The fence pins an HTTPS token, disables SSH and prompts, and SHALL refuse a jj command selecting another repository or config (`-R`, `--repository`, `--config`, `--config-file`), with exit 3.

#### Scenario: Push on jj
- **WHEN** the effective push URLs target the configured GitHub host, `github.login` is `code-bot`, and the active `gh` account is `other-user`
- **THEN** the push uses `code-bot`'s token, and no call uses `other-user`'s

#### Scenario: Repository option
- **WHEN** the fence is asked to run `jj -R ../other git push`
- **THEN** it exits 3 saying the option selects another repository, and nothing runs

#### Scenario: Config override
- **WHEN** the fence is asked to run `jj --config git.executable-path=/tmp/x git fetch`
- **THEN** it exits 3, and nothing runs

#### Scenario: Other jj subcommand
- **WHEN** the fence is asked to run `jj bookmark set feat/x -r @-`
- **THEN** it exits 3 saying only `jj git push` and `jj git fetch` are fenced, and nothing runs

### Requirement: GitButler pulls are fenced like git
With fencing enabled, `but pull` against a remote whose fetch URL is on the configured GitHub host SHALL use the same fenced transport as Git. The fence SHALL refuse every other `but` subcommand and any `but` option that selects another directory or repository (`-C`, `--current-dir`), with exit 3.

#### Scenario: Cleanup pull
- **WHEN** `github.login` is `code-bot`, the active `gh` account is `other-user`, and cleanup runs a fenced `but pull` in a GitButler repo
- **THEN** the fetch uses `code-bot`'s token, and no call uses `other-user`'s

#### Scenario: Other `but` subcommand
- **WHEN** the fence is asked to run `but push feat/x`
- **THEN** it exits 3 saying only `but pull` is fenced, and nothing runs

#### Scenario: Directory option
- **WHEN** the fence is asked to run `but -C ../other pull`
- **THEN** it exits 3 saying the option selects another directory or repository, and nothing runs

### Requirement: The fence runs in the project's sw
`sw as` SHALL be the only identity fence and SHALL run after the project's version check. A leading `--project <code-checkout>` SHALL select the project whose `VERSION` and GitHub settings are read; it SHALL NOT change the working directory, target repository, login or stdin. `sw as --resolve` SHALL run the same way. There SHALL be no fallback fence implementation.

#### Scenario: Fenced gh call with a matching sw
- **WHEN** the checked version and running `sw` match, `code-bot` has a stored GitHub credential and `<sw> as code-bot gh api user --jq .login` runs inside the project
- **THEN** stdout is `code-bot`, the exit status is 0, and `gh` saw that login's verified token

#### Scenario: Resolve through sw
- **WHEN** the active account on the configured host is `code-bot` and the checked project version matches
- **THEN** `<sw> as --resolve` prints exactly `code-bot` and a newline, with exit status 0

#### Scenario: A refusal keeps its exit status
- **WHEN** `<sw> as code-bot git push` runs in a repository whose selected GitHub push URL contains a token
- **THEN** the exit status is 3, stderr names the remote with userinfo masked as `***`, and `git push` did not run

#### Scenario: Fenced store call selects the code project
- **WHEN** a store with no `VERSION` starts `<sw> --project <code> as store-bot git credential fill` with caller input and the code project uses a configured Enterprise host
- **THEN** the command starts inside the store, receives the same input, and uses `store-bot`'s credential for the code project's configured host

#### Scenario: Selected project does not change target validation
- **WHEN** the selected code project has safe remotes but the caller's store has a URL on the configured GitHub host containing credentials
- **THEN** the fence refuses before the command runs, naming the store remote with credentials masked

#### Scenario: Resolve in a project of another version
- **WHEN** the project's `VERSION` differs from the running `sw` and `<sw> as --resolve` runs
- **THEN** the exit status is 1, not 3, stdout holds the `sw_mismatch` document and never a login, and no `gh` call ran

#### Scenario: Missing selected binary refuses without fallback
- **WHEN** `<sw> --project <code> as code-bot gh api user` names a project whose `VERSION` differs from the running `sw`, while the current directory's project matches and another `sw` is on `PATH`
- **THEN** stdout holds the `sw_mismatch` document, the exit status is 1, no identity lookup or command ran, and no other binary was used

#### Scenario: Malformed fence project prefix is refused
- **WHEN** the leading `--project` has no value or an empty value before `as`
- **THEN** `sw` exits 2 with a usage error before any credential lookup or command execution

### Requirement: sw as keeps as.sh's contract
With default connection settings, `sw as` SHALL keep its usual refusals, messages, exit codes, environment rules, saved `AS_SH_ORIG_*` values, Git transport settings and credential helper. Its own `gh` lookups SHALL keep their deadline and size bound, report `deadline_exceeded` or `response_too_large` with exit 3, and hold the token only in memory.

#### Scenario: Unchanged black-box evals pass on sw
- **WHEN** default-settings fence and backend evals run on Linux, Windows and macOS
- **THEN** their existing stdout, stderr and exit-status assertions pass without requiring any new connection setting

#### Scenario: Exit codes
- **WHEN** `<sw> as` runs with no arguments, with a login and no command, with `--resolve x`, and with a userinfo push URL
- **THEN** the exit statuses are 1, 2, 2 and 3 respectively

#### Scenario: A hung token lookup
- **WHEN** `gh auth token --user code-bot` does not answer before the deadline
- **THEN** `<sw> as code-bot gh api user` exits 3 with `as.sh: deadline_exceeded: gh auth token --user code-bot` on stderr, and the fenced command did not run

#### Scenario: A nested fence keeps the outer originals
- **WHEN** `GH_HOST=github.example.com` is set and `<sw> as code-bot <sw> as code-bot env` runs with the default host
- **THEN** the inner command's environment has `AS_SH_ORIG_GH_HOST=github.example.com` and no `GH_HOST`

## REMOVED Requirements

### Requirement: Fenced calls target github.com only
**Reason:** The fence now targets the explicitly configured GitHub host.
**Migration:** Leave `github.host` unset to retain the original github.com fence, or set the hostname and provision a stored `gh` credential on that host.
