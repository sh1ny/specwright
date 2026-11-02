# Proposal

## Why

`specwright-pr` watch can only tell three specific review bots apart, because `pr-snapshot.sh` hardcodes their logins and output formats: a "Reviewed commit" sha comment, a named check run, a walkthrough comment marker, the "Reviewing this PR / Code review in progress" text, and a map from one bot login to its check name. Any other bot falls back to "posted anything after the push". That rule counts an in-progress notice as a finished review and cannot tell a bot's review check from CI. A team using different review bots gets wrong readiness, and an optional bot's check can hold up a merge for an hour. On top of that, the archive step treats a commit that only moves planning Markdown like a code push: it runs the full `pr.validate` before the push and then waits a full 30-minute watch cycle before merging (#166, seen on sh1ny/mythspine#73).

We are switching to a more generic way of detecting reviewers. The scripts name no bots. They report what is observable on the current head, `pr.reviewers` can describe how a particular bot signals a finished review, and every other reviewer gets a generic default. The archive step becomes cheap when it is provably archive-only.

Milestone: M6 - Packs, inserted before `pack-mechanism` because other teams cannot use watch until it stops relying on our own bots. It advances the exit criteria "every issue in the changes below is closed by a merged PR with a regression test" (#166) and the release criterion, which this change renumbers (0.15.0 here, `pack-mechanism` 0.16.0, `gamedev-pack` 0.17.0).

## What Changes

- **Generic reviewer detection.** `pr-snapshot.sh` loses every bot login, check name, comment marker and output pattern. A configured reviewer counts as `reported` on the head by a GitHub review bound to the head commit, otherwise by its output at or after the head's cutoff (today's timestamp rule). Check runs count only when the settings name them, since a check's app can be shared (CI and a review action both run as `github-actions`). Each reviewer entry gains `by` (the rule that matched) and `evidence` (what it produced on the head), and the snapshot carries GitHub's `now`, so the agent can keep waiting for a reviewer whose only output looks like an announcement. The agent's judgment can only add waiting, never remove a gate.
- **Per-reviewer matching rules.** `pr.reviewers.<login>.report` (optional) takes `sha_pattern` and `ignore` (regular expressions), `marker` (literal text) and `check` (an exact check name), for bots the default cannot read exactly. A report rule replaces the default for that reviewer. `report` is part of `pr.reviewers`, so a PR that changes it is a policy difference that needs the user. Each snapshot names the digest of the rules it ran with, and `policy` accepts reports only when that digest is the authorizing set's, so a wait started with looser rules never authorizes a merge. `context` reads reviewer settings as strictly as `policy`.
- **Review checks follow their reviewer.** A check named by a reviewer's `report.check` stops counting as pending once that advisory reviewer reported or timed out. The snapshot adds `checks.ci_pending` (pending checks named by no reviewer), and a wait's check-progress filter follows it, so CI finishing wakes the wait even while a reviewer's check runs.
- **BREAKING (script interface): reviewer settings travel as a file.** `pr-pair.sh context` and `policy` write a reviewer-config JSON file per repo from the settings they read (for `policy`, main's and the head's) and print its path. `pr-snapshot.sh` takes `--reviewer-config <file>`. `--reviewer login:role:seconds` is removed and exits 2 naming `--reviewer-config`; `policy`'s `reviewer_args` output is replaced by `reviewer_config`.
- **Settle window.** New setting `pr.settle` (default `5m`, from 1m to 1h). Once a PR meets every ready condition but the quiet window, watch waits `pr.settle` instead of a full 30-minute wait; other waits keep `--timeout 1800`.
- **Cheap archive step (#166).** Watch hands the ready head to finish and ship. Before the archive push, ship runs `review-run.sh archive-only` against it; when it returns `true`, `pr.validate` is skipped (`planning_store.validate` still runs in the store). An archive head whose reports carry over is ready, with no further quiet window, on the first snapshot taken `pr.settle` after its push that shows it mergeable, `checks.ci_pending` 0, no failure and no new feedback. Then the merge follows as today.
- Docs and the settings template use placeholder bot names and show the three former built-in rules as `report:` examples to copy.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `pr-evidence`: reviewer reports are detected by generic rules plus optional per-reviewer `report` rules, with evidence and `now` in the snapshot; reviewer settings reach the snapshot as a config file, are read strictly by `context`, and the snapshot names the digest of the rules it used.
- `pr-watch`: the quiet window is `pr.settle` instead of one full wait; an advisory reviewer's named check stops blocking once it reported or timed out; the wait filter and the archive-only head follow `checks.ci_pending`; an archive-only head needs no review round and no further quiet window; an announced review can extend the wait.
- `pr-merge`: required reviewers count only under the authorizing set's report rules (`rules_mismatch` otherwise); the archive carry-over is described without "watched without reviewers".
- `change-finish`: the ready head is handed from watch to finish and ship, and an archive push that `archive-only` proves archive-only skips `pr.validate`.

## Impact

- **Scripts:** `skills/specwright-pr/scripts/pr-snapshot.sh` (detection, evidence, `--reviewer-config`, removal of `--reviewer`), `skills/specwright-pr/scripts/pr-pair.sh` (`reviewers_of` parses `report`, `context`/`policy` write the config file, strict reviewer read in `context`, `rules_mismatch`, `pr.settle` parsing), new `skills/specwright-pr/scripts/reviewers.py` (rule evaluator).
- **Skill text:** `skills/specwright-pr/SKILL.md` (Reviewers, settings block, ship validate, watch steps 1 and 3, the archive step), `skills/specwright-finish/SKILL.md` (`## pr`).
- **Template and docs:** `templates/openspec/specwright.yaml`, `README.md` (reviewer section), `openspec/roadmap.md` (M6 change list and release criterion), `VERSION`, the README badge and every `skills/*/SKILL.md` `metadata.version` (0.15.0).
- **Evals:** `evals/pr-pair/test_pr_snapshot.py`, `test_pr_pair.py` and `test_skill_text.py`, `evals/git-workflow/test_grade.py`, plus any fixture that passes `--reviewer`; new cases for each default rule, each `report` key, the config file and the settle window.
- **Projects that use Specwright:** projects whose bots relied on the built-in rules add `report:` blocks. Without them, the generic default applies: still exact for bots that post commit-bound reviews or own a check run, coarser for bots that only edit a comment.

## Release Notes

Watch now detects reviewers generically, so Specwright works with any review bots, and the archive step no longer re-runs validation or waits a full watch cycle.

### Added
- `pr.reviewers.<login>.report` (`sha_pattern`, `check`, `marker`, `ignore`) describes how a bot signals a finished review, and `pr.settle` (default 5m) sets the quiet window before a PR counts as ready. (#166)

### Changed
- Reviewer detection is generic: a review bound to the head commit or output after the push, plus the rules each project sets, with no bot named in the scripts. An advisory reviewer's named check stops blocking once it reported or timed out. Reviewer settings reach `pr-snapshot.sh` as a `--reviewer-config` file, and a merge counts only reports judged under main's rules. (#166)
- An archive-only push skips `pr.validate`, and its head is merged `pr.settle` after the push instead of after another 30-minute watch cycle. A PR that meets every other ready condition waits `pr.settle` instead of 30 minutes. (#166)

### Removed
- `pr-snapshot.sh --reviewer` and `pr-pair.sh policy`'s `reviewer_args`, replaced by `--reviewer-config` and `reviewer_config`. (#166)
