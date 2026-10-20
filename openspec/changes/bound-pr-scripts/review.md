# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (specwright-reviewer, Claude Code)
- **Reviewed:** proposal.md, design.md, specs/{pr-script-runtime,pr-watch,feedback-passes,review-routes,pr-descriptions}/spec.md of `bound-pr-scripts`; openspec/architecture.md; ADRs 0002, 0007, 0008 (docs/adr/); main specs pr-script-runtime, pr-watch, pr-descriptions, review-routes, feedback-passes; skills/specwright-pr/scripts/pr-pair.sh (process helpers, gh_list, ambient_login, ensure-pr, hand parser, intended_issues, closing-check, closed-check, has_reaction, merge), pr-snapshot.sh, pr-reply.sh, as.sh; skills/specwright-pr/SKILL.md (feedback step 8, after the limit); skills/specwright-review/scripts/review-run.sh (kill_tree, capture, probe, cmd_run); skills/specwright-release/scripts/release.sh (network calls only); evals/git-workflow/fixtures.py (install_fake_gh); evals/pr-pair/snapfix.py, test_pr_snapshot.py (watch tests), test_pr_pair.py (closing tests). Re-check: proposal.md, design.md, specs/{pr-watch,feedback-passes,pr-descriptions,pr-script-runtime,review-routes}/spec.md as edited; as.sh:36-90, pr-pair.sh:200-250 and :643-652, pr-snapshot.sh:400-500, pr-reply.sh `gh` calls, review-run.sh:308-363. Re-check 2: design.md D1, D3, D5 and the State & Ownership table; specs/pr-watch/spec.md; as.sh:60-95, pr-pair.sh:228-248 and :640-655, pr-snapshot.sh:400-500.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. D7 drops code text with no separator, which breaks an existing closing-reference scenario.**
D7 says text inside `<pre>` and `<code>` "is dropped". GitHub renders ``Fi`x`xes #52`` as `Fi<code>x</code>xes #52`. Dropping the code text gives `Fixes #52`, which `CLOSE_KW` matches, so 52 becomes an intended issue. The main pr-descriptions scenario "Code span inside a word" requires the opposite, and the existing eval pins it (`evals/pr-pair/test_pr_pair.py:3041-3042`: "the text around a removed code span never joins into a new word"). The parser being removed avoids this on purpose: `strip_code_spans` (pr-pair.sh:820-837) leaves a space for that reason. As written, the design would mark issue 52 for closing at cleanup.
D7's line-ending rules also have gaps:
- `pre`, `ul`, `ol`, `table`, `details` and `summary` are missing from the block list.
- A newline in text data is not listed as a line end, although Open Questions says "The parser treats both as line ends".
If soft breaks stay as `\n` and that newline is not a line end, `Fixes #21` followed by `#22 is unrelated` on the next source line joins into one line, and `LIST_GAP` reads #22 as part of the closing list.

**M2. The file-backed runner writes GitHub tokens to disk.**
D1 sends every bounded command's stdout to a file in a temp dir. D3 and the proposal route `as.sh`'s `gh auth token --user` (as.sh:82) and pr-pair's `token_for` (pr-pair.sh:235) through the runner, so the plaintext token of the fenced login lands in `%TEMP%`/`$TMPDIR`. The design removes it in `finally`, but its own Failure table accepts that the runner can be killed (the "bounded runner killed itself (the parent died)" row, for example by the harness's tool timeout). `taskkill /F` or SIGKILL skips `finally`, and the token is then left on disk outside the keyring. Today `token_for` captures through a pipe (`capture_output=True`), so this is a regression under T6. No row in the State & Ownership table covers it.

**M3. The bash scripts' runner command cannot start a shim or the fake `gh` on Windows.**
D1's CLI is `python bounded.py [--paged] -- cmd...`, and D3 has the bash scripts' `gh` function run it. Native Windows Python's `Popen(["gh", ...])` resolves only real executables, so it cannot run a `#!/bin/sh` `gh`. The eval fake is exactly that (`evals/git-workflow/fixtures.py:103`), and so are user shims. pr-pair.sh already handles this with `bash -c 'exec gh "$@"'` and a `cygpath -w` bash path (pr-pair.sh:70-73, 207). The design does not say whether `pr-snapshot.sh`, `pr-reply.sh` and `as.sh` pass the same wrapper or how they find bash. If they do not, every new and existing eval of those three scripts fails on Windows with `gh` not found, and a user's `gh` shim stops working. The Risks section assumes the `bash -c exec` form ("a native gh.exe started through MSYS bash -c exec") without stating it as a decision.

**M4. The first snapshot of a watch has no per-poll deadline.**
D5 exports `SPECWRIGHT_NET_DEADLINE_AT` for each poll in the loop. The first snapshot runs before the loop (`prepare_cfg; base=$(snapshot)`, pr-snapshot.sh:470), with only the per-command 120 s. That snapshot can make up to three `prepare_cfg` calls (graphql, `rate_limit`, activity) and two or more `snapshot` calls, so with hung calls it can run for 5 × 120 s or longer. The new pr-watch requirement says "the watcher reports the timeout within 120 seconds of it passing", and that fails whenever `--timeout` is shorter than this first snapshot. The "always reported" claim in the proposal holds only for polls inside the loop.

**M5. D8's recordings will not match the requests the tests send.**
D8 keys `markdown.json` on SHA-256 of the request JSON, which includes `context`, and records "as `sh1ny/specwright`". The closing tests run against `acme/code` and `acme/plans` (`evals/pr-pair/test_pr_pair.py:37`), and D7 sends the PR's repository as `context`. The two hashes never match, so every closing test fails with `no recorded rendering`. The alternative is recording with `acme/code` as context, but that renders against a real third-party repository, whose issues decide link text such as a URL becoming `#21`. The design must say which context is recorded and how the fake matches it.

**M6. ADR 0012's scope contradicts code that stays unbounded, and the architecture updates are not planned.**
The ADR to record says "Every network command a Specwright script runs goes through a deadline … It binds future scripts". `release.sh` keeps unbounded `git ls-remote` (release.sh:857, 1239), `gh api --paginate` (:1085), `gh release create` (:1364) and `git push` (:1431). `finish.sh` and `update.sh` are also untouched, and architecture.md:146 already names release's read as "#40's unbounded read". The ADR would therefore be accepted while the codebase violates it.
The Impact section also omits `openspec/architecture.md`. After this change the following entries are wrong:
- the "Network commands" Resource-bounds row (:145, "No Specwright deadline");
- the "Review run" row (:148, output checked only up to 2 MB after exit);
- the Known-gaps row for #40 (:169);
- the Script I/O contract (:131), which needs Python for `pr-snapshot.sh`/`pr-reply.sh`/`as.sh` and the new `item-issues` output.

**M7. The pr-watch timing THENs have zero slack.**
- "reports the timeout after at most 75 seconds": the arithmetic of D5's loop lands exactly on 75 s, before Python start-up and `$SECONDS` rounding.
- "no later than 180 seconds after it started": this is exactly 60 + 120 with the default interval.
- The requirement's "within 120 seconds of it passing" has the same problem.
D5's `sleep min(interval, timeout-elapsed)` uses whole-second `$SECONDS`, the deadline adds the 0.1 s kill poll, and each `gh` adds a Python start (Risks: 50–150 ms). None of these THENs can be asserted reliably. The pr-script-runtime scenarios already use "the deadline plus 10 seconds", and these should use the same allowance.

### Re-check (after the author's edits)

Per item:
- **RC1 (M1): applied.** D7 replaces dropped `<pre>`/`<code>` text with one space, lists `pre`, `ul`, `ol`, `table`, `details`, `summary` (and `dl`/`dt`/`dd`) as line-ending blocks, and makes a newline in text data a line end. specs/pr-descriptions adds "Code span inside a word, rendered" and "Reference on the next source line".
- **RC2 (M2): partly applied.** D1 adds a secret mode and the State & Ownership table has a token row, but see N1 and N2.
- **RC3 (M3): applied.** D1 states the shared header: Python discovery, `SW_DIR`/`SW_BASH` through `cygpath`, and `gh()` handing `"$SW_BASH" -c 'exec gh "$@"' gh "$@"` to `bounded.py` next to the scripts.
- **RC4 (M4): applied in the deadline, not in the exit.** D5 and the requirement put the first snapshot under the per-poll deadline, and specs/pr-watch adds "First snapshot hangs". See N3 for the exit status that scenario requires.
- **RC5 (M5): applied.** D8 records with context `sh1ny/specwright`, keys on `mode` + `text`, has the fake ignore `context`, and argues soundly that the text-only parser reads a reference the same under either context.
- **RC6 (M6): applied.** ADR 0012 is scoped to the PR scripts and `review-run.sh`, with `release.sh`, `finish.sh` and `update.sh` named as exceptions and an issue to file. The architecture rows are listed, and proposal Impact names `openspec/architecture.md` and the ADR.
- **RC7 (M7): applied.** The requirement says within 130 s, and the scenarios say at most 85 s, no later than 190 s, and 160 s for the new first-snapshot case. Checked against D5's loop: 75 s, 180 s and about 120 s respectively, each with at least 10 s of slack.
- **S1: applied.** D5 checks ownership before the timeout report, and the "Takeover after a hung poll" THEN says so.
- **S2: applied.** D5 unsets the deadline after each poll. A small inconsistency remains: the State & Ownership row for `SPECWRIGHT_NET_DEADLINE_AT` still says "overwritten at the next poll" and should say "unset after the poll".
- **S3: applied.** specs/feedback-passes says one read per repository as that repository's login and adds a store-backed scenario. D4 has the matching skill text.
- **S4: applied for the three named lines, but not complete.** See N2.

New defects introduced by the edits:

**N1 (Moderate). Secret mode's second `communicate()` has no timeout, so a token lookup can hang forever.**
D1's secret mode calls `kill_tree` on the deadline and "then `communicate()` once more, so the killed tree's pipes close". That only returns once every process holding the pipe's write end has exited. `review-run.sh` uses files for exactly this reason ("a killed process tree cannot leave a pipe open", review-run.sh:330-332). The design's own Risks section says `taskkill /T` may not reach a native `gh.exe` started through MSYS `bash -c exec`. In that case a hung `gh auth token` survives the kill, keeps the pipe open, and the unbounded second `communicate()` blocks the script with no report. The lookup is the first network step of `as.sh` and of every fenced `pr-pair.sh` call, so this reintroduces the #40 hang on the credential path. Fix: bound the second `communicate()` (for example, 5 s), then close the pipes and report `deadline_exceeded` whatever it returns.

**N2 (Moderate). as.sh's `--resolve` path is not covered: its token lookup goes through the file-backed runner, and a limit there is misreported.**
D1 and D3 name "as.sh's three lookups" (`:69` `--help`, `:82` the token, `:86` `api user`). The `--resolve` branch makes two more calls (as.sh:78 `gh api user` and as.sh:79 `gh auth token --hostname github.com --user "$login" >/dev/null`). Under D1's header, as.sh's `gh()` function runs every call in the default file-backed mode. The `:79` token is written to the runner's temp file before the shell discards it, which is M2's defect on a path that `specwright-commit`, `specwright-finish` and `specwright-branch` all run. Both calls also discard their exit status (`|| login=`, `>/dev/null 2>&1 ||`), so a deadline is reported as "no active gh account" or "no gh credential", which is S4's defect. The `:69` and `:86` calls carry no token and do not need secret mode. Fix: D1/D3 name the `gh auth token` calls (`:79` and `:82`) as the secret-mode calls, and give all five lookups the 124/125 check.

**N3 (Moderate). As D5 stands, the new "First snapshot hangs" scenario cannot exit 1.**
The scenario requires the watcher to exit 1. In the current code, a failed first snapshot leaves `base` empty and `ok=1` (pr-snapshot.sh:470). With `--timeout 30`, the first snapshot ends at its 120 s deadline, the loop never runs, `[ "$ok" = 1 ]` passes, and the script prints `{"wake":"timeout","waited":…,"snapshot":}` (invalid JSON) and exits 0. D5 does not say that a failed first snapshot sets `ok=0` or exits 1. Fix: state in D5 that a failed first snapshot is a failed poll (`ok=0`, so the report exits 1 "the last poll failed"), and decide whether `prepare_cfg`'s failure in that snapshot counts.

### Re-check 2 (after the author's second edits)

- **N1: applied.** D1's secret mode runs `communicate(timeout=5)` after `kill_tree`, then closes its own pipe ends and reports `deadline_exceeded`. A token lookup now waits at most its deadline plus 5 s, even when a process survives the kill.
- **N2: applied.** D1 names the secret calls (`gh auth token` in `token_for`, in as.sh's fenced path and in its `--resolve` path) and leaves `--help`, `api user` and `ambient_login` in file-backed mode. D3 lists all five as.sh lookups, `--resolve`'s two included, and requires a 124/125 check before each existing message. Two cited line numbers are wrong, but each call is also named by its content, so neither is ambiguous (S6).
- **N3: applied.** D5 makes a failed first snapshot a failed poll (`ok=0`, no base). Polling continues, a later good poll becomes the base, and a timeout with `ok=0` exits 1. Checked against "First snapshot hangs" (`--timeout 30`): the snapshot ends at its 120 s deadline, `elapsed >= timeout` stops the loop, and `ok=0` exits 1 at about 120 s, within the scenario's 160 s. The existing loop's `prepare_cfg && snapshot` pattern answers the `prepare_cfg` question: a hung `snapshot` fails the poll whether or not `prepare_cfg` reports its own failure.
- **S5: applied.** The State & Ownership row for `SPECWRIGHT_NET_DEADLINE_AT` says "unset right after the poll", which matches D5.

The edits introduced no Critical or Moderate defect. Three minor points follow as S6-S8.

### Suggestions

- **S1. Check ownership before reporting a timeout.** In D5's loop, a poll that hangs past `--timeout` goes straight to the timeout check and exits 1 with "the last poll failed; GitHub state unknown", even when a newer watcher took over during the hang. Its agent then sees state unknown instead of exit 4 and may start another watcher, which takes the PR back. Checking ownership before reporting, not only before polling, would avoid that.
- **S2. Unset the poll deadline after the loop.** `SPECWRIGHT_NET_DEADLINE_AT` stays exported in the main shell after the loop. With `--wait --logs`, `gh run view --log-failed` (pr-snapshot.sh:488) inherits an expired or nearly expired deadline, and the logs are silently lost (`|| true`). Unset it after each poll, or set it only in the poll's own subshell.
- **S3. "One read per pass" is really one read per repository.** In a store-backed pass, actionable items can come from both PRs, and `item-issues` takes one `--repo`. That is one read per repository, as SKILL.md's "in the repo of the PR it came from" implies. The feedback-passes requirement and the D4 skill text should say so and name the login for the store read: `item-issues` has no `--login` like `closed-check`, so the caller's `[as]` login must be that repository's.
- **S4. Keep the limit's exit status in `as.sh`.** `as.sh`'s lookups discard their exit status: `$(gh auth token --help 2>&1 || true)` (:69), `|| token=` (:82), `|| actual=` (:86). A plain function swap would report a deadline as "upgrade gh" or "no gh credential". D3's 124/125 mapping needs each of the three restructured. Saying so in D3 keeps the as.sh scenario achievable on the first try.
- **S5 (re-check).** Correct the State & Ownership row for `SPECWRIGHT_NET_DEADLINE_AT` to "unset after the poll", to match D5.
- **S6 (re-check 2). Correct the cited line numbers.** as.sh's `--resolve` lookups are at `as.sh:75` (`gh api user`) and `:77` (`gh auth token ... >/dev/null`), not `:78`/`:79`, and `token_for`'s `api user` is `pr-pair.sh:240`, not `:238`. The wrong numbers came from N2 in this review. D1 and D3 also name each call by its content, so an implementer can still find them.
- **S7 (re-check 2). Show how as.sh passes `--secret`.** The shared header's `gh()` passes only `${SW_PAGED:+--paged}`. If the two `gh auth token` calls use that function as written, they run in file-backed mode, and the token reaches a temp file (M2 again). D1 does say that both calls run in secret mode. Add `${SW_SECRET:+--secret}` to the header, or have those two calls run `bounded.py --secret` directly.
- **S8 (re-check 2). Apply the incomplete check to a late base.** When the first snapshot fails and a later poll becomes the base, D5 does not say that a base with `"complete":false` stops the wait (`wake=incomplete`), as the first snapshot does at pr-snapshot.sh:472. Without that check, such a watcher waits until the timeout for activity it cannot see.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

None outstanding. Re-check 2 found RC1-RC7 and N1-N3 applied (see Findings). The earlier list was:

1. **D1 (N1, part of RC2):** bound secret mode's post-kill `communicate()` with a short timeout, then close the pipes and report `deadline_exceeded`, so a tree that survives `kill_tree` cannot hang a token lookup. *(applied)*
2. **D1/D3 (N2, completing RC2 and S4):** cover as.sh's `--resolve` branch. Its `gh auth token` runs in secret mode like `:82`, and both of its calls check for 124/125 before their existing messages. Name the secret calls, and do not count `--help` or `api user` among them. *(applied)*
3. **D5 (N3, completing RC4):** state that a failed first snapshot is a failed poll (`ok=0`), so the watcher exits 1 "the last poll failed" as "First snapshot hangs" requires, and never prints an empty snapshot with exit 0. *(applied)*

CHANGES_APPLIED: yes

## Rebuttals
- **M1:** fixed. D7 now replaces dropped code with a space, lists `pre`, `ul`, `ol`, `table`, `details`, `summary` (and `dl`) as line-ending blocks, and makes a newline in text data end a line. specs/pr-descriptions adds "Code span inside a word, rendered" and "Reference on the next source line". *(accepted by reviewer)*
- **M2:** fixed. D1 adds a secret mode (pipes with `communicate(timeout)`, `kill_tree`, nothing on disk) for `token_for`, `ambient_login` and as.sh's lookups. The State & Ownership table adds a token row. *(accepted by reviewer after re-check 2, with N1 and N2)*
- **M3:** fixed. D1 states the bash scripts' shared header: Python discovery, `SW_DIR`/`SW_BASH` via `cygpath`, and `gh()` handing `"$SW_BASH" -c 'exec gh "$@"' gh "$@"` to `bounded.py` next to the scripts. *(accepted by reviewer)*
- **M4:** fixed. D5 puts the first snapshot under the per-poll deadline. specs/pr-watch adds "First snapshot hangs", and the requirement says "the first snapshot included". *(accepted by reviewer after re-check 2, with N3)*
- **M5:** fixed. D8 records with context `sh1ny/specwright`, keys on `mode` + `text`, and has the fake ignore `context`. It also explains why the text-only parser makes that sound. *(accepted by reviewer)*
- **M6:** fixed. ADR 0012 is scoped to the PR scripts and `review-run.sh`, with `release.sh`, `finish.sh` and `update.sh` as known exceptions and an issue to file. The architecture updates are listed, and proposal Impact names `openspec/architecture.md` and the new ADR. *(accepted by reviewer)*
- **M7:** fixed. specs/pr-watch allows 10 s: within 130 s of the timeout, at most 85 s, no later than 190 s. *(accepted by reviewer)*
- **S1:** applied. Ownership is checked before the timeout report (D5), and the "Takeover after a hung poll" THEN says so. *(accepted by reviewer)*
- **S2:** applied. The deadline variable is unset after each poll (D5). *(accepted by reviewer; see S5 for the State table wording)*
- **S3:** applied. specs/feedback-passes: one read per repository as that repository's login, with a store-backed scenario. D4 has the matching skill text. *(accepted by reviewer)*
- **S4:** applied. D3 restructures as.sh's three lookups to check for 124/125 before their existing messages. *(accepted by reviewer after re-check 2, with N2)*
- **N1 (re-check):** fixed. D1's secret mode bounds the post-kill `communicate` with `timeout=5`, then closes its pipe ends and reports `deadline_exceeded`. *(accepted by reviewer)*
- **N2 (re-check):** fixed. D1 names the secret calls by line (`pr-pair.sh:235`, `as.sh:79`, `as.sh:82`) and puts `--help`/`api user` outside secret mode. D3 restructures all five as.sh lookups, `--resolve`'s `:78`/`:79` included. *(accepted by reviewer; S6 corrects the line numbers)*
- **N3 (re-check):** fixed. D5 makes a failed first snapshot a failed poll (`ok=0`, no base). A later good poll becomes the base, and a timeout with `ok=0` exits 1. *(accepted by reviewer)*
- **S5 (re-check):** applied. The State & Ownership row says "unset right after the poll". *(accepted by reviewer)*
