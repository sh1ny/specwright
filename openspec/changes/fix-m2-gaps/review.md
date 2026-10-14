# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** proposal.md, design.md, specs/change-finish/spec.md, specs/github-identity/spec.md, specs/preship-review/spec.md; main specs openspec/specs/change-finish, github-identity, preship-review, review-routes; ADRs 0002, 0003, 0007, 0008; skills/specwright-pr/scripts/as.sh, skills/specwright-pr/scripts/pr-pair.sh (GH_URL, unfenced_env, git_net, HOST_VARS, FENCE_VAR), skills/specwright-review/scripts/review-run.sh (artifact_paths, build_prompt, cmd_preflight, cmd_run, archive_only), skills/specwright-review/SKILL.md, skills/specwright-review/references/brief.md, skills/specwright-finish/SKILL.md, skills/specwright-branch/SKILL.md (Used once), agents/claude/specwright-reviewer.md, agents/omp/specwright-reviewer.md, evals/git-workflow/fixtures.py (build_finish_resume_merged, WATCH_SHIM, build_watch_merge), evals/git-workflow/grade.py (changing_git, check_finish_resume_merged), evals/git-workflow/evals.json (the two resume-merged evals); issue #83.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

**C1. D1 makes a store-backed code repo with a merged PR and a deleted branch never done.**
The modified requirement ("A merged PR whose branch is gone is done after the backstop") now says finish SHALL refresh "that repo's `main`" and "read the archive fact again before it counts the repo done", and D1 says "A absent → report that the merged PR did not bring the archive to `main`, run no backstop, and leave the repo not done". Fact A never holds for the code repo of a store-backed change: the archive commit and directory live in the store only (`skills/specwright-finish/SKILL.md:23`: the directory "never gives the code repo an A"). Today the code repo reaches row `:35` with no A, M or B and a merged newest PR, and counts as done after `closed-check`. Under the delta, every store-backed `finish: pr` change whose code PR merged and whose code branch was cleaned up would report "the merged PR did not bring the change's archive to main" for the code repo and never reach `Nothing to finish`. The design's Flow & State Gaps paragraph ("For the code repo, A only ever comes from archive commits ... the code repo row still runs only when its newest PR merged") notices the asymmetry but neither the requirement text nor D1 exempts the code repo, and no scenario covers it.

### Moderate

**M1. The eval plan misses the second eval that D1 changes.**
`build_finish_resume_merged` and `check_finish_resume_merged` serve both `eval-finish-resume-squash-merged` and `eval-finish-resume-merged-branch-gone` (`fixtures.py` `build()`, `grade.py:510-540`). In the squash case main already holds the archive directory, so finish goes straight to row `:35`, and under D1 it now checks out and pulls main. The fixture's origin is behind an unreachable proxy, so the pull fails and finish stops. The grader also counts `checkout main` and `pull` as changing git, and the eval's expected output says "no commit, merge or branch command". The proposal's Impact and the design's Risks name only `finish-resume-merged-branch-gone`, so the squash-merged eval would fail after the change unless it gets the same fixture and grader update.

**M2. A persistent `insteadOf` rule would break the fixture's GitHub origin.**
The design's Risks entry proposes pointing the GitHub URL at the bare repo "through a `url.<file-url>.insteadOf` rule". `git remote get-url` expands `insteadOf`, so origin would read as a local path. Finish decides `[as]` vs plain git from that URL (`SKILL.md:16`), so the agent would run an unfenced pull. It also could not parse `<owner>/<name>` for `discover`, and `pr-pair.sh` `fetch_repo`/`identity` would classify the repo as non-GitHub. The eval would then pass without exercising the fenced pull it is meant to pin. The watch-merge fixture the design cites avoids this. Its `WATCH_SHIM` adds `-c url.$BARE.insteadOf=$URL` only to `pull`/`fetch` in the code repo, so `remote get-url` still shows `https://github.com/...`.

**M3. The stale-main scenario's THEN cannot be asserted as written, and the ledger misstates the residual case.**
The scenario "Stale main holds an older change's archive" ends with "never the older directory alone". D1 accepts any matching archive directory on the refreshed main (`^\d{4}-\d{2}-\d{2}-<change-name>$`). So if the refreshed `origin/main` still holds only the older directory, D1 counts A present and reports done: exactly "the older directory alone". The Mechanism Ledger says the opposite for that case ("then D1 reports 'no archive', which is already safe"). The case is narrow, because the branch gate's **Used once** check (`skills/specwright-branch/SKILL.md:17`) refuses to start a change whose name is already archived. But the scenario and the ledger should state what the design actually guarantees, which is "pull before judging A", not "never the older directory".

### Suggestions

**S1. The credential helper is case-sensitive, but the new requirement covers "any letter case".**
"The trailing-dot host is github.com" applies "in any letter case" to "the credential helper" too. D4 only adds `h=${h%.}` before `[ "$h" = github.com ]` (`as.sh:170`). A `GitHub.COM.` host reaching the helper would get no credential. That fails closed (inherited helpers are cleared), so it is not a bypass. Either lowercase `h` in the helper or limit "any letter case" to the refusal.

**S2. D5 should keep a single "once" guard.**
D5 moves the enterprise-variable save ahead of the unset at `as.sh:44`, "under the same guard". If that becomes a second `if [ -z "${AS_SH_ORIG_SET+x}" ]` block that sets `AS_SH_ORIG_SET`, the existing block at `as.sh:138` is skipped. The git variables (`GIT_SSH_COMMAND`, `GIT_CONFIG_*` and the rest) would then no longer be restored for unfenced reads. Move the whole save block above line 44 as one block (it only reads the environment), and keep a regression test that a non-GitHub store read still gets the caller's `GIT_SSH_COMMAND`.

**S3. The skill text should also treat `github.com.` as GitHub.**
Finish (`SKILL.md:16, :81`), `specwright-pr` (`:51, :155`), the branch gate and roadmap tell the agent to fence a fetch or pull "when the fetch URL is on github.com". An agent reading that literally runs plain, unfenced git for a `github.com.` origin, which is the identity drift D4 removes from `pr-pair.sh`. A short "(including `github.com.`)" in those sentences would close it. The new requirement is scoped to "the fence and the PR scripts", so this is outside the spec as written.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **(C1)** Change the spec delta requirement "A merged PR whose branch is gone is done after the backstop" in specs/change-finish/spec.md, and D1 in design.md. The refresh-and-re-read-A rule applies only to the planning repo: the one repo when repo-local, the store when store-backed. A store-backed code repo with a merged newest PR and no branch keeps today's outcome: the backstop runs and the repo is done (refreshing its main first is allowed, but A is not required). Add a scenario: store-backed `finish: pr`, store done, the code PR merged and the code branch gone → `closed-check` runs for the code PR, no "did not bring the archive" report, and `Nothing to finish - archive is on <main>`. Update the Flow & State Gaps "Store-backed resume" bullet to match.
2. **(M1)** In proposal.md Impact and design.md Risks, name `eval-finish-resume-squash-merged` beside `eval-finish-resume-merged-branch-gone` as an eval whose fixture (pullable origin) and grader (`checkout main` and `pull --ff-only` allowed, nothing else changing) change.
3. **(M2)** In design.md Risks, replace "a `url.<file-url>.insteadOf` rule" with the watch-merge mechanism: a `bin/git` shim that adds a command-scoped `-c url.<bare>.insteadOf=https://github.com/<slug>.git` to `pull`/`fetch` only, so `git remote get-url origin` still returns the github.com URL.
4. **(M3)** Rewrite the THEN of "Stale main holds an older change's archive" so it can be asserted. For example: "finish runs the fenced `git pull --ff-only` on `main` before it reads A; the refreshed `main` holds this change's archive directory, so the backstop runs once and finish reports `Nothing to finish - archive is on <main>`". The fixture's origin main must hold the new dated directory beside the older one. Correct the Mechanism Ledger's "Provenance check" row: when the refreshed `origin/main` holds only an older same-name archive, D1 counts it as A. State that this residual is accepted because the branch gate's **Used once** check refuses an already-archived name.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: yes

## Rebuttals

<!-- Author: fixed (cite) or rebutted (reason) per finding. A Critical/Moderate rebuttal counts only once marked "accepted by reviewer". -->

- **C1 - fixed (accepted by reviewer, re-check run).** specs/change-finish/spec.md: the requirement now refreshes each repo but re-reads A only in the planning repo ("A store-backed code repo needs no archive"), plus the new scenario "Store-backed code repo after merge". design.md D1 Choice and the Flow & State Gaps "Store-backed resume" bullet now match.
- **M1 - fixed (accepted by reviewer, re-check run).** proposal.md What Changes and Impact, and design.md Risks, now name `eval-finish-resume-squash-merged` beside `eval-finish-resume-merged-branch-gone` (shared fixture gets a pullable origin, shared grader allows `checkout main` and `pull --ff-only` only).
- **M2 - fixed (accepted by reviewer, re-check run).** design.md Risks now uses the watch-merge `bin/git` shim with a command-scoped `-c url.<bare>.insteadOf=...` on `pull`/`fetch` only, so `git remote get-url origin` still returns the github.com URL.
- **M3 - fixed (accepted by reviewer, re-check run).** The "Stale main holds an older change's archive" THEN is now assertable (fenced pull before A is read; refreshed main holds this change's archive; backstop once; `Nothing to finish`). The Mechanism Ledger "Provenance check" row now states the residual (an older same-name archive alone on refreshed `origin/main` counts as A) and why it is accepted (`specwright-branch` **Used once**).
- **S1-S3 - taken into tasks.md (suggestions, not required; tasks.md not checked in this run).** (case-insensitive host compare in the credential helper; one "once" guard in as.sh; `github.com.` noted in the skill texts' "fetch URL on github.com" rules); no artifact edit.
