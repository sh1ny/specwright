# Tasks

## Test map

Timing scenarios run with the test-only overrides from design D2:
- `SPECWRIGHT_NET_DEADLINE`, `SPECWRIGHT_NET_PAGED_DEADLINE`, `SPECWRIGHT_NET_MAX_BYTES`;
- the watch's per-poll deadline, which reads `SPECWRIGHT_NET_DEADLINE` and defaults to 120.

They assert the same bound relations as the specs. "Deadline plus 10 s" becomes "the override plus 10 s". A test that runs with the real defaults is marked as such.

| Requirement | Scenario | Test file | Test name | State |
|---|---|---|---|---|
| pr-script-runtime → Network commands have a deadline | GitHub answers in time | evals/pr-pair/test_pr_pair.py | ClosingCheck.test_closing_check_match (unchanged, re-run under the runner) | green |
| pr-script-runtime → Network commands have a deadline | Hung gh call in pr-pair.sh | evals/pr-pair/test_pr_pair.py | Bounded.test_discover_hung_gh_deadline_exceeded | red |
| pr-script-runtime → Network commands have a deadline | Hung gh call in a bash PR script | evals/pr-pair/test_pr_reply.py | Bounded.test_reply_hung_gh_deadline_exceeded_no_temp_file | red |
| pr-script-runtime → Network commands have a deadline | Hung credential lookup in as.sh | evals/pr-pair/test_as_sh.py | Bounded.test_token_lookup_hung_exits_3_named | red |
| pr-script-runtime → GitHub responses are bounded | Large but bounded list | evals/pr-pair/test_pr_pair.py | Bounded.test_discover_large_list_read_whole | red |
| pr-script-runtime → GitHub responses are bounded | Oversized paginated read | evals/pr-pair/test_pr_pair.py | Bounded.test_paginated_read_too_large | red |
| pr-script-runtime → GitHub responses are bounded | Reaction loop past its page cap | evals/pr-pair/test_pr_pair.py | Bounded.test_reaction_loop_page_cap | red |
| pr-watch → The watch timeout is elapsed time | Slow polls count toward the timeout | evals/pr-pair/test_pr_snapshot.py | WatchElapsed.test_slow_polls_count_toward_timeout | red |
| pr-watch → The watch timeout is elapsed time | Poll hangs during the watch | evals/pr-pair/test_pr_snapshot.py | WatchElapsed.test_hung_polls_exit_1_within_bound | red |
| pr-watch → The watch timeout is elapsed time | Takeover after a hung poll | evals/pr-pair/test_pr_snapshot.py | WatchElapsed.test_takeover_during_hung_poll_exits_4 | red |
| pr-watch → The watch timeout is elapsed time | First snapshot hangs | evals/pr-pair/test_pr_snapshot.py | WatchElapsed.test_first_snapshot_hung_exits_1 | red |
| feedback-passes → PR-item issues are found in one read per pass | Several findings, some already tracked | evals/pr-pair/test_pr_pair.py | ItemIssues.test_one_read_finds_tracked_item | red |
| feedback-passes → PR-item issues are found in one read per pass | Store-backed pass with items in both repositories | evals/pr-pair/test_pr_pair.py + evals/pr-pair/test_skill_text.py | ItemIssues.test_reads_only_its_repo_as_its_login; SkillText.test_after_limit_issues_one_lookup_per_repo | red |
| feedback-passes → PR-item issues are found in one read per pass | Pull requests carrying the marker | evals/pr-pair/test_pr_pair.py | ItemIssues.test_pull_request_with_marker_ignored | red |
| feedback-passes → PR-item issues are found in one read per pass | Issue list cannot be read | evals/pr-pair/test_pr_pair.py + evals/pr-pair/test_skill_text.py | ItemIssues.test_read_failure_exits_3_named; SkillText.test_after_limit_issues_files_nothing_on_lookup_failure | red |
| review-routes → Reviewer output is bounded while the CLI runs | Output within the bounds | evals/review-routes/test_review_run.py | OutputBound.test_omp_stream_within_bounds_passes | red |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stdout | evals/review-routes/test_review_run.py | OutputBound.test_claude_stdout_flood_stopped_nothing_written | red |
| review-routes → Reviewer output is bounded while the CLI runs | Runaway stderr | evals/review-routes/test_review_run.py | OutputBound.test_codex_stderr_flood_stopped_review_unchanged | red |
| review-routes → Reviewer output is bounded while the CLI runs | Codex answer file over the bound | evals/review-routes/test_review_run.py | OutputBound.test_codex_answer_file_flood_stopped | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Continued list paragraph | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_continued_list_paragraph_counts | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Quote-marked fence line inside a fence | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_quote_marked_fence_line_stays_code | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Code span inside a word, rendered | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_code_span_inside_word_no_join | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Reference on the next source line | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_soft_break_ends_closing_list | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Issue URL on a closing line | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_issue_url_counts | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Reference to another repository | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_other_repo_reported_outside | red |
| pr-descriptions → Closing references are read from GitHub's rendering | Rendering fails | evals/pr-pair/test_pr_pair.py | ClosingRendered.test_render_failure_unknown_both_checks | red |

## 1. ADR 0012 and architecture

- [x] 1.1 Write `docs/adr/0012-pr-scripts-and-reviewer-runs-are-bounded.md` (MADR-short, `Status: accepted`, today's date) with the decision text of design.md's ADRs section, including the known exceptions (`release.sh`, `finish.sh`, `update.sh`). Verify: the file exists with Status, Date, Context, Decision, Consequences.
- [x] 1.2 File one GitHub issue for the known exceptions, "Bound network commands in release.sh, finish.sh and update.sh", as KintsugiBot, fenced. Reference it from ADR 0012. Verify: the issue URL is in the ADR.
- [x] 1.3 Update `openspec/architecture.md`, per design.md's ADRs section:
  - the in-force index row for 0012;
  - the "Network commands" and "Review run" Resource-bounds rows;
  - the #40 Known-gaps row, narrowed to the new issue;
  - the Script I/O contract: Python 3.8+ for all four PR scripts, the `item-issues` output, and `deadline_exceeded`/`response_too_large`.

  Verify: `grep -n 0012 openspec/architecture.md` shows the index row; the old "No Specwright deadline" text is gone.

## 2. Fakes for hangs, floods and rendering

- [x] 2.1 Extend `evals/fakes/gh.py`:
  - `"hang": [regex | {match, pid_file}]`: sleep forever after writing its PID;
  - `"delay": [{match, seconds}]`;
  - `"flood": [{match, bytes}]`: print that many bytes of valid-looking JSON array pages;
  - a `POST markdown` endpoint (`--input` file) that serves `evals/pr-pair/fixtures/markdown.json` by SHA-256 of `mode` + `text`, ignores `context`, and exits 1 with `no recorded rendering` when the key is missing (design D8);
  - issue-list support with bodies and `pull_request` markers for `item-issues`.

  Add tests in `evals/pr-pair/test_fake_gh.py`. Verify: `python -m unittest evals.pr-pair.test_fake_gh` (or `discover evals/pr-pair -p test_fake_gh.py`) passes.
- [ ] 2.2 Extend `evals/fakes/reviewcli.py` with `FAKE_<CLI>_FLOOD_STDOUT`, `_FLOOD_STDERR` and `_FLOOD_ANSWER` (bytes to write, then keep running until killed, writing `_PID_FILE`). Verify: a direct run writes past the requested size and its PID file names a live process until killed.

## 3. Bounded runner

- [x] 3.1 Write the failing `evals/pr-pair/test_bounded.py`. It covers:
  - deadline → `deadline_exceeded`; the child's PID (from a PID file) is gone within deadline + 10 s;
  - stdout over the bound → `response_too_large`, child gone;
  - normal exit passes rc, stdout and stderr through;
  - `SPECWRIGHT_NET_DEADLINE_AT` caps the deadline;
  - secret mode writes no file under a fresh `TMPDIR`/`TEMP` (checked by listing it) and stops a hung lookup within its deadline + 5 s;
  - the CLI exit codes 124/125 and the `bounded: <limit>: <cmd>` stderr line;
  - a `#!/bin/sh` `gh` started through `"$BASH" -c 'exec gh "$@"'` runs on Windows.

  Verify: it fails because `bounded.py` is missing.
- [x] 3.2 Implement `skills/specwright-pr/scripts/bounded.py` per design D1/D2: file-backed mode, secret mode with the post-kill `communicate(timeout=5)`, `kill_tree` by PID only, the 0.1 s poll, the defaults and env overrides in its header, and the CLI. Verify: `test_bounded.py` passes.

## 4. pr-pair.sh under the runner

- [ ] 4.1 Write failing tests in `evals/pr-pair/test_pr_pair.py` class `Bounded`, per the test map rows for pr-pair.sh. Add one for `cmd_merge` (a hung PUT with a merged read-back reports `merged`, and with an open read-back reports unknown). Verify: they fail.
- [ ] 4.2 Load `bounded.py` by path (`importlib.util.spec_from_file_location`, `PR_PAIR_DIR`) and route the network calls through it per design D3:
  - `gh` (paged when `--paginate` is in the args), `git_net`, `token_for` (its `gh auth token` in secret mode at `pr-pair.sh:235`; its `gh api user` at `:240` file-backed) and `ambient_login`;
  - limits raise `deadline_exceeded`/`response_too_large` with code 3, `unknown: true`;
  - `cmd_merge`'s PUT passes `limit_ok=True`;
  - `has_reaction` stops at 50 pages.

  Verify: the `Bounded` tests pass, flip their rows green, and the whole `python -m unittest discover evals/pr-pair` stays green (GitHub-answers-in-time row).

## 5. Bash PR scripts under the runner, and the elapsed-time watch

- [ ] 5.1 Write failing tests: `test_as_sh.py` `Bounded` (hung `gh auth token` in the fenced path and in `--resolve`, each exit 3 naming `deadline_exceeded`, fenced command not run), `test_pr_reply.py` `Bounded`, and `test_pr_snapshot.py` `WatchElapsed` (four rows). Move the existing tests that relied on "timeout counts polls" (`test_pr_snapshot.py:365`) to `--timeout 3 --interval 1` elapsed bounds. Verify: the new tests fail; the moved tests still describe their original intent.
- [ ] 5.2 Add the shared header block (design D1) to `as.sh`, `pr-reply.sh` and `pr-snapshot.sh`: Python discovery (exit 2 `no_python`), `SW_DIR`, `SW_BASH`, and the `gh()` function. The hook must pass `--secret` as well as `--paged` (review S7: `${SW_SECRET:+--secret}`, or a direct `bounded.py --secret` call), so as.sh's two `gh auth token` calls never reach a file. Verify: a test asserts no file appears under a fresh `TEMP` during an as.sh token lookup.
- [ ] 5.3 Restructure as.sh's five lookups (design D3). The review's S6 corrects the line numbers: `--help` at `:69`; `--resolve`'s `api user` at `:75` and `gh auth token` at `:77`; the fenced `gh auth token` at `:82`; `api user` at `:86`. Each checks for 124/125 before its existing message. Verify: the `test_as_sh.py` `Bounded` tests pass and the existing as.sh tests stay green.
- [ ] 5.4 Route `pr-reply.sh`'s `gh` calls through the runner. Verify: its `Bounded` test passes (exit non-zero, `deadline_exceeded` on stderr, no temp file) and the existing reply tests stay green.
- [ ] 5.5 Rewrite the `pr-snapshot.sh --wait` loop per design D5:
  - `start=$SECONDS` before the first snapshot;
  - per-poll `SPECWRIGHT_NET_DEADLINE_AT`, the first snapshot included, unset after each poll;
  - a failed first snapshot is `ok=0` with no base, and a later good poll becomes the base;
  - when that later base has `"complete":false`, wake as `incomplete` at once, as the first snapshot does today (review S8);
  - ownership checked before each poll and before the timeout report;
  - `"waited"` is elapsed seconds.

  Update the script header comment ("Needs only gh" → gh and Python 3.8+; timeout is elapsed time). Verify: the `WatchElapsed` tests and all of `test_pr_snapshot.py` pass; flip the rows green.

## 6. One issue read per pass

- [ ] 6.1 Write failing `ItemIssues` tests in `test_pr_pair.py`, and the two `SkillText` tests in `evals/pr-pair/test_skill_text.py`, per the test map. Verify: they fail.
- [ ] 6.2 Implement `pr-pair.sh item-issues --repo o/n --item <id>...` per design D4: one paged read with the `--jq` filter, whole-line marker match, lowest number wins, output `{"ok":true,"found":{...},"missing":[...]}`, exit 3 naming the error. Verify: the `ItemIssues` tests pass.
- [ ] 6.3 Rewrite the `after_limit: issues` step in `skills/specwright-pr/SKILL.md` (`:119-123`). It calls `item-issues` once per repository per pass, as that repository's login (`[as]` run login in the code checkout, store login in the store checkout), passing only that PR's items. On exit 3 it files nothing and reports the lookup not done with the error name. Verify: the `SkillText` tests pass; flip the rows green.

## 7. Reviewer output bounded while it runs

- [ ] 7.1 Write the failing `OutputBound` tests in `evals/review-routes/test_review_run.py` per the test map. Each flood test asserts the reviewer PID is gone within 5 s of the bound, `status: invalid`, `output too large` naming the stream, and no `--out` or pre-ship record written (and `review.md` byte-identical for the design kind). Verify: they fail.
- [ ] 7.2 Rewrite `capture` in `skills/specwright-review/scripts/review-run.sh` per design D6:
  - a 0.25 s loop over elapsed time, stdout/stderr sizes and the optional `watch` file;
  - `over` in `Captured`;
  - per-route bounds from `cmd_run`; probes at 1 MiB;
  - `cmd_run` maps `over` before every other check.

  Verify: the `OutputBound` tests and all of `python -m unittest discover evals/review-routes` pass; flip the rows green.

## 8. Closing references from GitHub's rendering

- [ ] 8.1 Write `evals/pr-pair/record_markdown.py`. It collects every PR body the closing tests use (the existing `ClosingCheck`/`ClosedCheck` cases and the new `ClosingRendered` cases), renders each through the real `POST /markdown` (`mode: gfm`, `context: sh1ny/specwright`) via `as.sh KintsugiBot`, and writes `evals/pr-pair/fixtures/markdown.json` keyed per design D8. Run it once and commit the fixture. Record in this task line whether `gfm` mode returned soft breaks as `\n` or `<br>` (the design's open question). Verify: the fixture has one entry per body. Result: <fill in>.
- [ ] 8.2 Add a test that every body the closing tests send has a recording, and write the failing `ClosingRendered` tests per the test map. Verify: the coverage test passes; the `ClosingRendered` tests fail against the hand parser.
- [ ] 8.3 Implement the rendered read per design D7:
  - render with the request in a temp file removed on every exit, as the PR repository's login;
  - an `HTMLParser` with code replaced by a space, the full block list, and newline-in-text as a line end;
  - `intended_issues` over the rendered lines;
  - a failed or limited render is unknown, exit 3;
  - remove `without_code` and its helpers.

  Verify: the `ClosingRendered` tests and every existing `ClosingCheck`/`ClosedCheck` test pass; flip the rows green.
- [ ] 8.4 Update `skills/specwright-pr/references/description.md` and any skill text that describes how closing lines are found (code, comments) so it says they are read from GitHub's rendering. Verify: `grep -rn "without_code\|CommonMark" skills/` finds nothing stale, and `evals/pr-pair/test_skill_text.py` passes.

## 9. Release and integration

- [ ] 9.1 Run `release.sh bump --to 0.7.2` and verify with `release.sh check --main origin/main`.
- [ ] 9.2 Run the milestone eval suites `evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update` and `evals/release` (`python -m unittest discover <dir>` each), and `openspec schema validate specwright` and `openspec validate bound-pr-scripts --strict`. Verify: all pass, and every test map row is green.

## Workflow follow-up

- Pre-ship review, ship (PR closing #40, #80 and #64 with one `Fixes` line each), watch, merge, archive and release 0.7.2 follow the specwright-commit, specwright-pr and specwright-finish skills.
