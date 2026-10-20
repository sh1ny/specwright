# Proposal

## Why

The PR scripts and the reviewer runner trust GitHub and the reviewer CLIs to answer in reasonable time and size. When one doesn't, the run hangs or grows without limit.

- **#40:** no `gh` or `git` network call in `pr-pair.sh`, `pr-snapshot.sh`, `pr-reply.sh` or `as.sh` has a deadline. Paged lists (`gh_list`, the reaction cursor loop) are buffered whole, with no cap. With `pr.after_limit: issues` the agent scans every repository issue once per finding, so F findings × I issues records. The watch timeout counts sleeps, not elapsed time. A hung poll therefore blocks both the timeout report and the ownership check.
- **#80:** `review-run.sh run` checks the reviewer's output size only after the CLI exits or hits `review.timeout` (default 20m). Runaway stdout is bounded only by free disk, and stderr is never checked.
- **#64:** `pr-pair.sh` `without_code()` approximates GitHub's CommonMark renderer to find a PR's real closing references. Each review round on #62 found another construct it got wrong. Two are still open: a list item's paragraph continued and indented four columns, and a quote-marked fence line that closes a fence opened outside the quote.

This is change 4 of **M4 - Cost tier** (release 0.7.2). The cost tier needs bounded, predictable script runs before cheaper models lean on them. This change advances these exit criteria:
- every issue in the milestone's changes is closed by a merged PR, and each code fix has a regression test in `evals/`;
- `evals/pr-pair` and `evals/review-routes` pass;
- an eval with a hung or oversized `gh` response shows each PR script stopping within its deadline or bound with a named error, and an eval shows a reviewer run stopped once its output passes the bound, with no partial review recorded;
- each change ships as its own release.

## What Changes

- **Bounded network commands (#40).** A new shared runner, `skills/specwright-pr/scripts/bounded.py`, starts a command, kills its process tree when the deadline passes, and caps the bytes it reads from the command's stdout.
  - `pr-pair.sh` loads it for every `gh` and `git` network call, including `token_for` and `ambient_login`.
  - `pr-snapshot.sh`, `pr-reply.sh` and `as.sh` route their own `gh` calls through it.
  - A deadline or size stop is a named error: `deadline_exceeded` or `response_too_large`. In `pr-pair.sh` it is GitHub state unknown (exit 3). The bash scripts name it on stderr and keep their existing failure exits.
  - Paged reads are capped the same way. The GraphQL reaction loop also gets a page cap.
- **Elapsed-time watch.** `pr-snapshot.sh --wait` measures `--timeout` against the clock. It never sleeps past the timeout. Each poll, the first snapshot included, has one 120-second deadline, so the timeout is always reported. Ownership is checked before each poll and before the timeout report.
- **One issue read per pass.** A new `pr-pair.sh item-issues` subcommand reads the repository's issues once, within the bound. It returns the issue for every `specwright:pr-item` id it was given. The `after_limit: issues` step in `specwright-pr` calls it once per pass instead of scanning once per finding.
- **Reviewer output bounded while it runs (#80).** `review-run.sh`'s `capture` watches the sizes of the stdout and stderr files, and codex's last-message file, while the reviewer runs. Once one passes its bound, the process tree is stopped the way the timeout path stops it, and the run fails with `status: invalid` and `output too large`, naming the stream. No result or record is written. Probes are bounded the same way.
- **Closing references from GitHub's rendering (#64).** `closing-check` and `closed-check` render the PR body with `POST /markdown` (`mode: gfm`, the PR's repository as `context`). They read closing lines from the rendered text outside `<pre>` and `<code>`. The hand parser (`without_code` and its helpers) is removed. The closing-keyword rules (one closing list per keyword, `Related:`, issue scope) are unchanged. A failed render is GitHub state unknown, like any other failed lookup. Real renderings are recorded once as eval fixtures, so the fake `gh` serves GitHub's actual HTML.
- Release 0.7.2 (patch): `VERSION`, the README badge and the skill `metadata.version` fields.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `pr-script-runtime`: new requirements. Every network command in the PR scripts has a deadline and a response bound. Passing either is a named stop, not a hang or an unbounded read.
- `pr-watch`: a new requirement that the watch timeout is elapsed time and is always reported, even when a poll hangs.
- `feedback-passes`: a new requirement that existing PR-item issues are found in one bounded read per pass, not one scan per finding.
- `review-routes`: a new requirement that reviewer stdout, stderr and codex's answer file are bounded while the CLI runs. Passing a bound stops the reviewer and records nothing.
- `pr-descriptions`: a new requirement that closing references are read from GitHub's rendering of the description, including the two cases the hand parser got wrong. A failed render is GitHub state unknown.

## Impact

- New: `skills/specwright-pr/scripts/bounded.py`. It is stdlib-only, runs under the scripts' existing Python 3.8+ prerequisite, and is installed with the skill folder. `pr-snapshot.sh`, `pr-reply.sh` and `as.sh` now need that Python too.
- `skills/specwright-pr/scripts/pr-pair.sh`: `run`, `gh`, `git_net`, `token_for`, `ambient_login`, `gh_list`, `has_reaction`, the new `item-issues` subcommand, and the render-based `intended_issues` (with `without_code` and its helpers removed).
- `skills/specwright-pr/scripts/pr-snapshot.sh`, `pr-reply.sh`, `as.sh`: their `gh` calls go through the runner, and the watch loop measures elapsed time.
- `skills/specwright-pr/SKILL.md`: the `after_limit: issues` step.
- `skills/specwright-review/scripts/review-run.sh`: `capture`.
- `openspec/architecture.md`: the in-force index row for the new ADR 0012, the Resource-bounds rows for network commands and review runs, the #40 Known-gaps row, and the Script I/O contract. `docs/adr/0012-*.md` is new.
- `openspec/specs/` deltas for the five capabilities above.
- Tests:
  - `evals/fakes/gh.py` gains a hang/delay injection, an oversized-response injection, a `POST /markdown` endpoint serving recorded renderings, and issue-list support for `item-issues`.
  - New cases go in `evals/pr-pair/test_pr_pair.py`, `test_pr_snapshot.py`, `test_pr_reply.py` and `test_as_sh.py`. The existing `test_pr_snapshot.py` cases that relied on "timeout counts polls" move to short elapsed timeouts.
  - `evals/review-routes/test_review_run.py` gains cases using `evals/fakes/reviewcli.py` with a flood option.
- Deadlines and bounds are fixed defaults in the scripts. Test-only environment overrides keep evals fast. No configuration key is added and no dependency changes.
- Out of scope: commands the agent runs directly from skill text (`[as] gh ...`), which the harness's own tool timeout bounds; #9 (snapshot pagination).
