# Review

## Metadata

- **Round:** 3
- **Prior round:** Round 2: APPROVE_WITH_CHANGES with CHANGES_APPLIED: yes. RC1 and RC2 were applied, S1-S5 were addressed, and R2-S1 (a stale D1 sentence) was non-blocking.
- **Reviewer:** fresh-context subagent (Claude Agent SDK, Claude Opus 5.5)
- **Reviewed:** 2026-10-27. The uncommitted diff from `git diff -- openspec/changes/fix-m4-gaps/specs`. Both delta files in full: openspec/changes/fix-m4-gaps/specs/releases/spec.md and specs/review-routes/spec.md. openspec/changes/fix-m4-gaps/design.md (D9). openspec/changes/fix-m4-gaps/review.md (round 2). openspec/specs/releases/spec.md (the `check --main` requirements, about lines 258-345). skills/specwright-release/scripts/release.sh, lines 651-762 (`Unreadable`, `primary_at`, `judged_parent`, `own_bump`, `check_ahead_of`, `cmd_check`). Scope: whether the two shortening edits made during apply are clarifications, and whether the releases text still matches `own_bump`, D9 and the four scenarios. Both edited requirement texts are now under 500 characters: 489 for releases and 472 for review-routes, not counting the newline.

<!-- This verdict covers only the contents reviewed. Editing proposal, specs or design afterward (other than applying Required Changes) voids it. -->

## Findings

### Critical (blocking)

None.

### Moderate

None.

### Suggestions

**R3-1. Both edits are clarifications.**

- **review-routes, "Reviewer output is bounded while the CLI runs".** The change from "SHALL watch its output. The bounds are: ..." to "SHALL bound its output: ..." and the change from "where stdout is the answer" to "(the answer)" are rewording only. The bounds are the same (8 MiB stderr, 2 MiB stdout on claude, 64 MiB on codex and OMP), and so are the stop and the `status: invalid` / `output too large` outcome. All three scenarios (within the bounds, runaway stdout, runaway stderr) have the same outcome.
- **releases, "An unreadable commit changes the version only when its parent is not among its versions".**
  - The new term "its base (the version it is judged against)" names the same thing as before. It is `judged_parent` (release.sh:674-685), which the main spec defines in "An unreadable version is not absent" (main spec line 312).
  - "matched a version" is the same as "matched at least one version". "all it matched are greater than its base" is the same as "each is greater than the version it is judged against".
  - The final clause changed from "than each version it matched" to "than each version the base matched". In the old text the only sensible reading of "it" was "that one", meaning the base. Read as the commit, the clause would require each matched version to be greater than itself, so it could never hold. The new wording matches the old intent. It also matches D9 ("greater than each semver it matched", where "it" is `judged_parent`), round 2's S3 ("a parent with no semver counts every matched version as greater"), and the code.
  - No allowed behaviour changes.

**R3-2. The releases text matches `own_bump` and the four scenarios.**

- **Sentence 1 (D9 branch, release.sh:703-710).** The code reads the immediate parent `c^`, not the base. When that parent is unreadable and not an ancestor of `ref`, and `matched - direct.versions` is non-empty, the commit is a change. The text says "parent" here and "base" later, and keeps the two apart the same way the code does.
- **Sentence 3, with the D9 bump test at line 710.** The code builds `seen` from the semver values of the base: all of an unreadable base's versions, or one readable base's version, or nothing. It then requires every matched version to be semver and greater than each value in `seen`. "a version and all it matched are greater than its base or, when the base is unreadable, than each version the base matched" describes this. The D9 path guarantees `matched` is non-empty, so "matched a version" always holds there.
- **Sentence 2 (lines 711-713).** An unreadable commit whose base is among its matched versions, or whose base is unreadable too, gives `continue`, which is no change. This matches the text. Outside D9, an unreadable commit therefore never reaches the base-unreadable clause. That clause is reached only from the D9 branch and from a readable commit judged against an unreadable base on `ref` (lines 723-729).
  - On that second path, a commit that keeps a lower one of the base's versions returns False (line 727). The text says "bump only when ... greater than each version the base matched", and the kept version is among those versions, so it is not a bump. The text is consistent with this.
  - The remaining paths at lines 714-718 are also consistent with "only when it matched a version": with no matched versions the result is False, and otherwise each matched version must be greater than a readable base.
- **Scenario walk-through against the code:**
  - **Reverted through an unreadable version.** C3 reads 0.4.2. Its parent C2 matched {0.4.2}, so there is no new version and no D9 change. The base is 0.5.0, found by looking past C2. 0.4.2 is not greater than 0.5.0, so there is no bump and the check exits 0.
  - **Between two unreadable versions.** C3 reads 0.5.0 and its base is the merge base at 0.5.0, so C3 is no change. C2 matched {0.5.0} against parent C1's {0.6.0}, a new version, so the D9 branch applies. 0.5.0 is not greater than the base 0.5.0, so there is no bump and the check exits 0.
  - **Readable revert.** The D9 branch applies again with the base at 0.5.0, so there is no bump and the check exits 0.
  - **Keeps the matched versions.** C3 reads 0.6.0 and its parent matched {0.6.0}, so there is no D9 change. The base is the old merge base at 0.5.0, so this is a bump to 0.6.0. 0.6.0 is not greater than `origin/main`'s 0.6.0, so the check refuses with `version_not_ahead_of_main`.
  - All four outcomes match the text, and they are the same under the old text.

**R3-3. Bare `check --main` is unambiguous.** In the releases capability, `check --main` belongs only to `release.sh`. The main spec introduces it as "`release.sh check --main <ref>`" at line 258 and already uses the bare form in normative text at line 293 ("SHALL run `check --main origin/<main>`"). The scenarios of this same requirement use `check --main origin/main`. The new text no longer refers to `<ref>`: it says "on the branch" and "base". So dropping the placeholder leaves no unresolved term.

**R3-4 (optional, not introduced by this edit).** "each version the base matched" is slightly broader than the code and D9. Both compare only semver values: `seen` drops non-semver matches, and a base with no semver counts every matched version as greater. Changing "version" to "semver" ("than each semver the base matched") would make the text exact and shorten it by one character. The old text had the same looseness, and no scenario depends on it, so this has no consequence for this change.

## Verdict

VERDICT: APPROVE

## Required Changes

None.

<!-- yes (applied, and re-checked by the reviewer - only the reviewer sets it) | no (outstanding) | n/a (any other verdict) -->
CHANGES_APPLIED: n/a

## Rebuttals
