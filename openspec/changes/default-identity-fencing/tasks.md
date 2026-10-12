# Tasks

## Test map

Script behaviour is tested against the fake `gh` (`evals/fakes/gh.py`, installed by `fixtures.install_fake_gh`) and real `git`. `evals/pr-pair/test_as_sh.py` covers `as.sh`; it records the requests git makes to a localhost HTTP server and checks the pinned credential with `git credential fill` run under `as.sh` (the helper answers only `https://github.com`, so no network is needed). `evals/pr-pair/test_pr_pair.py` covers `pr-pair.sh`. Agent-instruction rules (run login hand-off, fenced call sites) are checked by position and key terms. `evals/pr-pair/test_skill_text.py` covers `specwright-pr`; `evals/git-workflow/test_instructions.py` covers `specwright-branch`, `-commit`, `-finish` and `-roadmap`.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| github-identity → Every GitHub call fenced to the run login | Configured login | evals/pr-pair/test_as_sh.py | test_configured_login_pins_its_token_not_the_active_one | green |
| github-identity → Every GitHub call fenced to the run login | Token resolves to someone else | evals/pr-pair/test_as_sh.py | test_token_for_other_login_exits_3_command_not_run | green |
| github-identity → Empty login resolved once per run | Switch mid-run | evals/pr-pair/test_as_sh.py | test_resolved_login_survives_auth_switch | green |
| github-identity → Empty login resolved once per run | Switch during watch | evals/pr-pair/test_skill_text.py | test_run_login_handed_to_watch_feedback_archive | green |
| github-identity → Empty login resolved once per run | Handed-off step without its run login | evals/pr-pair/test_skill_text.py | test_handed_off_step_without_login_stops_and_asks | green |
| github-identity → Empty login resolved once per run | No active account in a step that needs GitHub | evals/pr-pair/test_as_sh.py | test_resolve_without_account_exits_3_message | green |
| github-identity → Empty login resolved once per run | No gh account in a step that accepts local refs | evals/git-workflow/test_instructions.py | test_gate_and_roadmap_status_local_refs_when_resolve_fails | green |
| github-identity → Empty login resolved once per run | Ambient token variables do not choose the login | evals/pr-pair/test_as_sh.py | test_resolve_ignores_gh_token_env | green |
| github-identity → Login fallbacks end at the run login | Review requests with every login empty | evals/pr-pair/test_skill_text.py | test_review_request_poster_falls_back_to_run_login_fenced | green |
| github-identity → Login fallbacks end at the run login | Store login empty | evals/pr-pair/test_pr_pair.py | test_context_empty_store_login_uses_code_run_login | green |
| github-identity → Login fallbacks end at the run login | Fallback login has no credential | evals/pr-pair/test_as_sh.py | test_request_as_without_credential_exits_3 | green |
| github-identity → Login fallbacks end at the run login | Store reads with both logins empty | evals/pr-pair/test_pr_pair.py | test_rounds_store_token_url_exits_3_no_request | green |
| github-identity → Main refreshes and pulls fenced | Cleanup pull after merge | evals/pr-pair/test_pr_pair.py | test_cleanup_plan_pull_runs_through_as_sh | green |
| github-identity → Main refreshes and pulls fenced | Branch gate fetch over SSH | evals/git-workflow/test_instructions.py | test_branch_gate_fetch_fenced_local_refs_on_refusal | green |
| github-identity → Main refreshes and pulls fenced | Origin that pushes to a fork | evals/git-workflow/test_instructions.py | test_fetch_fenced_by_fetch_url_not_identity | green |
| github-identity → Main refreshes and pulls fenced | Post-merge pull refused | evals/git-workflow/test_instructions.py | test_finish_pull_fenced_stops_on_failure | green |
| github-identity → Post-merge PR check fenced | Merged PR check with a login set | evals/git-workflow/test_instructions.py | test_finish_post_merge_check_fenced_with_repo | green |
| github-identity → Post-merge PR check fenced | Check cannot authenticate | evals/git-workflow/test_instructions.py | test_finish_post_merge_check_exit3_stops | green |
| github-identity → Credentials in a URL refused | Credential-free HTTPS URL | evals/pr-pair/test_as_sh.py | test_credential_fill_returns_verified_token | green |
| github-identity → Credentials in a URL refused | Token in the fetch URL | evals/pr-pair/test_as_sh.py | test_token_in_fetch_url_refused_no_request | green |
| github-identity → Credentials in a URL refused | Token in one of several push URLs | evals/pr-pair/test_as_sh.py | test_token_in_second_push_url_refused | green |
| github-identity → Credentials in a URL refused | Credential added by a URL rewrite | evals/pr-pair/test_as_sh.py | test_insteadof_rule_with_token_refused | green |
| github-identity → Credentials in a URL refused | Token in the username slot | evals/pr-pair/test_as_sh.py | test_token_in_username_slot_refused_masked | green |
| github-identity → Credentials in a URL refused | Username without a secret | evals/pr-pair/test_as_sh.py | test_bare_username_refused | green |
| github-identity → Credentials in a URL refused | Credential rule for another host | evals/pr-pair/test_as_sh.py | test_gitlab_token_rule_ignored | green |
| github-identity → Fenced calls target github.com only | Enterprise host in the environment | evals/pr-pair/test_as_sh.py | test_gh_host_and_enterprise_tokens_unset | green |
| github-identity → Fenced calls target github.com only | Host variables set but empty | evals/pr-pair/test_as_sh.py | test_empty_gh_host_targets_github | green |
| github-identity → Non-GitHub remotes outside the fence | Local mode with a self-hosted remote | evals/git-workflow/test_instructions.py | test_non_github_fetch_runs_plain | green |
| github-identity → Non-GitHub remotes outside the fence | PR mode with a non-GitHub origin | evals/pr-pair/test_pr_pair.py | test_identity_not_github (existing) | green |

## 1. ADR 0008

- [x] 1.1 Write `docs/adr/0008-fenced-github-identity-by-default.md` (MADR-short, `Status: proposed`, `Supersedes: 0004`) from design D1-D6: fence by default, run login resolved once per user-started run and handed off, git network calls to GitHub fenced, any userinfo on github.com URLs refused, gh pinned to github.com, other hosts outside; rejected alternatives and reversal cost. Leave `0004` unchanged. Verify: file exists, `git diff --stat docs/adr/0004*` is empty.
- [x] 1.2 Update `openspec/architecture.md`: replace the 0004 row in the in-force index with 0008, accepted with today's date (the change's design review passed), and rewrite the **GitHub identity** paragraph (`:107`) and the `specwright-roadmap` row (`:68`) without the #38 exceptions. Set 0008 to `Status: accepted` with the date. Verify: `grep -n "#38" openspec/architecture.md` lists no open exception, and the index lists 0008 and not 0004.

## 2. `as.sh`: resolve, host pinning, URL refusal

- [x] 2.1 Extend the fake `gh` (`evals/fakes/gh.py`) as needed: `api user` answers by `GH_TOKEN` when set (else the state's active `user`), it logs `GH_HOST` and the enterprise token variables for each call, and a test can switch the active user between calls. Verify: `python -m unittest evals.pr-pair.test_fake_gh` passes (add cases for the new behaviour).
- [x] 2.2 Write the failing `test_as_sh.py` tests for the resolve and identity rows (Configured login, Token resolves to someone else, Switch mid-run, No active account, Ambient token variables, Fallback login has no credential) and the host rows (Enterprise host, empty `GH_HOST`). Verify they fail for the right reason (no `--resolve`, host variables reach the command).
- [x] 2.3 Implement `as.sh --resolve` (D1) and the host variable unsetting (D3) in `skills/specwright-pr/scripts/as.sh`. The `--resolve` stop message names `gh auth login`, `github.login`, and that `GH_TOKEN`/`GITHUB_TOKEN` are not used to pick the login. Verify: the 2.2 tests pass; flip their rows green.
- [x] 2.4 Write the failing URL tests (Credential-free HTTPS URL via `git credential fill`, Token in the fetch URL, Token in one of several push URLs, rewrite rule, token in the username slot, bare username, GitLab rule ignored, plus a `-c remote.origin.url=...` argument case), each asserting exit 3, the masked message, no request at the server and unchanged config where it applies. Verify that they fail.
- [x] 2.5 Implement the URL check (D2) in `as.sh`, for every fenced command started inside a work tree, plus the argument and `-c` scan. Verify: the 2.4 tests and the existing `AsShHeaderScrub` tests pass; flip rows green.
- [x] 2.6 Update the `as.sh` header comment and its README row (`README.md:254`): `--resolve`, the github.com userinfo refusal, the host variables. Verify: `grep -n "resolve\|userinfo" README.md skills/specwright-pr/scripts/as.sh`.

## 3. `pr-pair.sh`: store reads, token lookup, cleanup pulls

- [x] 3.1 Write the failing `test_pr_pair.py` tests: Store reads with both logins empty (`rounds` exits 3 on a store origin carrying a token, with no request at the server), Store login empty (`context` reports an empty store login, and the store's reads run as the code run login through `as.sh` inside the store), Cleanup pull after merge (each emitted `pull --ff-only` command is `bash <as.sh> <login> git pull --ff-only`), and a `token_for` case where `GH_HOST` and the enterprise tokens do not reach `gh`. Verify that they fail.
- [x] 3.2 Implement D6 in `git_net`: every network read of a repo other than the one the process started in goes through `as.sh <that repo's login>` from inside it, with `ambient_login()` when the store login is empty or equal. Also unset the host variables in `token_for`, and emit the fenced pull in `cleanup-plan` (D4). Verify: the 3.1 tests and the whole `evals/pr-pair` suite pass; flip rows green.

## 4. Skill text: run login, hand-offs, fenced call sites

- [x] 4.1 Write the failing `evals/pr-pair/test_skill_text.py` tests: the identity paragraph defines the run login (resolve once with `as.sh --resolve` at a user-started step, hand it off, stop and ask when missing), the "drop it when `github.login` is empty" wording is gone, every `gh`/`git push`/`git fetch`/`git pull` call site in `specwright-pr` carries `[as]` (or is the `--resolve` call), and review-request posters fall back to the run login, fenced. Verify that they fail.
- [x] 4.2 Update `skills/specwright-pr/SKILL.md`: the identity paragraph, review requests, the cleanup pulls, the `gh pr view` comment checks, the ship → watch → feedback / archive hand-offs naming the run login, and the `--wait` watcher command line. Verify: the 4.1 tests pass; flip rows green.
- [x] 4.3 Write the failing `evals/git-workflow/test_instructions.py` tests:
  - branch gate: the main refresh is fenced when the fetch URL is on github.com, decided by the fetch URL and not by `identity`; plain for other hosts; and on refusal or a failed `--resolve` the gate reports local refs only.
  - roadmap: status reads, and init/close pulls, are fenced the same way.
  - finish: the post-merge check is `[as] ... discover` or a fenced `gh pr view` with `--repo`, never plain `gh pr view <branch>`; exit 3 stops; the post-merge pull is fenced and stops on failure.
  - commit → ship and finish → ship / roadmap hand-offs pass the run login.

  Verify that they fail.
- [x] 4.4 Update `skills/specwright-branch/SKILL.md`, `skills/specwright-roadmap/SKILL.md`, `skills/specwright-finish/SKILL.md` and `skills/specwright-commit/SKILL.md` to match. Verify: the 4.3 tests and the whole `evals/git-workflow` suite pass; flip rows green.

## 5. Settings, docs and release 0.3.0

- [x] 5.1 Update `templates/openspec/specwright.yaml` (`github.login` comment: empty = the active `gh` account, resolved once per run and fenced) and the README settings block (`README.md:270`). In the README, add 0.3.0 notes with both **BREAKING** items (`GH_TOKEN`-only environments: `gh auth login --with-token`; userinfo on github.com remote URLs: remove it), the SSH-origin local-refs note, and the advice to set `github.login` when switching accounts between sessions. Verify: the install-update eval and `test_instructions.py` pass, and `grep -n "unsafe when agents" templates README.md` is empty.
- [x] 5.2 Bump `VERSION` and the README badge to 0.3.0. Verify: `cat VERSION` prints `0.3.0`.

## 6. Integration

- [ ] 6.1 Run every eval suite (`python -m unittest discover evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`), `openspec validate --all --strict` and `openspec schema validate specwright`. Verify: all pass, and every test-map row is green.
- [ ] 6.2 Exit-criterion evidence for M2 ("with `github.login` empty, the #38 regression cases prove every `gh` and git network call is fenced or refused"): list each #38 case (empty default, post-merge check, each fetch/pull site, credential URLs, host variables) with its passing test in the PR description. Verify: the PR description contains the list.

## Workflow follow-up

- Archive with `/opsx:archive`, then `specwright-finish` (pr mode: ship, watch, merge on GitHub).
- The PR closes #38.
