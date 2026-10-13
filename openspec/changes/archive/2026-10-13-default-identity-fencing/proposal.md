# Proposal

## Why

ADR 0004 fences authenticated GitHub work to one account per process, but the shipped default (`github.login: ""`) skips the fence entirely: pushes, PRs and replies go through whichever account `gh` has active, so another agent's `gh auth switch` can redirect them mid-run. #38 also tracks the places that escape the fence even with a login set: `specwright-finish`'s post-merge `gh pr view`, `git fetch`/`git pull` on main, credentials embedded in a remote URL, and inherited `GH_HOST`/enterprise token variables. The opt-in agent merge (M2 change 5, #15) will merge PRs as the fenced account, so the fence has to hold by default before it lands.

This is M2 (Ship flow) change 4, released as 0.3.0. It advances the exit criteria "With `github.login` empty, the #38 regression cases prove every `gh` and git network call is fenced or refused", "each code fix has a regression test in `evals/pr-pair` or `evals/git-workflow`" and "each change ships as its own release". Constrained by ADR 0004 (process-scoped GitHub identity), which this change supersedes, ADR 0002 (agent instructions with thin scripts) and ADR 0003 (git and GitHub as the state store).

## What Changes

- **Fence by default.** With `github.login` empty, a run resolves the active `gh` account once, at its start, and fences every later call to that login with `as.sh`, so a later `gh auth switch` cannot redirect the run (#38 option 2). A run is the chain of steps one user request starts, so the run login is handed from ship to watch, feedback, archive and finish, never re-resolved. Every login fallback (`planning_store.login`, `review_request.login`, `pr.request_as`) that ended at "the ambient account" ends at that resolved login instead. Plain unfenced `gh` disappears from the skill text.
- **BREAKING:** with `github.login` empty, an environment that has only `GH_TOKEN` and no stored `gh` login (CI, containers, cloud agents) now stops before its first GitHub call, since environment tokens never pick the login. Fix: `gh auth login --with-token`, and optionally set `github.login`.
- **Close the fence escapes #38 tracks:**
  - `specwright-finish`'s post-merge `gh pr view` runs fenced.
  - `git fetch` and `git pull` against a GitHub remote run fenced: the branch gate's main refresh, roadmap status/init/close, finish cleanup, `specwright-pr` cleanup, and the `git pull --ff-only` commands `pr-pair.sh cleanup-plan` emits.
  - **BREAKING:** `as.sh` refuses (exit 3) when any github.com URL git could use has userinfo (a token, password or bare username in a remote's fetch or push URL after `insteadOf`/`pushInsteadOf` rewriting, a rewrite rule for github.com, or a URL argument), since git would use it before asking the pinned helper. Other hosts are not checked. Users fix the remote URL; nothing is rewritten for them.
  - `as.sh` unsets `GH_HOST`, `GH_ENTERPRISE_TOKEN` and `GITHUB_ENTERPRISE_TOKEN`, so every fenced call targets github.com with the verified token.
- **Regression coverage** in `evals/pr-pair` and `evals/git-workflow` for each case: the empty login (resolve-once, then a switch mid-run), the post-merge check, each fetch/pull site, credential-free HTTPS URLs, credential-bearing fetch and push URLs, several push URLs, URL rewrites, and two hosts with different identities.
- **Docs and settings:** the template comment for `github.login` and the README describe the default fence; ADR 0008 supersedes ADR 0004 and removes its documented exceptions.
- Release 0.3.0.

Out of scope: non-GitHub remotes (local mode only; no GitHub identity is involved, so their git calls stay as they are), SSH support inside the fence (still disabled, as ADR 0004 decided), and the agent merge itself (#15).

## Capabilities

### New Capabilities
- `github-identity`: which GitHub account every Specwright `gh` call and GitHub git network call authenticates as, how the run resolves it when no login is configured, and what the fence refuses (credential-bearing URLs, other hosts).

### Modified Capabilities
<!-- None: the identity rules have lived only in ADR 0004 and skill text; no existing spec owns them. -->

## Impact

- `skills/specwright-pr/scripts/as.sh` (resolve mode, credential-URL refusal, host variables), `skills/specwright-pr/scripts/pr-pair.sh` (`cleanup-plan` emits fenced pulls; its internal store fence unsets the same host variables).
- Skill text: `specwright-pr`, `specwright-finish`, `specwright-branch`, `specwright-roadmap` (identity paragraphs and every fetch/pull/`gh` call site).
- `templates/openspec/specwright.yaml`, `README.md`, `VERSION`, `docs/adr/0008-*.md` (supersedes 0004), `openspec/architecture.md` ADR index.
- Evals: `evals/pr-pair/test_as_sh.py`, `test_pr_pair.py`, `test_skill_text.py`; `evals/git-workflow/test_instructions.py`.
- Behaviour for users: a local-mode project with an SSH GitHub origin sees the branch gate's fetch refused inside the fence and falls back to local refs with its existing notice; a project whose remote URL embeds a token must remove it before shipping.
