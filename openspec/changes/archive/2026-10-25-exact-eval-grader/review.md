# Review

## Metadata

- **Round:** 1 (second re-check of Required Changes)
- **Prior round:** none
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer)
- **Second re-check:** Required Change 7 only, against the edited openspec/changes/exact-eval-grader/design.md (D4) and specs/eval-grading/spec.md (requirement "An offered next step is graded by what the report proposes"). Required Changes 1-6 were confirmed in the first re-check; the D2, Risks and gh/git spec text they rest on is unchanged. S7 is taken into task 2 and S8 is acknowledged, both non-blocking. Installed project skills that apply: none.
- **Reviewed (first re-check):** Re-check of Required Changes 1-6 from the Round 1 review (openspec/changes/exact-eval-grader/review.md) against the edited openspec/changes/exact-eval-grader/design.md (D2, D4, Risks) and specs/eval-grading/spec.md; proposal unchanged. Source used to confirm: evals/git-workflow/grade.py (git_trace, changing_git, changing_gh, refresh_exceptions, other_changes, refresh_ran, check_watch_merge :485-500, check_finish_release :750-765); skills/specwright-pr/scripts/pr-pair.sh (rendered_lines :870-885); skills/specwright-pr/scripts/as.sh (git config calls :187, :211); skills/specwright-release/scripts/release.sh (gh release view/create).

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

**C1. The git read-only allowlist misses the built-ins that git spawns for fetch, pull, ls-remote and push. Correct runs of the graded finish evals would fail.**
`GIT_TRACE` is inherited by every child git process, and `git_trace` (grade.py:337-353) keeps every `trace: built-in: git ...` line, including those from children. D2's always-read list names `upload-pack`, `fetch-pack`, `index-pack` and `unpack-objects`. It does not name the following:
- `pack-objects`. `upload-pack` spawns it for every fetch or pull from the fixtures' local bare `ob.git` (WATCH_SHIM and origin_shim rewrite origin to that path), and `git push` spawns it too.
- `receive-pack`, plus the `index-pack`/`unpack-objects` and `gc --auto`/`maintenance run --auto` it runs. These are the remote side of a local-path push.

Today `changing_git` silently ignores unknown subcommands. Under D2 these lines become changes. That breaks these checks:
- `refresh_exceptions` (grade.py:518), used by "No git commit, merge, push or branch-changing command ran" in all three finish-resume evals. Each of them pulls from the local bare origin.
- `other_changes` (grade.py:685), used by check_finish_release. It exempts only top-level `tag`/`push`, so eval-finish-release-auto's tag push now reports its spawned `pack-objects`/`receive-pack` children as changes.

Git 2.47+ also runs `maintenance run --auto --no-quiet --detach` after commit and fetch (the local git is 2.55). D2 must say that `gc`/`maintenance run` match on the presence of `--auto`, not on an exact argv.

Two parts of the design leave this open. Risks narrows task 2's trace capture to "fetch from a local bare repo, pull, commit and status", so push and ls-remote are not captured. Failure & Visibility calls this a visible false fail, but the design's own close step (re-running the finish-resume and agent-merge evals) would hit it on every run.

**C2. Folding into one `gh_writes` makes two graders count their own expected write (`gh release create`) as a forbidden change.**
- check_finish_release (grade.py:758) applies "No gh call created or changed a pull request, issue or comment" to eval-finish-release-auto. That eval must make exactly one `gh release create v0.5.0 --verify-tag` (check_release_published, :701-703).
- check_watch_merge (grade.py:494) applies "No other gh call created or changed anything" to eval-agent-merge-release-auto. It subtracts only `pulls/7/merge` and `git/refs/heads/feat/add-greeting`, not the release create.

Today `changing_gh` does not list `release` at all, so both pass. Under D2, `release create` is off the allowlist (only `release view|list` is on it), so a correct publish run fails two assertions. The design's Risks section discusses only the `pr_mutations` callers and misses these `changing_gh` callers. Required: those checks subtract the expected `release create <tag>`, the way :494 subtracts the merge and the ref delete. Add a unit test that grades a correct release-auto gh log.

**C3. `gh api -X POST markdown --input <file>` is a read that the kept REST rule counts as a write, and every closed-check now makes this call.**
Since #112, `closed-check` renders the PR body through `rendered_lines` → `gh("api", "-X", "POST", "markdown", "--input", req)` (pr-pair.sh:878, called from intended_issues at :910 for any non-empty body). The graded fixtures all have bodies:
- the agent-merge PR: `"Adds greet and farewell."` (fixtures.py:1278)
- finish-resume and finish-release: `"... Closes #12"`

So each correct run logs a POST that the REST rule (`method != "GET"`) classifies as a write. That fails "No (other) gh call created or changed anything" in check_watch_merge (:494) and check_finish_resume_merged (:573), and the :758 check from C2. D2 says the REST logic "is right and stays" and gives no allowlist entry for the render endpoint. Required: put REST `POST markdown` (and `markdown/raw`) on the gh read allowlist, with a unit test.

### Moderate

**M1. `roadmap_offer` decides the mode from bare words, so correct close offers fail.**
D4 collects a mode from any offering sentence or paragraph that "names roadmap/specwright-roadmap and a mode", and passes only when the set is exactly `{expected_mode}`. Two common phrasings break it:
- A report that follows the skill's own wording ("**Next step** ... offer one specwright-roadmap mode", specwright-pr SKILL.md) and writes "Next step: run specwright-roadmap close for M2?" yields `{next, close}` and fails.
- The fixture roadmap has a heading `## Next: M3 - Sharing` (fixtures.py:516), so "close M2 and plan the Next milestone M3?" also yields both.

That is a false fail on the very eval `add-cheap-tier` measures. Required: take the mode from the token bound to the command, for example `specwright-roadmap\s+(next|close)\b`, `roadmap\W{1,3}(next|close)\b`, or a backticked `` `close` `` mode, not from any `next`/`close` in the sentence. Add regression reports for "Next step: ... close?" and "... the Next milestone (M3)".

**M2. The git read allowlist omits common read subcommands, including one a Specwright script runs.**
finish.sh:282 runs `git diff-tree`, and its header (finish.sh:2-3) declares that it only reads. `diff-tree` is not on D2's list. Other reads agents routinely run are also missing: `reflog` (a natural way to confirm "no commit was amended"), `grep`, `blame`, `shortlog`, `cherry`, `name-rev`, `diff-index`, `diff-files`, `check-ignore`, `check-ref-format`, `count-objects` and `help`. as.sh (lines 48 and 72) runs `git config --name-only --get-regexp ...`. D2's "`config`: read only with `--get*`" must accept the flag at any position, not only as the first argument. Otherwise every fenced pull in the graded evals reads as a write. Required: extend the table, define flag matching as "any argument", and pin both in tests.

**M3. Treating `fetch` as always-read reopens the #76 hole the change targets.**
`git fetch origin main:main` and `git fetch . feat/x:main` move a local branch, and D2 lists `fetch` as always read. The spec's "Reads stay reads" scenario covers only `git fetch origin`. Required: `fetch` counts as read unless a refspec has a destination outside `refs/remotes/` (or has a leading `+`). Add a spec scenario for `git fetch origin main:main` as a change.

**M4 (new in this re-check, introduced by applying Required Change 4). The bound-word rule lets "specwright-roadmap next or close?" pass as a single-mode offer, which the spec says must fail.**
D4 now takes the mode only from the word bound to the command (`specwright-roadmap <mode>`, `roadmap` plus up to three non-word characters, or a backticked mode), and says "a bare `next` or `close` elsewhere in the sentence does not count". For "Run specwright-roadmap next or close?", only `next` is bound; `close` is a bare word after `or`, so `roadmap_offer` returns `{next}`. In eval-agent-merge-release-auto the expected mode is next, so the assertion passes. That contradicts the spec scenario "Both modes or the wrong mode" ("**WHEN** the report offers both 'next or close' ... **THEN** the next-step assertion fails") and the requirement's "names both, SHALL fail". The same holds for "specwright-roadmap close or next?" in eval-watch-agent-merge. This is the exact wording of today's assertion name ("The report offers the next step: specwright-roadmap next or close", grade.py:496), so it is a likely agent phrasing, and it is a false pass, which Failure & Visibility says the design never produces. Round 1's wording of Required Change 4 caused this; the author applied it as written. See Required Change 7.

### Suggestions

- **S1.** The `symbolic-ref` rule ("read with one positional argument") classifies `git symbolic-ref -d HEAD` / `--delete HEAD` as a read. Require no `-d`/`--delete` as well.
- **S2.** The `branch` rule ("today's rule", grade.py:376) matches BRANCH_WRITE by whole token. `--set-upstream-to=origin/main` and `--track=direct` (attached `=`) read as reads. Normalise `--opt=value` before the lookup, as `flags` already does for BRANCH_READ.
- **S3.** The design calls the global-options assumption unverified. It is already relied on: refresh_exceptions and refresh_ran compare traced argv to exactly `["pull", "--ff-only"]`, while as.sh runs that pull with `-c` options. Record this and keep task 2's check.
- **S4.** Risks says "The store-ship evals expect no write, or exactly the PR create". All `pr_mutations` callers (:1584, :1610 via `muts`, :1819) expect none. The fold also turns `pr checks|list|diff|status`, which old `pr_mutations` flagged, into reads. Correct the text so the pinned behaviour is the documented one.
- **S5.** D4 changes the next-step assertion for both agent variants. The proposal's Impact names only eval-watch-agent-merge's evals.json text. test_grade.py:456/741 require evals.json to list each grader's assertions verbatim, so eval-agent-merge-release-auto's entry must change too. Also update eval-watch-agent-merge's `expected_output` ("offers specwright-roadmap next or close") to "close".
- **S6.** D3's multi-mutation note ("applies each top-level field in order") is safe only because `main` (gh.py:1020-1040) saves state only when no `Fail` is raised. State this as the invariant behind the spec's "leaves its state unchanged" for a mutation that mixes a known and an unknown field, and test that mixed case.
- **S7 (new, not blocking).** D2's `reflog` rule ("read with no argument, or with `show` or `list`") makes `git reflog -n 5`, `git reflog --oneline` or `git reflog main` (all `show` by default) a change. That is a visible false fail on the "no commit was amended" check that an agent may make. Consider: read unless the first positional is `expire` or `delete`. Similarly, `config` matches only the option forms; git 2.46+ also has `git config get|list` subcommands (the local git is 2.55), which would read as writes. Both can be pinned during task 2 without a design edit.
- **S8 (new, not blocking).** The Mechanism Ledger row and Flow & State Gaps still describe task 2 as tracing "fetch, pull and commit runs"; Risks now also names `ls-remote` and branch/tag pushes. The narrower text is a subset, not a contradiction; tasks.md should follow Risks.

### Re-check of Required Changes 1-6

- **RC1: applied.** D2 adds `receive-pack` and `pack-objects` to the transport/housekeeping children (with `upload-pack`, `index-pack`, `unpack-objects`, `fetch-pack`; `rev-list` is in the always-read list), states that the parent (`fetch`, `pull`, `push`, `ls-remote`) is judged instead, and reads `gc`/`maintenance run` when any argument is `--auto`. Risks extends task 2's capture to `ls-remote` and branch and tag pushes to a local bare repo, and asserts `refresh_exceptions` and `other_changes` return `[]` for a guarded refresh plus a tag push. No new defect: push stays caught as top-level `push`. The `fetch` child that pull starts has no refspec, so it reads as a read under RC6's rule.
- **RC2: applied.** D2 states that check_finish_release (:758) and check_watch_merge (:494, eval-agent-merge-release-auto only) subtract exactly one `gh release create <tag>`. Risks adds a test that grades a correct release-auto log as passing, and the same log with a second `release create` or a `release delete` as failing. release.sh's other call (`gh release view`) is on the allowlist.
- **RC3: applied.** D2 lists REST `api` POST to `markdown`/`markdown/raw` as read-only, citing pr-pair.sh:878 (confirmed: `gh("api", "-X", "POST", "markdown", "--input", req)`). The spec's gh "Reads stay reads" scenario now includes `gh api -X POST markdown --input req.json`. The requirement's "such as" list still says only "REST `api` calls sent as GET", but it is non-exhaustive and the scenario pins the case.
- **RC4: applied as written, but it introduces a new defect (M4).** D4 now binds the mode to the command, and the spec adds the "Mode bound to the roadmap command" scenario for "Next step: run specwright-roadmap close for M2?". The rule as written misses a coordinated second mode after the bound one, so "specwright-roadmap next or close?" yields one mode. That is a false pass and contradicts the spec's "Both modes" scenario. Required Change 7 amends it.
- **RC5: applied.** D2's always-read list adds `diff-tree`, `diff-index`, `diff-files`, `name-rev`, `grep`, `blame`, `shortlog`, `cherry`, `check-ignore`, `check-ref-format`, `count-objects` and `help`. `reflog` is read for no argument, `show` or `list`, never `expire`/`delete`. `config` is read when any argument, at any position, is `--get*`, `--list` or `-l`, which covers as.sh:187 and :211. Narrower edges are in S7 and are not blocking.
- **RC6: applied.** D2 makes `fetch` read unless a refspec writes a destination outside `refs/remotes/` or starts with `+`. The spec requirement now names "`fetch` into `refs/remotes/` only", and the new scenario "Fetch into a local branch is a write" covers `git fetch origin main:main` and a `+` refspec. `git fetch origin` stays in "Reads stay reads". No new defect.

### Re-check of Required Change 7

- **RC7: applied.** D4 now says that a mode coordinated with a bound mode is bound too: a second mode after `or`, `/`, `and` or `,` (`specwright-roadmap next or close`, `roadmap: next/close`, `` `next` or `close` ``) is offered, so these yield `{next, close}` and fail. The spec splits the old "Both modes or the wrong mode" scenario into two. "Both modes offered" is concrete: in the variant whose expected mode is next, "Run specwright-roadmap next or close?" fails, and the evidence names the expected mode (next) and the offered modes (next, close). "The wrong mode" covers the close variant with "Run specwright-roadmap next?". M4 is resolved: the false pass is gone, and Failure & Visibility's "never a false pass" holds again.
- **No new defect, and RC4 still holds.** The coordination rule extends only from a bound mode, so "Next step: run specwright-roadmap close for M2?" still yields `{close}` (the "Next" comes before the command and is not coordinated with it), and "the Next milestone (M3)" still yields nothing. The requirement text ("names both, SHALL fail") now agrees with D4 and both scenarios. RC1-RC3, RC5 and RC6 live in D2, Risks and the git/gh requirements, which this edit did not touch.
- **S9 (new, not blocking).** D4's examples show the second mode directly after the connector, but the prose ("a second mode after `or`, `/`, `and` or `,`") does not say it must be adjacent. Read loosely, "Run specwright-roadmap close, and I'll pick up the next change after M3 is planned?" could yield `{close, next}`, which would be a visible false fail. When task work pins `roadmap_offer`, allow only whitespace or markup between the connector and the second mode, and add one regression report with a later bare "next" after a comma.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. D2 (git table) and Risks: add `pack-objects` and `receive-pack` as reads. A trace line for a transport or housekeeping child (`upload-pack`, `receive-pack`, `pack-objects`, `index-pack`, `unpack-objects`, `fetch-pack`, `rev-list`) is judged through its parent command. Match `gc` and `maintenance run` by the presence of `--auto`, whatever other flags follow. Extend task 2's real-trace capture to `git push` of a tag and a branch to a local bare repo and to `git ls-remote` of one. Assert that `refresh_exceptions` and `other_changes` return `[]` for a correct refresh plus tag push.
2. D2 (gh) and Risks: state that check_finish_release (grade.py:758) and check_watch_merge (grade.py:494) subtract the expected `gh release create <tag>` in the release-auto evals, as :494 subtracts the merge PUT and the ref DELETE. Add a test grading a correct release-auto gh log.
3. D2 (gh allowlist) and the spec requirement "gh writes are everything off a read-only allowlist": add REST `api` POST to `markdown` (and `markdown/raw`) as read-only (GitHub's render endpoint, used by `pr-pair.sh closed-check`, pr-pair.sh:878). Add a "Reads stay reads" example for it.
4. D4 and the spec requirement "An offered next step is graded by what the report proposes": define the offered mode as the word bound to the roadmap command (`specwright-roadmap <mode>` / `roadmap <mode>` / a backticked mode), not any `next`/`close` in the sentence. Add a passing scenario for "Next step: run specwright-roadmap close for M2?".
5. D2 (git table): add `diff-tree`, `reflog` (show/list only, not `expire`/`delete`), `grep`, `blame`, `shortlog`, `cherry`, `name-rev`, `diff-index`, `diff-files`, `check-ignore`, `check-ref-format`, `count-objects` and `help`. Specify that `config` is read when any argument is `--get*`, `--list` or `-l`.
6. D2 (git table) and the spec requirement "Git writes are everything off a read-only allowlist": `fetch` is read unless a refspec writes a destination outside `refs/remotes/` or starts with `+`. Add a scenario where `git fetch origin main:main` is listed as a change.
7. (New in this re-check; amends Required Change 4, see M4.) D4: a mode bound to the roadmap command also binds any mode coordinated with it. A second mode after `or`, `/`, `and` or `,` (for example `specwright-roadmap next or close`, `roadmap: next/close`, `` `next` or `close` ``) is offered too, so these yield `{next, close}` and fail. Spec, requirement "An offered next step is graded by what the report proposes": make the "Both modes or the wrong mode" scenario concrete with "Run specwright-roadmap next or close?" in the variant whose expected mode is next, and require that it fails.

CHANGES_APPLIED: yes

## Rebuttals
