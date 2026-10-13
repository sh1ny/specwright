# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Second re-check:** design.md leftovers a, b and c are fixed; every Required Change is satisfied, and CHANGES_APPLIED is set to yes.
- **Re-check (Required Changes only):** proposal.md, specs/github-identity/spec.md and design.md were re-read after the author applied items 1-6. Items 1, 2, 3, 4 and 6 are satisfied. Item 5 is satisfied in the spec and in D2, but two other places in design.md still describe the old rule; see Re-check outstanding under Required Changes.
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** proposal.md, specs/github-identity/spec.md, design.md; docs/adr/0004-process-scoped-github-identity.md, openspec/architecture.md (diagram, GitHub identity paragraph), openspec/roadmap.md (M2 change 4); skills/specwright-pr/scripts/as.sh, skills/specwright-pr/scripts/pr-pair.sh (`git_net`, `gh`, `token_for`, `read_store_as`, `ambient_login`, `identity`, `remote_contains`, `cleanup-plan`), skills/specwright-pr/SKILL.md, skills/specwright-finish/SKILL.md, skills/specwright-branch/SKILL.md, skills/specwright-roadmap/SKILL.md, skills/specwright-commit/SKILL.md (hand-off), templates/openspec/specwright.yaml, README.md (prerequisites), evals/pr-pair/test_as_sh.py. Skill applied: `github-account-switch-race-fencing` (loaded).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

**C1. The run boundary re-opens the race at every hand-off.** The spec defines a run as "one invocation of a Specwright workflow step (branch gate, ship, watch, feedback, finish, roadmap mode)", and the design (State & Ownership, Flow & State Gaps) has every run resolve the active account again. But the skills chain steps within one session. `specwright-commit` hands off to ship and then watch (`skills/specwright-commit/SKILL.md:49`). Watch runs **feedback** and **ship** (`skills/specwright-pr/SKILL.md` watch step 2, "run **feedback** first", "`ship` → ... run **ship**"). Watch also starts the archive, and `specwright-finish` then ships it (`skills/specwright-pr/SKILL.md:133`, `skills/specwright-finish/SKILL.md:117-118`). Under the spec's definition, each of these is a new run that re-reads the active account. Take a watch that lasts up to 2 hours (`specwright-pr/SKILL.md` watch step 4). If another agent runs `gh auth switch other-bot` during it, the next feedback round posts replies and resolves threads as `other-bot`, and the archive push goes out as `other-bot`. With #15, the merge at the end of watch would too. That is exactly the redirect this change claims to close ("a later `gh auth switch` cannot redirect the run"). The Mechanism Ledger makes it worse. It says a run that loses context "would then resolve again, which is safe", but a mid-chain re-resolution is the race itself, not a safe fallback. The spec has no scenario for a switch between hand-offs, so the proposed regression suite would pass with this hole open.

### Moderate

**M1. Store reads under the code login escape the URL check and the header scrub.** `pr-pair.sh` sends a store network read through `as.sh` only when `REPO_LOGIN` has an entry for the store (`git_net`, `pr-pair.sh:129-140`). `read_store_as` adds that entry only when `planning_store.login` differs from the code login (`:190-194`). When the logins match, `remote_contains` runs `git ls-remote` / `git fetch` in the store as plain `git` (`:1187-1199`), under the outer `as.sh` that was started in the code checkout. D2's URL check, like the existing extraHeader scrub, reads only the repository `as.sh` starts in. `evals/pr-pair/test_as_sh.py:106-110` asserts this for headers ("as.sh only scrubs the repository it starts in"). With this change, both logins empty (the shipped default) resolves both repos to the same run login, so the bypass becomes the default store path. A store `origin` of `https://x:tok@github.com/o/store.git` then authenticates `rounds` / `pass plan` reads as the token's owner. That breaks the spec's "Credentials in a URL are refused" and "Every GitHub call ... fenced to the run login". The design does not mention it.

**M2. Fencing is keyed on `pr-pair.sh identity` succeeding, so a GitHub `mismatch` origin fetches unfenced.** D4 fences a fetch or pull "when the repo's `origin` is on github.com (`pr-pair.sh identity` succeeds), and plain otherwise". `identity` raises `mismatch` when origin fetches from `github.com/o/r` and pushes to `github.com/o/fork` (`pr-pair.sh:408-410`), and both URLs are GitHub. Local mode allows that setup, and so does PR mode before ship. In that case the branch gate's and roadmap's fetch run as plain `git` against github.com with ambient credentials. That contradicts the requirement "Main refreshes and pulls from GitHub are fenced" and the M2 exit criterion "every `gh` and git network call is fenced or refused".

**M3. The spec contradicts itself when `gh` is missing or logged out in a step that accepts local refs.** "No active account" says the run "stops before its first GitHub call". "Main refreshes ..." says a step that treats a failed fetch as "local refs only" reports that and continues. Both apply to a local-mode project with a GitHub HTTPS origin and no `gh`. README:44 makes `gh` a prerequisite of the PR skills only, and `as.sh` exits 3 without it (`as.sh:23-26`). Under the first rule the branch gate, a core local-mode step, now blocks every new change. Under the second it silently loses its reused-name check against `origin/<main>` (`skills/specwright-branch/SKILL.md:17`). Before this change, that fetch worked with anonymous or ambient git credentials. The implementer should not have to choose between these.

**M4. The URL check refuses on credentials that cannot affect a GitHub identity.** D2 checks every remote and every `url.<base>.insteadOf` / `pushInsteadOf` base, whatever the host, for every fenced command, `gh` included. The pinned helper answers only `https://github.com` (`as.sh:57`), so a credential for another host cannot change which GitHub account a call uses. A common global rule such as `url."https://oauth2:<tok>@gitlab.com/".insteadOf "https://gitlab.com/"` (the usual Go private-module setup), or a token-bearing non-GitHub `upstream` remote, would make every fenced command exit 3 in every repo. That includes `gh pr create` and `gh api`. The spec is narrower than the design: it covers "a URL git could use **for it**". The design and the spec should agree, and the check should be scoped to URLs that resolve to github.com.

**M5. GH_TOKEN-only environments break, and the proposal does not list it as breaking.** With `github.login: ""`, an environment that has only `GH_TOKEN` and no stored `gh` login (CI, containers, cloud agents) works today: plain `gh` uses the variable (SKILL.md:46, :50). After this change, `--resolve` unsets `GH_TOKEN` and finds no active account, and the spec scenario "Ambient token variables do not choose the login" makes this deliberate. Every authenticated step in those environments now stops. The proposal marks only the credential-URL refusal as **BREAKING**, so users get no migration note: `gh auth login --with-token`, then set `github.login`.

### Suggestions

**S1. Check `-c` config values in arguments, not just bare URL arguments.** D2 refuses "any command-line argument of that form". The URL check uses `git remote get-url`, which does not see a `-c` passed to the fenced command. So `as.sh <login> git -c url.https://u:tok@github.com/.insteadOf=https://github.com/ fetch` (or `-c remote.origin.pushurl=...`) passes both checks. Match `scheme://user:secret@` inside `-c`/`--config-env`-style values as well.

**S2. Give "Login fallbacks end at the run login" a failure scenario.** For example: `review_request.login` is set but has no stored credential, so the request stops with exit 3 and does not fall back to the run login.

**S3. State in the tasks how the regression suite can reach the helper.** The eval server is `http://127.0.0.1` (`test_as_sh.py:53`), and the helper answers only `https`/`github.com`, so "Credential-free HTTPS URL" and "Username without a secret" cannot be shown through that server. Assert them with `git credential fill` under `as.sh`. Also add GitHub's own embedded-token form, `https://<token>@github.com/...` (the token in the username slot), and assert that git ends up with `x-access-token` and the run login's token.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **(C1)** In the spec, change the run definition in "An empty login is resolved once per run" to: a run is the chain of workflow steps started by one user request in one session. A step invoked by another step (commit→ship, watch→feedback/ship/archive, finish→ship, finish→roadmap offer) receives the caller's run login and never resolves again. Add the scenario "Switch during watch": `github.login` is empty, ship resolved `sh1ny`, another process switches to `other-bot`, and watch then runs feedback; replies, resolutions, re-requests and the archive push all use `sh1ny`. In design.md (State & Ownership, Flow & State Gaps, Mechanism Ledger "Persisted run login file" row), replace "they would then resolve again, which is safe" with: a step that cannot find the run login it was handed stops and asks. Re-resolving is allowed only at the start of a user-started run.
2. **(M1)** In design.md, add the decision that `pr-pair.sh` `git_net` runs every network read of a repo other than the one the process started in through `as.sh <that repo's login>` from inside that repo, with the code run login (`ambient_login()` under the outer fence) when the store login is empty or equal. Add a spec scenario: with both logins empty, a store `origin` that carries a token makes `rounds` exit 3, and no request reaches the server.
3. **(M2)** In design.md D4, decide fencing by whether the remote the command uses has a GitHub fetch URL (`parse_repo` on it), not by `pr-pair.sh identity` succeeding. Add a spec scenario under "Main refreshes": origin fetches `https://github.com/o/r.git` and pushes to `https://github.com/o/fork.git`, and the branch gate's fetch runs fenced.
4. **(M3)** In the spec, state that in a step that accepts local refs (the branch gate, and roadmap status when it falls back), a failed `--resolve` (no `gh`, no account) counts as a fence refusal: the step reports "local refs only (no gh account)" and continues. Add that as a scenario. Restrict "No active account → the run stops" to steps that need GitHub.
5. **(M4)** In the spec requirement "Credentials in a URL are refused" and in design D2, limit the refusal to URLs whose host, after `insteadOf`/`pushInsteadOf` rewriting, is github.com: remote fetch and push URLs, rewrite bases that apply to a github.com URL, and URL arguments. Add a scenario where a credential-bearing `insteadOf` rule for `https://gitlab.com/` does not refuse a fenced `gh api` or a `git fetch` from a github.com origin.
6. **(M5)** In proposal.md What Changes, mark as **BREAKING**: with `github.login` empty, an environment that has only `GH_TOKEN` and no stored `gh` login now stops, and the fix is `gh auth login --with-token` (and optionally setting `github.login`). In the spec's "No active account" scenario, require the message to say that `GH_TOKEN`/`GITHUB_TOKEN` are not used to pick the login.

Re-check outstanding (item 5, plus one item 4 remnant). These are text left over in design.md that now contradicts the normative rule:

- a. URL-check flowchart: the node `any argument scheme://user:secret@?` and the node `any userinfo secret?` still describe the old secret-only rule for any host. Change them to: any github.com URL, `-c` value or rewrite rule with any userinfo.
- b. Risks / Trade-offs, last bullet: "the check covers `scheme://user:secret@` for any scheme" contradicts D2, which refuses any userinfo, a bare username included, on github.com URLs only. Rewrite it to match D2.
- c. Failure & Visibility, row `as.sh --resolve`: it still says only "the run stops". Add that in a step that accepts local refs (branch gate, roadmap status), the step reports `local refs only (no gh account)` and continues, as D1 and the spec now say.

Deviation judged (M4/S3): accepted. D2 and the spec refuse any userinfo on a github.com URL, a bare username included. A token in the username slot cannot be told apart from a username, and the helper supplies the credential either way, so this is fail-closed and consistent with the fence. The cost is that users with `https://<user>@github.com/...` remotes (for example a Git Credential Manager multi-account setup) must edit the remote. The proposal's BREAKING bullet names bare usernames, so that cost is disclosed.

Second re-check: all three leftovers are fixed in design.md. (a) Both URL-check flowchart nodes now ask about github.com URLs, `-c` values and github.com rewrite rules with any userinfo. (b) The last Risks bullet now matches D2: any userinfo on a github.com URL is refused, and other hosts are ignored. (c) The `as.sh --resolve` Failure & Visibility row has the local-refs case for the branch gate and roadmap status. Required Changes 1-6 are still present in proposal.md, the spec and design.md. Every item is satisfied.

CHANGES_APPLIED: yes

## Rebuttals

- C1: fixed. spec "An empty login is resolved once per run" (run = chain of steps one user request starts; hand-off carries the login; "Switch during watch" and "Handed-off step without its run login" scenarios); design D1 hand-off paragraph, State & Ownership, Flow & State Gaps, Mechanism Ledger.
- M1: fixed. design D6; spec scenario "Store reads with both logins empty".
- M2: fixed. design D4 (fetch URL parsed, not `identity`); spec scenario "Origin that pushes to a fork" and requirement text "fetch URL is on github.com, whatever its push URLs".
- M3: fixed. spec "No active account in a step that needs GitHub" and "No gh account in a step that accepts local refs"; design D1 last paragraph.
- M4: fixed. Refusal limited to github.com URLs and rules (spec requirement text, design D2); scenario "Credential rule for another host". Stricter than requested: any userinfo on a github.com URL is refused, including a bare username, since it cannot be told apart from a token (S3 token-in-username case); scenario "Username without a secret" now refuses.
- M5: fixed. proposal BREAKING bullet; "No active account" scenario message names `GH_TOKEN`/`GITHUB_TOKEN`.
- S1: fixed. design D2 checks `-c key=value` argument values.
- S2: fixed. spec scenario "Fallback login has no credential".
- S3: taken into tasks (`git credential fill` under `as.sh` for helper cases); token-in-username scenario added.

Reviewer re-check of the rebuttals: C1, M1, M2, M3 (normative text; see c above for the leftover row), M5, S1 and S2 are fixed and accepted by reviewer. M4 is accepted by reviewer, including its stricter bare-username rule, pending a and b above. S3 is accepted (it is deferred to tasks).

Second re-check: M4 is fully accepted by reviewer, and so is the leftover row from M3 (c). No findings remain open.
