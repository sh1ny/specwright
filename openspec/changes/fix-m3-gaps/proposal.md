# Proposal

## Why

Six known gaps were filed while M3 shipped (Codex findings on PRs #90, #92 and #96, and the first try at the deferred dogfood check #98), and #53 has been open since M1. Each one leaves a path where Specwright records a wrong result (a review that read nothing, a release that is never tagged), authenticates against ADR 0008, or can lose the user's work (a store rollback with no old schema, an interrupted stash). This change closes them before M4 adds a cheaper model tier that will lean on the same scripts. It is change 1 of **M4 - Cost tier** (release 0.6.1) and advances these exit criteria: every issue in the milestone's changes is closed by a merged PR, and each code fix has a regression test in `evals/`; `evals/pr-pair`, `evals/git-workflow`, `evals/review-routes`, `evals/update` and `evals/release` pass; each change ships as its own release.

## What Changes

- **#91 - OpenSpec version token boundary.** The install prompt (Step 1 root check and Step 3) treats a version token followed directly by another version character (`1.14.1.0`, `1.14.1vendor`) as unreadable output, which stops the install. It no longer matches the pin.
- **#93 - no unfenced tag read in `finish: local`.** Local finish lists untagged versions from local tags only (`release.sh untagged --local`), with no network call and no login, and says that the list comes from local tags. Publish still reads origin, fenced, once `main` is pushed.
- **#94 - a version already on main is refused before the merge.** `release.sh check --main <ref>` refuses a branch that bumped the version to a target that is not greater than the version on `<ref>`. Ship and the local merge call it against refreshed main, and so does watch before it reports a PR ready or merges it. The second change then bumps again.
- **#95 - design reviews that read nothing are refused.**
  - Codex on Windows keeps `--ignore-user-config`, but gets the user's `windows.sandbox` setting passed explicitly, so it can read the checkout.
  - A design review's `VERDICT:` must be `APPROVE`, `APPROVE_WITH_CHANGES` or `REVISE`, and its `CHANGES_APPLIED:` must match that verdict. Anything else fails with `invalid_output` and leaves `--out` untouched.
  - The subagent route writes its design review to a scratch file, and `record --out` copies it to `review.md` only when it validates. A refused review no longer replaces the earlier one there either.
  - The OMP route reads its answer from the final `agent_end` event, so a large event stream with a small answer is no longer rejected as "output too large". The size bound applies to the answer.
- **#97 - store staging per checkout.** Each code checkout stages the store schema in its own directory, keyed by that checkout. Stage, discard and recover remove only their own staging. Another checkout's staging makes the store busy instead of counting as this update's own.
- **#99 - update refusal blames the right version.** When a change in flight fails validation against the target version, the update also checks it against the installed schema. When it fails there too, the refusal says the change is already incomplete on the installed version and that the update did not cause it. The refusal itself is unchanged.
- **#53 - debug stash recovery.** `specwright-debug` names its stash `specwright-debug: <topic>`, reports the ref, and at the start of every run looks for a stash left by an interrupted run and offers to restore it.
- Release 0.6.1 (patch): `VERSION`, the README badge and the skill `metadata.version` fields.

## Capabilities

### New Capabilities
- `debugging`: the debug skill's handling of the user's uncommitted work: a named stash, reported by ref, and recovered after an interrupted run (#53).

### Modified Capabilities
- `install-update`: a version token followed directly by another version character counts as unreadable output (#91). A change in flight that fails against the target is also checked against the installed schema, and the refusal says when the gap already exists there (#99).
- `releases`: `untagged --local` reads local tags only (#93); a bumped version that is not greater than main's is refused before ship, merge or ready (#94).
- `change-finish`: local finish lists untagged versions from local tags, with no network call (#93).
- `review-routes`: codex on Windows gets the user's `windows.sandbox` setting (#95). Design verdict and `CHANGES_APPLIED` values are checked (#95). The OMP answer is bounded, not its event stream (#95).
- `planning-stores`: store staging belongs to one checkout, and another checkout's staging makes the store busy (#97).

## Impact

- `README.md` (install Steps 1 and 3).
- `skills/specwright-release/scripts/release.sh` (`untagged --local`, `check --main`), `skills/specwright-release/SKILL.md`, `skills/specwright-finish/SKILL.md` (Release step, local merge), `skills/specwright-pr/SKILL.md` (ship, watch ready and merge).
- `skills/specwright-review/scripts/review-run.sh` (`command_line`, `validate_design`, the OMP answer read, `record --scratch` and `record --out`) and the review-routes trial notes. The subagent design-review dispatch text changes in `schemas/specwright/schema.yaml` (review instruction text only: no artifact or dependency changes), `skills/specwright-review/SKILL.md`, `skills/specwright-roadmap/SKILL.md` (init step 5), and `agents/claude/specwright-reviewer.md` and `agents/omp/specwright-reviewer.md`.
- `scripts/update.sh` (store staging path, `check_change` callers).
- `skills/specwright-debug/SKILL.md`; `openspec/architecture.md` (the `specwright-debug` row now owns a named stash until it is restored).
- Tests: `evals/git-workflow/test_instructions.py`, `evals/release/test_release.py` and `test_skill_text.py`, `evals/review-routes/test_review_run.py` (its `VERDICT_OK` fixture uses values that will now be refused), `evals/update/test_store.py` and `test_inflight.py`, plus a new skill-text test for `specwright-debug`.
- No new configuration key and no dependency change. A change in flight needs no migration, because the schema is unchanged.
