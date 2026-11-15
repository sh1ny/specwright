# Review

## Metadata

- **Round:** 1 — re-check of the four Required Changes.
- **Prior result:** APPROVE_WITH_CHANGES; CHANGES_APPLIED: no.
- **Reviewer:** Codex.
- **Reviewed:** Current design D4, D6, D8, Resource Bounds, C3, C6 and Decision summary; proposal What Changes, Capabilities and Release Notes; new UTF-8 requirement in the releases delta. Re-read the cited tracked launcher, ADR, fixture helpers, release fixtures, release script and suite map.
- **Scope:** Design corrections only; implementation and test execution were not assessed.

## Findings

### Critical (blocking)

**C1 — D6 and D8 rely on unsupported Windows command lookup and incomplete native fixtures. — FIXED**

D6 now correctly states that Windows lookup uses `PATHEXT` and excludes extensionless shell-script commands, consistent with `cli/lib/src/process/resolve.dart:56-68` and ADR 0034 line 19.

D8 explicitly plans matching native installation setup for both release eval modules using `sw_home()` and `stamp_version()`. The cited helpers provide the binary home and installed-version marker. D8 also requires Windows-compatible `fakeexe` launchers, assertions that expected calls reached the fake, and a missing-binary case asserting no `git ls-remote` or `gh` call. This addresses the fixture gaps without claiming the current fixtures already implement the plan.

### Moderate

**M1 — New native release files are not routed to release regression coverage. — FIXED**

D8 now explicitly routes the new release modules, command and tests to `release`, alongside the existing `cli` routing. It includes shared process, settings, GitHub runner, VCS settings and filesystem dependencies, and requires the map test after each added file. The Decision summary reflects this plan.

**M2 — The claimed 64 KB proposal read bound is false for fallback notes. — FIXED**

Resource Bounds now distinguishes size-checked section reads from unbounded fallback blob reads. This matches `release.sh:1234-1236` and `1274-1277`: fallback proposals are read completely before slicing.

C6 explicitly retains that limitation and assigns it to the owning `notes.dart` `whyLines` comment. The design therefore satisfies the requested option of documenting and carrying the existing limitation.

**M3 — D4 introduces a refusal without updating the behavior contract. — FIXED**

The proposal now declares the non-UTF-8 bump refusal in What Changes, Modified Capabilities and Release Notes, including its breaking behavior.

The new releases requirement specifies `bad_version_files`, exit 1, the offending filename, validation of every planned rewrite before any write, and no changed files on refusal. Its malformed-file scenario places valid `VERSION` before malformed `README.md` and requires both to retain their exact bytes. D4 and C3 point to this requirement; the Decision summary records the refusal as an important behavior change.

### Suggestions

None. No new Critical finding follows from the reviewed edits.

## Verdict

VERDICT: APPROVE_WITH_CHANGES

## Required Changes

1. **Applied:** Correct Windows lookup and plan matching native fixtures, fake-call assertions and missing-binary refusal coverage.
2. **Applied:** Plan release suite routing for new native files and shared dependencies, with map validation.
3. **Applied:** Distinguish bounded section reads from unbounded fallback reads and carry the limitation into the owning comment.
4. **Applied:** Declare and specify the non-UTF-8 bump refusal, including validation before writes and byte-preservation coverage.

CHANGES_APPLIED: yes

## Rebuttals

None. All four original findings are fixed by the current planning artifacts.