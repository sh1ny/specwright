# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (Claude Code specwright-reviewer), re-check of Required Changes M1-M4 only
- **Reviewed:** openspec/changes/ci-os-matrix/review.md (prior findings, Required Changes, Rebuttals); openspec/changes/ci-os-matrix/proposal.md, design.md, specs/eval-runner/spec.md (against openspec/specs/eval-runner/spec.md); source: .gitattributes, `git ls-files` (VERSION files), CONTRIBUTING.md:40-51, README.md:629, evals/run.py (docstring, `tests_run`, `parse`). Installed project skills named by the request: none.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. Every Windows job will fail at setup: the VERSION files check out with CRLF.** D6 keeps the Windows checkout's `core.autocrlf=true` conversion, and Context says every text file not pinned by `.gitattributes` follows it. `.gitattributes` pins only `*.sh`, `*.md`, `*.yaml` and `evals/update/shims/*`, so `OPENSPEC_VERSION`, `JJ_VERSION`, `BUT_VERSION` and `VERSION` check out as CRLF on Windows (`git ls-files --eol` on this Windows checkout: `i/lf w/crlf attr/` for all three pin files). The workflow reads them with `$(cat …)`, which strips `\n` but not `\r`: `npm i -g @fission-ai/openspec@$(cat OPENSPEC_VERSION)` gets a version ending in `\r`, and D3's `version="${JJ_VERSION:-$(cat JJ_VERSION)}"` builds `jj-v0.46.0\r-x86_64-pc-windows-msvc.zip`, a URL that 404s. Both run before any suite, so every Windows job fails at setup on the first push. The design claims the OpenSpec CLI step works "on every OS" and D3 does not mention it. D9 would catch it, but the failure is predictable from the code, and D6's own rule (fix the CRLF for users too) already says how to fix it.
*Re-check: resolved.* D6 now adds `*VERSION text eol=lf` (the only tracked files it matches are the four pin files: `BUT_VERSION`, `JJ_VERSION`, `OPENSPEC_VERSION`, `VERSION`) and names the test (`git check-attr eol` on each of the four in `test_ci_workflow.py`). Context records the `i/lf w/crlf` evidence. Failure & Visibility has the row "A pin file checked out with CRLF". The proposal's What Changes ("Pin files stay LF") and Impact ("Repo config") list it.

**M2. A skip that fires on one OS only is not enforced and cannot be seen, but the proposal promises both.** The proposal says "No test is skipped on one OS without an issue that names it". D7 only catches skips whose condition names `os.name`, `sys.platform` or `platform.system`. Many existing skips depend on the environment and can fire on one OS only:
- `evals/vcs/test_gitbutler_ranges.py:178` and `evals/release/test_release.py:226,341`: "cannot create symlinks";
- `evals/pr-pair/test_pr_pair.py:2616`: no Python 3.8;
- `evals/pr-pair/test_fake_gh.py:681,690,985,1081`: `jq` or `sh` missing;
- `evals/git-workflow/test_task_cover.py:169`: `ssh-keygen` missing;
- the many "needs bash" skips.

None of these is checked. `run.py` also can't show them. On success it prints only `<suite>: N files, M tests, Xs` (`tests_run` counts `Ran N tests`, so skipped tests are counted) and deletes the passed files' logs (`evals/run.py` main, `r["log"].unlink()`). A test that skips only on Windows or macOS leaves a green check with nothing to tell it apart. D9's triage looks at failures only, so it misses these too. For the same reason, the ADDED scenario "A per-OS skip with its issue" cannot be checked as written: its THEN says "the Windows run reports that test skipped with that reason", and run.py reports no skip reasons.
*Re-check: resolved (option b).* D10 adds `K skipped` per suite, read from unittest's closing `OK (...)`/`FAILED (...)` line. The MODIFIED runner requirement states the field in "All files pass" and adds "Skips are counted per suite" (`2 skipped`, exit 0). D9 compares skipped counts across the three OSes and triages a difference like a failure, with the GitButler skips named as the expected difference. The ADDED requirement scopes the scan to OS-reading conditions and states that tool/interpreter skips are shown by the count. The scenario "A per-OS skip with its issue" now ends at "the runner test passes", which is assertable. The proposal's claim now matches the mechanism.

**M3. D8 leaves the full local suite runs in CONTRIBUTING.md.** D8 replaces only the `--changed main` bullet (CONTRIBUTING.md:42). Lines 47–51 still tell contributors to run whole suites locally: "run `python -m unittest discover evals/review-routes`", `evals/release`, `evals/finish`, `evals/update`, and "Run `python -m unittest discover evals/pr-pair`". The pr-pair suite is the one that takes about an hour on Windows (`evals/timings.md`: 3725 s before the runner). README.md:629 says the same ("Test the fake `gh` with `python -m unittest discover evals/pr-pair` …"). After this change the files would contradict each other: the new line says run only the module you are writing, and these lines name whole-suite runs. `test_agent_instructions.py` would check only for `--changed main`, so the contradiction passes CI. The point of #145 (stop local runs that take over the machine) is lost for anyone who follows the per-area bullets.
*Re-check: resolved.* D8 covers `CONTRIBUTING.md:44-51` and `README.md:629` and keeps the Python 3.8 note by module. The MODIFIED instructions requirement says none of `AGENTS.md`, `CONTRIBUTING.md`, `README.md` may tell the reader to run a whole suite locally, and the scenario "A file brings back a local suite run" fails on `python evals/run.py --changed main` or `python -m unittest discover evals/` (which also catches CONTRIBUTING.md:41's "Each `python -m unittest discover evals/<suite>` command below still works", so that line must change too; the test enforces it). The proposal's Docs impact names the testing section and its per-area bullets.

**M4. The Windows timeout fallback contradicts the exit criterion, and the starting numbers are not derived from the cited evidence.** D5 starts Windows at 120 min per job and `--timeout 3600` per test file. `evals/timings.md` shows pr-pair at 2077 s with 24 parallel jobs on an i7-13700K. With that many workers, the suite's wall time is roughly the time of its slowest file, so `test_pr_pair.py` alone likely takes most of 2077 s on that machine. The `windows-latest` runner (public repo: 4 vCPU, slower per core) can push that file past 3600 s, and `run.py` then kills it as `timeout after 3600 s`. The Risks entry answers this with "split its slow files across jobs in a follow-up issue". But the M6 exit criterion (proposal and roadmap) requires every job to pass on the PR that adds the matrix. D9's other way out, an issue plus a per-test `#n` skip, does not fit a whole file that times out. So the design has no in-change path for its most likely failure.
*Re-check: resolved.* Risks now lists ordered in-change steps (start at 120 min and measure; raise toward the 360-minute cap with `run_timeout` to match; split a suite's files across matrix jobs; split a file) and says none goes to a follow-up. Failure & Visibility has the row "A test file exceeds `run_timeout` on one OS". D9 excludes whole-file timeouts from the issue route. The proposal says a timeout "is fixed in this change … never deferred". See S4 for a spec gap in step 3.

### Suggestions

**S1. Context and D7 miss a sixth per-OS skip.** `evals/pr-pair/test_pr_reply.py:209-210` calls `self.skipTest("chmod cannot make a file unreadable here (Windows, …)")` inside `if os.access(f, os.R_OK) or os.name == "nt":`. D7's scan matches it, and its reason has neither `#n` nor `platform:`. *Re-check: addressed* (Context lists it; D7 says six reasons gain `platform:`).

**S2. The `timings.md` CI section must not match `test_timings.py`'s row regex.** *Re-check: addressed* (State & Ownership row for per-OS timeouts).

**S3. The roadmap entry for this change still says "`but` per OS".** *Re-check: addressed* (proposal Impact lists `openspec/roadmap.md`).

**S4. (new, from the M4 edit) Risks step 3 is not covered by the spec it would change.** Step 3 runs a slow file as its own matrix entry via `run.py <suite>/<file>` and says "`run.py` gains that target form if it lacks it". `run.py` lacks it: `parse` takes only suite names (`ap.add_argument("suites", nargs="*")`), and the runner requirement's "Unknown suite" scenario makes an unknown name exit 2. The CI requirement also says "one job per suite and OS" and "one check per suite and OS … three per suite", which a per-file split breaks. If step 3 is needed, the apply would contradict the delta. Editing the delta then would void this verdict. Steps 2 and 4 (raise the timeout, split a file inside its suite) stay within the spec. No change is required now. If step 3 is used, amend the delta in this change (a `<suite>/<file>` target in the runner requirement and "at least one job per suite and OS" in the CI requirement) and re-run the design review.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. (M1) In D3 or D6 and in the proposal's Impact, state how the version pin files reach the Windows steps without `\r`. Preferred: add an LF rule to `.gitattributes` for `OPENSPEC_VERSION`, `JJ_VERSION`, `BUT_VERSION` and `VERSION` (e.g. `*VERSION text eol=lf`). Alternatively, strip `\r` wherever the workflow reads them. Also name a test that checks this: `test_ci_workflow.py` runs the jj step body against a `JJ_VERSION` file with CRLF, or a check on `.gitattributes`. **Applied, re-checked.**
2. (M2) Make the per-OS skip claim and the mechanism agree. Do one of the following:
   - (a) Narrow the proposal's "No test is skipped on one OS without an issue that names it" to skips whose condition reads the OS, and say that environment-dependent skips (symlinks, Python 3.8, `jq`, `sh`, `ssh-keygen`, `bash`) are out of D7's scope.
   - (b) Make one-OS-only skips visible: `run.py` prints each suite's skipped count from unittest's `OK (skipped=N)` line (a MODIFIED run.py requirement in the delta), and D9's first-run triage compares skipped counts per suite across the three OSes and treats any difference like a failure (fix, or file an issue with an `#n` reason).

   Either way, rewrite the ADDED scenario "A per-OS skip with its issue" so its THEN can be checked. For example, drop "and the Windows run reports that test skipped with that reason", or under (b) say what run.py prints. **Applied (b), re-checked.**
3. (M3) Extend D8, the instructions requirement and the proposal's Docs impact to cover the whole-suite local runs: CONTRIBUTING.md:44–51 (`python -m unittest discover evals/<suite>` for review-routes, release, finish, update and pr-pair) and the matching sentence in README.md:629. Either replace them with "CI runs this suite; locally run only the module you are writing", or state why each one stays. Have `test_agent_instructions.py` also fail when `CONTRIBUTING.md` tells the reader to run `python -m unittest discover evals/pr-pair`. **Applied, re-checked.**
4. (M4) Replace the Risks fallback "split its slow files across jobs in a follow-up issue" with handling inside this change that keeps the exit criterion. Name the actions in order: raise the Windows job timeout toward the 360-minute hosted-runner cap and `run_timeout` to match; if that is not enough, split the slow suite's files across matrix jobs within this change. Add a Failure & Visibility row for "a test file exceeds `run_timeout` on one OS". **Applied, re-checked** (see S4).

CHANGES_APPLIED: yes

## Rebuttals

- **M1** fixed: design Context (pin files `i/lf w/crlf`) and D6 (`*VERSION text eol=lf`, asserted by `git check-attr eol` in `test_ci_workflow.py`); Failure & Visibility row "A pin file checked out with CRLF"; proposal "Pin files stay LF" and Impact "Repo config". — accepted by reviewer.
- **M2** fixed, option (b): new D10 (`run.py` prints `K skipped` per suite); D9 compares skipped counts across OSes and triages a difference like a failure; spec MODIFIED "The runner runs each test file as its own process" (scenario "Skips are counted per suite"); the ADDED requirement scopes the scan to OS conditions and its first scenario's THEN is now checkable; added scenario "A skip inside an OS branch". Proposal narrows the claim accordingly. — accepted by reviewer.
- **M3** fixed: D8 covers `CONTRIBUTING.md:44-51` and `README.md:629`; the instructions requirement forbids whole-suite local runs in `AGENTS.md`, `CONTRIBUTING.md` and `README.md`, with scenario "A file brings back a local suite run" (`python -m unittest discover evals/`); proposal Docs impact names the testing section. — accepted by reviewer.
- **M4** fixed: Risks now lists in-change steps (120 min, raise toward the 360-minute cap, split a suite's files across matrix jobs via `run.py <suite>/<file>`, split a file), none deferred; Failure & Visibility row "A test file exceeds `run_timeout` on one OS"; D9 excludes timeouts from the issue route. — accepted by reviewer (S4 notes that step 3, if used, needs a delta amendment).
- **Suggestions:** `test_pr_reply.py:209-210` added to Context and to D7's six `platform:` reasons; the State table says the CI timings section must not match `test_timings.py`'s row pattern; the roadmap line is listed in proposal Impact and fixed in tasks. — accepted by reviewer.
