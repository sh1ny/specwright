# Proposal

## Why

M4 closed with eight known gaps filed as issues. Most are in the process and network bounds of ADR 0012 and in edge cases of the PR, finish and release scripts. M5 (Commits and VCS backends) closes them first, so that the commit and VCS work builds on scripts with no open holes. This change serves M5's exit criteria: every issue below is closed by a merged PR with a regression test in `evals/`; `evals/pr-pair`, `git-workflow`, `review-routes`, `update`, `release` and `finish` pass; an eval with a hung or oversized response shows `release.sh`, `finish.sh` and `update.sh` stopping within their deadline or bound with a named error; it ships as 0.8.1.

## What Changes

- **#111** `release.sh`'s six network commands (`git ls-remote` twice, `git fetch` of a tag, `git push` of a tag, `gh api --paginate`, `gh release view/create`) and `update.sh`'s one `git ls-remote` run under ADR 0012's deadline and byte bound, and report a limit by name (`deadline_exceeded`, `response_too_large`). When the tag push or the release creation is cut off, the outcome is unknown until a read-back decides it. `finish.sh` runs no network command (its `git`/`gh` network steps are the agent's, through `as.sh`); an eval now holds it to that. This closes ADR 0012's listed exceptions.
- **#113** The codex reviewer's answer is read from its `--json` event stream (the last completed `agent_message` item), which is already bounded while codex runs. The `-o` answer file is no longer used, so nothing codex writes escapes the bound.
- **#114** A reviewer or network command that exits before its deadline is judged by that exit, also when a process it started still holds its output. Its exit is observed when it happens, not at the next poll.
- **#116** On Windows, a process that a reviewer or network command started, and that still holds its output after the parent exits, is stopped with the tree. The Windows skips in the tests for this go.
- **#117** A fractional `SPECWRIGHT_NET_DEADLINE` lowers the watch's poll-wide deadline as it lowers each command's. One parse rule serves both.
- **#115** A code span between a closing keyword and an issue reference ends the closing list in both places that read closing lines. `Fixes `later` #31` no longer closes #31.
- **#110** When a bulk archive's undo re-runs the archive of a non-deferred member, a main spec deleted on the branch after the archive stays deleted. The warning says how.
- **#109** In `release.sh check --main`, a commit whose parent is unreadable on the branch counts as a version change when it matched a version that parent did not. A bump reverted through two unreadable versions, or by a readable commit right after an unreadable bump, is then no bump. **Amends** the `releases` requirement "An unreadable commit changes the version only when its parent is not among its versions".

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pr-script-runtime`: a command that exits before its deadline keeps its result whatever its children do; a child left holding the output is stopped on Windows too; the deadline override is parsed one way for each command and for the whole poll.
- `review-routes`: codex's answer comes from its event stream, bounded like OMP's; an exit before `review.timeout` is never a timeout; a reviewer's surviving child is stopped on Windows.
- `releases`: publish's network commands are bounded, and a cut-off write is decided by a read-back; the unreadable-commit rule compares an unreadable commit with an unreadable parent by their matched versions (#109).
- `install-update`: the release-tag lookup is bounded and names its limit.
- `change-finish`: `finish.sh` runs no network command; a spec deleted after a bulk archive stays deleted after the after-rerun script.
- `pr-descriptions`: a code span between a closing keyword and a reference ends the closing list.

## Impact

- Code: `skills/specwright-release/scripts/release.sh`, `scripts/update.sh`, `skills/specwright-pr/scripts/bounded.py`, `pr-snapshot.sh`, `pr-pair.sh`, `skills/specwright-review/scripts/review-run.sh`, `skills/specwright-finish/scripts/finish.sh`. New identical copies of `bounded.py` go in the release and review skills, kept identical by a test (see design).
- Tests: `evals/release`, `evals/update`, `evals/finish`, `evals/review-routes`, `evals/pr-pair` (including new `POST /markdown` recordings for #115), and the codex fake in `evals/fakes/reviewcli.py`.
- Docs: `openspec/architecture.md` (Resource bounds, Known gaps, the ADR 0012 index row); the release, review and PR skill text where it names the bounds.
- ADR: 0014 supersedes 0012. It keeps 0012's bounds and drops its exceptions. It also records two choices that change 0012's text: codex's answer comes from its event stream, and `bounded.py` is copied into each skill that runs bounded processes (see design).
- Roadmap note: `finish.sh` has no network command to bound, so the exit criterion is met for it by the eval proving that, not by a bound.
