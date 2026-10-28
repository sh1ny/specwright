# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1 APPROVE_WITH_CHANGES: C1 rule carried by the git-ignored `openspec/config.yaml`; M1 pr-pair's import of `evals/git-workflow/fixtures.py` missed by the built-in rule; M2 `no_eval` examples that suites read; M3 runner timeout longer than the job timeout; S1-S3 (WSL clone, removed suite, job-failure wording).
- **Reviewer:** fresh-context subagent (Claude Code, specwright-reviewer); round 2 re-check run by a second fresh-context subagent (Claude Code)
- **Reviewed:** Round 2 full review: openspec/changes/targeted-eval-runs/proposal.md, design.md, specs/eval-runner/spec.md; openspec/specs/eval-runner/spec.md (context); round 1 review; `openspec instructions review --change targeted-eval-runs --json`; openspec/architecture.md (ADR index), docs/adr/0002, 0014 (index entries); openspec/roadmap.md (and its uncommitted diff); evals/run.py; evals/runner/test_run.py (setup), evals/runner/test_timings.py, evals/timings.md; evals/git-workflow/test_specs_strict.py, test_instructions.py (1270-1280, 1860-1870), fixtures.py and grade.py (repo-root reads); evals/pr-pair/* and other suites' `sys.path` imports; evals/release/test_release.py (1878-1898, TestThisRepo); every `skipTest`/`skipUnless`/`skipIf` under evals/; skills/specwright-pr/SKILL.md (watch, 125-150); skills/specwright-pr/scripts/pr-snapshot.sh (check state mapping, 256-267); CONTRIBUTING.md; .gitignore; .gitattributes; `git ls-files`; `git check-ignore`; the installed OpenSpec 1.14.1 `dist/core/archive.js` (schema resolution). Re-check: the round 2 review.md; current proposal.md, design.md, specs/eval-runner/spec.md; `git diff openspec/roadmap.md` (change 4 line); evals/run.py (1-62, 180-240); evals/release/test_release.py:1878-1898; evals/timings.md; evals/runner/test_timings.py (header); openspec/specs/eval-runner/spec.md (requirement "Suite wall times are recorded").

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

Round 1 status: **C1 resolved** (the rule moves to tracked `AGENTS.md`, `CLAUDE.md` and `CONTRIBUTING.md`; `git check-ignore` matches neither new root file; the roadmap line is still stale, see S1). **M1 resolved** (D2 "Union with built-ins", with every `sys.path` import into `evals/git-workflow` cited; the grep shows no other cross-suite import). **M2 partly resolved** (see M1 below). **M3 partly resolved** (see M2 below). **S1-S3 resolved** (D6 clone in `/dev/shm`; scenario "A path under a removed suite"; the reworded job-failure sentence).

The new single-file targets hold up against the code. `openspec/** → git-workflow/test_specs_strict.py` is sound: apart from the git-ignored `openspec/config.yaml` (`test_instructions.py:1866`), no suite reads the repository's own `openspec/` tree except `test_specs_strict.py:37`. Running one file needs no new runner path, because `Run.run_file(suite, fname)` (`evals/run.py:86`) already runs one file. `docs/adr/**` is read by no suite.

### Critical (blocking)

None.

### Moderate

**M1. `openspec/changes/**` is still a `no_eval` example, and a path that matches both a rule and `no_eval` has no defined outcome (round 1 M2, partly resolved).** *(Re-check: resolved.)*
- `design.md:49` still shows `"no_eval": ["openspec/changes/**", "docs/adr/**", ...]` in the format example, while D2 now sends `openspec/**` to `test_specs_strict.py`.
- `proposal.md:11` still says "A path listed as needing no eval (planning files, ADRs, the timing record) runs nothing", but D2 maps planning files (`openspec/**`) and the timing record (`evals/timings.md` → `runner`) to targets.
- Neither the design nor the spec says what happens when a path matches a rule and a `no_eval` pattern at once. The spec's coverage requirement only asks that a file match "a pattern ... or its no-eval list".

Consequence: an implementation that follows the example and checks `no_eval` first (a natural short-circuit) selects nothing for a delta spec under `openspec/changes/<name>/specs/`. That is round 1 M2's failure: a change whose delta spec breaks strict validation runs no test locally.

**M2. The timeout budget still lets GitHub kill the pr-pair job before the runner reports (round 1 M3, partly resolved).** *(Re-check: resolved.)*
D4 claims a hung file "is stopped and named by the runner at 40 minutes, well before the job's 60-minute limit". That leaves 20 minutes for the rest of the suite, but the runner prints its `FAILED` lines only after every file, serial ones included, has finished (`evals/run.py:225-240`).
- `evals/timings.md`: pr-pair takes 2077 s (about 35 min) with `--jobs 24` on a 24-logical-CPU machine. update takes 1052 s.
- Four pr-pair files are in `SERIAL` (`evals/run.py:44-49`) and run one at a time after the parallel batch. Their deadline-bound tests (12 s bounds, hung merges) do not get faster on Linux, and ubuntu-latest has 4 vCPUs, not 24.
- A hang in the parallel batch costs 2400 s, and then the whole serial tail still runs. A hang in the last serial file (`test_pr_snapshot.py`) starts only after the batch and the other serial files have finished. Either way, the 60-minute job limit is likely to arrive before the runner prints anything.

Consequence: the job log names no file and shows no output tail, so watch's CI-mode debug has nothing to work from, and the spec scenario "A suite fails ... with the runner's failure output in its log" is not met for a hang in pr-pair. That is the round 1 M3 consequence, now limited to the largest suite.

**M3. CI's default checkout makes an existing release test skip on every PR.** *(Re-check: resolved; see S5 for a gap in the example command.)*
`evals/release/test_release.py:1882-1891` (`TestThisRepo.test_backfill_ranges`) skips in three cases:
- on a shallow repository;
- when commits `9b33ec5`/`4f9b823` are missing;
- when a `git clone` of the checkout has no `origin/main`.

D4 lists plain `actions/checkout`. Its default is `fetch-depth: 1`, and on `pull_request` it checks out a detached merge commit with no local `main` branch. `git clone` copies only `refs/heads/*`, so even a full-depth checkout would hit the third skip.

Consequence: the CI gate skips this test on every pull request. That contradicts D6's "No skips" and the in-force requirement "Faster suites keep every test" ("no test is removed, skipped or weakened"). Full local runs now happen only at a milestone close, so the test also stops running locally unless a change selects `release`.

**M4. `--changed` has no hermetic test seam, so its spec scenarios cannot be tested reliably.** *(Re-check: resolved.)*
- `evals/runner/test_run.py` builds "throwaway suites in a temp dir and runs the runner on them with --root" (its docstring).
- `run.py` fixes `REPO = HERE.parent` (`evals/run.py:37`) and runs files with `cwd=REPO`.
- D3 runs `git merge-base`, `git diff` and `git ls-files` without saying in which repository. D2 does not say where `suites.json` is read from (`HERE` or `--root`), or what the built-in `evals/<suite>/` rule is relative to.

If `--changed` reads the live checkout, the scenarios for rename, delete, untracked file, unknown ref, missing merge base and removed suite depend on the developer's working tree. In CI they fail outright: the checkout is a detached merge commit with no `main` ref, so a test that calls `--changed main` gets exit 2. Apply would have to invent the interface, or test against mutable state.

### Suggestions

**S1. The roadmap entry still names `openspec/config.yaml`.** The uncommitted edit to `openspec/roadmap.md:27` keeps "The agent and contributor instructions (`openspec/config.yaml`, `CONTRIBUTING.md`)". D5 now rejects that file because it is git-ignored. Name `AGENTS.md` (imported by `CLAUDE.md`) and `CONTRIBUTING.md`, so the milestone close checks the right files. *(Re-check: applied.)*

**S2. Say why "Suite wall times are recorded" does not apply.** The in-force requirement (`openspec/specs/eval-runner/spec.md:44`) asks for before/after wall times "for each suite of a change that aims to cut eval time", and this proposal's Why is eval time. The design never says the requirement does not apply (no suite's own wall time changes; fewer suites run). Without that sentence, the pre-ship review or verify can flag a missing `timings.md` update and prompt a multi-hour re-measure. *(Re-check: applied, with a wording nit in S7.)*

**S3. The runner depends on `skills/specwright-pr/scripts/bounded.py`** (`evals/run.py:55`, `load_bounded`), and only `evals/runner/test_run.py` exercises the runner's timeout and kill paths through it. Add that path to D2's built-in harness list, or require an explicit rule that sends it to `runner` as well as `pr-pair`. *(Re-check: applied.)*

**S4. Dedupe overlapping targets.** When one changed path selects `git-workflow` (for example `README.md`) and another selects `git-workflow/test_specs_strict.py`, say that the whole-suite target covers the file target, so the file does not run twice. *(Re-check: applied.)*

**S5 (re-check). `git branch main origin/main` fails on a manual dispatch from `main`.** D4 (`design.md:83`) uses the command exactly as round 2's example gave it. On `pull_request` the checkout is a detached merge commit, so the command works. But `workflow_dispatch` is a specified trigger (spec, "CI runs every suite on Linux"). When it runs on `main`, `actions/checkout` has already created a local `main`, so `git branch` exits 128 ("a branch named 'main' already exists"), and every suite job fails at setup. Running main on Linux is the most likely reason to dispatch. Create the branch only when it is missing, for example `git show-ref --verify --quiet refs/heads/main || git branch main origin/main`. This is not blocking: the PR gate is unaffected, and the first dispatch would expose the problem.

**S6 (re-check). Two leftovers contradict the edits.**
- The Resource Bounds row "CI jobs per PR" (`design.md:163`) still gives a "60 min per job" timeout, but D4 now sets `timeout-minutes: 120`, both in Timeouts and in Settings.
- The spec requirement "The suite map covers every tracked file" (`spec.md:39`) says every tracked file must match "a rule of `evals/suites.json`". D2's built-in rules (`evals/<suite>/`, `evals/run.py`, `evals/fixturecache.py`, `evals/fakes/**`) have no entries in that file. Read literally, the map test would fail on every file under `evals/` unless the map repeats the built-ins, and D2 says it should not. Say "a rule (explicit or built-in)", as D2 does at `design.md:51`.

**S7 (re-check). The S2 note paraphrases the requirement it cites.** The Risks entry (`design.md:194`) says the requirement "applies to a change that aims to cut a suite's run time". The in-force text says "a change that aims to cut eval time", and this proposal's Why is about eval time. A verifier comparing the two could still flag it. Quote the requirement as written, and give the actual reason it does not apply: the requirement measures per-suite wall times and asks that the after total be lower, and this change leaves every suite's own time unchanged.

## Re-check (Round 2)

Each Required Change, checked against the current files:

1. **M1: applied exactly.**
   - `design.md:49`: `no_eval` is now `["docs/adr/**", ...]`.
   - `proposal.md:11` reads "(ADRs, for example)".
   - D2 Matching (`design.md:51`) and the spec requirement (`spec.md:39`, "never both: no-eval covers only paths no rule matches") state the precedence.
   - The new scenario "A no-eval pattern overlaps a rule" (`spec.md:53-55`) fails the map test, names the file and the pattern, and still selects the rule's targets.
2. **M2: applied exactly.**
   - D4 Timeouts (`design.md:88`) states the rule `timeout-minutes > --timeout + the suite's normal wall time + margin`, with `--timeout 2400` and `timeout-minutes: 120` (also in Settings, `design.md:93`). It says pr-pair's 4-CPU time is unknown and that both numbers are adjusted from measured per-file times before the PR is ready.
   - The Risks entry (`design.md:193`) records per-file times from the WSL run and the first CI run, and sets the half-of-`--timeout` ceiling.
   - The "CI suite job hangs" Failure row (`design.md:154`) matches.
   - The runner accepts `--timeout` (`evals/run.py:181`) and prints `FAILED ... (timeout after S s)` (`evals/run.py:233`), as the row says.
3. **M3: applied exactly.**
   - D4 per-job setup (`design.md:83`) uses `fetch-depth: 0` (all branches and tags, so `origin/main` and commits `9b33ec5`/`4f9b823` are present), followed by `git branch main origin/main`. A clone of the checkout then has `origin/main`, so none of the three skips at `evals/release/test_release.py:1882-1891` fires on a PR.
   - D6 (`design.md:117`) accounts for skips in the first CI run's output, and expects only the platform-only skips.
   - The literal example has a gap on a manual dispatch from `main` (S5). It is not blocking.
4. **M4: applied exactly.** D3 "Which repository" (`design.md:73`) says `--changed` reads `<root>/suites.json`, runs git in the repository found by `git -C <root> rev-parse --show-toplevel`, takes paths relative to that toplevel, evaluates the built-in suite rule for the root's path relative to it, and tests against a scratch git repository, never the live checkout.

Suggestions S1-S4 are all applied:
- **S1:** the roadmap's change 4 line now names "a tracked `AGENTS.md`, imported by `CLAUDE.md`, and `CONTRIBUTING.md`", and no longer names `openspec/config.yaml`.
- **S2:** a Risks note covers it (`design.md:194`; wording nit in S7).
- **S3:** bounded.py maps to `runner` (`design.md:59`; `evals/run.py:54-58` confirms the load).
- **S4:** the deduplication rule is in D2 (`design.md:52`).

What the edits broke or contradicted:
- S5: `git branch main origin/main` fails on a manual dispatch from `main`.
- S6: the stale 60-minute row in Resource Bounds, and the spec's "rule of `evals/suites.json`" wording, which leaves out the built-in rules.
- S7: the S2 note paraphrases the in-force requirement.

Each is a Suggestion with a contained consequence: a red manual run that shows up on first use, and wording that D4 and D2 already settle. None is a new Critical or Moderate problem, and the PR gate and the local selection behave as designed.

## Verdict

The approach holds. All four Required Changes are applied exactly, and so are S1-S4. The re-check adds three non-blocking suggestions (S5-S7) to fix during apply or with a later artifact edit.

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **M1:**
   - In D2's format example (`design.md:49`), remove `openspec/changes/**` from `no_eval`.
   - In `proposal.md`'s What Changes sub-bullet, replace "(planning files, ADRs, the timing record)" with paths no suite reads (for example "ADRs").
   - In D2, and in the spec requirement "The suite map covers every tracked file", state that a path matching any rule selects that rule's targets, and that `no_eval` applies only to paths no rule matches.
   - Add a map-test scenario: a `no_eval` pattern that matches a tracked file some rule also matches fails the map test and names that file and pattern.
2. **M2:**
   - In D4, set the job timeout from the rule `timeout-minutes > --timeout + the suite's normal wall time + margin`, for example `timeout-minutes: 120` with `--timeout 2400`. Alternatively, lower `--timeout` once per-file times are known.
   - In the Risks, require recording per-file times from the D6 WSL run or the first CI run, and confirming that no file normally comes near `--timeout`.
   - Correct the "CI suite job hangs" row of the Failure table to match.
3. **M3:**
   - In D4's per-job setup, check out with `fetch-depth: 0` and create a local `main` (for example `git branch main origin/main`), so `TestThisRepo.test_backfill_ranges` runs.
   - In D6, add that apply checks the first CI run's output for skipped tests and accounts for each one. Only the platform-only skips (Windows job objects, the Windows argument transport) are expected.
4. **M4:**
   - In D3, state that `--changed` reads `<root>/suites.json` and runs every git command in the repository that contains `--root` (`git -C <root> rev-parse --show-toplevel`).
   - Changed paths are relative to that toplevel, and the built-in `<suite>` rule is evaluated for `--root`'s path relative to it.
   - Tests build a scratch git repository with a root and a map inside it, never using the live checkout.

CHANGES_APPLIED: yes

## Rebuttals
