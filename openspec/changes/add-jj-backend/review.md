# Review

## Metadata

- **Round:** 2
- **Prior round:** Round 1, VERDICT: REVISE. C1: a Git fetch moves or conflicts a tracked jj bookmark. M1: a full `jj git fetch` deletes the change bookmark before `branch-check` runs. M2: the push deadline and `unmanaged_jj` broke the Git flow. M3: no carry-over path for a non-empty `@`. M4: the jj undo plan was under-specified. S1-S6: wording and coverage. All of these are resolved in this revision (see below).
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:**
  - openspec/changes/add-jj-backend/{proposal.md, design.md, specs/vcs-backends/spec.md, specs/github-identity/spec.md, specs/eval-runner/spec.md, review.md (round 1)}.
  - The review instruction (`openspec instructions review --change add-jj-backend --json`).
  - openspec/roadmap.md (M5), openspec/specs/eval-runner/spec.md and the docs/adr/ index (0001-0016).
  - skills/specwright-branch/SKILL.md (steps 1-8 and the store gate), skills/specwright-finish/SKILL.md (Resume, `## local`, `## pr`), skills/specwright-release/SKILL.md (publish), skills/specwright-roadmap/SKILL.md:20, skills/specwright-pr/SKILL.md (fetch and pull lines 82, 140, 157).
  - skills/specwright-pr/scripts/as.sh:60-80,150-215 and skills/specwright-pr/scripts/pr-pair.sh:1227-1243.
  - skills/specwright-release/scripts/release.sh:15-40, 1277-1330, 1379, 1733.
  - A grep of `origin/` and `refs/remotes` reads across skills/ and scripts/.
  - CLI claims checked against jj 0.46.0 in a scratch colocated clone under /tmp, since removed.
  - Skill loaded: jj-workflow (C:/Users/bgshi/.claude/skills/jj-workflow/SKILL.md).
- **Re-check run (2026-10-29):** a fresh-context reviewer re-checked only Required Changes 1-3 against proposal.md, design.md (D3, D12, Diagrams, Failure & Visibility, Mechanism Ledger), specs/vcs-backends/spec.md and skills/specwright-release/scripts/release.sh:852-853, 1278-1332, 1370-1395. The jj 0.46.0 flags the changes use (`jj file list -r`, `jj bookmark set --allow-backwards`, `jj git fetch --branch`) were confirmed with `--help`. No new full review was opened.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes, or an edit confined to the proposal's `## Release Notes` section) voids it. -->

## Findings

### Round 1 resolution

- **C1, resolved for reads.**
  - D12 takes Option A: `git fetch --refmap= origin refs/heads/<main>` writes only `FETCH_HEAD`, and the step reads the printed sha.
  - The spec requirement "Fetches for reading move no jj bookmark" has tracked-main and diverged scenarios.
  - The Context smoke-run claim is corrected.
  - D11 covers both tracking states.
  - `remote_contains` gets `--refmap=`.
  - The pull half is only partly resolved. See the new M1 below.
- **M1, resolved.** The pull fetches `--branch <main>` only, and a spec scenario keeps the bookmark when the remote head branch is deleted.
- **M2, resolved.** The push stays unbounded on both backends (D7, ADR 0017 note, spec "Git push" scenario). `unmanaged_jj` is replaced by a note (D4, spec "A jj repo on the Git backend is reported, not blocked").
- **M3, resolved.**
  - D3 carries a non-empty `@` with `jj rebase -r @ -o <target>` and rolls back on conflict.
  - I verified on 0.46.0 that `jj rebase -r @ -o <old parent>` after a conflicted carry restores the original content ("Existing conflicts were resolved"). The file on disk is back to the user's edit.
  - The "commit on the current branch" offer is gone (Flow & State Gaps).
- **M4, resolved.** D13 and the spec now cover:
  - the `@` guard;
  - `jj restore --from`;
  - the committed-on-another-branch `jj new <b>`;
  - the wrong-branch stop.

  The forbidden list (`git checkout`, `git rm`, `git read-tree`, `git restore`, `git commit`) now matches "No other Git write".
- **S1-S6, resolved.**
  - S1: the probe runs in `state`.
  - S2: "the one bookmark other than main".
  - S3: `jj abandon` replaces `op restore`.
  - S4: added files with `/` normalisation.
  - S5: roadmap branches use their branch name as scope.
  - S6: `vcs_script_missing`.

### Critical (blocking)

None.

### Moderate

**M1. On jj the pull conflicts a tracked main that diverged, and it stops when local main is merely ahead. `git pull --ff-only` handles both cases differently today.**

D12 step 2 checks main only after `jj git fetch --remote origin --branch <main>` has run.

- **Diverged, tracked.** I checked this on jj 0.46.0: a `jj git clone --colocate` repo, a local commit on main, origin moved, then `jj git fetch --remote origin --branch main`. The result was `main (conflicted)` with three targets.
  - vcs.sh then stops with `not_fast_forward`, but main is now conflicted by Specwright's own pull. Every later `state` stops on the conflicted bookmark, and `jj new main` fails.
  - The spec scenario "Local main diverged" says only "stops ... and no branch is deleted". It never asserts that main is left unconflicted. The design names no recovery.
  - `git pull --ff-only` leaves main untouched in this case. This is the C1 failure again, moved from reads to the pull.
- **Local ahead.** In pr mode, finish's "M and B" row (the change was merged locally and main was never pushed) runs `[as] git pull --ff-only` and then `branch-check` (skills/specwright-finish/SKILL.md, the Resume table).
  - On Git, a local main ahead of origin is "Already up to date", exit 0.
  - On jj, main != `main@origin`, so D12 and the spec ("Afterwards local main SHALL equal the remote's main ... Otherwise ... `not_fast_forward`") stop the cleanup. Git continues.

**M2. The release publish fetch is missing from D12, and the "read the sha instead of `origin/<main>`" rule breaks `release.sh`.**

- **The publish fetch.** `specwright-release` publish step 1 runs `[as] git fetch --no-tags origin <main>` and passes `--main origin/<main>`. The step is reached from finish, watch and roadmap close on a jj repo.
  - D12's list (gate, roadmap, ship/watch base, finish refresh) does not include it. On jj it stays a remote-tracking fetch.
  - That is the C1 effect: a tracked main moves off `@-`. It is conflicted after a `finish: local` merge followed by a publish.
  - It also breaks the spec's "No other Git write runs under jj" (the fetch has no empty refmap).
- **A sha for `--main`.** If the fetch is converted and `--main <sha>` is passed instead, `release.sh` derives the GitHub base branch from that argument:
  - `main_name = a["main"]` (release.sh:1379);
  - `branch = ref[len("origin/"):] if ref.startswith("origin/") else ref` (release.sh:1326);
  - so a sha becomes `pulls?base=<sha>`, which returns no merged PRs. Store-backed notes in pr mode then lose their PR references.
- **The store default.** `store_setup` defaults the store's main to `refs/remotes/origin/<n>` (release.sh:1288). On a jj store that ref moves only on a pull, so the notes can be built from a stale store main.

**M3. A jj commit silently drops a named path that jj refused to snapshot. The group commit then misses files with no stop.**

D3's pre-check ("the named paths have changes in `@`", `jj diff -r @ --name-only <filesets>`) passes when any one named path changed. I checked on jj 0.46.0:
- A group named `a.txt` (modified) and `big.bin` (new, 2 MB).
- jj refuses to snapshot new files over `snapshot.max-new-file-size`, which defaults to 1 MiB. It printed only a warning ("No matching entries for paths: big.bin").
- `jj commit 'root:"a.txt"' 'root:"big.bin"' -m ...` exited 0 with only `a.txt`. `git status` still showed `?? big.bin`.

The same happens for a named path that is gitignored. On Git, `git add -- big.bin` commits it, and `git add` of an ignored path fails loudly.

The consequences:
- The commit carries the group's `Specwright-Task:` trailers (ADR 0016) without the files.
- The spec's "commit exactly the named paths" is violated, and no scenario catches it.
- Binary assets over 1 MiB are routine in the gamedev dogfood projects.

### Suggestions

**S1.** The CI suite runs only on Linux (D11). There jj never prints `\` paths, so the "Carry-over on Windows" scenario cannot fail in CI. Cover the separator normalisation with a test on captured `\`-separated output, so the scenario is checked on every PR.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **The pull (M1).** In design D12 "Pulls" and in the spec requirement "The jj pull fetches only main and only fast-forwards":
   - Before any `jj git fetch`, run the D12 read fetch (`git fetch --refmap= origin refs/heads/<main>`) and classify with `git merge-base --is-ancestor`:
     - (a) the fetched commit is an ancestor of local main (equal or ahead): done, with no jj fetch and no move;
     - (b) local main is an ancestor of the fetched commit: run `jj git fetch --remote origin --branch <main>`, then the existing tracked or untracked move;
     - (c) otherwise: stop with `not_fast_forward` before any jj fetch.
   - If main is conflicted after step (b) anyway (origin moved again in between), set main back to its pre-pull commit (`jj bookmark set <main> -r <old> --allow-backwards`) and stop with `not_fast_forward`.
   - In the spec, change "local main SHALL equal the remote's main" to allow case (a).
   - Add the THEN "main is not conflicted and still points at its local commit" to the "Local main diverged" scenario.
   - Add a scenario: "Local main ahead (pr mode, change merged locally): the pull succeeds without moving main, and `branch-check` runs."
   - Update the fetch/pull sequence diagram and the Failure table row to match.

   **Re-check: applied.**
   - design.md D12 "Pulls" steps 1-3 now run the read-only fetch first, record `<old>`, and classify with `git merge-base --is-ancestor` into the three cases (a), (b) and (c). Case (c) stops before any jj fetch, and step 3 runs `jj bookmark set <main> -r <old> --allow-backwards` on a conflicted main.
   - The spec requirement "The jj pull fetches only main and only fast-forwards" allows the equal-or-ahead case with no jj fetch. "Local main diverged" now asserts that "main is not conflicted and still points at its local commit". The new scenarios "Local main ahead" (no jj fetch, main unmoved, `branch-check` runs) and "Remote moved again during the pull" are present.
   - The Diagrams sequence (fetch-main, pull) and the two Failure & Visibility rows for `vcs.sh pull` (jj) match.
2. **Release fetches (M2).**
   - Add `specwright-release` publish step 1 (and the `--main` it passes to `untagged`/`status`/`publish`) to D12's list of read-only fetches.
   - Specify how `release.sh` gets the base branch name when it reads a sha. For example, keep `--main` as the branch name and add a separate commit argument (`--main-commit <sha>`) for the history reads. Or have `merged_pulls` take the branch from the settings when `--main` is not `origin/<name>`.
   - Say what `store_setup` reads on a jj store, for example `--store-main <sha>` from the store's `fetch-main`.
   - Add a spec scenario under "Fetches for reading move no jj bookmark": "Release publish on jj with main tracked: no bookmark moves, and the notes list the merged PRs of the base branch by name."
   - Add `release.sh` to the Impact scripts list in proposal.md.

   **Re-check: applied.**
   - design.md D12 "Read-only fetches" lists `specwright-release` publish step 1. Its "Release" bullet passes the fetched commit as `--main <sha>`, adds a new `--base <branch>` that `merged_pulls` uses when given (release.sh:1326), and passes the store's fetched commit as `--store-main <sha>`. The store never falls back to `refs/remotes/origin/<main>` (release.sh:1288).
   - Checked in the code: `--store-main` is an existing option of `status` and `publish` (release.sh:1771-1777). `ref_exists` uses `rev-parse --verify <ref>^{commit}` (release.sh:852-853), so it accepts a sha. Only `merged_pulls` derives the branch name from `--main` (release.sh:1379-1380), so `--base` covers that one path.
   - spec "Fetches for reading move no jj bookmark" names release publish and has the scenario "Release publish on jj with main tracked": no bookmark moves, the history reads use the fetched commit, and the notes list the base branch's merged PRs by its name.
   - proposal.md Impact lists `release.sh` taking `--base <branch>`.
3. **Untracked named paths (M3).**
   - In D3's commit steps and the spec requirement "On jj a commit takes only its named paths", add a check before `jj commit`: every named path that exists on disk must be tracked in `@` (for example, `jj file list -r @ <fileset>` is non-empty).
   - Otherwise stop with `path_not_tracked`, naming the path and the reason (over `snapshot.max-new-file-size`, or ignored), before any write.
   - Add a spec scenario: "A named new file over jj's snapshot size limit: the commit stops with `path_not_tracked`, no commit is made, and the bookmark does not move."
   - Add a matching Mechanism Ledger row.

   **Re-check: applied.**
   - design.md D3 "Commit" step 3 checks, before `jj commit`, that every named path on disk is tracked in `@` (`jj file list -r @ <fileset>`). Otherwise it stops with `path_not_tracked`, naming the path and the likely reason (ignored, or over `snapshot.max-new-file-size`).
   - The spec requirement "On jj a commit takes only its named paths" adds the stop-before-any-write clause and the scenario "Named file jj did not snapshot" (a 2 MB new file: `path_not_tracked`, no commit, the bookmark does not move).
   - The Mechanism Ledger has a `path_not_tracked` pre-check row, and Failure & Visibility has a matching `vcs.sh commit` (jj) row.
   - Non-blocking observation: the check runs after the `nothing_to_commit` check (step 2). A group whose only named path is an untracked over-limit file therefore stops with `nothing_to_commit`, not `path_not_tracked`. It still stops before any write, so the required behaviour holds, but the error names the wrong reason. Running step 3 before step 2 would name it correctly.

CHANGES_APPLIED: yes

## Rebuttals
