# Review

## Metadata

- **Round:** 1
- **Prior round:** none
- **Reviewer:** fresh-context subagent (Claude Code, Claude Opus 5.5); project skill `github-account-switch-race-fencing` loaded and applied to D4 (and used to fence the read-only `gh issue view` calls as KintsugiBot)
- **Reviewed:** proposal.md; design.md (TIER: FULL); specs/pr-evidence/spec.md; specs/pr-watch/spec.md; specs/planning-stores/spec.md against openspec/specs/planning-stores/spec.md; openspec/roadmap.md (M1, change 3); openspec/architecture.md; docs/adr/0002, 0003, 0004 (0006 checked for path impact only); skills/specwright-pr/scripts/pr-snapshot.sh, pr-reply.sh, pr-pair.sh (identity, gh/token_for, read_store_as, norm_pr, expected_set call sites, readiness, cmd_pair_state, remote_contains, cmd_rounds, pass_plan), as.sh; skills/specwright-pr/SKILL.md (feedback and watch); evals/fakes/gh.py; evals/pr-pair/test_pr_pair.py; issues sh1ny/specwright #31, #33, #35, #39, #47.
- **Re-check (round 1, fresh-context subagent, 2026-10-10):** Required Changes 1-4 checked against design.md (D1-D4, State & Ownership, Failure & Visibility, Flow & State Gaps), specs/pr-evidence/spec.md and proposal.md, with pr-snapshot.sh, pr-pair.sh (`identity`, `read_store_as`, `cmd_rounds`, wrapper lines 50-55) as evidence. All four fully applied; no edits beyond them were found that would void the verdict. Result: CHANGES_APPLIED set to yes. One non-blocking note for apply: D4 says `PR_PAIR_DIR` is converted with `cygpath -m` "as `PR_PAIR_BASH` is today", but `PR_PAIR_BASH` uses `cygpath -w` (`pr-pair.sh:54`); `-m` is the right choice for a path handed to bash, so only the comparison is inexact.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

**M1. D2: the "unsaved" fallback means timestamp-based reviewers are never reported and never time out inside `--wait`. This is a regression from 0.1.10.**
Today `first_seen` is set once per process and reused on every poll (`pr-snapshot.sh:273`), so `pushed` stays fixed and `timed_out` (`:208`, `cfg.now - pushed >= timeout`) can eventually fire. D2 and the scenario "First-seen record cannot be written" set the cutoff to "the current GitHub time ... for this call". `--wait` runs `prepare_cfg` on every poll (`:327`), so each poll moves both `since` and `pushed` to that poll's `now`. Two things follow:
- every Mira or generic report is older than the cutoff, so it is never `reported`;
- `cfg.now - pushed` is 0, so it is never `timed_out`.

A required generic reviewer therefore stays `waiting` until watch's two-hour stop, which is the manual rescue this milestone exists to remove. The trigger is plausible: the pr-watch spec already plans for an unwritable state directory, and sandboxed harnesses often cannot write to `~/.cache`. The same thing happens if a writer dies between the `set -C` create and the write. That leaves an empty record that every later process fails to read, permanently for that head, because O_EXCL blocks a rewrite.

**M2. D3, threads: the binding check does not re-list a resolved thread, which is the usual case.**
D3 says that when the pre-reply revision differs from the marker's `rev`, "the thread is listed as open (`awaiting_reviewer: false`)". The thread filter is `select((.isResolved | not) or ($open | length > 0) or $held)` (`pr-snapshot.sh:148`). Feedback answers most threads with `--resolve` (SKILL step 8). In the #33 case (an edit that lands before the reply), `$open` is empty because the edit predates `$replied` (`:145-146`), and the thread is resolved. So the thread is dropped by the filter, and the hidden edit stays hidden: the #33 bug survives for resolved threads.

Even when the thread is listed, nothing in it tells feedback what is unanswered:
- the last comment is the agent's own reply;
- `$open` is empty;
- SKILL step 4 treats an edit as an answer only when `edited` is newer than the reply's `at`, which it is not here.

The pr-evidence spec has a scenario for this race only on a PR comment. Nothing covers a thread.

**M3. D4: as designed, `rounds` never reaches `git_net`'s store branch, and the as.sh path can be relative.**
- `git_net` switches when "`REPO_LOGIN` maps the repo at `d`". `REPO_LOGIN` is keyed by repository slug (`pr-pair.sh:113`, `:162`) and is filled only by `read_store_as`, which is called from `expected_set` (`:605`) and `pass_plan` (`:1592`). `cmd_rounds` (`:1168-1201`) never resolves the store's identity and never calls `read_store_as`. Its `remote_contains` calls (`:1189`) would therefore still run as the code login. That contradicts the planning-stores scenario "Private store readable only by the store login", which names `rounds`. The design also does not say how a directory `d` becomes a slug.
- D4 runs `bash <PR_PAIR_DIR>/as.sh ... git ...` with `cwd=d` (the store). SKILL invokes the script by a relative path (`bash scripts/pr-pair.sh`). If `PR_PAIR_DIR` comes from `$0` without being made absolute, the path resolves under the store checkout, so `as.sh` is not found and the check reports `remote_unreadable` for the store every time.

**M4. D1: the refresh after a `refresh:pr` mismatch does not say which PR to snapshot, and the watcher stays on the old PR.**
A PR-number mismatch happens when the branch's PR is replaced (PR 7 closed, PR 9 opened; `discover` takes the highest number). D1 says watch takes "a one-off snapshot of that PR into its file", and SKILL watch step 1 restarts "only its wait", meaning the wait on PR 7. Then:
- on every wake, the PR-7 watcher writes PR-7 snapshots into the file;
- `pair-state` reports `refresh:pr:7!=9` again;
- no background wait exists for PR 9, so its review and CI activity never wakes watch. Readiness is re-checked only when PR 7's 30-minute wait times out.

### Suggestions

**S1. D3 compatibility rule for mixed markers.** The reasoning behind 0.1.11 holds in the code:
- the 0.1.10 scan `specwright:handled ([A-Za-z0-9_=-]+)` (`pr-snapshot.sh:121`) stops at the space before `rev=`;
- `resolve_pending`'s `contains("specwright:handled " + $tid + " resolve")` (`:157`) still matches, as long as `rev=` follows `resolve`, which the stated format guarantees;
- `pr-pair.sh` does not parse reply markers;
- pass records already carry `revision.rev`.

One edge remains. The rule "when any marker carries `rev=`, only such markers count" re-lists an item if a 0.1.10 session answers it after an edit, following an earlier 0.1.11 marker. That produces a duplicate reply. It fails safe, but "the latest marker for the item decides its rule" would avoid it.

**S2. D6: define `rev` in `--full` output for a review-thread comment.** A thread's revision is the thread-wide formula, not one comment's time. If `--full` on a `PullRequestReviewComment` prints that comment's own `lastEditedAt // createdAt` as `rev`, an agent that passes it to `pr-reply.sh thread --rev` gets exit 5 every time. Either print the thread's revision for thread comments or name the field differently (for example `comment_rev`), and state that the snapshot's thread `rev` is what `--rev` takes.

**S3. A design citation is off.** "`as.sh:53-55`" for the `GH_TOKEN` and credential helper points at the extraHeader scrub. The export is `as.sh:31` and the helper is `as.sh:56-57`.

**S4. Risks: the "filter under test" claim is overstated.** `evals/fakes/gh.py:134-141` runs non-trivial `--jq` filters through the system `jq`. Real `gh --jq` uses gojq, which differs from jq in:
- object key order (gojq sorts keys);
- some regex syntax (RE2 vs Oniguruma);
- `strptime`/`mktime` edge cases.

The new filter relies on all three (`sig_of` grep, `(?s)` clip, Date-header parsing). Note the difference, or run the tests with gojq when it is installed.

**S5. D2: narrow the window that fails closed.** A report made between the push and the first `--reviewer` snapshot is discarded. Feedback and ship know exactly when they pushed. Taking one `--reviewer` snapshot right after their own push would seed the record at almost the push time. This is optional, since D2 already accepts the timeout fallback.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **(M1)** In design D2, the Failure & Visibility row "First-seen record", and the pr-evidence scenario "First-seen record cannot be written": when the record cannot be read or created, the fallback cutoff and timeout start must be the earliest time this process saw the head, kept across polls as `pr-snapshot.sh:273` does today, not each call's `now`. A record that exists but cannot be parsed must count as "cannot be read". Add a pr-evidence scenario: in a `--wait` with an unwritable state directory, a generic reviewer that comments after the watcher first saw the head is `reported` at the next poll, and a silent required reviewer reaches `timed_out` after its timeout. Either write the record atomically with its content (for example a temp file, then a no-clobber hard link) or note that an empty record falls back to the in-process time.
2. **(M2)** In design D3 (thread snapshot rule): a thread whose latest handled marker's `rev` differs from the pre-reply revision is listed even when it is resolved, by extending the `select` at `pr-snapshot.sh:148`. The listing carries an explicit field (for example `rebound: true`, or the edited comment in an `unanswered` list) so that feedback step 4 judges it as unanswered. Add a pr-evidence scenario under "Handled markers are bound to a revision": a reviewer edits a thread comment, then a reply with `--resolve` bound to the old revision is posted and the thread is resolved; the next snapshot lists the thread with that field and `awaiting_reviewer: false`. Name the SKILL step 4 wording that uses the field.
3. **(M3)** In design D4: state how `git_net` maps `d` to its login, either by resolving `identity(d)` and looking up `REPO_LOGIN`, or by callers passing the login. State that `cmd_rounds` resolves the store slug and calls `read_store_as` before its `remote_contains` calls. State that the wrapper exports `PR_PAIR_DIR` as an absolute path. Add `rounds` to the D4 test plan in the Risks section or the D4 text.
4. **(M4)** In design D1 and the Flow & State Gaps section: on a `refresh:pr` blocker, watch stops that side's wait, then takes the one-off snapshot and restarts the background wait for the PR number in `pair-state`'s `prs.<side>`, not the old one. On `refresh:head`, it snapshots the same PR. Reflect this in the SKILL watch-step change the proposal lists.

CHANGES_APPLIED: yes

## Rebuttals

- **M1:** fixed (Required Change 1). Accepted by reviewer.
  - design D2: the record is written to a temp file and published by a no-clobber hard link. When it cannot be published or read, or does not parse, the fallback is the in-process first-seen time, kept across polls.
  - Failure & Visibility: two First-seen record rows. State & Ownership: the record row.
  - pr-evidence spec: "First-seen record cannot be written" is revised, and "Waiting with an unwritable state directory" is new.
- **M2:** fixed (Required Change 2). Accepted by reviewer.
  - design D3: `rebound: true` and `awaiting_reviewer: false`; the `select` is extended with `$rebound`; `rebound` is part of `sig`; the SKILL feedback step 4 wording is given.
  - pr-evidence spec: new scenario "Thread edited before a resolving reply".
- **M3:** fixed (Required Change 3). Accepted by reviewer. design D4 now covers:
  - mapping through `identity(d)` and `REPO_LOGIN`;
  - `cmd_rounds` resolving the store slug and calling `read_store_as`;
  - `PR_PAIR_DIR` as an absolute path (`pwd -P`, plus `cygpath -m`);
  - tests for `rounds`, `pass plan` and a missing store credential.
- **M4:** fixed (Required Change 4). Accepted by reviewer.
  - design D1: the `refresh:head` and `refresh:pr` rules, with the wait restarted on `prs.<side>`. Flow & State Gaps: a new "PR replaced on a branch" entry.
  - proposal: the SKILL watch bullet.
- **S1:** accepted, deferred to apply. The design is unchanged, so this verdict still covers it. Implementation applies the rule as written, and the task for the snapshot marker rule records the mixed-version duplicate reply as a known, fail-safe edge.
- **S2:** handled in tasks, without a design edit. `--full` prints the item's own revision. SKILL text states that `pr-reply.sh --rev` always takes the `rev` from the snapshot (or the pass record's `revision.rev`), never from `--full`.
- **S3:** acknowledged. The correct references are `as.sh:31` (GH_TOKEN) and `as.sh:56-57` (credential helper). The design text is left as is, so this verdict is not voided for a citation.
- **S4:** handled in tasks. The snapshot tests run with `gojq` when it is installed, and otherwise with `jq`. The test module says which one ran.
- **S5:** not built. D2 already fails closed through the timeout, and Codex, the configured required reviewer, is unaffected. Seeding the record from ship and feedback is a follow-up if timeouts show up in practice.
