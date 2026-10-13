# 0008. Fenced GitHub identity by default

- Status: accepted
- Date: 2026-10-12
- Supersedes: 0004

## Context
ADR 0004 fenced authenticated GitHub work to one verified login per process, but only when a login was configured. The shipped default (`github.login: ""`) used the active `gh` account unfenced, so another agent's `gh auth switch` could redirect a run's pushes, PR comments and replies mid-flight. 0004 also listed escapes that applied even with a login set (#38): `specwright-finish`'s post-merge `gh pr view`, `git fetch` and `git pull` on main, credentials embedded in a remote URL (git uses them before asking the pinned helper), and inherited `GH_HOST` and enterprise token variables. The opt-in agent merge (#15) will merge PRs as the fenced account, so the fence has to hold by default first.

## Decision
Every `gh` call and every git network call to a github.com remote that a Specwright skill or script makes runs through `as.sh <run login>`. Specwright never runs `gh auth switch`.

- **Run login.** A configured login (`github.login`, `planning_store.login` for the store) is the run login. With none, the first user-started step of a run calls `as.sh --resolve`, which reads the active github.com account with the token and host variables unset, confirms `gh` has a stored token for it and prints it. A run is the chain of steps one user request starts in one session. Each hand-off names the run login (commit → ship, ship → watch, watch → feedback / ship / archive, archive → finish → ship, finish → the roadmap offer), and the receiving step uses it without resolving again. A handed-off step that cannot find its run login stops and asks. Each fenced call still looks up the login's own token, so a later `gh auth switch` changes nothing for the run. Login fallbacks (`planning_store.login`, `review_request.login`, `pr.request_as`) that ended at the ambient account end at the run login, fenced.
- **Environment tokens never pick the login.** `GH_TOKEN` and `GITHUB_TOKEN` are ignored by `--resolve`. An environment with only `GH_TOKEN` and no stored `gh` login stops; the fix is `gh auth login --with-token`.
- **Steps that accept local refs.** In the branch gate and roadmap status, a failed `--resolve` or a refused fetch counts as a fence refusal: the step reports local refs only and continues. Every other step stops.
- **git network calls to GitHub are fenced.** `git fetch` and `git pull` run through `as.sh` when the fetch URL of the remote they use is on github.com, whatever its push URLs; `pr-pair.sh cleanup-plan` emits fenced pulls. `pr-pair.sh` runs every network read of a repository other than the one it started in through `as.sh <that repo's login>` from inside that repository, so the checks below cover the store too. The post-merge PR check is fenced and names the repository.
- **Userinfo on github.com URLs is refused.** Before running anything, `as.sh` exits 3 when a github.com URL git could use has userinfo: a remote's fetch or push URL after `insteadOf`/`pushInsteadOf` rewriting, a rewrite rule that applies to a github.com URL, a github.com URL argument or a `-c` value. A bare username is refused too, since it cannot be told apart from a token, and the fence supplies the credential. The message names the remote and kind with the userinfo masked. Nothing is rewritten.
- **gh is pinned to github.com.** `as.sh` and `pr-pair.sh`'s token lookup unset `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN` with `GH_TOKEN`/`GITHUB_TOKEN`.
- **Other hosts stay outside.** git network calls to a remote not on github.com run as git normally runs them, and URLs for other hosts are not checked: the pinned helper never answers them, so no GitHub identity is involved. SSH stays disabled inside the fence, as 0004 decided.

**Rejected: require a configured login.** Refusing authenticated work until `github.login` is set breaks every default install on its first ship, for a race that resolving once per run already removes.

**Rejected: persist the resolved login in a file.** It adds persistent state with its own staleness and a second writer (two sessions in one checkout), while the run already carries its other per-run values in context.

**Rejected: strip credentials from URLs.** Command-scoped config adds to the multi-valued `remote.<r>.pushurl` instead of replacing it, so a stripped override would push to both URLs, and silently changing a remote hides the misconfiguration.

**Rejected: fence every git network call regardless of host.** `as.sh` drops inherited credential helpers, so a self-hosted remote would lose its credentials with no GitHub identity to protect.

**Reversal cost: low.** `as.sh` is one wrapper with one new mode and a pre-exec check; the skills carry one identity paragraph each.

## Consequences
- Requires `gh` 2.40 or later for every authenticated step, also with an empty `github.login`. Local mode keeps working without `gh`: the branch gate and roadmap status fall back to local refs.
- A remote URL with userinfo on github.com must be edited before any fenced command runs in that repository (breaking in 0.3.0).
- A project with an SSH GitHub origin loses the branch gate's main refresh, which falls back to local refs.
- A new user request in a later session resolves again; users who switch accounts between sessions set `github.login`.
