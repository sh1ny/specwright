# 0022. Reviewer detection is generic; bot-specific rules live in settings

- Status: accepted
- Date: 2026-11-02
- Adds to: 0020 (does not supersede it)

## Context

`pr-snapshot.sh` decided whether a reviewer had reported on a head with rules written for three specific review bots: their logins, a commit-SHA comment, a named check run, a comment marker and an in-progress text, plus a map from one login to its check name. Every other login fell back to "posted anything after the push". That fallback counts an in-progress notice as a finished review, and it cannot tell a bot's review check from CI, because a check's app can be shared: a review action posting as `github-actions` runs as the same app as every workflow. A team using other review bots got wrong readiness, and an advisory bot's check could hold up a merge (#166).

Reviewer reports gate the agent merge (ADR 0009, 0020). ADR 0020 compares the reviewer settings of main and the ready head and checks in the script that main's required reviewers reported. Once projects describe how their bots report, those descriptions decide a merge too, so they need the same protection.

## Decision

- **Scripts name no reviewer.** The snapshot detects reports by generic rules: a submitted review on the head commit, else the reviewer's output at or after the head's cutoff. Check runs count only when the settings name them.
- **Bot-specific rules live in settings.** `pr.reviewers.<login>.report` takes `sha_pattern`, `check`, `marker` and `ignore`. With any of the first three set, only those and a review on the head commit decide for that reviewer. A Python evaluator (`reviewers.py`) applies them; settings reach it as a canonical, content-addressed config file that `pr-pair.sh context` and `policy` write.
- **`report` is part of the compared reviewer settings.** ADR 0020's normalized comparison includes each reviewer's normalized `report`, so a PR that changes a rule is a policy difference that needs the user.
- **A report counts only under the authorizing set's rules.** Each snapshot names the SHA-256 digest of the config it ran with. `policy` counts required reviewers as reported for a set only when that digest equals the set's own; otherwise it reports `rules_mismatch`, merges nothing, and watch waits again with the authorizing config.
- **The agent may only add waiting.** Watch may treat a reviewer reported only `by: output` as still waiting when its evidence reads as an announcement, until its timeout. It never treats a `waiting` or `timed_out` reviewer as reported; the reported check stays the script's.

**Rejected: keep the rules in the snapshot's jq program.** gojq uses RE2 while `pr-pair.sh` validates in Python, so a pattern could pass validation and match differently at run time.

**Rejected: count a completed check of the app whose slug equals the login.** Shared apps would make CI report a required reviewer.

**Rejected: built-in presets for known bots.** They bring back the bot-specific knowledge this decision removes; the README shows copyable examples instead.

**Reversal cost: low.** The evaluator's input is internal; its output fields and the config file are the contract.

## Consequences

- Specwright works with any review bot; projects whose bots relied on the removed built-in rules add `report:` blocks, or get the coarser generic default.
- `pr-snapshot.sh --reviewer` is removed in favour of `--reviewer-config <file>`; `policy` prints `reviewer_config` paths instead of `reviewer_args`.
- A wait started with the work tree's looser rules can never authorize a merge; at worst it costs one more wait with main's config.
- A user regex runs over untrusted PR text inside the poll's deadline, so a pathological pattern fails the poll instead of hanging the wait.
